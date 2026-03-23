import asyncio
import json
import os
import re
import sys
import tempfile
from typing import AsyncIterator
from urllib.parse import urlparse

from models import (
    ErrorEvent,
    GraphCluster,
    GraphData,
    GraphEdge,
    GraphNode,
    IndexDoneEvent,
    IndexStepEvent,
)

# In-memory registry: { "owner/repo": { "path": str, "repo_name": str, "graph": GraphData | None } }
_registry: dict[str, dict] = {}

_STAGE_KEYWORDS: list[tuple[str, str]] = [
    ("clone", "clone"),
    ("cloning", "clone"),
    ("structur", "structure"),
    ("pars", "parsing"),
    ("resolv", "resolution"),
    ("cluster", "clustering"),
    ("community", "clustering"),
    ("process", "processes"),
    ("search", "search"),
    ("analyz", "analyze"),
    ("index", "analyze"),
]


def _parse_owner_repo(repo_url: str) -> tuple[str, str]:
    path = urlparse(repo_url).path.strip("/")
    path = re.sub(r"\.git$", "", path)
    parts = path.split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse owner/repo from URL: {repo_url}")
    return parts[0], parts[1]


def _detect_stage(line: str) -> str:
    lower = line.lower()
    for keyword, stage in _STAGE_KEYWORDS:
        if keyword in lower:
            return stage
    return "analyze"


def get_repo_name(owner_repo: str) -> str | None:
    """Return the GitNexus-registered repo name for an indexed repo."""
    entry = _registry.get(owner_repo)
    return entry.get("repo_name") if entry else None


def get_clone_path(owner_repo: str) -> str | None:
    """Return the absolute local path where the repo was cloned."""
    entry = _registry.get(owner_repo)
    return entry.get("path") if entry else None


async def index_repo(
    repo_url: str,
) -> AsyncIterator[IndexStepEvent | IndexDoneEvent | ErrorEvent]:
    try:
        owner, repo = _parse_owner_repo(repo_url)
    except ValueError as e:
        yield ErrorEvent(message=str(e))
        return

    repo_key = f"{owner}/{repo}"
    tmp_dir = tempfile.mkdtemp(prefix="qlankr_")
    clone_path = os.path.join(tmp_dir, repo)

    # ── Clone ──────────────────────────────────────────────────────────────────
    yield IndexStepEvent(stage="clone", summary=f"Cloning {repo_key}…")
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth=1", repo_url, clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            yield ErrorEvent(message=f"git clone failed: {stderr.decode().strip()}")
            return
    except Exception as e:
        yield ErrorEvent(message=f"git clone error: {e}")
        return

    yield IndexStepEvent(stage="clone", summary=f"Cloned {repo_key}")

    # ── Analyze ────────────────────────────────────────────────────────────────
    yield IndexStepEvent(stage="analyze", summary="Running gitnexus analyze…")
    try:
        proc = await asyncio.create_subprocess_exec(
            "gitnexus", "analyze", clone_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=clone_path,
        )
        assert proc.stdout is not None
        while True:
            line_bytes = await proc.stdout.readline()
            if not line_bytes:
                break
            line = line_bytes.decode().strip()
            if line:
                yield IndexStepEvent(stage=_detect_stage(line), summary=line)

        await proc.wait()
        if proc.returncode != 0:
            yield ErrorEvent(message=f"gitnexus analyze exited with code {proc.returncode}")
            return
    except FileNotFoundError:
        yield ErrorEvent(message="gitnexus not found — is it installed?")
        return
    except Exception as e:
        yield ErrorEvent(message=f"gitnexus analyze error: {e}")
        return

    # Register before fetching graph (so get_repo_name works in agent during analysis)
    _registry[repo_key] = {
        "path": clone_path,
        "repo_name": repo,
        "graph": None,
    }

    # ── Fetch stats + graph via MCP ────────────────────────────────────────────
    yield IndexStepEvent(stage="analyze", summary="Fetching graph data from GitNexus…")
    stats, graph = await _fetch_stats_and_graph(repo)
    _registry[repo_key]["graph"] = graph

    yield IndexDoneEvent(
        repo=repo_key,
        files=stats.get("files", 0),
        clusters=stats.get("communities", 0),
        symbols=stats.get("nodes", 0),
    )


async def get_graph_data(owner: str, repo: str) -> GraphData:
    """Return cached graph data for an indexed repo."""
    repo_key = f"{owner}/{repo}"
    entry = _registry.get(repo_key)
    if entry is None:
        return GraphData(nodes=[], edges=[], clusters=[])
    if entry.get("graph") is None:
        repo_name = entry.get("repo_name", repo)
        _, graph = await _fetch_stats_and_graph(repo_name)
        entry["graph"] = graph
    return entry["graph"]  # type: ignore[return-value]


