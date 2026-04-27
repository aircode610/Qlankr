"""
Bug Reproduction Agent — StateGraph wiring + entry points.

Graph:
  triage → mechanics_analysis → checkpoint_mechanics →
  reproduction_planning → research → checkpoint_research →
  report_generation → END

Entry points:
  run_bug_agent()      — start a new session, stream SSE events
  continue_bug_agent() — resume after a checkpoint interrupt
"""

import asyncio
import os
import re
import traceback
from typing import Any, AsyncIterator
from uuid import uuid4

from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from agent.agent import BugReproductionState, _extract_owner_repo
from indexer import get_repo_name
from models import (
    AgentStepEvent, AffectedComponent, BugCheckpointEvent, BugReport,
    BugReportResultEvent, BugStageChangeEvent, E2ETestStep, ErrorEvent,
    ResearchFindings,
)

# Alias for internal use
BugResultEvent = BugReportResultEvent

# Severity values the LLM uses vs what BugReport accepts
_SEV_MAP: dict[str, str] = {
    "critical": "critical",
    "high":     "major",
    "major":    "major",
    "medium":   "minor",
    "minor":    "minor",
    "low":      "trivial",
    "trivial":  "trivial",
}


def _coerce_to_bug_report(raw: dict, state: dict) -> BugReport:
    """Map the raw submit_report dict (from bug_report.py) to a valid BugReport."""
    severity = _SEV_MAP.get(str(raw.get("severity", "minor")).lower(), "minor")

    # affected_components: list[str | dict] → list[AffectedComponent]
    affected_components: list[AffectedComponent] = []
    for c in raw.get("affected_components", []):
        if isinstance(c, str):
            affected_components.append(AffectedComponent(component=c))
        elif isinstance(c, dict):
            affected_components.append(AffectedComponent(
                component=c.get("component", c.get("name", str(c))),
                files_changed=c.get("files_changed", []),
                impact_summary=c.get("impact_summary", ""),
                impact_detail=c.get("impact_detail"),
                risks=c.get("risks", []),
                confidence=str(c.get("confidence", "low")).lower() if str(c.get("confidence", "low")).lower() in ("high", "medium", "low") else "low",  # type: ignore[arg-type]
            ))

    # reproduction_steps: {step_number, action, expected_result} → E2ETestStep
    reproduction_steps: list[E2ETestStep] = []
    for i, s in enumerate(raw.get("reproduction_steps", []), start=1):
        if isinstance(s, dict):
            reproduction_steps.append(E2ETestStep(
                step=int(s.get("step_number", s.get("step", i))),
                action=str(s.get("action", "")),
                expected=str(s.get("expected_result", s.get("expected", ""))),
            ))

    # evidence: raw dict → ResearchFindings (best-effort)
    raw_ev = raw.get("evidence", {})
    try:
        evidence = ResearchFindings.model_validate(raw_ev) if isinstance(raw_ev, dict) else ResearchFindings()
    except Exception:
        evidence = ResearchFindings()

    # Pull supplemental fields from graph state
    triage = state.get("triage") or {}
    environment = str(state.get("environment") or triage.get("environment") or "unspecified")
    category = str(triage.get("bug_category") or triage.get("category") or triage.get("bug_type") or "general")
    expected_behavior = str(triage.get("expected_behavior") or "Not specified")
    actual_behavior = str(triage.get("actual_behavior") or "Not specified")

    confidence_raw = str(raw.get("confidence", "low")).lower()
    confidence = confidence_raw if confidence_raw in ("high", "medium", "low") else "low"

    return BugReport(
        title=str(raw.get("title") or "Untitled Bug"),
        severity=severity,  # type: ignore[arg-type]
        category=category,
        environment=environment,
        reproduction_steps=reproduction_steps,
        expected_behavior=expected_behavior,
        actual_behavior=actual_behavior,
        root_cause_analysis=str(raw.get("root_cause") or raw.get("root_cause_analysis") or "Unknown"),
        root_cause_detail=raw.get("root_cause_detail"),
        affected_components=affected_components,
        evidence=evidence,
        recommendations=[str(r) for r in raw.get("recommendations", [])],
        recommendation_details=[str(d) for d in raw.get("recommendation_details", [])],
        confidence=confidence,  # type: ignore[arg-type]
        jira_url=raw.get("jira_url"),
    )


