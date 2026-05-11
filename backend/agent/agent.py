import asyncio
import os
import re
import traceback
import unicodedata
from typing import Any, AsyncIterator, TypedDict
from uuid import uuid4

from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from contextlib import AsyncExitStack

from agent.tools import get_mcp_client, open_persistent_mcp_sessions
from indexer import get_repo_name

# ── Shared MCP tools (one set of persistent sessions per active run) ─────────
# Opened once in _start_graph/_resume_graph via open_persistent_mcp_sessions(),
# kept alive across all stage yields, then closed after the stream ends.
# Tools are bound to their live sessions — no new server spawns per tool call.

_run_tools: dict[str, list] = {}
from models import (
    AgentStepEvent,
    CheckpointEvent,
    ErrorEvent,
    ResultEvent,
    StageChangeEvent,
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

    # Human-in-the-loop
    user_choice: str | None        # "integration" | "e2e" — set by choice_node
    unit_feedback: str | None      # user refinement feedback for unit rerun


# ── Bug reproduction state ────────────────────────────────────────────────────

class BugReproductionState(TypedDict):
    # Input
    description: str
    environment: str | None
    severity_input: str | None
    repo_name: str | None
    jira_ticket: str | None
    attachments: list[str]
    session_id: str

    # Pre-fetched context
    repo_stats: dict
    processes: list[dict]

    # Stage outputs
    triage: dict
    mechanics: dict
    reproduction_plan: dict
    research_findings: dict
    bug_report: dict

    # Orchestration
    current_stage: str
    tool_calls_used: int
    messages: list
    available_tools: list[str]

    # Human-in-the-loop
    mechanics_feedback: str | None
    research_context: str | None


# ── Graph nodes (stubs — implemented stage by stage) ─────────────────────────

async def gather_node(state: AnalysisState) -> dict:
    from agent.stages.gather import run_gather
    return await run_gather(state, _llm, all_tools=_run_tools.get(state.get("session_id", "")))


async def unit_tests_node(state: AnalysisState) -> dict:
    from agent.stages.unit import run_unit
    return await run_unit(state, _llm, all_tools=_run_tools.get(state.get("session_id", "")))

def checkpoint_node(state: AnalysisState) -> dict:
    """
    Human-in-the-loop after unit tests.
    Shows unit test results; user can approve (→ choice) or refine (→ rerun unit_tests).
    """
    components_summary = [
        {
            "component": c.get("component"),
            "files_changed": c.get("files_changed", []),
            "unit_tests": c.get("unit_tests", []),
        }
        for c in state.get("affected_components", [])
    ]

    response = interrupt({
        "type": "checkpoint",
        "stage_completed": "unit_testing",
        "intermediate_result": {
            "pr_metadata": state.get("pr_metadata", {}),
            "affected_components": components_summary,
        },
        "prompt": (
            "Unit tests generated. Review the results above.\n"
            "  approve — proceed to choose next stage\n"
            "  refine  — provide feedback to improve the unit tests"
        ),
    })

    action = response.get("action", "approve")
    if action == "refine":
        return {
            "current_stage": "unit_tests",
            "unit_feedback": response.get("feedback", ""),
        }

    return {
        "current_stage": "choice",
        "unit_feedback": None,
    }


def choice_node(state: AnalysisState) -> dict:
    """
    Human-in-the-loop: user picks 'integration' or 'e2e'.
    """
    response = interrupt({
        "type": "choice",
        "options": ["integration", "e2e"],
        "prompt": (
            "Unit tests approved. Which tests do you want to run next?\n"
            "  integration — find cross-module integration points and generate test specs\n"
            "  e2e         — plan end-to-end user-facing test scenarios"
        ),
    })

    choice = response.get("choice", "integration")
    return {
        "user_choice": choice,
        "current_stage": choice,
    }


def e2e_checkpoint_node(state: AnalysisState) -> dict:
    """
    Human-in-the-loop before E2E planning.
    Asks user for any upfront context (user flows, bug reports, scenarios).
    """
    process_count = state.get("repo_stats", {}).get("processes", 0)
    processes_prefetched = len(state.get("processes", []))

    if process_count == 0:
        process_note = (
            "⚠️ No execution flows (processes) were detected in the knowledge graph "
            "for this repo. E2E plans will be derived from the PR diff and changed files "
            "rather than pre-indexed user flows — quality will be lower than usual. "
            "Consider re-indexing the repo if this is unexpected."
        )
    elif processes_prefetched == 0:
        process_note = (
            f"ℹ️ {process_count} execution flows are indexed, but pre-fetching them failed. "
            "The agent will re-fetch them during planning."
        )
    else:
        process_note = f"{process_count} execution flows indexed, {processes_prefetched} pre-fetched."

    response = interrupt({
        "type": "e2e_context",
        "process_count": process_count,
        "process_note": process_note,
        "prompt": (
            "Before planning E2E tests, do you have any context to share?\n"
            "For example: user flows, bug reports, feature descriptions, known edge cases.\n"
            "Leave empty to let the agent figure it out from the PR."
        ),
    })

    context = response.get("context", "")
    return {
        "user_context": context or state.get("user_context"),
        "current_stage": "e2e_planning",
    }


async def integration_tests_node(state: AnalysisState) -> dict:
    from agent.stages.integration import run_integration
    return await run_integration(state, _llm, all_tools=_run_tools.get(state.get("session_id", "")))


async def e2e_planning_node(state: AnalysisState) -> dict:
    from agent.stages.e2e import run_e2e
    return await run_e2e(state, _llm, all_tools=_run_tools.get(state.get("session_id", "")))


def submit_node(state: AnalysisState) -> dict:
    """
    Final node — marks analysis complete.
    The graph runner reads affected_components and e2e_test_plans from state.
    """
    return {"current_stage": "done"}


# ── Graph wiring ──────────────────────────────────────────────────────────────

def _checkpoint_router(state: AnalysisState) -> str:
    """After checkpoint_unit: rerun unit_tests or proceed to choice."""
    return state.get("current_stage", "choice")


def _choice_router(state: AnalysisState) -> str:
    """After choice_node: route to integration_tests or e2e_checkpoint."""
    choice = state.get("user_choice", "integration")
    return "e2e_checkpoint" if choice == "e2e" else "integration_tests"


def build_analysis_graph():
    graph = StateGraph(AnalysisState)

    graph.add_node("gather", gather_node)
    graph.add_node("unit_tests", unit_tests_node)
    graph.add_node("checkpoint_unit", checkpoint_node)
    graph.add_node("choice", choice_node)
    graph.add_node("integration_tests", integration_tests_node)
    graph.add_node("e2e_checkpoint", e2e_checkpoint_node)
    graph.add_node("e2e_planning", e2e_planning_node)
    graph.add_node("submit", submit_node)

    graph.set_entry_point("gather")
    graph.add_edge("gather", "unit_tests")
    graph.add_edge("unit_tests", "checkpoint_unit")

    # After unit checkpoint: approve → choice, refine → back to unit_tests
    graph.add_conditional_edges(
        "checkpoint_unit",
        _checkpoint_router,
        {"unit_tests": "unit_tests", "choice": "choice"},
    )

    # After choice: integration or e2e branch
    graph.add_conditional_edges(
        "choice",
        _choice_router,
        {"integration_tests": "integration_tests", "e2e_checkpoint": "e2e_checkpoint"},
    )

    graph.add_edge("e2e_checkpoint", "e2e_planning")
    graph.add_edge("integration_tests", "submit")
    graph.add_edge("e2e_planning", "submit")
    graph.add_edge("submit", END)

    return graph.compile(checkpointer=MemorySaver())


MAX_TOOL_CALLS = 25
TIMEOUT_SECONDS = 600

# ── Graph singleton ───────────────────────────────────────────────────────────
# MemorySaver stores checkpoint state in-process — must be the same instance
# across the initial run and all /continue resumes for a session.

_graph_instance = None


def _get_graph():
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_analysis_graph()
    return _graph_instance


# ── Session store (stub — Dev C owns sessions.py) ────────────────────────────
# Keyed by session_id (thread_id). Stores lightweight metadata only;
# actual graph state lives in the MemorySaver checkpointer above.
# Replace with create_session() / get_session() from agent/sessions.py once
# devc/testing-models lands.

_sessions: dict[str, dict] = {}


def has_analysis_thread(session_id: str) -> bool:
    """True if a PR analysis run was started for this id (in-memory, same as checkpointer thread)."""
    return session_id in _sessions

# ── Stage node names (for StageChangeEvent filtering) ────────────────────────

_STAGE_NODES = {
    "gather", "unit_tests", "checkpoint_unit", "choice",
    "integration_tests", "e2e_checkpoint", "e2e_planning", "submit",
}

_llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    temperature=0,
    max_tokens=4096,
    # Placeholder allows import in CI / tests; real calls still need a valid key in env.
    api_key=(
        os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("ANTHROPIC_API_KEY")
        or "dummy-not-configured"
    ),
    base_url=os.environ.get("ANTHROPIC_BASE_URL"),
)


