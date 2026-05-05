"""
Stage 3a: Integration Test Generation

Finds cross-module integration points affected by the PR and generates
IntegrationTestSpec objects. Runs in parallel with e2e.py after the checkpoint.

Writes only to: affected_components[i].integration_tests
Does NOT touch: e2e_test_plans

Budget: 15 tool calls.
"""

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from agent.prompts import BASE_PROMPT, INTEGRATION_PROMPT
from agent.tools import filter_tools, fix_dangling_tool_calls, get_mcp_client, make_messages_modifier, safe_tools

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

    def submit_integration_tests(integration_tests: list = []) -> str:
        if not integration_tests:
            return (
                "REJECTED: integration_tests is empty or missing. "
                "You MUST generate at least one integration test spec. "
                "If graph tools returned no results, generate specs from the affected "
                "components and PR diff you already have — identify the module boundaries "
                "that the changed files cross and describe them. "
                "Each spec needs: integration_point, modules_involved, test_cases "
                "[{name, scenario, expected}], data_setup, risk_level. "
                "Call submit_integration_tests again with a non-empty list."
            )
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

    _saver = MemorySaver()
    _thread = f"{state.get('session_id', state.get('pr_url', 'anon'))}-integration-{uuid4().hex[:8]}"
    _stage_config = {"configurable": {"thread_id": _thread}, "recursion_limit": 40}

    human_message = HumanMessage(content=(
        f"{diff_section}"
        f"Affected components:\n{components_block}\n\n"
        f"{repo_clause}\n\n"
        "Use impact/context/query/cypher to find cross-module integration points. "
        "When done, call submit_integration_tests with all specs at once."
    ))

    agent = create_react_agent(
        model=llm,
        tools=stage_tools + [submit_tool],
        prompt=SystemMessage(content=f"{BASE_PROMPT}\n\n{INTEGRATION_PROMPT}"),
        checkpointer=_saver,
        pre_model_hook=make_messages_modifier(),  # cap tool outputs at 12K chars
    )

    tool_call_count = 0
    pending_tools = 0   # tracks how many parallel tool calls are mid-flight
    budget_reached = False

    async for event in agent.astream_events(
        {"messages": [human_message]},
        version="v2",
        config=_stage_config,
    ):
        event_type = event["event"]
        if event_type == "on_tool_start":
            pending_tools += 1
            tool_call_count += 1
            print(f"  [integration {tool_call_count}/{BUDGET}] {event['name']}", flush=True)
            if event["name"] != "submit_integration_tests" and tool_call_count >= BUDGET:
                budget_reached = True
        elif event_type == "on_tool_end":
            pending_tools = max(0, pending_tools - 1)
            if event.get("name") == "submit_integration_tests":
                break
            # Only break once the current parallel batch is fully complete —
            # breaking mid-batch leaves dangling tool_calls with no ToolMessages,
            # which Anthropic's API rejects as invalid chat history.
            if budget_reached and pending_tools == 0:
                break

    if not integration_results:
        print(f"  [integration] budget hit without submit — forcing synthesis from {tool_call_count} calls", flush=True)
        agent_state = await agent.aget_state(_stage_config)
        # Fix any dangling tool_calls left by the budget break before handing the
        # history to the forced-submit agent — without this Anthropic rejects the request.
        accumulated = fix_dangling_tool_calls(agent_state.values.get("messages", []))
        submit_agent = create_react_agent(
            model=llm,
            tools=[submit_tool],
            prompt=SystemMessage(content=f"{BASE_PROMPT}\n\n{INTEGRATION_PROMPT}"),
        )
        async for _ in submit_agent.astream_events(
            {"messages": accumulated + [HumanMessage(content=(
                f"[BUDGET EXHAUSTED after {tool_call_count} tool calls] "
                "Call submit_integration_tests NOW with all integration points found. "
                "Use risk_level='LOW' for any specs with incomplete evidence."
            ))]},
            version="v2",
            config={"recursion_limit": 25},
        ):
            pass

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