# ── LLM singletons ────────────────────────────────────────────────────────────
# Heavy stages (mechanics, reproduction, research) need Sonnet for deep reasoning.
# Light stages (triage = classification, report = synthesis) run on Haiku (~37x cheaper).

_anthropic_key = (
    os.environ.get("ANTHROPIC_AUTH_TOKEN")
    or os.environ.get("ANTHROPIC_API_KEY")
    or "dummy-not-configured"
)
_llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    temperature=0,
    max_tokens=4096,
    api_key=_anthropic_key,
    base_url=os.environ.get("ANTHROPIC_BASE_URL"),
)

_llm_light = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    temperature=0,
    max_tokens=4096,
    api_key=_anthropic_key,
    base_url=os.environ.get("ANTHROPIC_BASE_URL"),
)

# ── Stage node names (for StageChangeEvent filtering) ────────────────────────

_BUG_STAGE_NODES = {
    "triage",
    "mechanics_analysis",
    "checkpoint_mechanics",
    "reproduction_planning",
    "research",
    "checkpoint_research",
    "report_generation",
}

TIMEOUT_SECONDS = 600

# ── Graph node wrappers ───────────────────────────────────────────────────────

async def _triage_node(state: BugReproductionState) -> dict:
    from agent.stages.bug_triage import triage_node
    return await triage_node(state, _llm_light, _run_clients.get(state["session_id"]))


async def _mechanics_node(state: BugReproductionState) -> dict:
    from agent.stages.bug_mechanics import mechanics_node
    return await mechanics_node(state, _llm, _run_clients.get(state["session_id"]))


def _checkpoint_mechanics_node(state: BugReproductionState) -> dict:
    """
    Human-in-the-loop after mechanics analysis.
    Exposes affected components and ranked hypotheses.
    approve → reproduction_planning
    refine  → back to mechanics_analysis with feedback
    """
    mechanics = state.get("mechanics", {})

    response = interrupt({
        "type": "checkpoint_mechanics",
        "stage_completed": "mechanics_analysis",
        "intermediate_result": {
            "affected_components": mechanics.get("affected_components", []),
            "root_cause_hypotheses": mechanics.get("root_cause_hypotheses", []),
            "code_paths": mechanics.get("code_paths", []),
        },
        "prompt": (
            "Mechanics analysis complete. Review the affected components and root cause hypotheses.\n"
            "  approve — proceed to reproduction planning\n"
            "  refine  — provide feedback to improve the analysis"
        ),
    })

    action = response.get("action", "approve")
    if action == "refine":
        return {
            "current_stage": "mechanics_analysis",
            "mechanics_feedback": response.get("feedback", ""),
        }
    return {
        "current_stage": "reproduction_planning",
        "mechanics_feedback": None,
    }


async def _reproduction_node(state: BugReproductionState) -> dict:
    from agent.stages.bug_reproduction import reproduction_node
    client = _run_clients.get(state["session_id"])
    print(f"[_reproduction_node] session_id={state['session_id']!r} client_present={client is not None}", flush=True)
    return await reproduction_node(state, _llm, client)


async def _research_node(state: BugReproductionState) -> dict:
    from agent.stages.bug_research import research_node
    return await research_node(state, _llm, _run_clients.get(state["session_id"]))