# ── Entry points ─────────────────────────────────────────────────────────────

async def run_agent(
    pr_url: str,
    context: str | None = None,
    session_id: str | None = None,
) -> AsyncIterator[AgentStepEvent | StageChangeEvent | CheckpointEvent | ResultEvent | ErrorEvent]:
    """
    Start a new PR analysis session.
    Streams SSE events until graph completes or hits a checkpoint interrupt.
    Called by main.py POST /analyze.
    """
    try:
        async with asyncio.timeout(TIMEOUT_SECONDS):
            async for event in _start_graph(pr_url, context, session_id):
                yield event
    except TimeoutError:
        yield ErrorEvent(message=f"Analysis timed out after {TIMEOUT_SECONDS} seconds.")
    except Exception as exc:
        traceback.print_exc()
        yield ErrorEvent(message=f"Unexpected error during analysis: {exc}")


async def continue_agent(
    session_id: str,
    user_response: dict,
) -> AsyncIterator[AgentStepEvent | StageChangeEvent | CheckpointEvent | ResultEvent | ErrorEvent]:
    """
    Resume a graph paused at a checkpoint interrupt.
    Called by main.py POST /analyze/{session_id}/continue (endpoint owned by Dev C).
    user_response is passed directly as the interrupt resume value, e.g.:
      {"action": "approve"}
      {"action": "refine", "feedback": "..."}
      {"choice": "integration"}
      {"context": "..."}
      {"answer": "..."}
    """
    try:
        async with asyncio.timeout(TIMEOUT_SECONDS):
            async for event in _resume_graph(session_id, user_response):
                yield event
    except TimeoutError:
        yield ErrorEvent(message=f"Resume timed out after {TIMEOUT_SECONDS} seconds.")
    except Exception as exc:
        traceback.print_exc()
        yield ErrorEvent(message=f"Unexpected error during resume: {exc}")


