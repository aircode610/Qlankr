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
from pydantic import BaseModel, Field

from agent.prompts import BASE_PROMPT, E2E_PROMPT
from agent.tools import filter_tools, fix_dangling_tool_calls, get_mcp_client, make_messages_modifier, make_process_tools, safe_tools

if TYPE_CHECKING:
    from agent.agent import AnalysisState

BUDGET = 20


class _E2EStep(BaseModel):
    step: int
    action: str
    expected: str


class _E2ETestPlan(BaseModel):
    process: str
    scenario: str
    preconditions: str = ""
    steps: list[_E2EStep]
    affected_by_pr: list[str] = Field(default_factory=list)
    priority: str = "MEDIUM"
    estimated_duration: str = "5 min"


class _E2EOutput(BaseModel):
    """Container for structured output fallback."""
    e2e_test_plans: list[_E2ETestPlan] = Field(min_length=1)


async def run_e2e(state: "AnalysisState", llm: Any) -> dict:
    client = get_mcp_client()
    all_tools = await client.get_tools()
    stage_tools = safe_tools(filter_tools(all_tools, "e2e"))

    repo_name = state.get("repo_name")
    if repo_name:
        stage_tools = stage_tools + make_process_tools(repo_name, all_tools=all_tools)

    e2e_results: list[dict] = []

    def submit_e2e_plans(e2e_test_plans: list | None = None) -> str:
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
        e2e_results.extend(e2e_test_plans)  # type: ignore[arg-type]
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

    # Include a diff snippet so the agent knows what actually changed
    pr_diff = state.get("pr_diff", "")
    diff_section = (
        f"\n## PR Diff\n```\n{pr_diff[:4000]}\n```\n"
        if pr_diff
        else ""
    )

    components_block = "\n".join(
        f"- {c.get('component')}: {', '.join(c.get('files_changed', []))}"
        for c in components
    )

    _saver = MemorySaver()
    _thread = f"{state.get('session_id', state.get('pr_url', 'anon'))}-e2e-{uuid4().hex[:8]}"
    _stage_config = {"configurable": {"thread_id": _thread}, "recursion_limit": 50}

    # When no processes exist, give a focused instruction that doesn't
    # contradict the "no processes" clause by asking to fetch process details.
    if process_count_in_graph == 0:
        human_message = HumanMessage(content=(
            f"{processes_clause}\n\n"
            f"Affected components:\n{components_block}\n\n"
            f"{files_clause}\n"
            f"{diff_section}"
            f"{context_clause}\n\n"
            "Generate E2E test plans directly from the affected components and PR diff above. "
            "For each component, create at least one plan describing user-facing test steps "
            "that exercise the changed functionality end-to-end. "
            "Do NOT call cypher, impact, or query — there is no process data to find. "
            "Call submit_e2e_plans with all plans when done."
        ))
        # Strip graph tools — they will only waste budget on Binder exceptions
        stage_tools = [t for t in stage_tools if t.name not in ("cypher", "impact", "query")]
    else:
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
    submit_rejections = 0
    MAX_SUBMIT_REJECTIONS = 3

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
                # Only break if submit actually recorded data — rejection
                # returns guidance the agent can use to retry.
                if e2e_results:
                    break
                submit_rejections += 1
                print(f"  [e2e] submit_e2e_plans rejected ({submit_rejections}/{MAX_SUBMIT_REJECTIONS})", flush=True)
                if submit_rejections >= MAX_SUBMIT_REJECTIONS:
                    break
            elif budget_reached and pending_tools == 0:
                break

    if not e2e_results:
        print(f"  [e2e] budget hit without submit — forcing synthesis from {tool_call_count} calls", flush=True)

        if process_count_in_graph == 0:
            # No processes — build a short, self-contained synthesis message from
            # state data (accumulated messages are just cypher errors / noise).
            pr_diff = state.get("pr_diff", "")
            diff_snippet = f"\n## PR Diff\n```\n{pr_diff[:3000]}\n```" if pr_diff else ""
            components_block = "\n".join(
                f"- {c.get('component')}: {', '.join(c.get('files_changed', []))}"
                for c in components
            )
            synthesis_messages = [HumanMessage(content=(
                "No execution flows exist in the knowledge graph for this repo.\n\n"
                f"Affected components:\n{components_block}\n"
                f"{files_clause}\n"
                f"{diff_snippet}\n\n"
                "Generate one E2E test plan per component from the above. Each plan needs: "
                "process (component name), scenario, preconditions, "
                "steps [{step, action, expected}], affected_by_pr (list of files), "
                "priority ('MEDIUM' unless obviously critical), estimated_duration."
            ))]
        else:
            agent_state = await agent.aget_state(_stage_config)
            accumulated = fix_dangling_tool_calls(agent_state.values.get("messages", []))
            # Trim to the last 30 messages to keep context small.
            accumulated = accumulated[-30:] if len(accumulated) > 30 else accumulated
            synthesis_messages = accumulated + [HumanMessage(content=(
                f"[BUDGET EXHAUSTED after {tool_call_count} tool calls] "
                "Return all E2E test plans from your analysis as structured output. "
                "Use priority='LOW' for any plans with incomplete process details."
            ))]

        # Use structured output instead of a full ReAct agent — one LLM call, no
        # tool overhead, Pydantic-validated response.
        structured_llm = llm.with_structured_output(_E2EOutput)
        try:
            result = await structured_llm.ainvoke(
                [SystemMessage(content=f"{BASE_PROMPT}\n\n{E2E_PROMPT}")]
                + synthesis_messages,
            )
            e2e_results.extend(
                [plan.model_dump() for plan in result.e2e_test_plans]
            )
        except Exception as e:
            print(f"  [e2e] structured output fallback failed: {e}", flush=True)

    return {
        "tool_calls_used": state.get("tool_calls_used", 0) + tool_call_count,
        "e2e_test_plans": e2e_results,
    }
