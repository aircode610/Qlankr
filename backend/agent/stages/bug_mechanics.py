"""
Bug Stage 2: Mechanics Analysis

Traces code paths, identifies affected components, and produces ranked root
cause hypotheses backed by evidence from the graph and file contents.
Budget: 15 tool calls.
"""

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from agent.prompts import BUG_BASE_PROMPT, BUG_MECHANICS_PROMPT
from agent.tools import filter_tools, get_mcp_client, safe_tools

if TYPE_CHECKING:
    from agent.agent import BugReproductionState

BUDGET = 15


async def mechanics_node(state: "BugReproductionState", llm: Any = None, client: Any = None) -> dict:
    if llm is None:
        from agent.agent import _llm
        llm = _llm

    _own_client = client is None
    if _own_client:
        print("[bug_mechanics] starting MCP client...", flush=True)
        client = get_mcp_client()
    all_tools = await client.get_tools()
    if _own_client:
        print(f"[bug_mechanics] got {len(all_tools)} tools, filtering to bug_mechanics stage...", flush=True)
    stage_tools = safe_tools(filter_tools(all_tools, "bug_mechanics"))

    class _MechanicsOutput(BaseModel):
        code_paths: list[dict] = Field(default_factory=list)
        affected_components: list[str] = Field(default_factory=list)
        root_cause_hypotheses: list[dict] = Field(default_factory=list)

    results: list[_MechanicsOutput] = []

    def submit_mechanics(
        code_paths: list = [],
        affected_components: list = [],
        root_cause_hypotheses: list = [],
    ) -> str:
        results.append(_MechanicsOutput(
            code_paths=code_paths,
            affected_components=affected_components,
            root_cause_hypotheses=root_cause_hypotheses,
        ))
        return "Mechanics analysis complete."

    submit_tool = StructuredTool.from_function(
        func=submit_mechanics,
        name="submit_mechanics",
        description=(
            "Submit mechanics findings when done. "
            "Pass: code_paths (list of {path, description, confidence}), "
            "affected_components (list of component/module name strings), "
            "root_cause_hypotheses (list of {hypothesis, confidence, evidence})."
        ),
    )

    triage = state.get("triage", {})
    repo_name = state.get("repo_name")
    repo_clause = (
        f'Repo "{repo_name}" is indexed in GitNexus. Pass repo="{repo_name}" to every GitNexus tool call.'
        if repo_name
        else "No indexed repo — use file contents and code search only."
    )

    triage_summary = (
        f"Keywords: {', '.join(triage.get('keywords', []))}\n"
        f"Affected files: {', '.join(triage.get('affected_files', []) or ['none found'])}\n"
        f"Initial hypotheses:\n" +
        "\n".join(f"  - {h}" for h in triage.get("initial_hypotheses", []))
    )

    human_content = (
        f"Analyse the mechanics of this bug:\n\n"
        f"Description: {state['description']}\n\n"
        f"Triage findings:\n{triage_summary}\n\n"
        f"{repo_clause}"
    )

    _saver = MemorySaver()
    _thread = f"{state.get('session_id', 'anon')}-mechanics-{uuid4().hex[:8]}"
    _stage_config = {"configurable": {"thread_id": _thread}, "recursion_limit": 40}

    agent = create_react_agent(
        model=llm,
        tools=stage_tools + [submit_tool],
        prompt=SystemMessage(content=f"{BUG_BASE_PROMPT}\n\n{BUG_MECHANICS_PROMPT}"),
        checkpointer=_saver,
    )

    tool_call_count = 0
    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=human_content)]},
        version="v2",
        config=_stage_config,
    ):
        if event["event"] == "on_tool_start":
            tool_call_count += 1
            print(f"  [{tool_call_count}/{BUDGET}] {event['name']}", flush=True)
            if event["name"] != "submit_mechanics" and tool_call_count >= BUDGET:
                break

    base_count = state.get("tool_calls_used", 0)
    if not results:
        print(f"  [mechanics] budget hit without submit — forcing synthesis from {tool_call_count} calls", flush=True)
        agent_state = await agent.aget_state(_stage_config)
        accumulated = agent_state.values.get("messages", [])
        submit_agent = create_react_agent(
            model=llm,
            tools=[submit_tool],
            prompt=SystemMessage(content=f"{BUG_BASE_PROMPT}\n\n{BUG_MECHANICS_PROMPT}"),
        )
        async for _ in submit_agent.astream_events(
            {"messages": accumulated + [HumanMessage(content=(
                f"[BUDGET EXHAUSTED after {tool_call_count} tool calls] "
                "Call submit_mechanics NOW with your findings. No more research tools available. "
                "Use confidence='medium' or 'low' as appropriate for what you found."
            ))]},
            version="v2",
            config={"recursion_limit": 5},
        ):
            pass

    if not results:
        return {
            "current_stage": "reproduction_planning",
            "tool_calls_used": base_count + tool_call_count,
        }

    r = results[-1]
    return {
        "current_stage": "reproduction_planning",
        "tool_calls_used": base_count + tool_call_count,
        "mechanics": r.model_dump(),
    }