def _checkpoint_research_node(state: BugReproductionState) -> dict:
    """
    Human-in-the-loop after research.
    Exposes evidence summary.
    approve      → report_generation
    add_context  → back to research with extra context
    """
    findings = state.get("research_findings", {})

    response = interrupt({
        "type": "checkpoint_research",
        "stage_completed": "research",
        "intermediate_result": {
            "sources_queried": findings.get("sources_queried", []),
            "sources_with_results": findings.get("sources_with_results", []),
            "related_issues_count": len(findings.get("related_issues", [])),
            "log_entries_count": len(findings.get("log_entries", [])),
            "doc_references_count": len(findings.get("doc_references", [])),
        },
        "prompt": (
            "Research complete. Review the evidence summary.\n"
            "  approve      — proceed to report generation\n"
            "  add_context  — provide additional context to expand the research"
        ),
    })

    action = response.get("action", "approve")
    if action == "add_context":
        return {
            "current_stage": "research",
            "research_context": response.get("context", ""),
        }
    return {
        "current_stage": "report_generation",
        "research_context": None,
    }


async def _report_node(state: BugReproductionState) -> dict:
    from agent.stages.bug_report import report_node
    return await report_node(state, _llm_light, _run_clients.get(state["session_id"]))


# ── Routers ───────────────────────────────────────────────────────────────────

def _mechanics_router(state: BugReproductionState) -> str:
    return state.get("current_stage", "reproduction_planning")


def _research_router(state: BugReproductionState) -> str:
    return state.get("current_stage", "report_generation")


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_bug_graph():
    graph = StateGraph(BugReproductionState)

    graph.add_node("triage", _triage_node)
    graph.add_node("mechanics_analysis", _mechanics_node)
    graph.add_node("checkpoint_mechanics", _checkpoint_mechanics_node)
    graph.add_node("reproduction_planning", _reproduction_node)
    graph.add_node("research", _research_node)
    graph.add_node("checkpoint_research", _checkpoint_research_node)
    graph.add_node("report_generation", _report_node)

    graph.set_entry_point("triage")
    graph.add_edge("triage", "mechanics_analysis")
    graph.add_edge("mechanics_analysis", "checkpoint_mechanics")

    graph.add_conditional_edges(
        "checkpoint_mechanics",
        _mechanics_router,
        {
            "mechanics_analysis": "mechanics_analysis",
            "reproduction_planning": "reproduction_planning",
        },
    )

    graph.add_edge("reproduction_planning", "research")
    graph.add_edge("research", "checkpoint_research")

    graph.add_conditional_edges(
        "checkpoint_research",
        _research_router,
        {
            "research": "research",
            "report_generation": "report_generation",
        },
    )

    graph.add_edge("report_generation", END)

    return graph.compile(checkpointer=MemorySaver())


# ── Graph singleton ───────────────────────────────────────────────────────────
# Single MemorySaver instance must be shared across run and continue calls
# so checkpoint state persists between the initial run and all resumes.

_bug_graph_instance = None


def _get_bug_graph():
    global _bug_graph_instance
    if _bug_graph_instance is None:
        _bug_graph_instance = build_bug_graph()
    return _bug_graph_instance


# ── Session store ─────────────────────────────────────────────────────────────

_bug_sessions: dict[str, dict] = {}

# ── Shared MCP clients (one per active run, keyed by session_id) ──────────────
# Created once in _start_bug_graph, reused across all stage nodes, cleaned up
# after the stream ends. Eliminates repeated server spawning per stage.

_run_clients: dict[str, Any] = {}


# ── Entry points ──────────────────────────────────────────────────────────────

async def run_bug_agent(
    description: str,
    environment: str | None = None,
    severity_input: str | None = None,
    repo_name: str | None = None,
    jira_ticket: str | None = None,
    attachments: list[str] | None = None,
    session_id: str | None = None,
    pr_url: str = "",
) -> AsyncIterator[AgentStepEvent | BugStageChangeEvent | BugCheckpointEvent | BugResultEvent | ErrorEvent]:
    """
    Start a new bug reproduction session.
    Streams SSE events until the graph completes or hits a checkpoint interrupt.
    Called by POST /bug-report (P3 wires the endpoint).
    """
    try:
        async with asyncio.timeout(TIMEOUT_SECONDS):
            async for event in _start_bug_graph(
                description, environment, severity_input,
                repo_name, jira_ticket, attachments or [], session_id, pr_url=pr_url,
            ):
                yield event
    except TimeoutError:
        yield ErrorEvent(message=f"Bug reproduction timed out after {TIMEOUT_SECONDS} seconds.")
    except Exception as exc:
        traceback.print_exc()
        yield ErrorEvent(message=f"Unexpected error during bug reproduction: {exc}")


