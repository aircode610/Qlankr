"""
Pre-fetch PR data and GitNexus context before the agent graph starts.

Called by run_agent() to populate the initial graph state so stage sub-agents
do not waste tool-call budget on basic context that can be loaded upfront.
"""

from agent.tools import get_mcp_client
from indexer import _to_records, _unwrap_text  # noqa: PLC0415


_EMPTY_RESULT: dict = {"processes": [], "stats": {}, "changed_symbols": []}


async def prefetch_context(pr_url: str, repo_name: str | None) -> dict:
    """
    Pre-fetch process list and repo stats from GitNexus before the agent runs.

    Args:
        pr_url:    GitHub PR URL (used for future symbol pre-fetch; unused here).
        repo_name: GitNexus repo name (e.g. "minetest"). If None, returns empty dicts.

    Returns:
        {
            "processes":       list[dict]   ? [{name, description}, ...]
            "stats":           dict         ? {files, nodes, edges, communities, processes}
            "changed_symbols": list         ? [] (populated by the gather stage)
        }
        Always returns a valid dict ? never raises.
    """
    if not repo_name:
        return dict(_EMPTY_RESULT)

    try:
        return await _fetch(repo_name)
    except Exception as exc:
        print(f"[prefetch] error for {repo_name}: {exc}", flush=True)
        return dict(_EMPTY_RESULT)


async def _fetch(repo_name: str) -> dict:
    result: dict = {"processes": [], "stats": {}, "changed_symbols": []}

    client = get_mcp_client()
    tools = await client.get_tools()
    tool_map = {t.name: t for t in tools}

    # ── Repo stats via list_repos ─────────────────────────────────────────────
    if "list_repos" in tool_map:
        try:
            raw = await tool_map["list_repos"].ainvoke({})
            for rec in _to_records(raw):
                rname = rec.get("name", "")
                rpath = rec.get("path", "")
                if rname == repo_name or str(rpath).endswith(f"/{repo_name}"):
                    s = rec.get("stats", {})
                    if isinstance(s, dict):
                        result["stats"] = {
                            "files": int(s.get("files", 0)),
                            "nodes": int(s.get("nodes", 0)),
                            "edges": int(s.get("edges", 0)),
                            "communities": int(s.get("communities", 0)),
                            "processes": int(s.get("processes", 0)),
                        }
                    break
            print(f"[prefetch] stats: {result['stats']}", flush=True)
        except Exception as e:
            print(f"[prefetch] list_repos error: {e}", flush=True)

    # ── Process list via resource URI, falling back to Cypher ─────────────────
    result["processes"] = await _fetch_processes(client, tool_map, repo_name)
    print(f"[prefetch] processes fetched: {len(result['processes'])}", flush=True)

    return result


async def _fetch_processes(client, tool_map: dict, repo_name: str) -> list[dict]:
    """Try resource URI first; fall back to Cypher query."""
    # Option A: MCP resource read
    try:
        raw = await client.read_resource(f"gitnexus://repo/{repo_name}/processes")
        records = _to_records(_unwrap_text(raw))
        if records:
            return records
    except Exception:
        pass

    # Option B: Cypher fallback
    if "cypher" not in tool_map:
        return []
    try:
        raw = await tool_map["cypher"].ainvoke({
            "query": (
                "MATCH (p:Process) "
                "RETURN p.name AS name, p.description AS description "
                "LIMIT 100"
            ),
            "repo": repo_name,
        })
        return _to_records(raw)
    except Exception as e:
        print(f"[prefetch] cypher process fallback error: {e}", flush=True)
        return []
