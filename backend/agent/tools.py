import os
import shutil
from typing import Any

from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient


# ── Stage tool subsets ────────────────────────────────────────────────────────
# Each set defines the tool names a stage's sub-agent is allowed to call.

GATHER_TOOLS: set[str] = {
    "get_pull_request",
    "get_pull_request_files",
    "get_pull_request_comments",
    "get_file_contents",
    "list_directory",
    "search_code",
    "get_commits",
    "list_repos",
    "impact",
    "cypher",
    "detect_changes",
}

UNIT_TOOLS: set[str] = {
    "context",
    "cypher",
    "get_file_contents",
}

INTEGRATION_TOOLS: set[str] = {
    "impact",
    "context",
    "query",
    "cypher",
}

E2E_TOOLS: set[str] = {
    "impact",
    "query",
    "cypher",
    "list_processes",
    "get_process",
}

# ── Bug reproduction stage tool subsets ──────────────────────────────────────

BUG_TRIAGE_TOOLS: set[str] = {
    "jira_search",
    "jira_get_issue",
    "jira_get_comments",
    "search_code",
    "cypher",
    "impact",
    "list_repos",
}

BUG_MECHANICS_TOOLS: set[str] = {
    "get_file_contents",
    "search_code",
    "cypher",
    "query",
    "context",
    "impact",
    "list_directory",
}

BUG_REPRODUCTION_TOOLS: set[str] = {
    "get_file_contents",
    "search_code",
    "cypher",
    "context",
    "list_directory",
    "list_processes",
    "get_process",
}

BUG_RESEARCH_TOOLS: set[str] = {
    "cypher",
    "query",
    "jira_search",
    "jira_get_issue",
    "jira_get_comments",
    "notion_search",
    "notion_get_page",
    "confluence_search",
    "confluence_get_page",
    "grafana_query_logs",
    "kibana_search",
    "sniffer_parse_har",
    "sniffer_find_errors",
}

BUG_REPORT_TOOLS: set[str] = {
    "jira_create_issue",
    "jira_update_issue",
}

_STAGE_TOOLS: dict[str, set[str]] = {
    "gather": GATHER_TOOLS,
    "unit": UNIT_TOOLS,
    "integration": INTEGRATION_TOOLS,
    "e2e": E2E_TOOLS,
    "bug_triage": BUG_TRIAGE_TOOLS,
    "bug_mechanics": BUG_MECHANICS_TOOLS,
    "bug_reproduction": BUG_REPRODUCTION_TOOLS,
    "bug_research": BUG_RESEARCH_TOOLS,
    "bug_report": BUG_REPORT_TOOLS,
}


def _server_config() -> dict:
    import shutil
    utf8_env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "LANG": "en_US.UTF-8",
        "LC_ALL": "en_US.UTF-8",
    }
    config = {
        "github": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {
                **utf8_env,
                # The GitHub MCP server expects GITHUB_PERSONAL_ACCESS_TOKEN
                "GITHUB_PERSONAL_ACCESS_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
            },
        },
    }
    # Only include GitNexus if the binary is available (not present in local dev)
    if shutil.which("gitnexus"):
        config["gitnexus"] = {
            "transport": "stdio",
            "command": "gitnexus",
            "args": ["mcp"],
            "env": utf8_env,
        }
    return config


def get_mcp_client() -> MultiServerMCPClient:
    """
    Returns a MultiServerMCPClient instance configured with GitHub and GitNexus servers.

    Usage (async context manager):
        async with get_mcp_client() as client:
            tools = await client.get_tools()
    """
    return MultiServerMCPClient(_server_config())


def safe_tools(tools: list) -> list:
    """Wrap each tool so MCP errors become ToolMessages instead of exceptions.

    MCP tools from langchain_mcp_adapters use response_format='content_and_artifact',
    which requires the coroutine to return a (content, artifact) tuple.  Returning a
    plain string causes a ValueError in LangChain's tool validation, so we check the
    tool's response_format and return the appropriate type on error.
    """
    wrapped = []
    for tool in tools:
        original_coro = tool.coroutine
        if original_coro is None:
            wrapped.append(tool)
            continue

        is_artifact = getattr(tool, "response_format", None) == "content_and_artifact"

        async def _safe(*args, _coro=original_coro, _artifact=is_artifact, **kwargs):
            try:
                return await _coro(*args, **kwargs)
            except Exception as e:
                msg = f"Tool error: {e}"
                return (msg, None) if _artifact else msg

        wrapped.append(tool.copy(update={"coroutine": _safe, "func": None}))
    return wrapped


_TOOL_OUTPUT_MAX_CHARS = 12_000  # ~3k tokens per tool result

# Keep the old name as an alias so existing call sites don't break
_FILE_TOOL_MAX_CHARS = _TOOL_OUTPUT_MAX_CHARS


