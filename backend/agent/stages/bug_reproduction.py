"""
Bug Stage 3: Reproduction Planning

Translates confirmed code paths and root cause hypotheses into QA-readable
step-by-step reproduction instructions.
Budget: 12 tool calls.
"""

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from agent.prompts import BUG_BASE_PROMPT, BUG_REPRODUCTION_PROMPT
from agent.tools import filter_tools, fix_dangling_tool_calls, get_mcp_client, make_messages_modifier, safe_tools

if TYPE_CHECKING:
    from agent.agent import BugReproductionState

BUDGET = 12


async def reproduction_node(state: "BugReproductionState", llm: Any = None, client: Any = None) -> dict:
    if llm is None:
        from agent.agent import _llm
        llm = _llm

    _own_client = client is None
    if _own_client:
        print("[bug_reproduction] starting MCP client...", flush=True)
        client = get_mcp_client()
    all_tools = await client.get_tools()
    if _own_client:
        print(f"[bug_reproduction] got {len(all_tools)} tools, filtering to bug_reproduction stage...", flush=True)
    stage_tools = safe_tools(filter_tools(all_tools, "bug_reproduction"))

    class _ReproductionOutput(BaseModel):
        steps: list[dict] = Field(default_factory=list)
        prerequisites: list[str] = Field(default_factory=list)
        environment_requirements: list[str] = Field(default_factory=list)
        confidence: str = "low"

    results: list[_ReproductionOutput] = []

    def submit_reproduction(
        steps: list = [],
        prerequisites: list = [],
        environment_requirements: list = [],
        confidence: str = "low",
    ) -> str:
        results.append(_ReproductionOutput(
            steps=steps,
            prerequisites=prerequisites,
            environment_requirements=environment_requirements,
            confidence=confidence,
        ))
        return "Reproduction plan complete."

    submit_tool = StructuredTool.from_function(
        func=submit_reproduction,
        name="submit_reproduction",
        description=(
            "Submit the reproduction plan when done. "
            "Pass: steps (list of {step_number, action, expected_result}, minimum 3), "
            "prerequisites (list of setup conditions in plain English), "
            "environment_requirements (list of platform/build/settings requirements), "
            "confidence (high|medium|low)."
        ),
    )

    triage = state.get("triage", {})
    mechanics = state.get("mechanics", {})
    repo_name = state.get("repo_name")
    repo_clause = (
        f'Repo "{repo_name}" is indexed in GitNexus. Pass repo="{repo_name}" to every GitNexus tool call.'
        if repo_name
        else "No indexed repo — use mechanics findings only."
    )

    top_hypothesis = ""
    hypotheses = mechanics.get("root_cause_hypotheses", [])
    if hypotheses:
        h = hypotheses[0]
        top_hypothesis = f"Top hypothesis: {h.get('hypothesis', '')}"

    top_path = ""
    paths = mechanics.get("code_paths", [])
    if paths:
        top_path = f"Primary code path: {paths[0].get('path', '')}"

    human_content = (
        f"Write reproduction steps for this bug:\n\n"
        f"Description: {state['description']}\n\n"
        f"Affected area: {triage.get('affected_area', 'unknown')}\n"
        f"Affected components: {', '.join(mechanics.get('affected_components', []))}\n"
        f"{top_path}\n"
        f"{top_hypothesis}\n\n"
        f"{repo_clause}"
    )

    _saver = MemorySaver()
    _thread = f"{state.get('session_id', 'anon')}-reproduction-{uuid4().hex[:8]}"
    _stage_config = {"configurable": {"thread_id": _thread}, "recursion_limit": 40}

    agent = create_react_agent(
        model=llm,
        tools=stage_tools + [submit_tool],
        prompt=SystemMessage(content=f"{BUG_BASE_PROMPT}\n\n{BUG_REPRODUCTION_PROMPT}"),
        checkpointer=_saver,
        pre_model_hook=make_messages_modifier(),
    )

    tool_call_count = 0
    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=human_content)]},
        version="v2",
        config=_stage_config,
    ):
        event_type = event["event"]
        if event_type == "on_tool_start":
            tool_call_count += 1
            print(f"  [{tool_call_count}/{BUDGET}] {event['name']}", flush=True)
            if event["name"] != "submit_reproduction" and tool_call_count >= BUDGET:
                break
        elif event_type == "on_tool_end" and event.get("name") == "submit_reproduction":
            break

    base_count = state.get("tool_calls_used", 0)
    if not results:
        print(f"  [reproduction] budget hit without submit — forcing synthesis from {tool_call_count} calls", flush=True)
        agent_state = await agent.aget_state(_stage_config)
        accumulated = fix_dangling_tool_calls(agent_state.values.get("messages", []))
        submit_agent = create_react_agent(
            model=llm,
            tools=[submit_tool],
            prompt=SystemMessage(content=f"{BUG_BASE_PROMPT}\n\n{BUG_REPRODUCTION_PROMPT}"),
            pre_model_hook=make_messages_modifier(),
        )
        async for _ in submit_agent.astream_events(
            {"messages": accumulated + [HumanMessage(content=(
                f"[BUDGET EXHAUSTED after {tool_call_count} tool calls] "
                "Call submit_reproduction NOW with your findings. No more research tools available. "
                "Use confidence='low' if you couldn't fully verify all steps."
            ))]},
            version="v2",
            config={"recursion_limit": 10},
        ):
            pass

    if not results:
        return {
            "current_stage": "research",
            "tool_calls_used": base_count + tool_call_count,
        }

    r = results[-1]
    return {
        "current_stage": "research",
        "tool_calls_used": base_count + tool_call_count,
        "reproduction_plan": r.model_dump(),
    }
