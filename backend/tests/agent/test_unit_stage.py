"""
Quick manual test for unit_tests_node.
Run from backend/: python3 tests/agent/test_unit_stage.py [pr_url]

Runs gather_node first to get real components, then feeds them into unit_tests_node.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.agent import gather_node, unit_tests_node, AnalysisState

PR_URL = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/aircode610/Qlankr/pull/41"

BASE_STATE: AnalysisState = {
    "pr_url": PR_URL,
    "repo_name": None,
    "user_context": None,
    "session_id": "test-unit",
    "pr_diff": "",
    "pr_files": [],
    "pr_metadata": {},
    "processes": [],
    "repo_stats": {},
    "affected_components": [],
    "integration_tests": [],
    "e2e_test_plans": [],
    "current_stage": "gathering",
    "tool_calls_used": 0,
    "messages": [],
}


async def main():
    print(f"PR: {PR_URL}\n", flush=True)

    # Step 1 — gather
    print("=== Step 1: gather_node ===", flush=True)
    gather_result = await gather_node(BASE_STATE)
    components = gather_result.get("affected_components", [])
    print(f"  components found: {len(components)}")
    for c in components:
        print(f"    - {c.get('component')}: {c.get('files_changed', [])}")

    if not components:
        print("\nNo components found — nothing to unit test.")
        return

    # Step 2 — unit tests
    print("\n=== Step 2: unit_tests_node ===", flush=True)
    state_after_gather = {**BASE_STATE, **gather_result}
    unit_result = await unit_tests_node(state_after_gather)

    print("\n=== Unit test results ===")
    for comp in unit_result.get("affected_components", []):
        name = comp.get("component", "?")
        tests = comp.get("unit_tests", [])
        print(f"\n  {name} — {len(tests)} unit test spec(s)")
        for spec in tests:
            print(f"    target   : {spec.get('target', '?')}")
            print(f"    priority : {spec.get('priority', '?')}")
            print(f"    mocks    : {spec.get('mocks_needed', [])}")
            for tc in spec.get("test_cases", []):
                print(f"    case     : {tc.get('name', '?')}")

    print(f"\n=== Summary ===")
    print(f"  total tool_calls_used : {unit_result.get('tool_calls_used', 0)}")
    total_specs = sum(len(c.get("unit_tests", [])) for c in unit_result.get("affected_components", []))
    print(f"  total UnitTestSpecs   : {total_specs}")


asyncio.run(main())
