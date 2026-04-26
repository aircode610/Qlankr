"""
Bug reproduction LangGraph entrypoints and final BugReport assembly.

Yields Server-Sent Events matching Sprint 3 bug_* Pydantic models in models.py.
"""

from __future__ import annotations

import asyncio
import re
import traceback
from typing import Any, AsyncIterator, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from agent.agent import _extract_owner_repo, _llm
from agent.agent import BugReproductionState
from agent.prefetch import prefetch_context
from agent.bug_run_registry import clear_bug_runs, is_active_bug_run, mark_bug_run_started
from agent.sessions import SessionType, create_session, get_session, update_session
from agent.stages.bug_mechanics import mechanics_node
from agent.stages.bug_reproduction import reproduction_node
from agent.stages.bug_triage import triage_node
from indexer import get_repo_name
from models import (
    AffectedComponent,
    BugCheckpointEvent,
    BugReport,
    BugReportResultEvent,
    BugStageChangeEvent,
    E2ETestStep,
    ErrorEvent,
    ResearchFindings,
    ResearchProgressEvent,
)

_bug_graph: Any = None

BUG_NODE_NAMES: set[str] = {
    "bug_triage",
    "bug_mechanics",
    "bug_checkpoint_mech",
    "bug_reproduction",
    "bug_research",
    "bug_checkpoint_research",
    "bug_final",
}

TIMEOUT_SECONDS = 600


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


def _map_severity(raw: str | None) -> Literal["critical", "major", "minor", "trivial"]:
    s = (raw or "major").lower()
    if s == "critical":
        return "critical"
    if s in ("high", "major", "medium"):
        return "major"
    if s in ("low", "minor"):
        return "minor"
    if s == "trivial":
        return "trivial"
    return "major"


def _coerce_confidence(
    t: Any,
) -> Literal["high", "medium", "low"]:
    c = str(
        t.get("confidence", "medium") or "medium"
    ).lower()
    if c in ("high", "medium", "low"):
        return c  # type: ignore[return-value]
    return "medium"


def assemble_bug_report(
    state: dict,
) -> BugReport:
    t = state.get("triage") or {}
    m = state.get("mechanics") or {}
    r = state.get("reproduction_plan") or {}
    rf_raw = state.get("research_findings") or {}
    if isinstance(rf_raw, dict):
        try:
            evidence = ResearchFindings.model_validate(rf_raw)
        except Exception:
            evidence = ResearchFindings(
                evidence_summary=str(rf_raw.get("evidence_summary", "")) or "Research (partial).",
            )
    else:
        evidence = ResearchFindings(evidence_summary="Research (partial).")

    title = (f"[{t.get('bug_category')}] " if t.get("bug_category") else "")
    desc = (state.get("description") or "Bug report")[:200]
    title = (title + desc).strip() or "Bug report"

    ac_raw = m.get("affected_components", []) or []
    affected: list[AffectedComponent] = []
    for c in ac_raw if isinstance(ac_raw, list) else []:
        if isinstance(c, str):
            affected.append(
                AffectedComponent(
                    component=c, files_changed=[
                        f for f in t.get("affected_files", []) or []
                        if f == c or c in str(f)
                    ][:1]
                    or (t.get("affected_files", []) or []),
                )
            )
        elif isinstance(c, dict) and c.get("component"):
            try:
                affected.append(AffectedComponent.model_validate(c))
            except Exception:
                affected.append(AffectedComponent(component=str(c.get("component", "Unknown"))))

    if not affected:
        for fn in t.get("affected_files", []) or []:
            if isinstance(fn, str):
                affected.append(
                    AffectedComponent(
                        component=fn,
                        files_changed=[fn],
                        impact_summary="Mentioned in triage.",
                    )
                )
    if not affected:
        affected.append(AffectedComponent(component="Unknown", files_changed=[]))

    steps: list[E2ETestStep] = []
    for i, s in enumerate(r.get("steps", []) or []):
        if not isinstance(s, dict):
            continue
        sn = s.get("step_number", s.get("step", i + 1))
        try:
            n = int(sn) if sn is not None else i + 1
        except (TypeError, ValueError):
            n = i + 1
        steps.append(
            E2ETestStep(
                step=n,
                action=str(s.get("action", s.get("description", "")) or "Step"),
                expected=str(
                    s.get("expected_result", s.get("expected", "See actual behavior."))
                ),
            )
        )
    if not steps:
        steps = [
            E2ETestStep(
                step=1,
                action="Reproduce the issue using the preconditions in the plan.",
                expected="Issue reproduces or expected behavior observed.",
            )
        ]

    hyps: list = m.get("root_cause_hypotheses", []) or []
    hyp_lines: list[str] = []
    for h in hyps if isinstance(hyps, list) else []:
        if isinstance(h, dict):
            hyp_lines.append(str(h.get("hypothesis", h.get("text", h))) or str(h))
        else:
            hyp_lines.append(str(h))
    if not hyp_lines and t.get("initial_hypotheses"):
        hyp_lines = [str(x) for x in (t.get("initial_hypotheses", []) or []) if x]

    rc_paths = m.get("code_paths", []) or []
    for p in (rc_paths if isinstance(rc_paths, list) else []):
        if isinstance(p, dict) and (not hyp_lines) and p.get("path") is not None:
            hyp_lines.append(f"Path {p.get('path')!s}: {p.get('description', '') or ''}")
            break

    root_cause = "\n".join(f"• {h}" for h in hyp_lines) or "See triage and mechanics; confirm in staging."

    env: str
    e = state.get("environment") or t.get("reported_in")
    if isinstance(e, str):
        env = e
    else:
        env = str(e) if e else "Unspecified"

    pre = (r.get("prerequisites", []) or [])
    if isinstance(pre, str):
        pre = [pre]
    pre_text = " ".join(str(x) for x in (pre or [])[:3])
    expected_behavior = f"With preconditions: {pre_text} — the system should behave as designed."
    if r.get("prerequisites") is None and (r.get("steps") is None or len((r.get("steps") or [])) == 0):
        expected_behavior = "Application behaves according to spec (see evidence)."

    rec: list[str] = []
    if t.get("keywords"):
        kws = t.get("keywords", [])
        if isinstance(kws, list) and kws:
            rec.append("Verify: " + ", ".join([str(x) for x in kws[:5]]))
    rec.append("Reproduce in staging; capture logs if not already in evidence.")

    return BugReport(
        title=title,
        severity=_map_severity(
            t.get("severity", state.get("severity_input", "major") or "major")
        ),
        category=str(t.get("bug_category", t.get("category", "other")) or "other"),
        environment=env,
        reproduction_steps=steps,
        expected_behavior=expected_behavior,
        actual_behavior=state.get("description", "") or "As in report.",
        root_cause_analysis=root_cause,
        affected_components=affected,
        evidence=evidence,
        recommendations=rec,
        confidence=_coerce_confidence(t) if t else "medium",
    )


