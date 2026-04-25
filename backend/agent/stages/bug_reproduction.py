"""
Bug Stage 3: Reproduction Planning

Translates confirmed code paths and root cause hypotheses into QA-readable
step-by-step reproduction instructions.
Budget: 12 tool calls.
"""

from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from agent.prompts import BUG_BASE_PROMPT, BUG_REPRODUCTION_PROMPT
from agent.tools import filter_tools, get_mcp_client, safe_tools

if TYPE_CHECKING:
    from agent.agent import BugReproductionState

BUDGET = 12


async def reproduction_node(state: "BugReproductionState", llm: Any = None) -> dict:
    if llm is None:
        from agent.agent import _llm
        llm = _llm

    print("[bug_reproduction] starting MCP client...", flush=True)
    client = get_mcp_client()
    all_tools = await client.get_tools()
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

    agent = create_react_agent(
        model=llm,
        tools=stage_tools + [submit_tool],
        prompt=SystemMessage(content=f"{BUG_BASE_PROMPT}\n\n{BUG_REPRODUCTION_PROMPT}"),
    )

    tool_call_count = 0
    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=human_content)]},
        version="v2",
        config={"recursion_limit": 40},
    ):
        if event["event"] == "on_tool_start":
            tool_call_count += 1
            print(f"  [{tool_call_count}/{BUDGET}] {event['name']}", flush=True)
            if event["name"] != "submit_reproduction" and tool_call_count >= BUDGET:
                break

    base_count = state.get("tool_calls_used", 0)
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
