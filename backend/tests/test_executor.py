from unittest.mock import MagicMock, patch

import pytest

from agent.sessions import clear_sessions, create_session, update_session
from models import TestRunDoneEvent, TestRunEvent
from runner.executor import execute_tests


@pytest.mark.asyncio
async def test_execute_tests_streams_events_and_cleans_container():
    clear_sessions()
    s = create_session("https://github.com/org/repo/pull/99")
    update_session(
        s.session_id,
        intermediate_result={
            "affected_components": [
                {
                    "unit_tests": [
                        {"target": "T", "generated_code": "print(1)"},
                    ],
                }
            ]
        },
    )

    mock_container = MagicMock()
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.return_value = (
        b'{"test_name":"t1","status":"pass","duration_ms":12,"stage":"unit"}\n'
        b'{"test_name":"t2","status":"fail","duration_ms":3,"stage":"integration"}\n'
    )
    mock_client = MagicMock()
    mock_client.containers.run.return_value = mock_container

    with patch("runner.executor.docker.from_env", return_value=mock_client):
        events = []
        async for ev in execute_tests(s.session_id):
            events.append(ev)

    assert len(events) == 3
    assert isinstance(events[0], TestRunEvent)
    assert events[0].result.test_name == "t1"
    assert events[0].result.status == "pass"
    assert isinstance(events[1], TestRunEvent)
    assert events[1].stage == "integration"
    assert isinstance(events[2], TestRunDoneEvent)
    assert events[2].total == 2
    assert events[2].passed == 1
    assert events[2].failed == 1

    mock_client.containers.run.assert_called_once()
    call_kw = mock_client.containers.run.call_args[1]
    assert call_kw["mem_limit"] == "512m"
    assert call_kw["network_mode"] == "none"
    assert call_kw["cpu_quota"] == 50000

    mock_container.stop.assert_called_once()
    mock_container.remove.assert_called_once()


@pytest.mark.asyncio
async def test_execute_tests_session_missing_raises():
    clear_sessions()
    with pytest.raises(ValueError, match="Session not found"):
        async for _ in execute_tests("nope"):
            pass


@pytest.mark.asyncio
async def test_execute_tests_container_cleanup_on_wait_error():
    clear_sessions()
    s = create_session("https://github.com/org/repo/pull/1")

    mock_container = MagicMock()
    mock_container.wait.side_effect = RuntimeError("wait failed")
    mock_container.logs.return_value = b""
    mock_client = MagicMock()
    mock_client.containers.run.return_value = mock_container

    with patch("runner.executor.docker.from_env", return_value=mock_client):
        events = []
        async for ev in execute_tests(s.session_id):
            events.append(ev)

    mock_container.stop.assert_called_once()
    mock_container.remove.assert_called_once()
    assert isinstance(events[-1], TestRunDoneEvent)
