"""
Stage 2: Unit Test Generation

For each affected component, generates UnitTestSpec objects describing
test cases, mock dependencies, and priority.
Budget: 15 tool calls.
"""

from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

from agent.prompts import BASE_PROMPT, UNIT_PROMPT
from agent.tools import filter_tools, get_mcp_client

if TYPE_CHECKING:
    from agent.agent import AnalysisState

BUDGET = 15


async def run_unit(state: "AnalysisState", llm: Any) -> dict:
    components = state.get("affected_components", [])
    if not components:
        return {"current_stage": "checkpoint_unit"}

    client = get_mcp_client()
    all_tools = await client.get_tools()
    stage_tools = filter_tools(all_tools, "unit")

    unit_results: dict[str, list] = {}  # component -> [UnitTestSpec dicts]

    def submit_unit_tests(component: str, unit_tests: list) -> str:
        """
        Submit unit test specs for one component.
        component: exact component name from affected_components.
        unit_tests: list of UnitTestSpec dicts with keys:
          target (str), test_cases (list), mocks_needed (list), priority (str).
        """
        unit_results[component] = unit_tests
        return f"Unit tests recorded for {component}."

    submit_tool = StructuredTool.from_function(
        func=submit_unit_tests,
        name="submit_unit_tests",
        description=(
            "Submit unit test specs for one affected component. "
            "Call once per component. "
            "Pass component (exact name from the list) and unit_tests "
            "(list of objects with: target, test_cases [{name, scenario, expected}], "
            "mocks_needed, priority ['high'|'medium'|'low'])."
        ),
    )

    repo_name = state.get("repo_name")
    repo_clause = (
        f'Pass repo="{repo_name}" to every GitNexus tool call.'
        if repo_name
        else "No indexed repo — use get_file_contents only."
    )

    components_list = "\n".join(
        f"- {c.get('component')}: {', '.join(c.get('files_changed', []))}"
        for c in components
    )

    submit_instruction = (
        "\n\n## Output requirement\n"
        "You MUST call `submit_unit_tests` once for EACH component when done.\n"
        "Do NOT write test specs as text — only tool calls count as output.\n"
        "After reading files, immediately call submit_unit_tests for that component."
    )

    agent = create_react_agent(
        model=llm,
        tools=stage_tools + [submit_tool],
        prompt=SystemMessage(content=f"{BASE_PROMPT}\n\n{UNIT_PROMPT}{submit_instruction}"),
    )

    tool_call_count = 0
    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=(
            f"Generate unit test specs for these components:\n{components_list}\n\n"
            f"{repo_clause}\n"
            f"You have {BUDGET} tool calls total. After analysing each component, "
            "call submit_unit_tests before moving to the next one."
        ))]},
        version="v2",
        config={"recursion_limit": 40},
    ):
        if event["event"] == "on_tool_start":
            tool_call_count += 1
            print(f"  [unit {tool_call_count}/{BUDGET}] {event['name']}", flush=True)
            if tool_call_count >= BUDGET:
                break

    updated = [
        {**c, "unit_tests": unit_results.get(c.get("component", ""), [])}
        for c in components
    ]

    return {
        "current_stage": "checkpoint_unit",
        "tool_calls_used": state.get("tool_calls_used", 0) + tool_call_count,
        "affected_components": updated,
    }
