"""
Stage 3b: E2E Test Planning

Maps affected execution flows (processes) to user-facing E2E test scenarios.
Runs in parallel with integration.py after the checkpoint.

Writes only to: e2e_test_plans
Does NOT touch: affected_components

Budget: 20 tool calls.
"""

from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from langgraph.types import interrupt

from agent.prompts import BASE_PROMPT, E2E_PROMPT
from agent.tools import filter_tools, get_mcp_client, safe_tools, make_process_tools

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

    def submit_e2e_plans(e2e_test_plans: list) -> str:
        e2e_results.extend(e2e_test_plans)
        return "E2E test plans recorded."

    def ask_user(question: str) -> str:
        """Ask the human a question when you need information to proceed."""
        response = interrupt({"type": "question", "question": question})
        return response.get("answer", "")

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

    ask_user_tool = StructuredTool.from_function(
        func=ask_user,
        name="ask_user",
        description=(
            "Ask the human a specific question when you need information to continue. "
            "Use this when you don't know the user flow, expected behavior, or any scenario detail "
            "that can't be determined from the PR or code. "
            "Pass question as a clear, specific question string. "
            "Do NOT use this for general clarifications — only when genuinely stuck."
        ),
    )

    repo_clause = (
        f'Pass repo="{repo_name}" to every GitNexus tool call.'
        if repo_name
        else "No GitNexus repo indexed — E2E plans will be based on PR diff only."
    )

    # Processes already pre-fetched in gather stage
    processes = state.get("processes", [])
    processes_clause = (
        "Pre-fetched processes: " + ", ".join(p.get("name", "") for p in processes[:20])
        if processes
        else "No processes pre-fetched — use list_processes tool to discover them."
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

    agent = create_react_agent(
        model=llm,
        tools=stage_tools + [submit_tool, ask_user_tool],
        prompt=SystemMessage(content=f"{BASE_PROMPT}\n\n{E2E_PROMPT}"),
    )

    tool_call_count = 0
    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=(
            f"{processes_clause}\n"
            f"{files_clause}\n"
            f"{repo_clause}"
            f"{context_clause}\n\n"
            "Identify which processes are affected by these file changes, "
            "fetch their details, and generate E2E test plans. "
            "Call submit_e2e_plans with all plans when done."
        ))]},
        version="v2",
        config={"recursion_limit": 50},
    ):
        if event["event"] == "on_tool_start":
            tool_call_count += 1
            print(f"  [e2e {tool_call_count}/{BUDGET}] {event['name']}", flush=True)
            if event["name"] != "submit_e2e_plans" and tool_call_count >= BUDGET:
                break

    return {
        "tool_calls_used": state.get("tool_calls_used", 0) + tool_call_count,
        "e2e_test_plans": e2e_results,
    }
