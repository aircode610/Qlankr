"""
Bug Stage 5: Report Generation

Assembles the final BugReport from all previous stage outputs, computes
overall confidence, and optionally pushes to Jira.
Budget: 5 tool calls.
"""

import json
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from agent.prompts import BUG_BASE_PROMPT, BUG_REPORT_PROMPT
from agent.tools import filter_tools, fix_dangling_tool_calls, get_mcp_client, make_messages_modifier, safe_tools

if TYPE_CHECKING:
    from agent.agent import BugReproductionState

BUDGET = 5


async def report_node(state: "BugReproductionState", llm: Any = None, client: Any = None) -> dict:
    if llm is None:
        from agent.agent import _llm
        llm = _llm

    _own_client = client is None
    if _own_client:
        print("[bug_report] starting MCP client...", flush=True)
        client = get_mcp_client()
    all_tools = await client.get_tools()
    if _own_client:
        print(f"[bug_report] got {len(all_tools)} tools, filtering to bug_report stage...", flush=True)
    stage_tools = safe_tools(filter_tools(all_tools, "bug_report"))

    class _ReportOutput(BaseModel):
        title: str
        severity: str
        affected_components: list[str] = Field(default_factory=list)
        root_cause: str
        reproduction_steps: list[dict] = Field(default_factory=list)
        prerequisites: list[str] = Field(default_factory=list)
        environment_requirements: list[str] = Field(default_factory=list)
        evidence: dict = Field(default_factory=dict)
        recommendations: list[str] = Field(default_factory=list)
        confidence: str = "low"
        jira_url: str | None = None

    results: list[_ReportOutput] = []

    def submit_report(
        title: str,
        severity: str,
        root_cause: str,
        confidence: str,
        affected_components: list = [],
        reproduction_steps: list = [],
        prerequisites: list = [],
        environment_requirements: list = [],
        evidence: dict = {},
        recommendations: list = [],
        jira_url: str | None = None,
    ) -> str:
        results.append(_ReportOutput(
            title=title,
            severity=severity,
            affected_components=affected_components,
            root_cause=root_cause,
            reproduction_steps=reproduction_steps,
            prerequisites=prerequisites,
            environment_requirements=environment_requirements,
            evidence=evidence,
            recommendations=recommendations,
            confidence=confidence,
            jira_url=jira_url,
        ))
        return "Report submitted."

    submit_tool = StructuredTool.from_function(
        func=submit_report,
        name="submit_report",
        description=(
            "Submit the completed bug report. "
            "Pass: title (one sentence describing the bug), "
            "severity (critical|high|medium|low), "
            "affected_components (list of component name strings), "
            "root_cause (2-3 sentence explanation grounded in evidence), "
            "reproduction_steps (list of {step_number, action, expected_result}), "
            "prerequisites (list of setup condition strings), "
            "environment_requirements (list of platform/build requirement strings), "
            "evidence (dict with keys: log_entries, doc_references, related_issues, network_traces), "
            "recommendations (list of 2-4 actionable fix suggestion strings), "
            "confidence (high|medium|low), "
            "jira_url (URL string if a Jira issue was created/updated, otherwise null)."
        ),
    )

    triage = state.get("triage", {})
    mechanics = state.get("mechanics", {})
    reproduction_plan = state.get("reproduction_plan", {})
    research_findings = state.get("research_findings", {})
    jira_ticket = state.get("jira_ticket")

    jira_clause = (
        f"Existing Jira ticket: {jira_ticket} — update it with `jira_update_issue` if available."
        if jira_ticket
        else "No existing Jira ticket — create one with `jira_create_issue` if severity is critical or high and the tool is available."
    )

    human_content = "\n".join([
        "Assemble the final bug report from the stage outputs below.",
        "",
        f"=== ORIGINAL REPORT ===",
        f"Description: {state['description']}",
        f"Environment: {state.get('environment', 'unspecified')}",
        f"Reported severity: {state.get('severity_input', 'unspecified')}",
        "",
        f"=== TRIAGE ===",
        json.dumps(triage, indent=2) if triage else "(empty — triage did not complete)",
        "",
        f"=== MECHANICS ===",
        json.dumps(mechanics, indent=2) if mechanics else "(empty — mechanics did not complete)",
        "",
        f"=== REPRODUCTION PLAN ===",
        json.dumps(reproduction_plan, indent=2) if reproduction_plan else "(empty — reproduction stage did not complete)",
        "",
        f"=== RESEARCH FINDINGS ===",
        json.dumps(research_findings, indent=2) if research_findings else "(empty — no external sources queried)",
        "",
        jira_clause,
    ])

    _saver = MemorySaver()
    _thread = f"{state.get('session_id', 'anon')}-report-{uuid4().hex[:8]}"
    _stage_config = {"configurable": {"thread_id": _thread}, "recursion_limit": 20}

    agent = create_react_agent(
        model=llm,
        tools=stage_tools + [submit_tool],
        prompt=SystemMessage(content=f"{BUG_BASE_PROMPT}\n\n{BUG_REPORT_PROMPT}"),
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
            if event["name"] != "submit_report" and tool_call_count >= BUDGET:
                break
        elif event_type == "on_tool_end" and event.get("name") == "submit_report":
            break

    base_count = state.get("tool_calls_used", 0)
    if not results:
        print(f"  [report] budget hit without submit — forcing synthesis from {tool_call_count} calls", flush=True)
        agent_state = await agent.aget_state(_stage_config)
        accumulated = fix_dangling_tool_calls(agent_state.values.get("messages", []))
        submit_agent = create_react_agent(
            model=llm,
            tools=[submit_tool],
            prompt=SystemMessage(content=f"{BUG_BASE_PROMPT}\n\n{BUG_REPORT_PROMPT}"),
            pre_model_hook=make_messages_modifier(),
        )
        async for _ in submit_agent.astream_events(
            {"messages": accumulated + [HumanMessage(content=(
                f"[BUDGET EXHAUSTED after {tool_call_count} tool calls] "
                "Call submit_report NOW with a complete bug report. "
                "Use confidence='low' and note any missing data."
            ))]},
            version="v2",
            config={"recursion_limit": 10},
        ):
            pass

    if not results:
        return {
            "current_stage": "done",
            "tool_calls_used": base_count + tool_call_count,
            "bug_report": {},
        }

    r = results[-1]
    return {
        "current_stage": "done",
        "tool_calls_used": base_count + tool_call_count,
        "bug_report": r.model_dump(),
    }
