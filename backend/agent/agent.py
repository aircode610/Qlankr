import asyncio
import os
import re
import sys
import traceback
from typing import Annotated, Any, AsyncIterator, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field, model_validator

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

class AnalysisState(TypedDict):
    # Input
    pr_url: str
    repo_name: str | None
    user_context: str | None
    session_id: str

    # Pre-fetched context (populated by gather stage)
    pr_diff: str
    pr_files: list[str]
    pr_metadata: dict
    processes: list[dict]
    repo_stats: dict

    # Stage outputs
    affected_components: list[dict]
    integration_tests: list[dict]
    e2e_test_plans: list[dict]

    # Orchestration
    current_stage: str
    tool_calls_used: int
    messages: list


# ── Graph nodes (stubs — implemented stage by stage) ─────────────────────────

async def gather_node(state: AnalysisState) -> dict:
    raise NotImplementedError

async def unit_tests_node(state: AnalysisState) -> dict:
    raise NotImplementedError

def checkpoint_node(state: AnalysisState) -> dict:
    raise NotImplementedError

async def integration_tests_node(state: AnalysisState) -> dict:
    raise NotImplementedError

async def e2e_planning_node(state: AnalysisState) -> dict:
    raise NotImplementedError

def submit_node(state: AnalysisState) -> dict:
    raise NotImplementedError


# ── Graph wiring ──────────────────────────────────────────────────────────────

def build_analysis_graph():
    graph = StateGraph(AnalysisState)

    graph.add_node("gather", gather_node)
    graph.add_node("unit_tests", unit_tests_node)
    graph.add_node("checkpoint_unit", checkpoint_node)
    graph.add_node("integration_tests", integration_tests_node)
    graph.add_node("e2e_planning", e2e_planning_node)
    graph.add_node("submit", submit_node)

    graph.set_entry_point("gather")
    graph.add_edge("gather", "unit_tests")
    graph.add_edge("unit_tests", "checkpoint_unit")
    graph.add_edge("checkpoint_unit", "integration_tests")
    graph.add_edge("checkpoint_unit", "e2e_planning")
    graph.add_edge("integration_tests", "submit")
    graph.add_edge("e2e_planning", "submit")
    graph.add_edge("submit", END)

    return graph.compile(checkpointer=MemorySaver())


MAX_TOOL_CALLS = 25
TIMEOUT_SECONDS = 180

_llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    temperature=0,
    max_tokens=4096,
    api_key=os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"),
    base_url=os.environ.get("ANTHROPIC_BASE_URL"),
)


# ── Submit tool schema ────────────────────────────────────────────────────────
# Mirrors AnalyzeResponse but without agent_steps (we track that ourselves).
# Claude calls this tool as its final action — the input IS the structured output.

class _AnalysisResult(BaseModel):
    pr_title: str
    pr_url: str
    pr_summary: str
    affected_components: Annotated[list[AffectedComponent], Field(min_length=1)]


class _SubmitAnalysisToolArgs(BaseModel):
    """Single `analysis` dict validated inside the tool so partial payloads become ToolMessages, not crashes."""

    analysis: dict = Field(
        description=(
            "Complete analysis object. Required keys: pr_title (string), pr_url (string), "
            "pr_summary (string), affected_components (non-empty array). "
            "Each element of affected_components must have: component, impact_summary, confidence "
            '("high"|"medium"|"low"); optional: files_changed, risks (arrays of strings), '
            "test_suggestions with skip, run, deeper (arrays of strings, may be empty). "
            "You may instead pass those keys at the top level of the tool input (without nesting under analysis)."
        )
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_flat_or_nested(cls, data: Any) -> Any:
        if isinstance(data, dict) and "analysis" not in data:
            return {"analysis": data}
        return data


def _make_submit_tool(result_holder: list[_AnalysisResult]) -> StructuredTool:
    def submit_analysis(analysis: dict) -> str:
        try:
            parsed = _AnalysisResult.model_validate(analysis)
        except Exception as e:
            return (
                "submit_analysis rejected ? fix the payload and call submit_analysis again. "
                f"Validation error: {e}"
            )
        result_holder.append(parsed)
        return "Analysis submitted."

    return StructuredTool.from_function(
        func=submit_analysis,
        name="submit_analysis",
        description=(
            "Submit the completed QA impact analysis. "
            "Pass one argument: `analysis`, a single JSON object with pr_title, pr_url, pr_summary, "
            "and affected_components (non-empty array of component objects). "
            "Call exactly once with a valid payload when done ? this is your ONLY way to return the result. "
            "If you get a rejection message, correct the object and call again."
        ),
        args_schema=_SubmitAnalysisToolArgs,
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
        traceback.print_exc()
        yield ErrorEvent(message=f"Unexpected error during analysis: {exc}")


def _extract_owner_repo(pr_url: str) -> tuple[str, str] | None:
    m = re.search(r"github\.com/([^/]+)/([^/]+)/pull/", pr_url)
    return (m.group(1), m.group(2)) if m else None


async def _run_agent_inner(
    pr_url: str,
) -> AsyncIterator[AgentStepEvent | ResultEvent | ErrorEvent]:
    client = get_mcp_client()
    mcp_tools = await client.get_tools()

    submit_results: list[_AnalysisResult] = []
    agent = create_react_agent(
        model=_llm,
        tools=mcp_tools + [_make_submit_tool(submit_results)],
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
            "\nNo indexed repo found for this PR ? use GitHub tools only "
            "and set all confidence to 'low'."
        )

    tool_call_count = 0

    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=f"Analyze this pull request: {pr_url}{repo_context}")]},
        version="v2",
        config={"recursion_limit": 60},
    ):
        if event["event"] != "on_tool_start":
            continue

        tool_name = event["name"]
        tool_input = event["data"].get("input", {})

        tool_call_count += 1
        yield AgentStepEvent(tool=tool_name, summary=_tool_summary(tool_name, tool_input))

        if tool_call_count >= MAX_TOOL_CALLS:
            break

    analysis_result = submit_results[-1] if submit_results else None
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
        "submit_analysis": lambda i: "Submitting QA impact analysis",
    }
    try:
        builder = builders.get(tool_name)
        return builder(tool_input) if builder else f"Calling tool: {tool_name}"
    except Exception:
        return f"Calling tool: {tool_name}"
