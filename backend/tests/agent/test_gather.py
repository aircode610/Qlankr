"""
Quick manual test for gather_node.
Run from backend/: python3 test_gather.py [pr_url]
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.agent import gather_node, AnalysisState

PR_URL = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/aircode610/Qlankr/pull/41"

state: AnalysisState = {
    "pr_url": PR_URL,
    "repo_name": None,       # set to your indexed repo name if you have one, e.g. "minetest"
    "user_context": None,
    "session_id": "test-gather",
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
    print(f"Running gather_node on: {PR_URL}", flush=True)
    print("Step 1: getting MCP tools...", flush=True)
    result = await gather_node(state)

    print("=== State updates returned ===")
    for key, value in result.items():
        if key in ("pr_diff",):
            # truncate long diff
            print(f"  {key}: {str(value)[:200]}{'...' if len(str(value)) > 200 else ''}")
        else:
            print(f"  {key}: {json.dumps(value, indent=2) if isinstance(value, (dict, list)) else value}")

    print(f"\n=== Summary ===")
    print(f"  tool_calls_used : {result.get('tool_calls_used', 0)}")
    print(f"  pr_title        : {result.get('pr_metadata', {}).get('title', '(empty)')}")
    print(f"  files changed   : {len(result.get('pr_files', []))}")
    print(f"  components found: {len(result.get('affected_components', []))}")
    for c in result.get("affected_components", []):
        print(f"    - {c.get('component', '?')}: {c.get('files_changed', [])}")


asyncio.run(main())