async def _fetch_stats_and_graph(repo_name: str) -> tuple[dict, GraphData]:
    """
    Use GitNexus MCP tools to fetch stats and graph data.
    Uses the client as an async context manager to ensure server connections are live.
    """
    from agent.tools import get_mcp_client  # noqa: PLC0415

    stats: dict = {}
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    clusters: list[GraphCluster] = []

    try:
        client = get_mcp_client()
        tools_list = await client.get_tools()
        tool_map = {t.name: t for t in tools_list}
        print(f"[indexer] MCP tools available: {sorted(tool_map)}", flush=True)

        # ── Stats via list_repos ───────────────────────────────────────────
        if "list_repos" in tool_map:
            try:
                raw = await tool_map["list_repos"].ainvoke({})
                for r in _to_records(raw):
                    rname = r.get("name", "")
                    rpath = r.get("path", "")
                    if rname == repo_name or rpath.endswith(f"/{repo_name}"):
                        s = r.get("stats", {})
                        if isinstance(s, dict):
                            stats = {
                                "files": int(s.get("files", 0)),
                                "nodes": int(s.get("nodes", 0)),
                                "edges": int(s.get("edges", 0)),
                                "communities": int(s.get("communities", 0)),
                                "processes": int(s.get("processes", 0)),
                            }
                        break
                print(f"[indexer] stats for {repo_name}: {stats}", flush=True)
            except Exception as e:
                print(f"[indexer] list_repos error: {e}", flush=True)

        # ── Graph data via cypher ─────────────────────────────────────────
        if "cypher" in tool_map:
            cypher = tool_map["cypher"]
            nodes, clusters = await _cypher_nodes(cypher, repo_name)
            edges = await _cypher_edges(cypher, repo_name)
            print(
                f"[indexer] graph: {len(nodes)} nodes, {len(edges)} edges, {len(clusters)} clusters",
                flush=True,
            )
        else:
            print("[indexer] cypher tool not found — graph will be empty", flush=True)

    except Exception as e:
        print(f"[indexer] _fetch_stats_and_graph error: {e}", flush=True)

    return stats, GraphData(nodes=nodes, edges=edges, clusters=clusters)


async def _cypher_nodes(
    cypher_tool, repo_name: str
) -> tuple[list[GraphNode], list[GraphCluster]]:
    """Fetch File nodes grouped by Community membership."""
    nodes: list[GraphNode] = []
    file_cluster: dict[str, str] = {}    # file_id → community_id
    cluster_labels: dict[str, str] = {}  # community_id → label

    # Step 1: file → community membership (2-hop: File → Symbol → Community)
    # MEMBER_OF is on symbol nodes (Class/Function), not on File nodes directly.
    try:
        raw = await cypher_tool.ainvoke({
            "query": (
                "MATCH (f:File)-[:CodeRelation]->(s)-[r:CodeRelation]->(c:Community) "
                "WHERE r.type = 'MEMBER_OF' "
                "RETURN f.id AS file_id, c.id AS community_id, c.heuristicLabel AS community_label "
                "LIMIT 5000"
            ),
            "repo": repo_name,
        })
        # A file can have symbols in multiple communities — tally votes, pick dominant one
        vote: dict[str, dict[str, int]] = {}  # file_id → {community_id → count}
        for rec in _to_records(raw):
            fid = str(rec.get("file_id", "")).strip()
            cid = str(rec.get("community_id", "")).strip()
            label = str(rec.get("community_label") or cid or "Unknown").strip()
            if fid and cid:
                vote.setdefault(fid, {})[cid] = vote.get(fid, {}).get(cid, 0) + 1
                cluster_labels[cid] = label
        for fid, counts in vote.items():
            file_cluster[fid] = max(counts, key=lambda c: counts[c])
        print(f"[indexer] membership rows: {len(file_cluster)}", flush=True)
    except Exception as e:
        print(f"[indexer] cypher membership error: {e}", flush=True)

    # Step 2: all File nodes
    try:
        raw = await cypher_tool.ainvoke({
            "query": "MATCH (f:File) RETURN f LIMIT 1000",
            "repo": repo_name,
        })
        for rec in _to_records(raw):
            node_data = rec.get("f", rec)
            if not isinstance(node_data, dict):
                continue
            fid = str(node_data.get("id", "")).strip()
            if not fid:
                continue
            label = str(
                node_data.get("name")
                or node_data.get("filePath")
                or node_data.get("path")
                or fid
            ).strip()
            cluster_id = file_cluster.get(fid, "unclustered")
            if cluster_id not in cluster_labels:
                cluster_labels[cluster_id] = "Unclustered"
            nodes.append(GraphNode(id=fid, label=label, type="file", cluster=cluster_id))
        print(f"[indexer] file nodes: {len(nodes)}", flush=True)
    except Exception as e:
        print(f"[indexer] cypher file nodes error: {e}", flush=True)

    # Build cluster list with sizes
    size_map: dict[str, int] = {}
    for n in nodes:
        size_map[n.cluster] = size_map.get(n.cluster, 0) + 1

    clusters = [
        GraphCluster(id=cid, label=cluster_labels[cid], size=size_map.get(cid, 0))
        for cid in cluster_labels
    ]
    return nodes, clusters