async def continue_bug_agent(
    session_id: str,
    user_response: dict,
) -> AsyncIterator[AgentStepEvent | BugStageChangeEvent | BugCheckpointEvent | BugResultEvent | ErrorEvent]:
    """
    Resume a bug reproduction graph paused at a checkpoint interrupt.
    Called by POST /bug-report/{session_id}/continue (P3 wires the endpoint).
    user_response examples:
      {"action": "approve"}
      {"action": "refine", "feedback": "Focus on the save serialization path"}
      {"action": "add_context", "context": "This only started after the 2.4 patch"}
    """
    try:
        async with asyncio.timeout(TIMEOUT_SECONDS):
            async for event in _resume_bug_graph(session_id, user_response):
                yield event
    except TimeoutError:
        yield ErrorEvent(message=f"Bug reproduction resume timed out after {TIMEOUT_SECONDS} seconds.")
    except Exception as exc:
        traceback.print_exc()
        yield ErrorEvent(message=f"Unexpected error during bug reproduction resume: {exc}")


# ── Internal graph drivers ────────────────────────────────────────────────────

async def _start_bug_graph(
    description: str,
    environment: str | None,
    severity_input: str | None,
    repo_name: str | None,
    jira_ticket: str | None,
    attachments: list[str],
    session_id: str | None,
    pr_url: str = "",
) -> AsyncIterator[AgentStepEvent | BugStageChangeEvent | BugCheckpointEvent | BugResultEvent | ErrorEvent]:
    thread_id = session_id or str(uuid4())
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}

    from agent.prefetch import prefetch_context

    pref = await prefetch_context(pr_url, repo_name)
    initial_state: BugReproductionState = {
        "description": description,
        "environment": environment,
        "severity_input": severity_input,
        "repo_name": repo_name,
        "jira_ticket": jira_ticket,
        "attachments": attachments,
        "session_id": thread_id,
        "repo_stats": pref.get("stats", {}),
        "processes": pref.get("processes", []),
        "triage": {},
        "mechanics": {},
        "reproduction_plan": {},
        "research_findings": {},
        "bug_report": {},
        "current_stage": "triage",
        "tool_calls_used": 0,
        "messages": [],
        "available_tools": [],
        "mechanics_feedback": None,
        "research_context": None,
    }

    _bug_sessions[thread_id] = {"description": description, "repo_name": repo_name, "emitted_stages": set()}

    from agent.tools import get_mcp_client
    print("[bug_agent] starting shared MCP client...", flush=True)
    client = get_mcp_client()
    _run_clients[thread_id] = client
    try:
        async for event in _stream_bug_graph(_get_bug_graph(), initial_state, config, thread_id):
            yield event
    finally:
        _run_clients.pop(thread_id, None)


async def _resume_bug_graph(
    session_id: str,
    user_response: dict,
) -> AsyncIterator[AgentStepEvent | BugStageChangeEvent | BugCheckpointEvent | BugResultEvent | ErrorEvent]:
    if session_id not in _bug_sessions:
        yield ErrorEvent(message=f"Bug session {session_id!r} not found.")
        return

    config = {"configurable": {"thread_id": session_id}, "recursion_limit": 100}

    from agent.tools import get_mcp_client
    client = get_mcp_client()
    _run_clients[session_id] = client
    try:
        async for event in _stream_bug_graph(
            _get_bug_graph(), Command(resume=user_response), config, session_id
        ):
            yield event
    finally:
        _run_clients.pop(session_id, None)


