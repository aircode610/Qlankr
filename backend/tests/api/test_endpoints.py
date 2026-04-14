from unittest.mock import patch

import pytest

import indexer
from agent.sessions import create_session
from models import AgentStepEvent, GraphCluster, GraphData, GraphNode
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


@pytest.mark.asyncio
async def test_analyze_accepts_context_field(client):
    async def fake_run(pr_url, context=None, session_id=None):
        assert pr_url == "https://github.com/o/r/pull/1"
        assert context == "users see a blank screen"
        yield AgentStepEvent(tool="noop", summary="ok")

    with patch("agent.agent.run_agent", fake_run):
        response = await client.post(
            "/analyze",
            json={
                "pr_url": "https://github.com/o/r/pull/1",
                "context": "users see a blank screen",
            },
        )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    events = parse_sse_body(response.text)
    assert any(e["event"] == "agent_step" for e in events)


@pytest.mark.asyncio
async def test_analyze_continue_unknown_session_returns_404(client):
    response = await client.post(
        "/analyze/not-a-real-id/continue",
        json={"action": "approve"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_analyze_continue_known_session_streams(client):
    session = create_session("https://github.com/o/r/pull/2")
    response = await client.post(
        f"/analyze/{session.session_id}/continue",
        json={"action": "approve"},
    )
    assert response.status_code == 200
    events = parse_sse_body(response.text)
    assert len(events) >= 2
    kinds = {e["event"] for e in events}
    assert "stage_change" in kinds
    assert "error" in kinds


@pytest.mark.asyncio
async def test_analyze_status_unknown_returns_404(client):
    response = await client.get("/analyze/does-not-exist/status")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_analyze_status_returns_payload(client):
    session = create_session("https://github.com/o/r/pull/3")
    response = await client.get(f"/analyze/{session.session_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session.session_id
    assert data["current_stage"] == "gathering"
    assert "created_at" in data


@pytest.mark.asyncio
async def test_run_tests_returns_501(client):
    response = await client.post("/run-tests", json={"session_id": "abc"})
    assert response.status_code == 501