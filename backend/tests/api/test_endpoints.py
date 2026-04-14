from unittest.mock import patch

import pytest

import indexer
from models import GraphCluster, GraphData, GraphNode
from tests.conftest import parse_sse_body


async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_index_streams_sse_content_type(client):
    # Bad URL — returns an error SSE event, but content-type must be text/event-stream
    response = await client.post("/index", json={"repo_url": "https://github.com/onlyone"})
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


async def test_index_bad_url_streams_error_event(client):
    response = await client.post(
        "/index", json={"repo_url": "https://github.com/onlyone"}
    )
    events = parse_sse_body(response.text)
    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1
    assert "Cannot parse" in error_events[0]["data"]["message"]


async def test_index_git_clone_fail_streams_error_event(client):
    from tests.conftest import parse_sse_body
    from unittest.mock import MagicMock, AsyncMock

    git_proc = MagicMock()
    git_proc.returncode = 1
    git_proc.communicate = AsyncMock(return_value=(b"", b"repo not found"))

    async def mock_exec(*args, **kwargs):
        return git_proc

    with patch("asyncio.create_subprocess_exec", mock_exec):
        response = await client.post(
            "/index", json={"repo_url": "https://github.com/owner/repo"}
        )

    events = parse_sse_body(response.text)
    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) == 1
    assert "git clone failed" in error_events[0]["data"]["message"]


async def test_index_request_validation(client):
    response = await client.post("/index", json={})
    assert response.status_code == 422


async def test_graph_unindexed_returns_empty(client):
    response = await client.get("/graph/unknown/repo")
    assert response.status_code == 200
    data = response.json()
    assert data["nodes"] == []
    assert data["edges"] == []
    assert data["clusters"] == []


async def test_graph_after_index_returns_data(client):
    seeded = GraphData(
        nodes=[GraphNode(id="n1", label="file.py", type="file", cluster="auth")],
        edges=[],
        clusters=[GraphCluster(id="auth", label="Auth", size=1)],
    )
    indexer._registry["myorg/myrepo"] = {"path": "/fake", "graph": seeded}

    response = await client.get("/graph/myorg/myrepo")
    assert response.status_code == 200
    data = response.json()
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["id"] == "n1"
    assert len(data["clusters"]) == 1