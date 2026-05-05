"""
Stage 3b: E2E Test Planning

Maps affected execution flows (processes) to user-facing E2E test scenarios.
Runs in parallel with integration.py after the checkpoint.

Writes only to: e2e_test_plans
Does NOT touch: affected_components

Budget: 20 tool calls.
"""

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from agent.prompts import BASE_PROMPT, E2E_PROMPT
from agent.tools import filter_tools, fix_dangling_tool_calls, get_mcp_client, make_messages_modifier, make_process_tools, safe_tools

if TYPE_CHECKING:
    from agent.agent import AnalysisState

BUDGET = 20


async def run_e2e(state: "AnalysisState", llm: Any) -> dict:
    client = get_mcp_client()
    all_tools = await client.get_tools()
    stage_tools = safe_tools(filter_tools(all_tools, "e2e"))

    repo_name = state.get("repo_name")
    if repo_name:
        stage_tools = stage_tools + make_process_tools(repo_name)

    e2e_results: list[dict] = []

    def submit_e2e_plans(e2e_test_plans: list = []) -> str:
        if not e2e_test_plans:
            return (
                "REJECTED: e2e_test_plans is empty or missing. "
                "You MUST generate at least one E2E test plan. "
                "If no processes were found in the graph, create plans directly from "
                "the changed files and PR diff — use the file list you already have. "
                "Each plan needs: process (use the file/feature name), scenario, "
                "preconditions, steps [{step, action, expected}], affected_by_pr, "
                "priority, estimated_duration. "
                "Call submit_e2e_plans again with a non-empty list."
            )
        e2e_results.extend(e2e_test_plans)
        return "E2E test plans recorded."

    submit_tool = StructuredTool.from_function(
        func=submit_e2e_plans,
        name="submit_e2e_plans",
        description=(
            "Submit all E2E test plans when done. "
            "Pass e2e_test_plans as a list of E2ETestPlan objects, each with: "
            "process (str), scenario (str), preconditions (str), "
            "steps [{step, action, expected}], affected_by_pr (list), "
            "priority ('CRITICAL'|'HIGH'|'MEDIUM'|'LOW'), estimated_duration (str)."
        ),
    )

    repo_clause = (
        f'Pass repo="{repo_name}" to every GitNexus tool call.'
        if repo_name
        else "No GitNexus repo indexed — E2E plans will be based on PR diff only."
    )

    # Processes already pre-fetched in gather stage
    processes = state.get("processes", [])
    process_count_in_graph = state.get("repo_stats", {}).get("processes", 0)

    if process_count_in_graph == 0:
        print(
            "  [e2e] WARNING: repo_stats.processes=0 — no Process nodes in graph. "
            "E2E plans will be derived from PR diff only.",
            flush=True,
        )
        processes_clause = (
            "NO PROCESSES FOUND: The knowledge graph contains no indexed execution flows "
            f"for repo '{repo_name}'. Do NOT call list_processes — it will fail. "
            "Instead, generate E2E test plans directly from the changed files listed below. "
            "Use the feature/module name of each changed file as the 'process' field."
        )
    elif processes:
        processes_clause = (
            "Pre-fetched processes: " + ", ".join(p.get("name", "") for p in processes[:20])
        )
    else:
        # Graph has processes but pre-fetch failed — let the agent discover them
        processes_clause = (
            f"Graph has {process_count_in_graph} indexed processes but pre-fetch failed. "
            "Use list_processes tool to discover them."
        )

    # User context (optional bug report / scenario)
    user_context = state.get("user_context")
    context_clause = (
        f"\nUser-provided context (bug report / scenario to trace):\n{user_context}"
        if user_context
        else ""
    )

    components = state.get("affected_components", [])
    affected_files = [f for c in components for f in c.get("files_changed", [])]
    files_clause = f"Changed files: {', '.join(affected_files[:20])}" if affected_files else ""

    _saver = MemorySaver()
    _thread = f"{state.get('session_id', state.get('pr_url', 'anon'))}-e2e-{uuid4().hex[:8]}"
    _stage_config = {"configurable": {"thread_id": _thread}, "recursion_limit": 50}

    human_message = HumanMessage(content=(
        f"{processes_clause}\n"
        f"{files_clause}\n"
        f"{repo_clause}"
        f"{context_clause}\n\n"
        "Identify which processes are affected by these file changes, "
        "fetch their details, and generate E2E test plans. "
        "Call submit_e2e_plans with all plans when done."
    ))

    agent = create_react_agent(
        model=llm,
        tools=stage_tools + [submit_tool],
        prompt=SystemMessage(content=f"{BASE_PROMPT}\n\n{E2E_PROMPT}"),
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
            print(f"  [e2e {tool_call_count}/{BUDGET}] {event['name']}", flush=True)
            if event["name"] != "submit_e2e_plans" and tool_call_count >= BUDGET:
                budget_reached = True
        elif event_type == "on_tool_end":
            pending_tools = max(0, pending_tools - 1)
            if event.get("name") == "submit_e2e_plans":
                break
            if budget_reached and pending_tools == 0:
                break

    if not e2e_results:
        print(f"  [e2e] budget hit without submit — forcing synthesis from {tool_call_count} calls", flush=True)
        agent_state = await agent.aget_state(_stage_config)
        accumulated = fix_dangling_tool_calls(agent_state.values.get("messages", []))
        submit_agent = create_react_agent(
            model=llm,
            tools=[submit_tool],
            prompt=SystemMessage(content=f"{BASE_PROMPT}\n\n{E2E_PROMPT}"),
        )
        async for _ in submit_agent.astream_events(
            {"messages": accumulated + [HumanMessage(content=(
                f"[BUDGET EXHAUSTED after {tool_call_count} tool calls] "
                "Call submit_e2e_plans NOW with all E2E test plans from your analysis. "
                "Use priority='LOW' for any plans with incomplete process details."
            ))]},
            version="v2",
            config={"recursion_limit": 25},
        ):
            pass

    return {
        "tool_calls_used": state.get("tool_calls_used", 0) + tool_call_count,
        "e2e_test_plans": e2e_results,
    }
