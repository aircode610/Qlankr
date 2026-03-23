import asyncio
import sys
from typing import AsyncIterator

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from agent.prompts import SYSTEM_PROMPT
from agent.tools import get_mcp_client
from models import AgentStepEvent, AnalyzeResponse, ErrorEvent, ResultEvent

MAX_TOOL_CALLS = 25
BUDGET_WARNING_AT = 20
TIMEOUT_SECONDS = 180

_llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0, max_tokens=4096)


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


async def _run_agent_inner(
    pr_url: str,
) -> AsyncIterator[AgentStepEvent | ResultEvent | ErrorEvent]:
    async with get_mcp_client() as client:
        tools = await client.get_tools()

    agent = create_react_agent(
        model=_llm,
        tools=tools,
        prompt=SystemMessage(content=SYSTEM_PROMPT),
        response_format=AnalyzeResponse,
    )

    tool_call_count = 0
    budget_warning_sent = False
    structured_response: AnalyzeResponse | None = None

    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=f"Analyze this pull request: {pr_url}")]},
        version="v2",
        config={"recursion_limit": 60},
    ):
        etype = event["event"]

        if etype == "on_tool_start":
            tool_call_count += 1
            tool_name = event["name"]
            tool_input = event["data"].get("input", {})
            yield AgentStepEvent(tool=tool_name, summary=_tool_summary(tool_name, tool_input))

            if tool_call_count >= BUDGET_WARNING_AT and not budget_warning_sent:
                budget_warning_sent = True
                # The system prompt already instructs the agent to synthesize near the budget.
                # Mid-stream injection is not possible with astream_events; this is logged only.

            if tool_call_count >= MAX_TOOL_CALLS:
                break

        elif etype == "on_chain_end" and event.get("name") == "LangGraph":
            output = event["data"].get("output", {})
            raw = output.get("structured_response")
            if raw is not None:
                if isinstance(raw, AnalyzeResponse):
                    structured_response = raw
                elif isinstance(raw, dict):
                    try:
                        structured_response = AnalyzeResponse.model_validate(raw)
                    except Exception:
                        pass

    if structured_response is None:
        yield ErrorEvent(message="Agent produced no structured output.")
        return

    structured_response.agent_steps = tool_call_count
    yield ResultEvent(**structured_response.model_dump())


def _tool_summary(tool_name: str, tool_input: dict) -> str:
    """Maps tool name + input to a human-readable summary for the AgentTrace panel."""
    builders = {
        "get_pull_request": lambda i: (
            f"Reading PR from {i.get('owner', '')}/{i.get('repo', '')}"
        ),
        "get_pull_request_files": lambda i: (
            f"Fetching diffs for PR #{i.get('pull_number', '')}"
        ),
        "get_pull_request_comments": lambda _: "Reading PR comments",
        "get_file_contents": lambda i: (
            f"Reading file: {i.get('path', i.get('file_path', ''))}"
        ),
        "list_directory": lambda i: f"Listing directory: {i.get('path', '')}",
        "get_commits": lambda _: "Fetching recent commits",
        "search_code": lambda i: f"Searching code: {i.get('query', '')}",
        "detect_changes": lambda _: "Detecting changed symbols in knowledge graph",
        "impact": lambda i: (
            f"Checking blast radius: {i.get('target', i.get('file', ''))}"
        ),
        "context": lambda i: f"Getting caller/callee context for: {i.get('name', '')}",
        "query": lambda i: f"Semantic search: {i.get('query', '')}",
        "cypher": lambda i: f"Graph query: {str(i.get('query', ''))[:60]}",
    }
    try:
        builder = builders.get(tool_name)
        return builder(tool_input) if builder else f"Calling tool: {tool_name}"
    except Exception:
        return f"Calling tool: {tool_name}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m agent.agent <pr_url>")
        sys.exit(1)

    async def _main() -> None:
        async for event in run_agent(sys.argv[1]):
            print(event.model_dump_json(indent=2))

    asyncio.run(_main())
