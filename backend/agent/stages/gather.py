"""
Stage 1: Context Gathering

Collects PR metadata, changed files, diff, and initial affected components.
Budget: 10 tool calls. Does not generate test specs — collect only.
"""

from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from agent.prompts import BASE_PROMPT, GATHER_PROMPT
from agent.tools import filter_tools, get_mcp_client

if TYPE_CHECKING:
    from agent.agent import AnalysisState

BUDGET = 10


async def run_gather(state: "AnalysisState", llm: Any) -> dict:
    print("[gather] starting MCP client...", flush=True)
    client = get_mcp_client()
    all_tools = await client.get_tools()
    print(f"[gather] got {len(all_tools)} tools, filtering to gather stage...", flush=True)
    stage_tools = filter_tools(all_tools, "gather")

    class _GatherOutput(BaseModel):
        pr_title: str
        pr_description: str = ""
        pr_author: str = ""
        pr_files: list[str] = Field(default_factory=list)
        pr_diff: str = ""
        affected_components: list[dict] = Field(default_factory=list)

    results: list[_GatherOutput] = []

    def submit_gather(
        pr_title: str,
        pr_description: str = "",
        pr_author: str = "",
        pr_files: list = [],
        pr_diff: str = "",
        affected_components: list = [],
    ) -> str:
        results.append(_GatherOutput(
            pr_title=pr_title,
            pr_description=pr_description,
            pr_author=pr_author,
            pr_files=pr_files,
            pr_diff=pr_diff,
            affected_components=affected_components,
        ))
        return "Context gathered."

    submit_tool = StructuredTool.from_function(
        func=submit_gather,
        name="submit_gather",
        description=(
            "Submit the gathered PR context when done collecting. "
            "Pass: pr_title, pr_description, pr_author, "
            "pr_files (list of changed file paths), pr_diff (full diff text), "
            "affected_components (list of objects, each with: "
            "component (str), files_changed ([str]), "
            "impact_summary (str — 1-2 sentences on what breaks), "
            "risks ([str] — specific risk strings), "
            "confidence ('high'|'medium'|'low'))."
        ),
    )

    repo_name = state.get("repo_name")
    repo_clause = (
        f'Repo "{repo_name}" is indexed in GitNexus. Pass repo="{repo_name}" to every GitNexus tool call.'
        if repo_name
        else "No indexed repo — use GitHub tools only."
    )

    agent = create_react_agent(
        model=llm,
        tools=stage_tools + [submit_tool],
        prompt=SystemMessage(content=f"{BASE_PROMPT}\n\n{GATHER_PROMPT}"),
    )

    tool_call_count = 0
    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=f"Gather context for: {state['pr_url']}\n{repo_clause}")]},
        version="v2",
        config={"recursion_limit": 30},
    ):
        if event["event"] == "on_tool_start":
            tool_call_count += 1
            print(f"  [{tool_call_count}/{BUDGET}] {event['name']}", flush=True)
            if event["name"] != "submit_gather" and tool_call_count >= BUDGET:
                break

    base_count = state.get("tool_calls_used", 0)
    if not results:
        return {"current_stage": "unit_tests", "tool_calls_used": base_count + tool_call_count}

    r = results[-1]
    return {
        "current_stage": "unit_tests",
        "tool_calls_used": base_count + tool_call_count,
        "pr_metadata": {"title": r.pr_title, "description": r.pr_description, "author": r.pr_author},
        "pr_files": r.pr_files,
        "pr_diff": r.pr_diff,
        "affected_components": r.affected_components,
    }