async def _stream_bug_graph(
    graph: Any,
    input_or_command: Any,
    config: dict,
    thread_id: str,
) -> AsyncIterator[AgentStepEvent | BugStageChangeEvent | BugCheckpointEvent | BugResultEvent | ErrorEvent]:
    """Drive the bug graph, mapping LangGraph events to SSE events."""
    # Load emitted_stages from session so resume calls don't re-emit already-seen stages (Bug #3)
    session = _bug_sessions.get(thread_id, {})
    emitted_stages: set[str] = session.get("emitted_stages", set())
    agent_steps = 0

    async for event in graph.astream_events(input_or_command, version="v2", config=config):
        event_type = event["event"]
        node_name = event.get("metadata", {}).get("langgraph_node", "")

        if event_type == "on_chain_start" and node_name in _BUG_STAGE_NODES:
            if node_name not in emitted_stages:
                emitted_stages.add(node_name)
                if thread_id in _bug_sessions:
                    _bug_sessions[thread_id]["emitted_stages"] = emitted_stages
                yield BugStageChangeEvent(
                    stage=node_name,
                    summary=f"Starting {node_name.replace('_', ' ')}",
                )

        elif event_type == "on_tool_start":
            agent_steps += 1
            tool_name = event["name"]
            tool_input = event["data"].get("input", {})
            yield AgentStepEvent(tool=tool_name, summary=_bug_tool_summary(tool_name, tool_input))

    # Stream ended — check for interrupt or completion
    state = await graph.aget_state(config)

    if state.next:
        interrupt_values = [
            intr.value
            for task in state.tasks
            for intr in getattr(task, "interrupts", [])
        ]
        payload = interrupt_values[0] if interrupt_values else {}
        yield BugCheckpointEvent(
            session_id=thread_id,
            # Use the interrupt payload's stage_completed — state.current_stage already
            # points to the NEXT stage by the time we read it (Bug #2)
            stage_completed=payload.get("stage_completed", state.values.get("current_stage", "unknown")),
            interrupt_type=payload.get("type", "checkpoint"),
            payload=payload,
        )
    else:
        bug_report = state.values.get("bug_report", {})
        if not bug_report:
            yield ErrorEvent(message="Bug reproduction completed but produced no report.")
            return
        from agent.sessions import get_session, update_session

        br_parsed: BugReport | None = None
        try:
            br_parsed = (
                bug_report
                if isinstance(bug_report, BugReport)
                else _coerce_to_bug_report(bug_report, state.values)
            )
            s = get_session(thread_id)
            if s is not None and br_parsed is not None:
                update_session(thread_id, bug_report=br_parsed, current_stage="done")
        except Exception as e:
            import traceback
            print(f"[bug_agent] failed to parse bug report: {e}", flush=True)
            traceback.print_exc()
        if br_parsed is None:
            yield ErrorEvent(message="Bug reproduction completed but report could not be parsed.")
            return
        yield BugResultEvent(
            session_id=thread_id,
            report=br_parsed,
            agent_steps=agent_steps,
        )


# ── Tool summary builders ─────────────────────────────────────────────────────