def make_messages_modifier(max_chars: int = _TOOL_OUTPUT_MAX_CHARS):
    """
    Return a pre_model_hook for create_react_agent that caps every ToolMessage
    content at max_chars before it reaches the LLM.

    This runs inside the agent executor right before each LLM call, so it prevents
    large tool outputs from bloating the context window across the entire stage.
    Handles both plain-string and list-of-blocks ToolMessage formats.

    Usage: create_react_agent(..., pre_model_hook=make_messages_modifier())
    """
    from langchain_core.messages import ToolMessage

    def _hook(state: dict) -> dict:
        messages = state.get("messages", [])
        updated = []
        any_changed = False
        for msg in messages:
            if not isinstance(msg, ToolMessage):
                updated.append(msg)
                continue
            content = msg.content
            if isinstance(content, str) and len(content) > max_chars:
                content = content[:max_chars] + f"\n...[output truncated — {len(content) - max_chars} chars omitted]"
                msg = msg.copy(update={"content": content})
                any_changed = True
            elif isinstance(content, list):
                new_blocks = []
                changed = False
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        if len(text) > max_chars:
                            block = {**block, "text": text[:max_chars] + f"\n...[output truncated — {len(text) - max_chars} chars omitted]"}
                            changed = True
                    new_blocks.append(block)
                if changed:
                    msg = msg.copy(update={"content": new_blocks})
                    any_changed = True
            updated.append(msg)
        return {"messages": updated} if any_changed else {}

    return _hook


def fix_dangling_tool_calls(messages: list) -> list:
    """
    After a budget break the last AIMessage may contain tool_calls that never
    executed (common when the agent issues parallel tool calls and we break
    mid-stream).  Without matching ToolMessages the chat history is invalid and
    most LLM providers reject it.

    Appends a synthetic ToolMessage for every unmatched tool_call_id so the
    history is well-formed before passing it to the forced-submit agent.
    """
    from langchain_core.messages import AIMessage, ToolMessage

    tool_message_ids = {msg.tool_call_id for msg in messages if isinstance(msg, ToolMessage)}
    fixed = []
    for msg in messages:
        fixed.append(msg)
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc["id"] not in tool_message_ids:
                    fixed.append(ToolMessage(
                        content="[Interrupted: budget limit reached before this tool call completed]",
                        tool_call_id=tc["id"],
                    ))
    return fixed


def truncate_large_tools(tools: list, max_chars: int = _TOOL_OUTPUT_MAX_CHARS) -> list:
    """Kept for backwards compatibility — prefer make_messages_modifier instead."""
    return tools


def filter_tools(all_tools: list, stage: str) -> list:
    """
    Return only the tools allowed for the given stage.

    Args:
        all_tools: Full list of tools from client.get_tools().
        stage: One of "gather", "unit", "integration", "e2e".

    Returns:
        Filtered list containing only tools whose names are in the stage's allowed set.

    Raises:
        KeyError: If stage is not a recognised stage name.
    """
    allowed = _STAGE_TOOLS[stage]
    return [t for t in all_tools if t.name in allowed]


def make_process_tools(repo_name: str) -> list[StructuredTool]:
    """
    Create two StructuredTools that expose GitNexus process resources.

    Each tool opens its own MCP client context when invoked, so they remain
    usable after the call site's context has exited.

    Tries MCP resource reads first; falls back to Cypher queries if the
    adapter raises on resource reads.

    Args:
        repo_name: The GitNexus repo name (e.g. "minetest").

    Returns:
        [list_processes_tool, get_process_tool]
    """

    async def list_processes() -> str:
        """List all execution flows (processes) in the indexed repo."""
        async with get_mcp_client() as client:
            try:
                result = await client.read_resource(
                    f"gitnexus://repo/{repo_name}/processes"
                )
                return str(result)
            except Exception:
                return await _cypher_fallback_list_processes(client, repo_name)

    async def get_process(process_name: str) -> str:
        """Get the full execution flow for a specific process by name."""
        async with get_mcp_client() as client:
            try:
                result = await client.read_resource(
                    f"gitnexus://repo/{repo_name}/process/{process_name}"
                )
                return str(result)
            except Exception:
                return await _cypher_fallback_get_process(client, repo_name, process_name)

    return [
        StructuredTool.from_function(
            coroutine=list_processes,
            name="list_processes",
            description=(
                "List all execution flows (processes) in the indexed repo. "
                "Returns process names and descriptions."
            ),
        ),
        StructuredTool.from_function(
            coroutine=get_process,
            name="get_process",
            description=(
                "Get the full execution flow for a specific process. "
                "Pass the process name as returned by list_processes."
            ),
        ),
    ]


async def _cypher_fallback_list_processes(client: Any, repo_name: str) -> str:
    """Fallback: fetch process list via Cypher when resource reads are unavailable."""
    try:
        tools = await client.get_tools()
        tool_map = {t.name: t for t in tools}
        if "cypher" not in tool_map:
            return "[]"
        raw = await tool_map["cypher"].ainvoke({
            "query": "MATCH (p:Process) RETURN p.name AS name, p.description AS description LIMIT 100",
            "repo": repo_name,
        })
        return str(raw)
    except Exception as e:
        return f"Error fetching processes: {e}"


async def _cypher_fallback_get_process(
    client: Any, repo_name: str, process_name: str
) -> str:
    """Fallback: fetch a single process's steps via Cypher."""
    try:
        tools = await client.get_tools()
        tool_map = {t.name: t for t in tools}
        if "cypher" not in tool_map:
            return "[]"
        raw = await tool_map["cypher"].ainvoke({
            "query": (
                f"MATCH (p:Process {{name: '{process_name}'}})<-[r:CodeRelation]-(s) "
                "WHERE r.type = 'STEP_IN_PROCESS' "
                "RETURN s.name AS name, s.filePath AS filePath, r.order AS order "
                "ORDER BY r.order"
            ),
            "repo": repo_name,
        })
        return str(raw)
    except Exception as e:
        return f"Error fetching process '{process_name}': {e}"
