"""
Bug Stage 4: Research

Queries all configured external sources (Jira, Notion, Confluence, Grafana,
Kibana, Sniffer, code graph) for evidence related to the bug.
Each source is independent — one failure does not stop the rest.
Budget: 20 tool calls.
"""

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from agent.prompts import BUG_BASE_PROMPT, BUG_RESEARCH_PROMPT
from agent.tools import filter_tools, get_mcp_client, safe_tools

if TYPE_CHECKING:
    from agent.agent import BugReproductionState

BUDGET = 20


async def research_node(state: "BugReproductionState", llm: Any = None, client: Any = None) -> dict:
    if llm is None:
        from agent.agent import _llm
        llm = _llm

    _own_client = client is None
    if _own_client:
        print("[bug_research] starting MCP client...", flush=True)
        client = get_mcp_client()
    all_tools = await client.get_tools()
    if _own_client:
        print(f"[bug_research] got {len(all_tools)} tools, filtering to bug_research stage...", flush=True)
    stage_tools = safe_tools(filter_tools(all_tools, "bug_research"))

    available_tool_names = {t.name for t in stage_tools}

    class _ResearchOutput(BaseModel):
        log_entries: list[dict] = Field(default_factory=list)
        doc_references: list[dict] = Field(default_factory=list)
        related_issues: list[dict] = Field(default_factory=list)
        network_traces: list[dict] = Field(default_factory=list)
        code_graph_hits: list[dict] = Field(default_factory=list)
        sources_queried: list[str] = Field(default_factory=list)
        sources_with_results: list[str] = Field(default_factory=list)

    results: list[_ResearchOutput] = []

    def submit_research(
        log_entries: list = [],
        doc_references: list = [],
        related_issues: list = [],
        network_traces: list = [],
        code_graph_hits: list = [],
        sources_queried: list = [],
        sources_with_results: list = [],
    ) -> str:
        results.append(_ResearchOutput(
            log_entries=log_entries,
            doc_references=doc_references,
            related_issues=related_issues,
            network_traces=network_traces,
            code_graph_hits=code_graph_hits,
            sources_queried=sources_queried,
            sources_with_results=sources_with_results,
        ))
        return "Research complete."

    submit_tool = StructuredTool.from_function(
        func=submit_research,
        name="submit_research",
        description=(
            "Submit all research findings when done. "
            "Pass: log_entries (list of {timestamp, level, message, source}), "
            "doc_references (list of {title, url, excerpt}), "
            "related_issues (list of {id, title, url, status, relevance}), "
            "network_traces (list of {url, method, status_code, error}), "
            "code_graph_hits (list of {process, symbol, note}), "
            "sources_queried (list of source name strings you attempted), "
            "sources_with_results (list of source names that returned useful data). "
            "Use empty lists for sources with no results — never omit a field."
        ),
    )

    triage = state.get("triage", {})
    mechanics = state.get("mechanics", {})

    keywords = triage.get("keywords", [])
    affected_area = triage.get("affected_area", "unknown")

    top_hypothesis = ""
    hypotheses = mechanics.get("root_cause_hypotheses", [])
    if hypotheses:
        top_hypothesis = hypotheses[0].get("hypothesis", "")

    affected_components = mechanics.get("affected_components", [])

    repo_name = state.get("repo_name")
    # If mechanics already queried the code graph, steer research toward external sources only
    if mechanics.get("code_paths"):
        code_graph_clause = (
            "Code graph was already queried extensively during mechanics analysis. "
            "Do NOT use cypher or query tools — focus exclusively on external sources "
            "(Jira, logs, documentation, network traces)."
        )
    elif repo_name:
        code_graph_clause = (
            f'Repo "{repo_name}" is indexed in GitNexus. '
            "Use `query` and `cypher` to find processes and symbols in the affected area."
        )
    else:
        code_graph_clause = "No indexed repo — skip GitNexus tools."

    attachments = state.get("attachments", [])
    attachment_clause = (
        f"Attachments available for sniffer: {', '.join(attachments)}"
        if attachments
        else "No attachments provided — skip sniffer tools."
    )

    research_context = state.get("research_context")
    context_clause = (
        f"\nAdditional context from reviewer: {research_context}"
        if research_context
        else ""
    )

    available_sources = _available_sources(available_tool_names)
    # Exclude code graph from listed sources if mechanics already covered it
    if mechanics.get("code_paths") and "code graph" in available_sources:
        available_sources = [s for s in available_sources if s != "code graph"]
    sources_clause = (
        f"Available sources for this run: {', '.join(available_sources)}"
        if available_sources
        else "No external sources are configured — call submit_research immediately with empty lists."
    )

    human_content = "\n".join(filter(None, [
        "Research evidence for this bug:",
        "",
        f"Description: {state['description']}",
        f"Affected area: {affected_area}",
        f"Keywords: {', '.join(keywords) if keywords else 'none'}",
        f"Affected components: {', '.join(affected_components) if affected_components else 'none'}",
        f"Top hypothesis: {top_hypothesis}" if top_hypothesis else "",
        code_graph_clause,
        attachment_clause,
        sources_clause,
        context_clause,
    ]))

    _saver = MemorySaver()
    _thread = f"{state.get('session_id', 'anon')}-research-{uuid4().hex[:8]}"
    _stage_config = {"configurable": {"thread_id": _thread}, "recursion_limit": 50}

    agent = create_react_agent(
        model=llm,
        tools=stage_tools + [submit_tool],
        prompt=SystemMessage(content=f"{BUG_BASE_PROMPT}\n\n{BUG_RESEARCH_PROMPT}"),
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
            tool_name = event["name"]
            print(f"  [{tool_call_count}/{BUDGET}] {tool_name}", flush=True)
            if tool_name != "submit_research" and tool_call_count >= BUDGET:
                break

    base_count = state.get("tool_calls_used", 0)
    if not results:
        print(f"  [research] budget hit without submit — forcing synthesis from {tool_call_count} calls", flush=True)
        agent_state = await agent.aget_state(_stage_config)
        accumulated = agent_state.values.get("messages", [])
        submit_agent = create_react_agent(
            model=llm,
            tools=[submit_tool],
            prompt=SystemMessage(content=f"{BUG_BASE_PROMPT}\n\n{BUG_RESEARCH_PROMPT}"),
        )
        async for _ in submit_agent.astream_events(
            {"messages": accumulated + [HumanMessage(content=(
                f"[BUDGET EXHAUSTED after {tool_call_count} tool calls] "
                "Call submit_research NOW with all findings gathered so far. "
                "Use empty lists for sources you didn't reach."
            ))]},
            version="v2",
            config={"recursion_limit": 5},
        ):
            pass

    if not results:
        return {
            "current_stage": "report_generation",
            "tool_calls_used": base_count + tool_call_count,
            "research_findings": {},
        }

    r = results[-1]
    return {
        "current_stage": "report_generation",
        "tool_calls_used": base_count + tool_call_count,
        "research_findings": r.model_dump(),
    }


def _available_sources(tool_names: set[str]) -> list[str]:
    """Returns human-readable source names based on which tools are present."""
    sources = []
    if tool_names & {"jira_search", "jira_get_issue"}:
        sources.append("Jira")
    if tool_names & {"notion_search", "notion_get_page"}:
        sources.append("Notion")
    if tool_names & {"confluence_search", "confluence_get_page"}:
        sources.append("Confluence")
    if "grafana_query_logs" in tool_names:
        sources.append("Grafana")
    if "kibana_search" in tool_names:
        sources.append("Kibana")
    if tool_names & {"sniffer_parse_har", "sniffer_find_errors"}:
        sources.append("Sniffer")
    if tool_names & {"cypher", "query"}:
        sources.append("code graph")
    return sources
