"""
Stage 1: Context Gathering

Collects PR metadata, changed files, diff, and initial affected components.
Budget: 10 tool calls. Does not generate test specs — collect only.
"""

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from agent.prompts import BASE_PROMPT, GATHER_PROMPT
from agent.tools import filter_tools, fix_dangling_tool_calls, get_mcp_client, safe_tools

if TYPE_CHECKING:
    from agent.agent import AnalysisState

BUDGET = 15


def _extract_file_paths(messages: list) -> list[str]:
    """Extract file paths from ToolMessage content (get_pull_request_files responses)."""
    import json
    import re
    paths: list[str] = []
    for msg in messages:
        if not hasattr(msg, "content"):
            continue
        content = msg.content
        if isinstance(content, list):
            content = " ".join(
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in content
            )
        if not isinstance(content, str):
            continue
        # Match file paths like "filename": "path/to/file.py" from JSON-like tool output
        for match in re.findall(r'"filename"\s*:\s*"([^"]+)"', content):
            if match not in paths:
                paths.append(match)
        # Also match "path/to/file.ext" patterns that look like source files
        if not paths:
            for match in re.findall(r'(?:^|\s)([\w./]+\.\w{1,5})(?:\s|$|,)', content):
                if "/" in match and match not in paths:
                    paths.append(match)
    return paths


def _extract_pr_metadata(messages: list) -> dict:
    """Extract PR title and description from ToolMessage content (get_pull_request response)."""
    import json
    import re
    meta: dict = {}
    for msg in messages:
        if not hasattr(msg, "content"):
            continue
        content = msg.content
        if isinstance(content, list):
            content = " ".join(
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in content
            )
        if not isinstance(content, str):
            continue
        # Try to extract title from JSON-like patterns
        title_match = re.search(r'"title"\s*:\s*"([^"]+)"', content)
        if title_match and "title" not in meta:
            meta["title"] = title_match.group(1)
        desc_match = re.search(r'"body"\s*:\s*"((?:[^"\\]|\\.)*)"', content)
        if desc_match and "description" not in meta:
            meta["description"] = desc_match.group(1)[:500]
    return meta


