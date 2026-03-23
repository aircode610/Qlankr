import asyncio
import re
import sys
from typing import AsyncIterator

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from agent.prompts import SYSTEM_PROMPT
from agent.tools import get_mcp_client
from indexer import get_repo_name
from models import (
    AffectedComponent,
    AgentStepEvent,
    AnalyzeResponse,
    ErrorEvent,
    ResultEvent,
)

MAX_TOOL_CALLS = 25
TIMEOUT_SECONDS = 180

_llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0, max_tokens=4096)


# ── Submit tool schema ────────────────────────────────────────────────────────
# Mirrors AnalyzeResponse but without agent_steps (we track that ourselves).
# Claude calls this tool as its final action — the input IS the structured output.

class _AnalysisResult(BaseModel):
    pr_title: str
    pr_url: str
    pr_summary: str
    affected_components: list[AffectedComponent]


def _make_submit_tool() -> StructuredTool:
    def submit_analysis(**kwargs) -> str:
        return "Analysis submitted."

    return StructuredTool.from_function(
        func=submit_analysis,
        name="submit_analysis",
        description=(
            "Submit the completed QA impact analysis. "
            "Call this exactly once when your analysis is complete. "
            "This is your ONLY way to return the final result."
        ),
        args_schema=_AnalysisResult,
    )


# ── Entry point ───────────────────────────────────────────────────────────────

async def run_agent(
    pr_url: str,
) -> AsyncIterator[AgentStepEvent | ResultEvent | ErrorEvent]:
    """
    Entry point for PR impact analysis.
    Yields AgentStepEvent per tool call (for live trace), then ResultEvent or ErrorEvent.
    Called by main.py's POST /analyze handler.
    """
    try:
        async with asyncio.timeout(TIMEOUT_SECONDS):
            async for event in _run_agent_inner(pr_url):
                yield event
    except TimeoutError:
        yield ErrorEvent(message=f"Analysis timed out after {TIMEOUT_SECONDS} seconds.")
    except Exception as exc:
        yield ErrorEvent(message=f"Unexpected error during analysis: {exc}")


def _extract_owner_repo(pr_url: str) -> tuple[str, str] | None:
    m = re.search(r"github\.com/([^/]+)/([^/]+)/pull/", pr_url)
    return (m.group(1), m.group(2)) if m else None


async def _run_agent_inner(
    pr_url: str,
) -> AsyncIterator[AgentStepEvent | ResultEvent | ErrorEvent]:
    client = get_mcp_client()
    mcp_tools = await client.get_tools()

    agent = create_react_agent(
        model=_llm,
        tools=mcp_tools + [_make_submit_tool()],
        prompt=SystemMessage(content=SYSTEM_PROMPT),
    )

    owner_repo = _extract_owner_repo(pr_url)
    repo_name: str | None = None
    if owner_repo:
        repo_name = get_repo_name(f"{owner_repo[0]}/{owner_repo[1]}")

    if repo_name:
        repo_context = (
            f"\nThe repo '{repo_name}' is indexed in GitNexus."
            f"\nPass repo=\"{repo_name}\" to every GitNexus tool call."
        )
    else:
        repo_context = (
            "\nNo indexed repo found for this PR — use GitHub tools only "
            "and set all confidence to 'low'."
        )

    tool_call_count = 0
    analysis_result: _AnalysisResult | None = None

    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=f"Analyze this pull request: {pr_url}{repo_context}")]},
        version="v2",
        config={"recursion_limit": 60},
    ):
        if event["event"] != "on_tool_start":
            continue

        tool_name = event["name"]
        tool_input = event["data"].get("input", {})

        if tool_name == "submit_analysis":
            try:
                analysis_result = _AnalysisResult.model_validate(tool_input)
            except Exception as e:
                yield ErrorEvent(message=f"submit_analysis validation failed: {e}")
            break

        tool_call_count += 1
        yield AgentStepEvent(tool=tool_name, summary=_tool_summary(tool_name, tool_input))

        if tool_call_count >= MAX_TOOL_CALLS:
            break

    if analysis_result is None:
        yield ErrorEvent(message="Agent did not submit an analysis result.")
        return

    yield ResultEvent(**AnalyzeResponse(
        pr_title=analysis_result.pr_title,
        pr_url=analysis_result.pr_url,
        pr_summary=analysis_result.pr_summary,
        affected_components=analysis_result.affected_components,
        agent_steps=tool_call_count,
    ).model_dump())


# ── Tool summary builders ─────────────────────────────────────────────────────

def _tool_summary(tool_name: str, tool_input: dict) -> str:
    """Maps tool name + input to a human-readable summary for the AgentTrace panel."""
    builders = {
        "get_pull_request": lambda i: f"Reading PR from {i.get('owner', '')}/{i.get('repo', '')}",
        "get_pull_request_files": lambda i: f"Fetching diffs for PR #{i.get('pull_number', '')}",
        "get_pull_request_comments": lambda _: "Reading PR comments",
        "get_file_contents": lambda i: f"Reading file: {i.get('path', i.get('file_path', ''))}",
        "list_directory": lambda i: f"Listing directory: {i.get('path', '')}",
        "get_commits": lambda _: "Fetching recent commits",
        "search_code": lambda i: f"Searching code: {i.get('query', '')}",
        "detect_changes": lambda _: "Detecting changed symbols in knowledge graph",
        "impact": lambda i: f"Checking blast radius: {i.get('target', i.get('file', ''))}",
        "context": lambda i: f"Getting caller/callee context for: {i.get('name', '')}",
        "query": lambda i: f"Semantic search: {i.get('query', '')}",
        "cypher": lambda i: f"Graph query: {str(i.get('query', ''))[:60]}",
    }
    try:
        builder = builders.get(tool_name)
        return builder(tool_input) if builder else f"Calling tool: {tool_name}"
    except Exception:
        return f"Calling tool: {tool_name}"


# ── Standalone runner ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m agent.agent <pr_url>")
        sys.exit(1)

    async def _main() -> None:
        async for event in run_agent(sys.argv[1]):
            print(event.model_dump_json(indent=2))

    asyncio.run(_main())
