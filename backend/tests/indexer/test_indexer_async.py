from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

import db
from tests.fake_supabase import FakeSupabaseClient

from indexer import get_graph_data, index_repo, list_indexed_repos
from models import (
    ErrorEvent,
    GraphCluster,
    GraphData,
    GraphNode,
    IndexDoneEvent,
    IndexStepEvent,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_supabase(monkeypatch):
    fake = FakeSupabaseClient()
    monkeypatch.setattr(db, "get_client", lambda: fake)
    return fake


# ── helpers ───────────────────────────────────────────────────────────────────

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

async def test_index_repo_bad_url_yields_error(fake_supabase):
    uid = uuid4()
    events = await collect(index_repo(uid, "https://github.com/onlyone"))
    assert len(events) == 1
    assert isinstance(events[0], ErrorEvent)
    assert "Cannot parse" in events[0].message


async def test_index_repo_git_clone_failure(fake_supabase):
    uid = uuid4()
    git_proc = make_git_proc(returncode=1, stderr=b"repository not found")

    async def mock_exec(*args, **kwargs):
        return git_proc

    with patch("asyncio.create_subprocess_exec", mock_exec):
        events = await collect(index_repo(uid, "https://github.com/owner/repo"))

    error_events = [e for e in events if isinstance(e, ErrorEvent)]
    assert len(error_events) == 1
    assert "git clone failed" in error_events[0].message


async def test_index_repo_gitnexus_not_found(fake_supabase):
    uid = uuid4()
    git_proc = make_git_proc(returncode=0)

    async def mock_exec(*args, **kwargs):
        if args[0] == "git":
            return git_proc
        raise FileNotFoundError("gitnexus not found")

    with patch("asyncio.create_subprocess_exec", mock_exec):
        events = await collect(index_repo(uid, "https://github.com/owner/repo"))

    error_events = [e for e in events if isinstance(e, ErrorEvent)]
    assert len(error_events) == 1
    assert "gitnexus not found" in error_events[0].message


async def test_index_repo_successful_flow_events(fake_supabase):
    uid = uuid4()
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
        with patch("indexer._fetch_stats_and_graph", return_value=({}, mock_graph)):
            events = await collect(index_repo(uid, "https://github.com/owner/myrepo"))

    assert any(isinstance(e, IndexStepEvent) for e in events)
    assert any(isinstance(e, IndexDoneEvent) for e in events)
    assert not any(isinstance(e, ErrorEvent) for e in events)

    done = next(e for e in events if isinstance(e, IndexDoneEvent))
    assert done.repo == "owner/myrepo"


async def test_index_repo_successful_flow_event_order(fake_supabase):
    uid = uuid4()
    git_proc = make_git_proc(returncode=0)
    gitnexus_proc = make_gitnexus_proc(lines=[], returncode=0)
    mock_graph = GraphData(nodes=[], edges=[], clusters=[])

    async def mock_exec(*args, **kwargs):
        if args[0] == "git":
            return git_proc
        return gitnexus_proc

    with patch("asyncio.create_subprocess_exec", mock_exec):
        with patch("indexer._fetch_stats_and_graph", return_value=({}, mock_graph)):
            events = await collect(index_repo(uid, "https://github.com/owner/repo"))

    # IndexDoneEvent must come last
    assert isinstance(events[-1], IndexDoneEvent)


async def test_index_repo_creates_project_record(fake_supabase):
    """After successful indexing, the project should exist in the DB with status 'ready'."""
    uid = uuid4()
    git_proc = make_git_proc(returncode=0)
    gitnexus_proc = make_gitnexus_proc(lines=[], returncode=0)
    mock_graph = GraphData(nodes=[], edges=[], clusters=[])

    async def mock_exec(*args, **kwargs):
        if args[0] == "git":
            return git_proc
        return gitnexus_proc

    with patch("asyncio.create_subprocess_exec", mock_exec):
        with patch("indexer._fetch_stats_and_graph", return_value=({}, mock_graph)):
            await collect(index_repo(uid, "https://github.com/owner/myrepo"))

    repos = list_indexed_repos(uid)
    assert len(repos) == 1
    assert repos[0]["owner"] == "owner"
    assert repos[0]["repo_name"] == "myrepo"
    assert repos[0]["index_status"] == "ready"


# --- get_graph_data ---

async def test_get_graph_data_not_indexed(fake_supabase):
    uid = uuid4()
    result = await get_graph_data(uid, "nobody", "norepo")
    assert result.nodes == []
    assert result.edges == []
    assert result.clusters == []


async def test_get_graph_data_returns_live_graph(fake_supabase):
    """get_graph_data fetches live from MCP for an existing project."""
    uid = uuid4()
    # Pre-create a project record so get_graph_data finds it
    from projects import create_project
    create_project(uid, "https://github.com/owner/repo")

    mock_graph = GraphData(
        nodes=[GraphNode(id="n1", label="f.py", type="file", cluster="c")],
        edges=[],
        clusters=[GraphCluster(id="c", label="C", size=1)],
    )

    with patch("indexer._fetch_stats_and_graph", return_value=({}, mock_graph)):
        result = await get_graph_data(uid, "owner", "repo")

    assert len(result.nodes) == 1
    assert result.nodes[0].id == "n1"


# --- embeddings ---

async def test_embeddings_flag_passed(fake_supabase):
    """gitnexus analyze must be called with --embeddings."""
    uid = uuid4()
    git_proc = make_git_proc(returncode=0)
    gitnexus_proc = make_gitnexus_proc(lines=[], returncode=0)
    mock_graph = GraphData(nodes=[], edges=[], clusters=[])
    captured_args = []

    async def mock_exec(*args, **kwargs):
        captured_args.append(args)
        if args[0] == "git":
            return git_proc
        return gitnexus_proc

    with patch("asyncio.create_subprocess_exec", mock_exec):
        with patch("indexer._fetch_stats_and_graph", return_value=({}, mock_graph)):
            await collect(index_repo(uid, "https://github.com/owner/repo"))

    gitnexus_calls = [a for a in captured_args if a[0] == "gitnexus"]
    assert gitnexus_calls, "gitnexus was never called"
    assert "--embeddings" in gitnexus_calls[0], (
        f"--embeddings flag missing from gitnexus call: {gitnexus_calls[0]}"
    )


async def test_embeddings_stage_emitted(fake_supabase):
    """A stdout line containing 'embedding' must yield IndexStepEvent(stage='embeddings')."""
    uid = uuid4()
    git_proc = make_git_proc(returncode=0)
    gitnexus_proc = make_gitnexus_proc(
        lines=["Generating embeddings for 42 files\n"], returncode=0
    )
    mock_graph = GraphData(nodes=[], edges=[], clusters=[])

    async def mock_exec(*args, **kwargs):
        if args[0] == "git":
            return git_proc
        return gitnexus_proc

    with patch("asyncio.create_subprocess_exec", mock_exec):
        with patch("indexer._fetch_stats_and_graph", return_value=({}, mock_graph)):
            events = await collect(index_repo(uid, "https://github.com/owner/repo"))

    embedding_events = [
        e for e in events
        if isinstance(e, IndexStepEvent) and e.stage == "embeddings"
    ]
    assert embedding_events, "No IndexStepEvent with stage='embeddings' was emitted"
