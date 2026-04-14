"""
Eval target — wraps the Sprint 2 StateGraph agent for LangSmith evaluate().

The agent has human-in-the-loop checkpoints. In eval mode we auto-approve
at each checkpoint and pick a path (integration or e2e) based on the
`eval_path` parameter.

Two target functions:
  - agent_target_integration: auto-approves → picks integration
  - agent_target_e2e: auto-approves → picks e2e
"""

import asyncio
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.agent import run_agent, continue_agent


async def _run_full_pipeline(pr_url: str, path: str = "integration") -> dict:
    """
    Drive the agent through all checkpoints, collecting events.

    Returns a dict with:
      - tool_calls: list of tool names called
      - stages_seen: list of stage names
      - result: the final AnalyzeResult dict (or None)
      - checkpoints_hit: list of checkpoint types encountered
      - error: error message if any
      - unit_tests: list of unit test specs from checkpoint intermediate result
      - integration_tests / e2e_test_plans: from final result
    """
    tool_calls: list[str] = []
    stages_seen: list[str] = []
    checkpoints_hit: list[str] = []
    result: dict | None = None
    error: str | None = None
    session_id: str | None = None
    unit_intermediate: list[dict] = []

    # Phase 1: Start the agent — runs until first checkpoint or completion
    async for event in run_agent(pr_url):
        data = event.model_dump()
        etype = data.get("type")

        if etype == "agent_step":
            tool_calls.append(data["tool"])
        elif etype == "stage_change":
            stages_seen.append(data["stage"])
        elif etype == "checkpoint":
            session_id = data.get("session_id")
            interrupt_type = data.get("interrupt_type", "checkpoint")
            checkpoints_hit.append(interrupt_type)
            # Save unit test intermediate results
            payload = data.get("payload", {})
            if interrupt_type == "checkpoint":
                ir = payload.get("intermediate_result", {})
                unit_intermediate = ir.get("affected_components", [])
            break  # paused — need to resume
        elif etype == "result":
            result = data
        elif etype == "error":
            error = data.get("message", "unknown error")

    # Phase 2: Auto-approve at each checkpoint until we get a result
    max_resumes = 5  # safety limit
    resumes = 0

    while session_id and result is None and error is None and resumes < max_resumes:
        resumes += 1
        last_checkpoint = checkpoints_hit[-1] if checkpoints_hit else "unknown"

        # Build the appropriate resume payload
        if last_checkpoint == "checkpoint":
            # Unit test review — approve
            user_response = {"action": "approve"}
        elif last_checkpoint == "choice":
            # Pick integration or e2e
            user_response = {"choice": path}
        elif last_checkpoint == "e2e_context":
            # E2E context — skip (no extra context in eval)
            user_response = {"context": ""}
        else:
            # Unknown — approve and hope
            user_response = {"action": "approve"}

        async for event in continue_agent(session_id, user_response):
            data = event.model_dump()
            etype = data.get("type")

            if etype == "agent_step":
                tool_calls.append(data["tool"])
            elif etype == "stage_change":
                stages_seen.append(data["stage"])
            elif etype == "checkpoint":
                interrupt_type = data.get("interrupt_type", "checkpoint")
                checkpoints_hit.append(interrupt_type)
                payload = data.get("payload", {})
                if interrupt_type == "checkpoint":
                    ir = payload.get("intermediate_result", {})
                    unit_intermediate = ir.get("affected_components", [])
                break  # paused again
            elif etype == "result":
                result = data
            elif etype == "error":
                error = data.get("message", "unknown error")

    # Assemble output
    output: dict[str, Any] = {
        "tool_calls": tool_calls,
        "stages_seen": stages_seen,
        "checkpoints_hit": checkpoints_hit,
        "unit_intermediate": unit_intermediate,
        "path_taken": path,
    }

    if error:
        output["error"] = error
        return output

    if result:
        output["pr_title"] = result.get("pr_title", "")
        output["pr_summary"] = result.get("pr_summary", "")
        output["affected_components"] = result.get("affected_components", [])
        output["e2e_test_plans"] = result.get("e2e_test_plans", [])
        output["agent_steps"] = result.get("agent_steps", 0)
    else:
        output["error"] = f"No result after {resumes} resumes. Checkpoints: {checkpoints_hit}"

    return output


async def agent_target_integration(inputs: dict) -> dict:
    """Eval target: full pipeline, auto-approve, pick integration path."""
    return await _run_full_pipeline(inputs["pr_url"], path="integration")


async def agent_target_e2e(inputs: dict) -> dict:
    """Eval target: full pipeline, auto-approve, pick e2e path."""
    return await _run_full_pipeline(inputs["pr_url"], path="e2e")


async def agent_target_gather_only(inputs: dict) -> dict:
    """Eval target: gather stage only — stops at first checkpoint.
    Useful for evaluating component identification without test generation cost."""
    pr_url = inputs["pr_url"]

    tool_calls: list[str] = []
    stages_seen: list[str] = []
    result: dict | None = None
    error: str | None = None
    unit_intermediate: list[dict] = []

    async for event in run_agent(pr_url):
        data = event.model_dump()
        etype = data.get("type")

        if etype == "agent_step":
            tool_calls.append(data["tool"])
        elif etype == "stage_change":
            stages_seen.append(data["stage"])
        elif etype == "checkpoint":
            payload = data.get("payload", {})
            ir = payload.get("intermediate_result", {})
            unit_intermediate = ir.get("affected_components", [])
            # Extract components from the checkpoint's intermediate_result
            result = {
                "affected_components": unit_intermediate,
                "agent_steps": len(tool_calls),
            }
            break
        elif etype == "result":
            result = data
        elif etype == "error":
            error = data.get("message", "unknown error")

    output: dict[str, Any] = {
        "tool_calls": tool_calls,
        "stages_seen": stages_seen,
        "path_taken": "gather_only",
    }

    if error:
        output["error"] = error
    elif result:
        output["affected_components"] = result.get("affected_components", [])
        output["agent_steps"] = result.get("agent_steps", 0)
    else:
        output["error"] = "No result or checkpoint reached"

    return output