# ── Graph node wrappers ──────────────────────────────────────────────────────


async def n_bug_triage(state: BugReproductionState) -> dict:
    return await triage_node(state, _llm)


async def n_bug_mechanics(state: BugReproductionState) -> dict:
    return await mechanics_node(state, _llm)


def bug_checkpoint_mech_node(state: BugReproductionState) -> dict:
    tri = state.get("triage", {})
    mec = state.get("mechanics", {})
    response = interrupt(
        {
            "type": "bug_checkpoint",
            "stage_completed": "checkpoint_mechanics",
            "intermediate_result": {
                "triage": tri,
                "mechanics": mec,
            },
            "prompt": (
                "Check mechanics. Send action: approve, refine, or add_context. "
                "For refine or add_context include feedback in additional_context."
            ),
        }
    )
    action = response.get("action", "approve")
    if action in ("refine", "add_context") and (
        response.get("feedback")
        or response.get("context")
        or response.get("additional_context")
    ):
        ctx = str(
            response.get("feedback")
            or response.get("additional_context")
            or response.get("context")
            or ""
        )
        return {
            "mechanics_feedback": ctx,
            "current_stage": "mechanics_rerun",
        }
    return {
        "mechanics_feedback": None,
        "current_stage": "bug_reproduction",
    }


def route_post_mech(state: BugReproductionState) -> str:
    if state.get("current_stage") == "mechanics_rerun":
        return "mechanics"
    return "reproduction"


async def n_bug_reproduction(state: BugReproductionState) -> dict:
    return await reproduction_node(state, _llm)


async def n_bug_research(state: BugReproductionState) -> dict:
    line = (state.get("research_context")
            or "Research (stub) — P2 can extend with live tool calls.")
    if not isinstance(line, str):
        line = str(line)
    ev = f"Context: {line}." if state.get("research_context") else "Stub research pass. Configure integrations in Settings."
    return {
        "research_findings": {
            "log_entries": [],
            "doc_references": [],
            "related_issues": [],
            "db_state": [],
            "admin_notes": [line],
            "evidence_summary": ev,
        },
        "current_stage": "research_checkpoint",
    }


