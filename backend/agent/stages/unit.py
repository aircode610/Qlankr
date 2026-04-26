"""
Stage 2: Unit Test Generation

One sequential agent processes components one at a time.
For each component it reads files, generates specs, calls submit_unit_tests,
then moves to the next — never reading ahead.

Budget: 15 tool calls total across all components.
"""

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from agent.prompts import BASE_PROMPT, UNIT_PROMPT
from agent.tools import filter_tools, get_mcp_client, safe_tools

if TYPE_CHECKING:
    from agent.agent import AnalysisState

BUDGET = 15


async def run_unit(state: "AnalysisState", llm: Any) -> dict:
    components = state.get("affected_components", [])
    if not components:
        return {"current_stage": "checkpoint_unit"}

    client = get_mcp_client()
    all_tools = await client.get_tools()
    stage_tools = safe_tools(filter_tools(all_tools, "unit"))

    unit_results: dict[str, list] = {}

    def submit_unit_tests(component: str, unit_tests: list) -> str:
        unit_results[component] = unit_tests
        return f"Recorded. Move to the next component."

    submit_tool = StructuredTool.from_function(
        func=submit_unit_tests,
        name="submit_unit_tests",
        description=(
            "Submit unit test specs for the current component before moving to the next. "
            "Pass component (exact name) and unit_tests "
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

    # Build a numbered component list so the agent processes them in order
    components_block = "\n".join(
        f"{i+1}. Component: {c.get('component')}\n"
        f"   Files: {', '.join(c.get('files_changed', []))}"
        for i, c in enumerate(components)
    )

    pr_diff = state.get("pr_diff", "")
    diff_section = (
        f"## PR Diff (already fetched — do NOT call get_file_contents)\n```\n{pr_diff[:6000]}\n```"
        if pr_diff
        else "No diff available — use get_file_contents if needed."
    )

    unit_feedback = state.get("unit_feedback")
    feedback_section = (
        f"\n## User Feedback (from previous run — address this)\n{unit_feedback}\n"
        if unit_feedback
        else ""
    )

    _saver = MemorySaver()
    _thread = f"{state.get('session_id', state.get('pr_url', 'anon'))}-unit-{uuid4().hex[:8]}"
    _stage_config = {"configurable": {"thread_id": _thread}, "recursion_limit": 60}

    human_message = HumanMessage(content=(
        f"{diff_section}"
        f"{feedback_section}\n\n"
        f"Process these components ONE AT A TIME in order:\n\n{components_block}\n\n"
        f"{repo_clause}\n\n"
        "For each component:\n"
        "1. Use the diff above — do NOT call get_file_contents\n"
        "2. Use context/cypher only if you need deeper graph info\n"
        "3. Call submit_unit_tests with the specs\n"
        "4. Only then move to the next component\n\n"
        f"Total budget: {BUDGET} tool calls."
    ))

    agent = create_react_agent(
        model=llm,
        tools=stage_tools + [submit_tool],
        prompt=SystemMessage(content=f"{BASE_PROMPT}\n\n{UNIT_PROMPT}"),
        checkpointer=_saver,
    )

    tool_call_count = 0
    submit_count = 0
    expected_submits = len(components)

    async for event in agent.astream_events(
        {"messages": [human_message]},
        version="v2",
        config=_stage_config,
    ):
        if event["event"] == "on_tool_start":
            tool_call_count += 1
            print(f"  [unit {tool_call_count}/{BUDGET}] {event['name']}", flush=True)
            if event["name"] == "submit_unit_tests":
                submit_count += 1
                if submit_count >= expected_submits:
                    break  # All components submitted
            elif tool_call_count >= BUDGET:
                break

    # If budget hit before any component was submitted, force a submit pass
    if not unit_results:
        print(f"  [unit] budget hit without any submit — forcing synthesis from {tool_call_count} calls", flush=True)
        agent_state = await agent.aget_state(_stage_config)
        accumulated = agent_state.values.get("messages", [])
        pending = "\n".join(f"- {c.get('component')}" for c in components)
        submit_agent = create_react_agent(
            model=llm,
            tools=[submit_tool],
            prompt=SystemMessage(content=f"{BASE_PROMPT}\n\n{UNIT_PROMPT}"),
        )
        async for _ in submit_agent.astream_events(
            {"messages": accumulated + [HumanMessage(content=(
                f"[BUDGET EXHAUSTED after {tool_call_count} tool calls] "
                f"Call submit_unit_tests for each of these components with your best analysis:\n{pending}\n"
                "Use the diff context already in this conversation. Prioritise high-risk components."
            ))]},
            version="v2",
            config={"recursion_limit": 20},
        ):
            pass

    updated = [
        {**c, "unit_tests": unit_results.get(c.get("component", ""), [])}
        for c in components
    ]

    return {
        "current_stage": "checkpoint_unit",
        "tool_calls_used": state.get("tool_calls_used", 0) + tool_call_count,
        "affected_components": updated,
    }
