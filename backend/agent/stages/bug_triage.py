"""
Bug Stage 1: Triage

Classifies the bug, extracts keywords, estimates severity, searches similar
Jira issues and relevant code paths.
Budget: 8 tool calls.
"""

from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from agent.prompts import BUG_BASE_PROMPT, BUG_TRIAGE_PROMPT
from agent.tools import filter_tools, get_mcp_client, safe_tools

if TYPE_CHECKING:
    from agent.agent import BugReproductionState

BUDGET = 8


async def triage_node(state: "BugReproductionState", llm: Any = None) -> dict:
    if llm is None:
        from agent.agent import _llm
        llm = _llm

    print("[bug_triage] starting MCP client...", flush=True)
    client = get_mcp_client()
    all_tools = await client.get_tools()
    print(f"[bug_triage] got {len(all_tools)} tools, filtering to bug_triage stage...", flush=True)
    stage_tools = safe_tools(filter_tools(all_tools, "bug_triage"))

    class _TriageOutput(BaseModel):
        bug_category: str
        keywords: list[str] = Field(default_factory=list)
        severity: str
        affected_area: str = ""
        similar_issues: list[dict] = Field(default_factory=list)
        affected_files: list[str] = Field(default_factory=list)
        initial_hypotheses: list[str] = Field(default_factory=list)
        confidence: str = "low"

    results: list[_TriageOutput] = []

    def submit_triage(
        bug_category: str,
        keywords: list = [],
        severity: str = "medium",
        affected_area: str = "",
        similar_issues: list = [],
        affected_files: list = [],
        initial_hypotheses: list = [],
        confidence: str = "low",
    ) -> str:
        results.append(_TriageOutput(
            bug_category=bug_category,
            keywords=keywords,
            severity=severity,
            affected_area=affected_area,
            similar_issues=similar_issues,
            affected_files=affected_files,
            initial_hypotheses=initial_hypotheses,
            confidence=confidence,
        ))
        return "Triage complete."

    submit_tool = StructuredTool.from_function(
        func=submit_triage,
        name="submit_triage",
        description=(
            "Submit triage findings when done. "
            "Pass: bug_category (crash|gameplay|networking|UI|data|performance|other), "
            "keywords (list of 3-8 search terms), "
            "severity (critical|high|medium|low), "
            "affected_area (short subsystem name), "
            "similar_issues (list of {id, title, url, relevance} from Jira, empty if none), "
            "affected_files (file paths found via code search), "
            "initial_hypotheses (list of 1-3 plain-English root cause guesses), "
            "confidence (high|medium|low)."
        ),
    )

    repo_name = state.get("repo_name")
    repo_clause = (
        f'Repo "{repo_name}" is indexed in GitNexus. Pass repo="{repo_name}" to every GitNexus tool call.'
        if repo_name
        else "No indexed repo — skip GitNexus tools."
    )

    jira_ticket = state.get("jira_ticket")
    jira_clause = f"Related Jira ticket: {jira_ticket}." if jira_ticket else ""

    human_content = "\n".join(filter(None, [
        f"Triage this bug report:",
        f"",
        f"Description: {state['description']}",
        f"Environment: {state.get('environment', 'unspecified')}",
        f"Reported severity: {state.get('severity_input', 'unspecified')}",
        jira_clause,
        repo_clause,
    ]))

    agent = create_react_agent(
        model=llm,
        tools=stage_tools + [submit_tool],
        prompt=SystemMessage(content=f"{BUG_BASE_PROMPT}\n\n{BUG_TRIAGE_PROMPT}"),
    )

    tool_call_count = 0
    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=human_content)]},
        version="v2",
        config={"recursion_limit": 30},
    ):
        if event["event"] == "on_tool_start":
            tool_call_count += 1
            print(f"  [{tool_call_count}/{BUDGET}] {event['name']}", flush=True)
            if event["name"] != "submit_triage" and tool_call_count >= BUDGET:
                break

    base_count = state.get("tool_calls_used", 0)
    if not results:
        return {
            "current_stage": "mechanics_analysis",
            "tool_calls_used": base_count + tool_call_count,
        }

    r = results[-1]
    return {
        "current_stage": "mechanics_analysis",
        "tool_calls_used": base_count + tool_call_count,
        "triage": r.model_dump(),
    }