def bug_checkpoint_research_node(state: BugReproductionState) -> dict:
    res = state.get("research_findings", {})
    response = interrupt(
        {
            "type": "bug_checkpoint",
            "stage_completed": "checkpoint_research",
            "intermediate_result": {"research_findings": res},
            "prompt": "Review research. approve to finalize, or add_context with more detail.",
        }
    )
    action = response.get("action", "approve")
    if action in ("add_context", "refine") and (
        response.get("additional_context")
        or response.get("feedback")
        or response.get("context")
    ):
        ctx = str(
            response.get("additional_context")
            or response.get("feedback")
            or response.get("context")
            or ""
        )
        return {
            "research_context": ctx,
            "current_stage": "research_rerun",
        }
    return {
        "current_stage": "bug_final",
    }


def route_post_research(state: BugReproductionState) -> str:
    if state.get("current_stage") == "research_rerun":
        return "research"
    return "final"


def n_bug_final(state: BugReproductionState) -> dict:
    br = assemble_bug_report({**state})
    return {
        "bug_report": br.model_dump(),
        "current_stage": "done",
    }


def _build_bug_graph() -> Any:
    g = StateGraph(BugReproductionState)
    g.add_node("bug_triage", n_bug_triage)
    g.add_node("bug_mechanics", n_bug_mechanics)
    g.add_node("bug_checkpoint_mech", bug_checkpoint_mech_node)
    g.add_node("bug_reproduction", n_bug_reproduction)
    g.add_node("bug_research", n_bug_research)
    g.add_node("bug_checkpoint_research", bug_checkpoint_research_node)
    g.add_node("bug_final", n_bug_final)
    g.set_entry_point("bug_triage")
    g.add_edge("bug_triage", "bug_mechanics")
    g.add_edge("bug_mechanics", "bug_checkpoint_mech")
    g.add_conditional_edges(
        "bug_checkpoint_mech",
        route_post_mech,
        {"mechanics": "bug_mechanics", "reproduction": "bug_reproduction"},
    )
    g.add_edge("bug_reproduction", "bug_research")
    g.add_edge("bug_research", "bug_checkpoint_research")
    g.add_conditional_edges(
        "bug_checkpoint_research",
        route_post_research,
        {"research": "bug_research", "final": "bug_final"},
    )
    g.add_edge("bug_final", END)
    return g.compile(checkpointer=MemorySaver())


def get_bug_graph() -> Any:
    global _bug_graph
    if _bug_graph is None:
        _bug_graph = _build_bug_graph()
    return _bug_graph


def _bug_initial_state(
    session_id: str,
    description: str,
    environment: str | None,
    severity: str | None,
    repo_name: str | None,
    jira_ticket: str | None,
    attachments: list[str],
    processes: list[dict],
    repo_stats: dict,
) -> dict:
    return {
        "description": description,
        "environment": environment,
        "severity_input": severity,
        "repo_name": repo_name,
        "jira_ticket": jira_ticket,
        "attachments": list(attachments or []),
        "session_id": session_id,
        "processes": processes,
        "repo_stats": repo_stats,
        "triage": {},
        "mechanics": {},
        "reproduction_plan": {},
        "research_findings": {},
        "bug_report": {},
        "current_stage": "bug_triage",
        "tool_calls_used": 0,
        "messages": [],
        "available_tools": [],
        "mechanics_feedback": None,
        "research_context": None,
    }


