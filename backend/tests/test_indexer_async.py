from unittest.mock import AsyncMock, MagicMock, patch

import indexer
from indexer import get_graph_data, index_repo
from models import (
    ErrorEvent,
    GraphCluster,
    GraphData,
    GraphNode,
    IndexDoneEvent,
    IndexStepEvent,
)


def make_git_proc(returncode=0, stderr=b""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(b"", stderr))
    return proc


def make_gitnexus_proc(lines=None, returncode=0):
    proc = MagicMock()
    proc.returncode = returncode
    encoded = [l.encode() if isinstance(l, str) else l for l in (lines or [])]
    proc.stdout = MagicMock()
    proc.stdout.readline = AsyncMock(side_effect=[*encoded, b""])
    proc.wait = AsyncMock()
    return proc


async def collect(gen):
    events = []
    async for event in gen:
        events.append(event)
    return events


# --- index_repo ---

async def test_index_repo_bad_url_yields_error():
    events = await collect(index_repo("https://github.com/onlyone"))
    assert len(events) == 1
    assert isinstance(events[0], ErrorEvent)
    assert "Cannot parse" in events[0].message


async def test_index_repo_git_clone_failure():
    git_proc = make_git_proc(returncode=1, stderr=b"repository not found")

    async def mock_exec(*args, **kwargs):
        return git_proc

    with patch("asyncio.create_subprocess_exec", mock_exec):
        events = await collect(index_repo("https://github.com/owner/repo"))

    error_events = [e for e in events if isinstance(e, ErrorEvent)]
    assert len(error_events) == 1
    assert "git clone failed" in error_events[0].message


async def test_index_repo_gitnexus_not_found():
    git_proc = make_git_proc(returncode=0)

    async def mock_exec(*args, **kwargs):
        if args[0] == "git":
            return git_proc
        raise FileNotFoundError("gitnexus not found")

    with patch("asyncio.create_subprocess_exec", mock_exec):
        events = await collect(index_repo("https://github.com/owner/repo"))

    error_events = [e for e in events if isinstance(e, ErrorEvent)]
    assert len(error_events) == 1
    assert "gitnexus not found" in error_events[0].message


async def test_index_repo_successful_flow_events():
    git_proc = make_git_proc(returncode=0)
    gitnexus_proc = make_gitnexus_proc(
        lines=["Parsing files\n", "Clustering nodes\n"], returncode=0
    )
    mock_graph = GraphData(nodes=[], edges=[], clusters=[])

    async def mock_exec(*args, **kwargs):
        if args[0] == "git":
            return git_proc
        return gitnexus_proc

    with patch("asyncio.create_subprocess_exec", mock_exec):
        with patch("indexer._read_graph_data", return_value=mock_graph):
            events = await collect(index_repo("https://github.com/owner/myrepo"))

    assert any(isinstance(e, IndexStepEvent) for e in events)
    assert any(isinstance(e, IndexDoneEvent) for e in events)
    assert not any(isinstance(e, ErrorEvent) for e in events)

    done = next(e for e in events if isinstance(e, IndexDoneEvent))
    assert done.repo == "owner/myrepo"


async def test_index_repo_successful_flow_event_order():
    git_proc = make_git_proc(returncode=0)
    gitnexus_proc = make_gitnexus_proc(lines=[], returncode=0)
    mock_graph = GraphData(nodes=[], edges=[], clusters=[])

    async def mock_exec(*args, **kwargs):
        if args[0] == "git":
            return git_proc
        return gitnexus_proc

    with patch("asyncio.create_subprocess_exec", mock_exec):
        with patch("indexer._read_graph_data", return_value=mock_graph):
            events = await collect(index_repo("https://github.com/owner/repo"))

    # IndexDoneEvent must come last
    assert isinstance(events[-1], IndexDoneEvent)


async def test_index_repo_populates_registry():
    git_proc = make_git_proc(returncode=0)
    gitnexus_proc = make_gitnexus_proc(lines=[], returncode=0)
    mock_graph = GraphData(nodes=[], edges=[], clusters=[])

    async def mock_exec(*args, **kwargs):
        if args[0] == "git":
            return git_proc
        return gitnexus_proc

    with patch("asyncio.create_subprocess_exec", mock_exec):
        with patch("indexer._read_graph_data", return_value=mock_graph):
            await collect(index_repo("https://github.com/owner/myrepo"))

    assert "owner/myrepo" in indexer._registry


# --- get_graph_data ---

async def test_get_graph_data_not_indexed():
    result = await get_graph_data("nobody", "norepo")
    assert result.nodes == []
    assert result.edges == []
    assert result.clusters == []


async def test_get_graph_data_cached_graph():
    cached = GraphData(
        nodes=[GraphNode(id="n1", label="f.py", type="file", cluster="c")],
        edges=[],
        clusters=[GraphCluster(id="c", label="C", size=1)],
    )
    indexer._registry["owner/repo"] = {"path": "/fake", "graph": cached}

    result = await get_graph_data("owner", "repo")
    assert len(result.nodes) == 1
    assert result.nodes[0].id == "n1"


async def test_get_graph_data_lazy_read(tmp_path):
    mock_graph = GraphData(
        nodes=[GraphNode(id="n2", label="g.py", type="file", cluster="c")],
        edges=[],
        clusters=[],
    )
    indexer._registry["owner/repo2"] = {"path": str(tmp_path), "graph": None}

    with patch("indexer._read_graph_data", return_value=mock_graph):
        result = await get_graph_data("owner", "repo2")

    assert len(result.nodes) == 1
    # Result is now cached in registry
    assert indexer._registry["owner/repo2"]["graph"] is not None
