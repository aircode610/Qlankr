import asyncio
import json
import os
import re
import sys
import tempfile
from pathlib import Path
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

# In-memory registry: { "owner/repo": { "path": str, "graph": GraphData | None } }
_registry: dict[str, dict] = {}

# Map substrings found in gitnexus output lines → stage names
_STAGE_KEYWORDS: list[tuple[str, str]] = [
    ("clone", "clone"),
    ("cloning", "clone"),
    ("structur", "structure"),
    ("pars", "parsing"),
    ("resolv", "resolution"),
    ("cluster", "clustering"),
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

    # Clone
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

    # Analyze
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

    # Read graph and store
    try:
        graph = _read_graph_data(clone_path)
    except Exception as e:
        yield ErrorEvent(message=f"Failed to read graph data: {e}")
        return

    _registry[repo_key] = {"path": clone_path, "graph": graph}

    files = sum(1 for n in graph.nodes if n.type == "file")
    yield IndexDoneEvent(
        repo=repo_key,
        files=files,
        clusters=len(graph.clusters),
        symbols=len(graph.edges),
    )


def _read_graph_data(clone_path: str) -> GraphData:
    """Read .gitnexus output files and map to GraphData."""
    gitnexus_dir = Path(clone_path) / ".gitnexus"
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    clusters: list[GraphCluster] = []

    if not gitnexus_dir.exists():
        return GraphData(nodes=nodes, edges=edges, clusters=clusters)

    # Try unified graph.json first
    graph_file = gitnexus_dir / "graph.json"
    if graph_file.exists():
        data = json.loads(graph_file.read_text())
        for n in data.get("nodes", []):
            raw_type = n.get("type", "file")
            node_type = raw_type if raw_type in ("file", "cluster") else "file"
            nodes.append(GraphNode(
                id=n.get("id", n.get("name", "")),
                label=n.get("label", n.get("name", "")),
                type=node_type,
                cluster=str(n.get("cluster", n.get("clusterId", ""))),
            ))
        for e in data.get("edges", []):
            raw_type = e.get("type", "CALLS")
            edge_type = raw_type if raw_type in ("CALLS", "IMPORTS") else "CALLS"
            edges.append(GraphEdge(
                source=e.get("source", e.get("from", "")),
                target=e.get("target", e.get("to", "")),
                type=edge_type,
            ))
        for c in data.get("clusters", []):
            clusters.append(GraphCluster(
                id=str(c.get("id", c.get("name", ""))),
                label=c.get("label", c.get("name", "")),
                size=int(c.get("size", 0)),
            ))
        return GraphData(nodes=nodes, edges=edges, clusters=clusters)

    # Fall back to separate files
    clusters_file = gitnexus_dir / "clusters.json"
    nodes_file = gitnexus_dir / "nodes.json"
    edges_file = gitnexus_dir / "edges.json"

    if clusters_file.exists():
        for c in json.loads(clusters_file.read_text()):
            clusters.append(GraphCluster(
                id=str(c.get("id", c.get("name", ""))),
                label=c.get("label", c.get("name", "")),
                size=int(c.get("size", c.get("fileCount", 0))),
            ))
    if nodes_file.exists():
        for n in json.loads(nodes_file.read_text()):
            raw_type = n.get("type", "file")
            node_type = raw_type if raw_type in ("file", "cluster") else "file"
            nodes.append(GraphNode(
                id=n.get("id", n.get("name", "")),
                label=n.get("label", n.get("name", "")),
                type=node_type,
                cluster=str(n.get("cluster", n.get("clusterId", ""))),
            ))
    if edges_file.exists():
        for e in json.loads(edges_file.read_text()):
            raw_type = e.get("type", "CALLS")
            edge_type = raw_type if raw_type in ("CALLS", "IMPORTS") else "CALLS"
            edges.append(GraphEdge(
                source=e.get("source", e.get("from", "")),
                target=e.get("target", e.get("to", "")),
                type=edge_type,
            ))

    return GraphData(nodes=nodes, edges=edges, clusters=clusters)


async def get_graph_data(owner: str, repo: str) -> GraphData:
    """Return graph data for an already-indexed repo."""
    repo_key = f"{owner}/{repo}"
    entry = _registry.get(repo_key)
    if entry is None:
        return GraphData(nodes=[], edges=[], clusters=[])
    graph = entry.get("graph")
    if graph is None:
        try:
            graph = _read_graph_data(entry["path"])
            entry["graph"] = graph
        except Exception:
            return GraphData(nodes=[], edges=[], clusters=[])
    return graph


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m indexer <repo_url>")
        sys.exit(1)

    async def _main() -> None:
        async for event in index_repo(sys.argv[1]):
            print(event.model_dump_json())

    asyncio.run(_main())