async def _cypher_edges(cypher_tool, repo_name: str) -> list[GraphEdge]:
    """Fetch IMPORTS edges between File nodes.
    Note: CALLS exists only at symbol level, not file level — IMPORTS is the only
    file-to-file edge type in the GitNexus schema.
    """
    edges: list[GraphEdge] = []
    for rel_type in ("IMPORTS",):
        try:
            raw = await cypher_tool.ainvoke({
                "query": (
                    f"MATCH (a:File)-[r:CodeRelation]->(b:File) "
                    f"WHERE r.type = '{rel_type}' "
                    f"RETURN a.id AS source, b.id AS target "
                    f"LIMIT 1000"
                ),
                "repo": repo_name,
            })
            before = len(edges)
            for rec in _to_records(raw):
                src = str(rec.get("source", "")).strip()
                tgt = str(rec.get("target", "")).strip()
                if src and tgt:
                    edges.append(GraphEdge(source=src, target=tgt, type=rel_type))
            print(f"[indexer] {rel_type} edges: {len(edges) - before}", flush=True)
        except Exception as e:
            print(f"[indexer] cypher {rel_type} edges error: {e}", flush=True)
    return edges


# ── Response parsing helpers ───────────────────────────────────────────────────

def _unwrap_text(raw) -> str:
    """
    Extract plain text from whatever ainvoke returns.
    langchain-mcp-adapters may return:
      - ToolMessage / BaseMessage with .content
      - list of content blocks: [{"type": "text", "text": "..."}]
      - plain string
    """
    if hasattr(raw, "content"):
        raw = raw.content
    if isinstance(raw, list):
        parts = [
            block.get("text", "") if isinstance(block, dict) and block.get("type") == "text"
            else block if isinstance(block, str)
            else ""
            for block in raw
        ]
        return "\n".join(p for p in parts if p)
    return raw if isinstance(raw, str) else ""


def _to_records(raw) -> list[dict]:
    """
    Parse GitNexus MCP tool output into a list of dicts.

    GitNexus appends a prose footer to every response:
        <JSON or markdown table>\\n\\n---\\n**Next:** ...

    Strip everything after the first \\n---\\n before parsing.

    Remaining content is either:
    - A JSON object with a "markdown" key:  {"markdown": "| col |\\n..."}
    - A bare JSON array:                    [{...}, ...]
    - A raw markdown table
    """
    text = _unwrap_text(raw).strip()
    if not text:
        return []

    # Strip GitNexus prose footer ("---\n**Next:** ...")
    text = re.split(r"\n---\n", text, maxsplit=1)[0].strip()
    if not text:
        return []

    try:
        outer = json.loads(text)
    except Exception:
        return _parse_markdown_table(text)

    if isinstance(outer, dict) and "markdown" in outer:
        return _parse_markdown_table(outer["markdown"])
    if isinstance(outer, list):
        return [r for r in outer if isinstance(r, dict)]
    if isinstance(outer, dict):
        return [outer]
    return []


def _parse_markdown_table(md: str) -> list[dict]:
    """
    Parse a Markdown table where cells may be JSON objects or plain scalars.

    Single-column (RETURN f):
        | f |
        | --- |
        | {"id":"File:foo.py","name":"foo.py",...} |

    Multi-column (RETURN f.id AS file_id, c.id AS community_id, ...):
        | file_id | community_id | community_label |
        | --- | --- | --- |
        | File:foo.py | Community:auth | Authentication |
    """
    lines = [ln.strip() for ln in md.split("\n") if ln.strip()]
    if len(lines) < 2:
        return []

    headers = _split_row(lines[0])
    if not headers:
        return []

    records: list[dict] = []
    for line in lines[2:]:  # skip header row + separator row
        values = _split_row(line)
        if not values or len(values) != len(headers):
            continue
        record: dict = {}
        for header, value in zip(headers, values):
            try:
                record[header] = json.loads(value)
            except Exception:
                record[header] = value
        records.append(record)
    return records


def _split_row(line: str) -> list[str]:
    """Split '| a | b | c |' into ['a', 'b', 'c']."""
    if not line.startswith("|"):
        return []
    parts = line.split("|")
    return [p.strip() for p in parts[1:-1]] if len(parts) > 2 else []


# ── Standalone runner ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m indexer <repo_url>")
        sys.exit(1)

    async def _main() -> None:
        async for event in index_repo(sys.argv[1]):
            print(event.model_dump_json())

    asyncio.run(_main())
