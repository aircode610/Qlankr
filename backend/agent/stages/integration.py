"""
Stage 3a: Integration Test Generation

Finds cross-module integration points affected by the PR and generates
IntegrationTestSpec objects. Runs in parallel with e2e.py after the checkpoint.

Writes only to: affected_components[i].integration_tests
Does NOT touch: e2e_test_plans

Budget: 15 tool calls.
"""

from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

from agent.prompts import BASE_PROMPT, INTEGRATION_PROMPT
from agent.tools import filter_tools, get_mcp_client, safe_tools

if TYPE_CHECKING:
    from agent.agent import AnalysisState

BUDGET = 15


async def run_integration(state: "AnalysisState", llm: Any) -> dict:
    components = state.get("affected_components", [])
    if not components:
        return {}

    client = get_mcp_client()
    all_tools = await client.get_tools()
    stage_tools = safe_tools(filter_tools(all_tools, "integration"))

    integration_results: list[dict] = []

    def submit_integration_tests(integration_tests: list) -> str:
        integration_results.extend(integration_tests)
        return "Integration tests recorded."

    submit_tool = StructuredTool.from_function(
        func=submit_integration_tests,
        name="submit_integration_tests",
        description=(
            "Submit all integration test specs when done. "
            "Pass integration_tests as a list of IntegrationTestSpec objects, each with: "
            "integration_point (str), modules_involved (list), "
            "test_cases [{name, scenario, expected}], data_setup (str), "
            "risk_level ('CRITICAL'|'HIGH'|'MEDIUM'|'LOW')."
        ),
    )

    repo_name = state.get("repo_name")
    repo_clause = (
        f'Pass repo="{repo_name}" to every GitNexus tool call.'
        if repo_name
        else "No GitNexus repo indexed — integration analysis will be limited."
    )

    # Give the agent the component + file list so it knows what symbols to investigate
    components_block = "\n".join(
        f"- {c.get('component')}: {', '.join(c.get('files_changed', []))}"
        for c in components
    )

    # Include a short diff snippet so the agent knows what changed
    pr_diff = state.get("pr_diff", "")
    diff_section = (
        f"## PR Diff (summary of changes)\n```\n{pr_diff[:4000]}\n```\n"
        if pr_diff
        else ""
    )

    agent = create_react_agent(
        model=llm,
        tools=stage_tools + [submit_tool],
        prompt=SystemMessage(content=f"{BASE_PROMPT}\n\n{INTEGRATION_PROMPT}"),
    )

    tool_call_count = 0
    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=(
            f"{diff_section}"
            f"Affected components:\n{components_block}\n\n"
            f"{repo_clause}\n\n"
            "Use impact/context/query/cypher to find cross-module integration points. "
            "When done, call submit_integration_tests with all specs at once."
        ))]},
        version="v2",
        config={"recursion_limit": 40},
    ):
        if event["event"] == "on_tool_start":
            tool_call_count += 1
            print(f"  [integration {tool_call_count}/{BUDGET}] {event['name']}", flush=True)
            if event["name"] != "submit_integration_tests" and tool_call_count >= BUDGET:
                break

    # Distribute integration specs back into affected_components by module name matching
    updated = []
    for comp in components:
        comp_name = comp.get("component", "").lower()
        matched = [
            spec for spec in integration_results
            if any(m.lower() in comp_name or comp_name in m.lower()
                   for m in spec.get("modules_involved", []))
        ]
        updated.append({**comp, "integration_tests": matched})

    return {
        "tool_calls_used": state.get("tool_calls_used", 0) + tool_call_count,
        "affected_components": updated,
    }
