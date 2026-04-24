"""
Manual test for bug reproduction stages 1-3.
Run from backend/: python -m tests.agent.test_bug_triage [stage]

Stages: triage (default), mechanics, reproduction, all
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.agent import BugReproductionState, _llm
from agent.stages.bug_triage import triage_node

# mechanics_analysis_node and reproduction_planning_node not yet implemented
mechanics_analysis_node = None
reproduction_planning_node = None

# ── Sample bug description ────────────────────────────────────────────────────
BUG_DESCRIPTION = """\
After using the fast travel system to teleport between zones, players lose all equipped \
items. The items are not deleted — they reappear in the inventory as unequipped. \
This only happens when the player has more than 5 items equipped simultaneously. \
The bug is consistent and 100% reproducible. Fast travel via the world map is affected; \
walking through portals is not.
"""

STAGE = sys.argv[1] if len(sys.argv) > 1 else "triage"

initial_state: BugReproductionState = {
    "description": BUG_DESCRIPTION,
    "environment": "Windows 10, build 2.4.1-beta",
    "severity_input": "high",
    "repo_name": None,
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


def _print_result(stage: str, result: dict) -> None:
    print(f"\n{'='*60}")
    print(f"=== {stage.upper()} RESULT ===")
    print(f"{'='*60}")
    print(f"  next stage      : {result.get('current_stage')}")
    print(f"  tool_calls_used : {result.get('tool_calls_used', 0)}")

    key = {"triage": "triage", "mechanics": "mechanics", "reproduction": "reproduction_plan"}[stage]
    data = result.get(key, {})
    if data:
        print(f"\n--- {key} ---")
        print(json.dumps(data, indent=2))
    else:
        print(f"\n  WARNING: {key} is empty — stage may have hit budget before submitting")


async def run_triage_only():
    print(f"Running triage stage...", flush=True)
    result = await triage_node(initial_state)
    _print_result("triage", result)
    return result


async def run_mechanics_only(triage_result: dict | None = None):
    if mechanics_analysis_node is None:
        print("mechanics_analysis_node not yet implemented — skipping")
        return {}
    state = {**initial_state}
    if triage_result:
        state = {**state, **triage_result}
    elif not state.get("triage"):
        state["triage"] = {
            "bug_category": "gameplay",
            "keywords": ["fast travel", "equip", "inventory", "zone transition"],
            "severity": "high",
            "affected_area": "fast travel / inventory system",
            "affected_files": [],
            "initial_hypotheses": [
                "Equipment state is serialized before zone unload but not restored correctly",
                "Zone transition clears equipped slots without restoring from save",
            ],
            "confidence": "medium",
        }
    print(f"Running mechanics stage...", flush=True)
    result = await mechanics_analysis_node(state)
    _print_result("mechanics", result)
    return result


async def run_reproduction_only(mechanics_result: dict | None = None):
    if reproduction_planning_node is None:
        print("reproduction_planning_node not yet implemented — skipping")
        return {}
    state = {**initial_state}
    if mechanics_result:
        state = {**initial_state, **mechanics_result}
    elif not state.get("mechanics"):
        state["triage"] = {
            "bug_category": "gameplay",
            "keywords": ["fast travel", "equip", "inventory"],
            "affected_area": "fast travel / inventory system",
        }
        state["mechanics"] = {
            "code_paths": [{"path": "FastTravel.execute→ZoneManager.transition→InventoryManager.reset", "description": "Equipment state is cleared during zone transition", "confidence": "medium"}],
            "affected_components": ["FastTravelSystem", "InventoryManager", "ZoneManager"],
            "entry_points": ["FastTravel.execute"],
            "root_cause_hypotheses": [
                {"hypothesis": "InventoryManager.reset() called during zone transition drops equipped items", "confidence": "high", "evidence": "code path ends in reset()"},
            ],
        }
    print(f"Running reproduction stage...", flush=True)
    result = await reproduction_planning_node(state)
    _print_result("reproduction", result)
    return result


async def run_all():
    print("Running full pipeline: triage → (mechanics → reproduction when implemented)\n")
    triage_result = await triage_node(initial_state)
    _print_result("triage", triage_result)

    if mechanics_analysis_node is not None:
        state_after_triage = {**initial_state, **triage_result}
        mechanics_result = await mechanics_analysis_node(state_after_triage)
        _print_result("mechanics", mechanics_result)

        if reproduction_planning_node is not None:
            state_after_mechanics = {**state_after_triage, **mechanics_result}
            repro_result = await reproduction_planning_node(state_after_mechanics)
            _print_result("reproduction", repro_result)
            total = repro_result.get("tool_calls_used", 0)
            print(f"\n{'='*60}")
            print(f"Total tool calls across all stages: {total}")


async def main():
    if STAGE == "all":
        await run_all()
    elif STAGE == "mechanics":
        await run_mechanics_only()
    elif STAGE == "reproduction":
        await run_reproduction_only()
    else:
        await run_triage_only()


asyncio.run(main())
