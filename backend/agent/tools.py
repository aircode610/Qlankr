import os
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

_STAGE_TOOLS: dict[str, set[str]] = {
    "gather": GATHER_TOOLS,
    "unit": UNIT_TOOLS,
    "integration": INTEGRATION_TOOLS,
    "e2e": E2E_TOOLS,
}


def _server_config() -> dict:
    utf8_env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "LANG": "en_US.UTF-8",
        "LC_ALL": "en_US.UTF-8",
    }
    return {
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
        "gitnexus": {
            "transport": "stdio",
            "command": "gitnexus",
            "args": ["mcp"],
            "env": utf8_env,
        },
    }


def get_mcp_client() -> MultiServerMCPClient:
    """
    Returns a MultiServerMCPClient instance configured with GitHub and GitNexus servers.

    Usage (async context manager):
        async with get_mcp_client() as client:
            tools = await client.get_tools()
    """
    return MultiServerMCPClient(_server_config())


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
