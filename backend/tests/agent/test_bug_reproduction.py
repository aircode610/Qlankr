"""
Manual test for the bug reproduction pipeline.
Run from backend/: python -m tests.agent.test_bug_reproduction [mode]

Modes:
  pipeline (default) — run full graph through bug_agent (checkpoints auto-approved)
  stages             — run all 5 stages directly (bypasses graph, no shared MCP client)
  triage             — run triage stage only
  mechanics          — run mechanics stage only
  reproduction       — run reproduction stage only
  research           — run research stage only
  report             — run report stage only
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env", override=True)

from agent.agent import BugReproductionState, _llm
from agent.stages.bug_triage import triage_node
from agent.stages.bug_mechanics import mechanics_node as mechanics_analysis_node
from agent.stages.bug_reproduction import reproduction_node as reproduction_planning_node
from agent.stages.bug_research import research_node
from agent.stages.bug_report import report_node
from evals.bug_evaluators import (
    triage_accuracy, mechanics_grounding, reproduction_executability,
    bug_pipeline_health, research_coverage, report_completeness,
    report_actionability, evidence_quality, tool_efficiency, graceful_degradation,
)

# ── Sample bug description ────────────────────────────────────────────────────

BUG_DESCRIPTION = """\
After disabling "Show arrival and departure date on timetable" in Settings → Interface → \
Timetable settings, opening any vehicle's timetable window causes an immediate crash with \
assertion failure: "cur_height < max_smallest" at widget.cpp line 1578 inside \
NWidgetHorizontal::SetupSmallestSize(). Reproducible 100% on a fresh game with no mods. \
Reverting the setting prevents the crash.
"""

MODE = sys.argv[1] if len(sys.argv) > 1 else "pipeline"

initial_state: BugReproductionState = {
    "description": BUG_DESCRIPTION,
    "environment": "Windows 11, openttd-15.0-beta3",
    "severity_input": "high",
    "repo_name": "OpenTTD",
    "jira_ticket": None,
    "attachments": [],
    "session_id": "test-bug-stages",
    "repo_stats": {},
    "processes": [],
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

_STAGE_KEY = {
    "triage": "triage",
    "mechanics": "mechanics",
    "reproduction": "reproduction_plan",
    "research": "research_findings",
    "report": "bug_report",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _print_result(stage: str, result: dict) -> None:
    print(f"\n{'='*60}")
    print(f"=== {stage.upper()} RESULT ===")
    print(f"{'='*60}")
    print(f"  next stage      : {result.get('current_stage')}")
    print(f"  tool_calls_used : {result.get('tool_calls_used', 0)}")

    key = _STAGE_KEY.get(stage, stage)
    data = result.get(key, {})
    if data:
        print(f"\n--- {key} ---")
        print(json.dumps(data, indent=2))
    else:
        print(f"\n  WARNING: {key} is empty — stage may have hit budget before submitting")


def _print_evals(combined: dict) -> None:
    print(f"\n{'='*60}")
    print("=== EVALUATOR SCORES ===")
    print(f"{'='*60}")
    all_evals = [
        triage_accuracy, mechanics_grounding, reproduction_executability,
        bug_pipeline_health, research_coverage, report_completeness,
        report_actionability, evidence_quality, tool_efficiency, graceful_degradation,
    ]
    for ev in all_evals:
        result = ev(combined)
        score_bar = "█" * int(result["score"] * 10) + "░" * (10 - int(result["score"] * 10))
        print(f"\n  {result['key']}")
        print(f"  score   : {score_bar}  {result['score']:.2f}")
        print(f"  summary : {result['comment']}")
        for d in result.get("details", []):
            icon = "✓" if d["passed"] else "✗"
            print(f"    {icon} {d['check']:<50} {d['value']}")


# ── Full pipeline via bug_agent (recommended) ─────────────────────────────────

async def run_pipeline():
    """Run the full graph through bug_agent — shared MCP client, real checkpoints auto-approved."""
    from agent.bug_agent import run_bug_agent, continue_bug_agent, BugResultEvent
    from models import CheckpointEvent, ErrorEvent, StageChangeEvent, AgentStepEvent

    print("Running full pipeline via bug_agent (checkpoints auto-approved)\n")

    session_id = "test-pipeline-001"
    combined: dict = {}
    checkpoint_count = 0

    async def _stream(generator):
        async for event in generator:
            if isinstance(event, StageChangeEvent):
                print(f"\n>>> STAGE: {event.stage}", flush=True)
            elif isinstance(event, AgentStepEvent):
                print(f"  → {event.summary}", flush=True)
            elif isinstance(event, CheckpointEvent):
                return event
            elif isinstance(event, BugResultEvent):
                return event
            elif isinstance(event, ErrorEvent):
                print(f"\n!!! ERROR: {event.message}")
                return None
        return None

    # Start pipeline
    result = await _stream(run_bug_agent(
        description=BUG_DESCRIPTION,
        environment="Windows 11, openttd-15.0-beta3",
        severity_input="high",
        repo_name="OpenTTD",
        session_id=session_id,
    ))

    # Auto-approve checkpoints
    while isinstance(result, CheckpointEvent):
        checkpoint_count += 1
        print(f"\n>>> CHECKPOINT [{checkpoint_count}]: {result.interrupt_type}", flush=True)
        print(f"    stage_completed: {result.stage_completed}", flush=True)
        print(f"    auto-approving...", flush=True)

        result = await _stream(continue_bug_agent(
            session_id=result.session_id,
            user_response={"action": "approve"},
        ))

    if isinstance(result, BugResultEvent):
        print(f"\n{'='*60}")
        print("=== FINAL BUG REPORT ===")
        print(f"{'='*60}")
        print(json.dumps(result.bug_report, indent=2))
        combined = {**result.bug_report, "bug_report": result.bug_report}
        # Flatten for evaluators
        combined["tool_calls_used"] = result.bug_report.get("tool_calls_used", 0)
    else:
        print("\nPipeline did not produce a result.")
        return

    _print_evals(combined)


# ── Individual stage runners (bypass graph, useful for quick iteration) ───────

async def run_triage_only():
    print("Running triage stage...", flush=True)
    result = await triage_node(initial_state)
    _print_result("triage", result)
    return result


async def run_mechanics_only(triage_result: dict | None = None):
    state = {**initial_state}
    if triage_result:
        state = {**state, **triage_result}
    elif not state.get("triage"):
        state["triage"] = {
            "bug_category": "crash",
            "keywords": ["NWidgetHorizontal", "SetupSmallestSize", "TimetableWindow", "widget assertion"],
            "severity": "critical",
            "affected_area": "timetable window UI / widget layout",
            "affected_files": ["src/timetable_gui.cpp", "src/widget.cpp"],
            "initial_hypotheses": ["SZSP_NONE on a vertically-filling child inside NWidgetHorizontal violates height invariant"],
            "confidence": "high",
        }
    print("Running mechanics stage...", flush=True)
    result = await mechanics_analysis_node(state)
    _print_result("mechanics", result)
    return result


async def run_reproduction_only(mechanics_result: dict | None = None):
    state = {**initial_state}
    if mechanics_result:
        state = {**initial_state, **mechanics_result}
    elif not state.get("mechanics"):
        state["triage"] = {"bug_category": "crash", "keywords": ["NWidgetHorizontal"], "affected_area": "widget layout"}
        state["mechanics"] = {
            "code_paths": [{"path": "TimetableWindow::UpdateSelectionStates→NWidgetHorizontal::SetupSmallestSize→assert", "description": "assert fires on layout pass", "confidence": "high"}],
            "affected_components": ["TimetableWindow", "NWidgetHorizontal", "NWidgetStacked"],
            "root_cause_hypotheses": [{"hypothesis": "SZSP_NONE sets fill_y=1 causing max_smallest to be too tight", "confidence": "high", "evidence": "widget.cpp step 1b loop"}],
        }
    print("Running reproduction stage...", flush=True)
    result = await reproduction_planning_node(state)
    _print_result("reproduction", result)
    return result


async def run_research_only(repro_result: dict | None = None):
    state = {**initial_state}
    if repro_result:
        state = {**state, **repro_result}
    if not state.get("triage"):
        state["triage"] = {"keywords": ["NWidgetHorizontal", "TimetableWindow"], "affected_area": "timetable widget layout"}
    if not state.get("mechanics"):
        state["mechanics"] = {
            "affected_components": ["TimetableWindow", "NWidgetHorizontal"],
            "root_cause_hypotheses": [{"hypothesis": "SZSP_NONE fill_y=1 violates height invariant", "confidence": "high", "evidence": "widget.cpp"}],
        }
    print("Running research stage...", flush=True)
    result = await research_node(state)
    _print_result("research", result)
    return result


async def run_report_only(research_result: dict | None = None):
    state = {**initial_state}
    if research_result:
        state = {**state, **research_result}
    if not state.get("triage"):
        state["triage"] = {"bug_category": "crash", "severity": "critical", "affected_area": "widget layout", "keywords": ["NWidgetHorizontal"]}
    if not state.get("mechanics"):
        state["mechanics"] = {
            "code_paths": [{"path": "UpdateSelectionStates→SetupSmallestSize→assert", "description": "assert on layout", "confidence": "high"}],
            "affected_components": ["TimetableWindow", "NWidgetHorizontal"],
            "root_cause_hypotheses": [{"hypothesis": "SZSP_NONE fill_y=1 violates height invariant", "confidence": "high", "evidence": "widget.cpp step 1b"}],
        }
    if not state.get("reproduction_plan"):
        state["reproduction_plan"] = {
            "steps": [
                {"step_number": 1, "action": "Start OpenTTD with no mods", "expected_result": "Game loads normally"},
                {"step_number": 2, "action": "Disable 'Show arrival and departure date' in Settings", "expected_result": "Setting toggles off"},
                {"step_number": 3, "action": "Open any vehicle timetable window", "expected_result": "Game crashes with assertion failure"},
            ],
            "prerequisites": ["Vanilla OpenTTD installation"],
            "environment_requirements": ["Debug build recommended"],
            "confidence": "high",
        }
    print("Running report stage...", flush=True)
    result = await report_node(state)
    _print_result("report", result)
    return result


async def run_stages():
    """Run all 5 stages directly in sequence (no graph, no shared client)."""
    print("Running all stages directly: triage → mechanics → reproduction → research → report\n")

    triage_result = await triage_node(initial_state)
    _print_result("triage", triage_result)

    state_after_triage = {**initial_state, **triage_result}
    mechanics_result = await mechanics_analysis_node(state_after_triage)
    _print_result("mechanics", mechanics_result)

    state_after_mechanics = {**state_after_triage, **mechanics_result}
    repro_result = await reproduction_planning_node(state_after_mechanics)
    _print_result("reproduction", repro_result)

    state_after_repro = {**state_after_mechanics, **repro_result}
    research_result = await research_node(state_after_repro)
    _print_result("research", research_result)

    state_after_research = {**state_after_repro, **research_result}
    report_result = await report_node(state_after_research)
    _print_result("report", report_result)

    total = report_result.get("tool_calls_used", 0)
    print(f"\n{'='*60}")
    print(f"Total tool calls across all stages: {total}")

    combined = {**triage_result, **mechanics_result, **repro_result, **research_result, **report_result}
    _print_evals(combined)


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    if MODE == "pipeline":
        await run_pipeline()
    elif MODE == "stages":
        await run_stages()
    elif MODE == "mechanics":
        await run_mechanics_only()
    elif MODE == "reproduction":
        await run_reproduction_only()
    elif MODE == "research":
        await run_research_only()
    elif MODE == "report":
        await run_report_only()
    else:
        await run_triage_only()


asyncio.run(main())