def _extract_owner_repo(pr_url: str) -> tuple[str, str] | None:
    m = re.search(r"github\.com/([^/]+)/([^/]+)/pull/", pr_url)
    return (m.group(1), m.group(2)) if m else None


async def _start_graph(
    pr_url: str,
    context: str | None,
    session_id: str | None,
) -> AsyncIterator[AgentStepEvent | StageChangeEvent | CheckpointEvent | ResultEvent | ErrorEvent]:
    thread_id = session_id or str(uuid4())
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}

    owner_repo = _extract_owner_repo(pr_url)
    repo_name: str | None = None
    if owner_repo:
        repo_name = get_repo_name(f"{owner_repo[0]}/{owner_repo[1]}")

    # Open persistent MCP sessions for the full pipeline run.
    # Tools are bound to their live server processes — no new spawn per tool call.
    print("[agent] opening persistent MCP sessions...", flush=True)
    async with AsyncExitStack() as stack:
        all_tools = await open_persistent_mcp_sessions(get_mcp_client(), stack)
        _run_tools[thread_id] = all_tools
        print(f"[agent] {len(all_tools)} MCP tools ready on persistent sessions", flush=True)

        # Pre-fetch GitNexus process list + repo stats before graph starts
        # so gather/e2e stages don't waste tool call budget on basic context.
        from agent.prefetch import prefetch_context
        prefetched = await prefetch_context(pr_url, repo_name, all_tools=all_tools)

        initial_state: AnalysisState = {
            "pr_url": pr_url,
            "repo_name": repo_name,
            "user_context": context,
            "session_id": thread_id,
            "pr_diff": "",
            "pr_files": [],
            "pr_metadata": {},
            "processes": prefetched["processes"],
            "repo_stats": prefetched["stats"],
            "affected_components": [],
            "integration_tests": [],
            "e2e_test_plans": [],
            "current_stage": "gather",
            "tool_calls_used": 0,
            "messages": [],
            "user_choice": None,
            "unit_feedback": None,
        }

        _sessions[thread_id] = {"pr_url": pr_url, "repo_name": repo_name}

        try:
            async for event in _stream_graph(_get_graph(), initial_state, config, thread_id, pr_url):
                yield event
        finally:
            _run_tools.pop(thread_id, None)
    # AsyncExitStack.__aexit__ runs here — all server processes terminated cleanly


