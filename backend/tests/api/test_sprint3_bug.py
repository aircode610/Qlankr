from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from models import AffectedComponent, BugReport, E2ETestStep, ResearchFindings


@pytest.mark.asyncio
async def test_bug_report_streams_mocked():
    async def fake_run(*args, **kwargs):
        from models import (
            BugReportResultEvent,
            BugStageChangeEvent,
            ResearchProgressEvent,
        )

        yield BugStageChangeEvent(stage="x", summary="s")
        yield ResearchProgressEvent(source="stub", finding_count=0, summary="k")
        yield BugReportResultEvent(
            session_id="s1",
            report=BugReport(
                title="t",
                severity="trivial",
                category="c",
                environment="e",
                reproduction_steps=[E2ETestStep(step=1, action="a", expected="b")],
                expected_behavior="eb",
                actual_behavior="ab",
                root_cause_analysis="r",
                affected_components=[AffectedComponent(component="C")],
                evidence=ResearchFindings(),
                recommendations=["r"],
                confidence="low",
            ),
            agent_steps=0,
        )

    with patch("agent.bug_agent.run_bug_report", fake_run):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            r = await client.post(
                "/bug-report",
                json={"description": "d"},
            )
    assert r.status_code == 200
    assert "text/event-stream" in (r.headers.get("content-type") or "")


@pytest.mark.asyncio
async def test_get_integrations_returns_six():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get("/settings/integrations")
    assert r.status_code == 200
    j = r.json()
    assert "integrations" in j
    assert len(j["integrations"]) == 6
    assert {i["name"] for i in j["integrations"]} == {
        "jira", "notion", "confluence", "grafana", "kibana", "postman"
    }
