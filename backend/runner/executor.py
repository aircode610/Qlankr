from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import docker

from agent.sessions import Session, get_session
from models import TestResult, TestRunDoneEvent, TestRunEvent


def _collect_generated_tests(session: Session) -> list[str]:
    """Paths or labels for generated tests from the latest intermediate agent state."""
    paths: list[str] = []
    ir: dict[str, Any] = session.intermediate_result or {}
    for ac in ir.get("affected_components", []) or []:
        if not isinstance(ac, dict):
            continue
        for ut in ac.get("unit_tests", []) or []:
            if isinstance(ut, dict) and ut.get("generated_code"):
                paths.append(f"unit:{ut.get('target', 'unknown')}")
        for it in ac.get("integration_tests", []) or []:
            if isinstance(it, dict) and it.get("generated_code"):
                paths.append(f"integration:{it.get('integration_point', 'unknown')}")
    return paths


def _pr_base_repo_url(pr_url: str) -> str:
    if "/pull/" in pr_url:
        return pr_url.rsplit("/pull/", 1)[0]
    return pr_url


def _accumulate(totals: dict[str, int], status: str) -> None:
    totals["total"] += 1
    if status == "pass":
        totals["passed"] += 1
    elif status == "fail":
        totals["failed"] += 1
    elif status == "error":
        totals["errors"] += 1
    elif status == "skip":
        totals["skipped"] += 1


def _execute_tests_blocking(session_id: str) -> list[TestRunEvent | TestRunDoneEvent]:
    session = get_session(session_id)
    if session is None:
        raise ValueError("Session not found")

    test_files = _collect_generated_tests(session)
    config = {
        "repo_url": _pr_base_repo_url(session.pr_url),
        "commit_sha": "HEAD",
        "test_files": test_files,
    }

    client = docker.from_env()
    container = None
    start = time.monotonic()
    totals = {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    events: list[TestRunEvent | TestRunDoneEvent] = []

    try:
        container = client.containers.run(
            "qlankr-test-runner:latest",
            detach=True,
            mem_limit="512m",
            cpu_period=100000,
            cpu_quota=50000,
            network_mode="none",
            environment={"QLANKR_RUN_CONFIG": json.dumps(config)},
            stdin_open=False,
        )
        try:
            container.wait(timeout=300)
        except Exception:
            pass

        raw = container.logs(stream=False) or b""
        text = raw.decode(errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            stage = row.get("stage", "unit")
            if stage not in ("unit", "integration"):
                stage = "unit"
            try:
                tr = TestResult(
                    test_name=row["test_name"],
                    status=row["status"],
                    duration_ms=int(row.get("duration_ms", 0)),
                    output=str(row.get("output", "")),
                )
            except Exception:
                continue
            _accumulate(totals, tr.status)
            events.append(TestRunEvent(stage=stage, result=tr))

        duration_ms = int((time.monotonic() - start) * 1000)
        events.append(
            TestRunDoneEvent(
                total=totals["total"],
                passed=totals["passed"],
                failed=totals["failed"],
                errors=totals["errors"],
                skipped=totals["skipped"],
                duration_ms=duration_ms,
            )
        )
        return events
    finally:
        if container is not None:
            try:
                container.stop(timeout=5)
            except Exception:
                pass
            try:
                container.remove(force=True)
            except Exception:
                pass


async def execute_tests(session_id: str):
    """
    Spin up a runner container, collect test results from container logs, clean up.
    Yields TestRunEvent for each parsed line, then TestRunDoneEvent.
    """
    loop = asyncio.get_running_loop()
    events = await loop.run_in_executor(None, _execute_tests_blocking, session_id)
    for ev in events:
        yield ev