async def _stream_bug_graph(
    graph: Any,
    input_or_cmd: Any,
    config: dict,
    session_id: str,
) -> AsyncIterator[
    BugStageChangeEvent
    | BugCheckpointEvent
    | ResearchProgressEvent
    | BugReportResultEvent
    | ErrorEvent
]:
    emitted: set[str] = set()
    research_progress_sent = False

    async for event in graph.astream_events(input_or_cmd, version="v2", config=config):
        if event.get("event") == "on_chain_start":
            name = (event.get("metadata") or {}).get("langgraph_node", "")
            if name in BUG_NODE_NAMES and name not in emitted:
                emitted.add(name)
                if name not in (
                    "bug_triage", "bug_mechanics", "bug_reproduction", "bug_research", "bug_final"
                ):
                    continue
                yield BugStageChangeEvent(
                    stage=name,
                    summary=f"Starting {name.replace('bug_', '').replace('_', ' ')}",
                )
            if name == "bug_research" and not research_progress_sent:
                research_progress_sent = True
                rfs = 0
                st = event.get("data", {}).get("input", {})
                if isinstance(st, dict) and st.get("research_findings") is not None:
                    rfs = 0
                yield ResearchProgressEvent(
                    source="stub",
                    finding_count=rfs,
                    summary="Consolidated evidence (stub) — P2 for full run.",
                )

    state = await graph.aget_state(config)

    if state.next:
        payload: dict = {}
        for task in state.tasks or []:
            for it in getattr(task, "interrupts", []):
                v = getattr(it, "value", it)
                if isinstance(v, dict):
                    payload = dict(v)
                    break
            if payload:
                break
        if not payload:
            payload = {"type": "bug_checkpoint", "stage_completed": "mechanics"}
        sc = str(payload.get("stage_completed", "mechanics"))
        yield BugCheckpointEvent(
            session_id=session_id,
            stage_completed=sc,
            payload=payload,
        )
    else:
        val = state.values
        if not val:
            yield ErrorEvent(message="Bug pipeline ended with empty state.")
            return
        brd = val.get("bug_report")
        if brd is None:
            yield ErrorEvent(message="Bug pipeline completed without a bug_report.")
            return
        if isinstance(brd, dict):
            br = BugReport.model_validate(brd)
        else:
            br = brd
        steps = int(val.get("tool_calls_used", 0) or 0) if isinstance(val, dict) else 0
        sess = get_session(session_id)
        if sess is not None:
            update_session(session_id, bug_report=br, current_stage="done", intermediate_result={})
        yield BugReportResultEvent(
            session_id=session_id,
            report=br,
            agent_steps=steps,
        )


async def run_bug_report(
    description: str,
    environment: str | None = None,
    severity: str | None = None,
    repo_url: str | None = None,
    jira_ticket: str | None = None,
    attachments: list[str] | None = None,
) -> AsyncIterator[
    BugStageChangeEvent
    | BugCheckpointEvent
    | ResearchProgressEvent
    | BugReportResultEvent
    | ErrorEvent
]:
    try:
        async with asyncio.timeout(TIMEOUT_SECONDS):
            sess: Any = create_session(
                pr_url=repo_url or "bug://session",
                session_type=SessionType.BUG_REPRODUCTION,
                bug_description=description,
            )
            session_id = sess.session_id
            if repo_url and repo_url != "bug://session":
                update_session(session_id, pr_url=repo_url)
            repo = _repo_name_for_bug(repo_url) if repo_url else None
            pref = await prefetch_context(repo_url or "", repo)
            initial = _bug_initial_state(
                session_id,
                description,
                environment,
                severity,
                repo,
                jira_ticket,
                attachments or [],
                processes=pref.get("processes", []),
                repo_stats=pref.get("stats", {}),
            )
            mark_bug_run_started(session_id)
            config = {
                "configurable": {"thread_id": session_id},
                "recursion_limit": 200,
            }
            async for ev in _stream_bug_graph(
                get_bug_graph(), initial, config, session_id
            ):
                yield ev
    except Exception as exc:
        traceback.print_exc()
        yield ErrorEvent(message=f"Unexpected error in bug run: {exc}")


def _resume_to_interrupt(
    user_response: dict,
) -> dict:
    r = {**user_response}
    a = r.get("action", "approve")
    if a == "approve":
        r["action"] = "approve"
    if a in ("add_context", "refine"):
        c = r.get("additional_context") or r.get("feedback")
        if c:
            r["additional_context"] = c
            r["feedback"] = c
    return r


async def continue_bug_report(
    session_id: str,
    user_response: dict,
) -> AsyncIterator[
    BugStageChangeEvent
    | BugCheckpointEvent
    | ResearchProgressEvent
    | BugReportResultEvent
    | ErrorEvent
]:
    try:
        if get_session(session_id) is None:
            yield ErrorEvent(message="Session not found for bug pipeline.")
            return
        if not is_active_bug_run(session_id):
            yield ErrorEvent(
                message="This session was not started with POST /bug-report, or the server was restarted."
            )
            return
        async with asyncio.timeout(TIMEOUT_SECONDS):
            res = _resume_to_interrupt(user_response)
            config = {
                "configurable": {"thread_id": session_id},
                "recursion_limit": 200,
            }
            async for ev in _stream_bug_graph(
                get_bug_graph(), Command(resume=res), config, session_id
            ):
                yield ev
    except Exception as exc:
        traceback.print_exc()
        yield ErrorEvent(message=f"Unexpected error in bug continue: {exc}")