async def run_gather(state: "AnalysisState", llm: Any) -> dict:
    print("[gather] starting MCP client...", flush=True)
    client = get_mcp_client()
    all_tools = await client.get_tools()
    print(f"[gather] got {len(all_tools)} tools, filtering to gather stage...", flush=True)
    stage_tools = safe_tools(filter_tools(all_tools, "gather"))

    class _GatherOutput(BaseModel):
        pr_title: str
        pr_description: str = ""
        pr_author: str = ""
        pr_files: list[str] = Field(default_factory=list)
        pr_diff: str = ""
        pr_summary: str = ""
        pr_summary_detail: str | None = None
        affected_components: list[dict] = Field(default_factory=list)

    results: list[_GatherOutput] = []

    def submit_gather(
        pr_title: str,
        pr_description: str = "",
        pr_author: str = "",
        pr_files: list = [],
        pr_diff: str = "",
        affected_components: list = [],
        pr_summary: str = "",
        pr_summary_detail: str | None = None,
    ) -> str:
        if not affected_components:
            return (
                "REJECTED: affected_components is empty. "
                "You MUST group the changed files into at least one logical component "
                "before calling submit_gather. Each component needs: component (name), "
                "files_changed, impact_summary, risks, confidence. "
                "Analyse the PR diff and file list, then call submit_gather again "
                "with a non-empty affected_components list."
            )
        results.append(_GatherOutput(
            pr_title=pr_title,
            pr_description=pr_description,
            pr_author=pr_author,
            pr_files=pr_files,
            pr_diff=pr_diff,
            pr_summary=pr_summary,
            pr_summary_detail=pr_summary_detail,
            affected_components=affected_components,
        ))
        return "Context gathered."

    submit_tool = StructuredTool.from_function(
        func=submit_gather,
        name="submit_gather",
        description=(
            "Submit the gathered PR context when done collecting. "
            "IMPORTANT: affected_components MUST be non-empty — the call will be rejected otherwise. "
            "Group ALL changed files into logical components BEFORE calling this tool. "
            "Pass: pr_title, pr_description, pr_author, "
            "pr_files (list of changed file paths), pr_diff (full diff text), "
            "pr_summary (ONE sentence overview of the PR, max 25 words), "
            "pr_summary_detail (2-5 sentences with full context — motivation, scope, approach), "
            "affected_components (REQUIRED non-empty list of objects, each with: "
            "component (str), files_changed ([str]), "
            "impact_summary (str — ONE sentence on what breaks, max 20 words), "
            "impact_detail (str — 2-4 sentences expanding on the impact, optional), "
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

    _saver = MemorySaver()
    _thread = f"{state.get('session_id', state.get('pr_url', 'anon'))}-gather-{uuid4().hex[:8]}"
    _stage_config = {"configurable": {"thread_id": _thread}, "recursion_limit": 30}

    agent = create_react_agent(
        model=llm,
        tools=stage_tools + [submit_tool],
        prompt=SystemMessage(content=f"{BASE_PROMPT}\n\n{GATHER_PROMPT}"),
        checkpointer=_saver,
    )

    tool_call_count = 0
    submit_rejections = 0
    MAX_SUBMIT_REJECTIONS = 3  # Break after 3 rejected submit_gather calls
    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=f"Gather context for: {state['pr_url']}\n{repo_clause}")]},
        version="v2",
        config=_stage_config,
    ):
        event_type = event["event"]
        if event_type == "on_tool_start":
            tool_call_count += 1
            print(f"  [{tool_call_count}/{BUDGET}] {event['name']}", flush=True)
            if event["name"] != "submit_gather" and tool_call_count >= BUDGET:
                break
        elif event_type == "on_tool_end" and event.get("name") == "submit_gather":
            # Only break if submit_gather actually accepted the submission
            if results:
                break
            submit_rejections += 1
            print(f"  [gather] submit_gather rejected ({submit_rejections}/{MAX_SUBMIT_REJECTIONS})", flush=True)
            if submit_rejections >= MAX_SUBMIT_REJECTIONS:
                break

    base_count = state.get("tool_calls_used", 0)
    accumulated = None

    if not results:
        # Fallback 1: force LLM to synthesize from accumulated context
        print(f"  [gather] budget hit without submit — forcing synthesis from {tool_call_count} calls", flush=True)
        agent_state = await agent.aget_state(_stage_config)
        accumulated = fix_dangling_tool_calls(agent_state.values.get("messages", []))

        # Non-rejecting submit tool — always accepts, even with empty components
        def force_submit(
            pr_title: str = "",
            pr_description: str = "",
            pr_author: str = "",
            pr_files: list = [],
            pr_diff: str = "",
            affected_components: list = [],
            pr_summary: str = "",
            pr_summary_detail: str | None = None,
        ) -> str:
            results.append(_GatherOutput(
                pr_title=pr_title,
                pr_description=pr_description,
                pr_author=pr_author,
                pr_files=pr_files,
                pr_diff=pr_diff,
                pr_summary=pr_summary,
                pr_summary_detail=pr_summary_detail,
                affected_components=affected_components,
            ))
            return "Context gathered."

        force_tool = StructuredTool.from_function(
            func=force_submit,
            name="submit_gather",
            description=submit_tool.description,
        )

        submit_agent = create_react_agent(
            model=llm,
            tools=[force_tool],
            prompt=SystemMessage(content=f"{BASE_PROMPT}\n\n{GATHER_PROMPT}"),
        )
        async for _ in submit_agent.astream_events(
            {"messages": accumulated + [HumanMessage(content=(
                f"[BUDGET EXHAUSTED after {tool_call_count} tool calls] "
                "Call submit_gather NOW with all context collected so far. "
                "You MUST include at least one component in affected_components. "
                "Group ALL changed files into logical components. "
                "Use confidence='low' for any components not fully analysed."
            ))]},
            version="v2",
            config={"recursion_limit": 5},
        ):
            pass

    # Fallback 2: programmatic extraction from message history
    if not results:
        print(f"  [gather] forced synthesis also failed — building from file list", flush=True)
        if accumulated is None:
            agent_state = await agent.aget_state(_stage_config)
            accumulated = fix_dangling_tool_calls(agent_state.values.get("messages", []))
        pr_files_found = _extract_file_paths(accumulated)
        pr_meta = _extract_pr_metadata(accumulated)

        if pr_files_found:
            dir_groups: dict[str, list[str]] = {}
            for f in pr_files_found:
                top_dir = f.split("/")[0] if "/" in f else "root"
                dir_groups.setdefault(top_dir, []).append(f)
            fallback_components = [
                {
                    "component": dir_name,
                    "files_changed": files,
                    "impact_summary": f"Changes in {dir_name} — {len(files)} file(s) modified.",
                    "risks": ["Incomplete analysis — manual review recommended"],
                    "confidence": "low",
                }
                for dir_name, files in dir_groups.items()
            ]
            print(f"  [gather] built {len(fallback_components)} components from {len(pr_files_found)} files", flush=True)
            return {
                "current_stage": "unit_tests",
                "tool_calls_used": base_count + tool_call_count,
                "pr_metadata": pr_meta,
                "pr_files": pr_files_found,
                "affected_components": fallback_components,
            }
        # Last resort: single unknown component so pipeline never breaks
        print("  [gather] no file data found — returning last-resort component", flush=True)
        return {
            "current_stage": "unit_tests",
            "tool_calls_used": base_count + tool_call_count,
            "affected_components": [{
                "component": "Unknown",
                "files_changed": [],
                "impact_summary": "Could not determine affected components — manual review needed.",
                "risks": ["Full analysis required"],
                "confidence": "low",
            }],
        }

    r = results[-1]
    # Even if the LLM submitted but with empty components, provide a fallback
    components = r.affected_components if r.affected_components else [{
        "component": "Unknown",
        "files_changed": r.pr_files,
        "impact_summary": "Components could not be determined — manual review needed.",
        "risks": ["Full analysis required"],
        "confidence": "low",
    }]
    return {
        "current_stage": "unit_tests",
        "tool_calls_used": base_count + tool_call_count,
        "pr_metadata": {
            "title": r.pr_title,
            "description": r.pr_description,
            "author": r.pr_author,
            "pr_summary": r.pr_summary,
            "pr_summary_detail": r.pr_summary_detail,
        },
        "pr_files": r.pr_files,
        "pr_diff": r.pr_diff,
        "affected_components": components,
    }