async def _resume_graph(
    session_id: str,
    user_response: dict,
) -> AsyncIterator[AgentStepEvent | StageChangeEvent | CheckpointEvent | ResultEvent | ErrorEvent]:
    if session_id not in _sessions:
        yield ErrorEvent(message=f"Session {session_id!r} not found.")
        return

    config = {"configurable": {"thread_id": session_id}, "recursion_limit": 100}
    pr_url = _sessions[session_id].get("pr_url", "")

    # Re-open persistent sessions for this resume segment
    async with AsyncExitStack() as stack:
        all_tools = await open_persistent_mcp_sessions(get_mcp_client(), stack)
        _run_tools[session_id] = all_tools
        try:
            async for event in _stream_graph(
                _get_graph(), Command(resume=user_response), config, session_id, pr_url
            ):
                yield event
        finally:
            _run_tools.pop(session_id, None)


async def _stream_graph(
    graph: Any,
    input_or_command: Any,
    config: dict,
    thread_id: str,
    pr_url: str,
) -> AsyncIterator[AgentStepEvent | StageChangeEvent | CheckpointEvent | ResultEvent | ErrorEvent]:
    """
    Drive the graph, mapping LangGraph events to SSE events.
    After the stream ends, checks state for interrupt or completion.
    """
    emitted_stages: set[str] = set()
    # Buffer tool inputs keyed by run_id so we can emit combined input+output on completion
    _tool_input_buffer: dict[str, dict] = {}

    async for event in graph.astream_events(input_or_command, version="v2", config=config):
        event_type = event["event"]
        node_name = event.get("metadata", {}).get("langgraph_node", "")

        if event_type == "on_chain_start" and node_name in _STAGE_NODES:
            if node_name not in emitted_stages:
                emitted_stages.add(node_name)
                yield StageChangeEvent(
                    stage=node_name,
                    summary=f"Starting {node_name.replace('_', ' ')}",
                )

        elif event_type == "on_tool_start":
            run_id = event.get("run_id", "")
            tool_name = event["name"]
            tool_input = event["data"].get("input", {})
            _tool_input_buffer[run_id] = {
                "tool": tool_name,
                "input": tool_input if isinstance(tool_input, dict) else {},
                "summary": _tool_summary(tool_name, tool_input),
            }

        elif event_type == "on_tool_end":
            run_id = event.get("run_id", "")
            buffered = _tool_input_buffer.pop(run_id, None)
            if buffered:
                raw_output = event["data"].get("output", {})
                if hasattr(raw_output, "content"):
                    tool_output: dict = {"content": raw_output.content}
                elif isinstance(raw_output, dict):
                    tool_output = raw_output
                else:
                    tool_output = {"content": str(raw_output)}
                yield AgentStepEvent(
                    tool=buffered["tool"],
                    summary=buffered["summary"],
                    input=buffered["input"],
                    output=tool_output,
                )

    # Stream ended — check whether graph paused at interrupt or finished
    state = await graph.aget_state(config)

    if state.next:
        # Graph is paused — extract interrupt payload
        interrupt_values = [
            intr.value
            for task in state.tasks
            for intr in getattr(task, "interrupts", [])
        ]
        payload = interrupt_values[0] if interrupt_values else {}
        yield CheckpointEvent(
            session_id=thread_id,
            stage_completed=state.values.get("current_stage", "unknown"),
            interrupt_type=payload.get("type", "checkpoint"),
            payload=payload,
        )
    else:
        # Graph completed — assemble ResultEvent from final state
        final = state.values
        components = final.get("affected_components", [])
        if not components:
            yield ErrorEvent(message="Analysis completed but produced no affected components.")
            return

        normalized = [
            {
                "component": c.get("component", "Unknown"),
                "files_changed": c.get("files_changed", []),
                "impact_summary": c.get("impact_summary", ""),
                "impact_detail": c.get("impact_detail"),
                "risks": c.get("risks", []),
                "test_suggestions": c.get("test_suggestions", {"skip": [], "run": [], "deeper": []}),
                "confidence": c.get("confidence", "low"),
                "unit_tests": c.get("unit_tests", []),
                "integration_tests": c.get("integration_tests", []),
            }
            for c in components
        ]

        pr_meta = final.get("pr_metadata", {})
        yield ResultEvent(
            pr_title=pr_meta.get("title", pr_url),
            pr_url=pr_url,
            pr_summary=pr_meta.get("pr_summary") or pr_meta.get("description", ""),
            pr_summary_detail=pr_meta.get("pr_summary_detail"),
            affected_components=normalized,
            e2e_test_plans=final.get("e2e_test_plans", []),
            agent_steps=final.get("tool_calls_used", 0),
        )