def _bug_tool_summary(tool_name: str, tool_input: dict) -> str:
    builders = {
        "jira_search": lambda i: f"Searching Jira: {i.get('query', '')}",
        "jira_get_issue": lambda i: f"Fetching Jira issue: {i.get('issue_key', '')}",
        "jira_get_comments": lambda i: f"Reading comments on: {i.get('issue_key', '')}",
        "jira_create_issue": lambda i: f"Creating Jira issue: {i.get('summary', '')}",
        "jira_update_issue": lambda i: f"Updating Jira issue: {i.get('issue_key', '')}",
        "notion_search": lambda i: f"Searching Notion: {i.get('query', '')}",
        "notion_get_page": lambda i: f"Reading Notion page: {i.get('page_id', '')}",
        "confluence_search": lambda i: f"Searching Confluence: {i.get('query', '')}",
        "confluence_get_page": lambda i: f"Reading Confluence page: {i.get('page_id', '')}",
        "grafana_query_logs": lambda i: f"Querying Grafana logs: {i.get('query', '')}",
        "kibana_search": lambda i: f"Searching Kibana: {i.get('query', '')}",
        "sniffer_parse_har": lambda i: f"Parsing HAR file: {i.get('file_path', '')}",
        "sniffer_find_errors": lambda i: f"Finding errors in: {i.get('file_path', '')}",
        "get_file_contents": lambda i: f"Reading file: {i.get('path', i.get('file_path', ''))}",
        "search_code": lambda i: f"Searching code: {i.get('query', '')}",
        "impact": lambda i: f"Checking blast radius: {i.get('target', i.get('file', ''))}",
        "context": lambda i: f"Getting context for: {i.get('name', '')}",
        "query": lambda i: f"Semantic search: {i.get('query', '')}",
        "cypher": lambda i: f"Graph query: {str(i.get('query', ''))[:60]}",
        "submit_triage": lambda _: "Submitting triage findings",
        "submit_mechanics": lambda _: "Submitting mechanics analysis",
        "submit_reproduction": lambda _: "Submitting reproduction plan",
        "submit_research": lambda _: "Submitting research findings",
        "submit_report": lambda _: "Submitting bug report",
    }
    try:
        builder = builders.get(tool_name)
        return builder(tool_input) if builder else f"Calling tool: {tool_name}"
    except Exception:
        return f"Calling tool: {tool_name}"


# ── Person 3 API aliases (main.py) + sessions + registry ────────────────────

def _repo_name_for_bug(repo_url: str | None) -> str | None:
    if not repo_url:
        return None
    if "/pull/" in repo_url:
        o_r = _extract_owner_repo(repo_url)
        if o_r:
            return get_repo_name(f"{o_r[0]}/{o_r[1]}")
    m = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
    if m:
        return get_repo_name(f"{m.group(1)}/{m.group(2)}")
    return None


def _resume_to_interrupt_p3(user_response: dict) -> dict:
    r = {**user_response}
    a = r.get("action", "approve")
    if a in ("add_context", "refine"):
        c = r.get("additional_context") or r.get("feedback")
        if c:
            r["additional_context"] = c
            r["feedback"] = c
            r["context"] = c
    return r


async def run_bug_report(
    description: str,
    environment: str | None = None,
    severity: str | None = None,
    repo_url: str | None = None,
    jira_ticket: str | None = None,
    attachments: list[str] | None = None,
) -> Any:
    """P3: create `Session` + `bug_run_registry` entry, then run `run_bug_agent`."""
    from agent.bug_run_registry import mark_bug_run_started
    from agent.sessions import SessionType, create_session, update_session

    any_sess = create_session(
        pr_url=repo_url or "bug://session",
        session_type=SessionType.BUG_REPRODUCTION,
        bug_description=description,
    )
    session_id = any_sess.session_id
    if repo_url and repo_url != "bug://session":
        update_session(session_id, pr_url=repo_url)
    mark_bug_run_started(session_id)
    repo = _repo_name_for_bug(repo_url) if repo_url else None
    async for ev in run_bug_agent(
        description=description,
        environment=environment,
        severity_input=severity,
        repo_name=repo,
        jira_ticket=jira_ticket,
        attachments=attachments,
        session_id=session_id,
        pr_url=repo_url or "",
    ):
        yield ev


async def continue_bug_report(session_id: str, user_response: dict) -> Any:
    from agent.bug_run_registry import is_active_bug_run
    from agent.sessions import get_session
    if get_session(session_id) is None:
        yield ErrorEvent(message="Session not found for bug pipeline.")
        return
    if (not is_active_bug_run(session_id)) and (session_id not in _bug_sessions):
        yield ErrorEvent(
            message="This session was not started with POST /bug-report, or the server was restarted.",
        )
        return
    res = _resume_to_interrupt_p3(user_response)
    async for ev in continue_bug_agent(session_id, res):
        yield ev