# ── Unicode sanitization ──────────────────────────────────────────────────────
# Neo4j (used by GitNexus MCP) fails on non-latin-1 characters in arguments.
# Normalize typographic characters to ASCII equivalents before tool dispatch.

_UNICODE_MAP = str.maketrans({
    "\u2014": "--",   # em dash
    "\u2013": "-",    # en dash
    "\u2018": "'",    # left single quote
    "\u2019": "'",    # right single quote
    "\u201c": '"',    # left double quote
    "\u201d": '"',    # right double quote
    "\u2026": "...",  # ellipsis
    "\u00a0": " ",    # non-breaking space
    "\u2022": "*",    # bullet
})


def _sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFKC", value).translate(_UNICODE_MAP)
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    return value


def _wrap_mcp_tools(tools: list) -> list:
    """Wrap each MCP tool to sanitize non-ASCII characters in its inputs."""
    wrapped = []
    for tool in tools:
        original_func = tool.func
        original_coro = tool.coroutine

        if original_coro is not None:
            async def _acall(*args: Any, _coro=original_coro, **kwargs: Any) -> Any:
                return await _coro(*args, **_sanitize(kwargs))
            wrapped_tool = tool.copy(update={"coroutine": _acall, "func": None})
        elif original_func is not None:
            def _call(*args: Any, _fn=original_func, **kwargs: Any) -> Any:
                return _fn(*args, **_sanitize(kwargs))
            wrapped_tool = tool.copy(update={"func": _call})
        else:
            wrapped_tool = tool

        wrapped.append(wrapped_tool)
    return wrapped




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
        "submit_gather": lambda _: "Submitting gathered PR context",
        "submit_unit_tests": lambda i: f"Submitting unit tests for {i.get('component', '?')}",
        "submit_integration_tests": lambda _: "Submitting integration test specs",
        "submit_e2e_plans": lambda _: "Submitting E2E test plans",
    }
    try:
        builder = builders.get(tool_name)
        return builder(tool_input) if builder else f"Calling tool: {tool_name}"
    except Exception:
        return f"Calling tool: {tool_name}"


