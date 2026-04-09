# Dev C: Shared Models + API Endpoints

**Branch:** `devc/testing-models`
**Merges:** First (all other branches depend on this)
**Files owned:**
- `backend/models.py` (primary ownership — canonical source of truth)
- `backend/main.py` (endpoint signatures, routing, SSE wiring)
- `backend/agent/sessions.py` — NEW: session state store
- `backend/runner/executor.py` — NEW (Phase 4): container orchestration + SSE streaming

---

## Overview

You own the contract layer. Every Pydantic model, SSE event type, request/response schema, and API endpoint signature lives in your code. The other three devs import from `models.py` and call/serve endpoints in `main.py`. Your code merges first so everyone else can rebase.

---

## File: backend/models.py — Complete Schema

Replace the current contents with the models below. This is the canonical, copy-paste-ready schema that all devs will use.

```python
from typing import Literal
from pydantic import BaseModel, Field


# ─── Requests ────────────────────────────────────────────────────────────────

class IndexRequest(BaseModel):
    repo_url: str  # e.g. https://github.com/owner/repo


class AnalyzeRequest(BaseModel):
    pr_url: str
    context: str | None = None       # optional bug report or user scenario for E2E stage
    session_id: str | None = None    # set when resuming after a checkpoint


class ContinueRequest(BaseModel):
    """Sent to POST /analyze/{session_id}/continue after a checkpoint pause."""
    action: Literal["approve", "add_context", "skip", "rerun"]
    additional_context: str | None = None


# ─── Stage 1: Unit Tests ─────────────────────────────────────────────────────

class UnitTestCase(BaseModel):
    name: str                        # e.g. "rejects when inventory full"
    scenario: str                    # setup / input description
    expected: str                    # expected outcome


class UnitTestSpec(BaseModel):
    target: str                      # symbol under test, e.g. "PlayerInventory.addItem"
    test_cases: list[UnitTestCase]
    mocks_needed: list[str] = Field(default_factory=list)
    priority: Literal["high", "medium", "low"]
    generated_code: str | None = None   # Phase 4: actual executable test code


# ─── Stage 2: Integration Tests ──────────────────────────────────────────────

class IntegrationTestCase(BaseModel):
    name: str
    scenario: str
    expected: str


class IntegrationTestSpec(BaseModel):
    integration_point: str           # e.g. "PlayerInventory <> CraftingSystem"
    modules_involved: list[str]      # e.g. ["inventory", "crafting"]
    test_cases: list[IntegrationTestCase]
    data_setup: str                  # preconditions / fixture description
    risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    generated_code: str | None = None


# ─── Stage 3: E2E Test Plan ──────────────────────────────────────────────────

class E2ETestStep(BaseModel):
    step: int
    action: str
    expected: str


class E2ETestPlan(BaseModel):
    process: str                     # GitNexus process name
    scenario: str                    # human-readable scenario title
    steps: list[E2ETestStep]
    preconditions: str
    affected_by_pr: list[str] = Field(default_factory=list)
    priority: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    estimated_duration: str          # e.g. "5 min"


# ─── Affected Component (updated) ────────────────────────────────────────────

class AffectedComponent(BaseModel):
    component: str
    files_changed: list[str] = Field(default_factory=list)
    impact_summary: str
    risks: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]
    unit_tests: list[UnitTestSpec] = Field(default_factory=list)
    integration_tests: list[IntegrationTestSpec] = Field(default_factory=list)


# ─── Analyze Response (updated) ──────────────────────────────────────────────

class AnalyzeResponse(BaseModel):
    pr_title: str
    pr_url: str
    pr_summary: str
    affected_components: list[AffectedComponent]
    e2e_test_plans: list[E2ETestPlan] = Field(default_factory=list)
    agent_steps: int


# ─── SSE Events ──────────────────────────────────────────────────────────────

class AgentStepEvent(BaseModel):
    type: Literal["agent_step"] = "agent_step"
    tool: str
    summary: str


class StageChangeEvent(BaseModel):
    type: Literal["stage_change"] = "stage_change"
    stage: Literal[
        "gathering",
        "unit_testing",
        "integration_testing",
        "e2e_planning",
        "submitting",
    ]
    summary: str


class CheckpointEvent(BaseModel):
    type: Literal["checkpoint"] = "checkpoint"
    session_id: str
    stage_completed: Literal[
        "gathering",
        "unit_testing",
        "integration_testing",
        "e2e_planning",
    ]
    intermediate_result: dict        # partial AnalyzeResponse serialized
    prompt: str                      # question for the user


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


class ResultEvent(AnalyzeResponse):
    type: Literal["result"] = "result"


# ─── Index SSE Events (unchanged from Sprint 1) ─────────────────────────────

class IndexStepEvent(BaseModel):
    type: Literal["index_step"] = "index_step"
    stage: str
    summary: str


class IndexDoneEvent(BaseModel):
    type: Literal["index_done"] = "index_done"
    repo: str
    files: int
    clusters: int
    symbols: int


# ─── Graph / Viz Models (unchanged from Sprint 1) ───────────────────────────

class GraphNode(BaseModel):
    id: str
    label: str
    type: Literal["file", "cluster"]
    cluster: str


class GraphEdge(BaseModel):
    source: str
    target: str
    type: Literal["CALLS", "IMPORTS"]


class GraphCluster(BaseModel):
    id: str
    label: str
    size: int


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    clusters: list[GraphCluster]


# ─── Test Execution Models (Phase 4) ─────────────────────────────────────────

class RunTestsRequest(BaseModel):
    session_id: str


class TestResult(BaseModel):
    test_name: str
    status: Literal["pass", "fail", "error", "skip"]
    duration_ms: int
    output: str = ""                 # stdout/stderr


class TestRunEvent(BaseModel):
    type: Literal["test_result"] = "test_result"
    stage: Literal["unit", "integration"]
    result: TestResult


class TestRunDoneEvent(BaseModel):
    type: Literal["test_run_done"] = "test_run_done"
    total: int
    passed: int
    failed: int
    errors: int
    skipped: int
    duration_ms: int
```

---

## File: backend/main.py — API Endpoints

### Existing endpoints (keep as-is)
- `GET /health`
- `POST /index` — SSE stream, uses `IndexStepEvent`, `IndexDoneEvent`
- `GET /graph/{owner}/{repo}` — returns `GraphData`
- `GET /debug/mcp/tools`, `GET /debug/mcp/repos`, `POST /debug/mcp/call`

### Updated endpoint

**`POST /analyze`** — now accepts `AnalyzeRequest` (with optional `context` and `session_id`)

```python
@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    async def stream():
        async for event in run_agent(
            pr_url=req.pr_url,
            context=req.context,
            session_id=req.session_id,
        ):
            yield f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")
```

SSE event types emitted: `agent_step`, `stage_change`, `checkpoint`, `result`, `error`

### New endpoints

**`POST /analyze/{session_id}/continue`** — resume after checkpoint

```python
@app.post("/analyze/{session_id}/continue")
async def continue_analysis(session_id: str, req: ContinueRequest):
    async def stream():
        async for event in resume_agent(session_id, req):
            yield f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")
```

**`GET /analyze/{session_id}/status`** — get session state

```python
@app.get("/analyze/{session_id}/status")
async def session_status(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session.to_status_dict()
```

**`POST /run-tests`** (Phase 4)

```python
@app.post("/run-tests")
async def run_tests(req: RunTestsRequest):
    async def stream():
        async for event in execute_tests(req.session_id):
            yield f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")
```

---

## Session Management (`backend/agent/sessions.py`)

You own the session store. Dev A calls your helpers to create and update sessions; the API endpoints you own in `main.py` call `get_session()` directly.

```python
from dataclasses import dataclass, field
from datetime import datetime
import uuid

@dataclass
class Session:
    session_id: str
    pr_url: str
    created_at: datetime
    current_stage: str = "gathering"
    thread_id: str = ""               # LangGraph thread ID for checkpoint resume
    intermediate_result: dict = field(default_factory=dict)

    def to_status_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "current_stage": self.current_stage,
            "created_at": self.created_at.isoformat(),
            "intermediate_result": self.intermediate_result,
        }

# In-memory store (no persistence for now)
_sessions: dict[str, Session] = {}

def create_session(pr_url: str) -> Session:
    sid = uuid.uuid4().hex[:12]
    session = Session(session_id=sid, pr_url=pr_url, created_at=datetime.utcnow())
    _sessions[sid] = session
    return session

def get_session(session_id: str) -> Session | None:
    return _sessions.get(session_id)

def update_session(session_id: str, **kwargs) -> None:
    session = _sessions.get(session_id)
    if session:
        for k, v in kwargs.items():
            setattr(session, k, v)
```

---

## SSE Event Flow (what the frontend sees)

```
POST /analyze
  ← event: stage_change   { stage: "gathering", summary: "..." }
  ← event: agent_step     { tool: "get_pull_request", summary: "..." }
  ← event: agent_step     { tool: "cypher", summary: "..." }
  ...
  ← event: stage_change   { stage: "unit_testing", summary: "..." }
  ← event: agent_step     { tool: "context", summary: "..." }
  ...
  ← event: checkpoint     { session_id: "abc", stage_completed: "unit_testing", ... }
  [stream pauses — user reviews intermediate results]

POST /analyze/abc/continue   { action: "approve" }
  ← event: stage_change   { stage: "integration_testing", summary: "..." }
  ← event: agent_step     { tool: "impact", summary: "..." }
  ...
  ← event: checkpoint     { session_id: "abc", stage_completed: "integration_testing", ... }

POST /analyze/abc/continue   { action: "add_context", additional_context: "users report crash when..." }
  ← event: stage_change   { stage: "e2e_planning", summary: "..." }
  ...
  ← event: stage_change   { stage: "submitting", summary: "..." }
  ← event: result         { pr_title: "...", affected_components: [...], e2e_test_plans: [...] }
```

---

## Phase 4: Container Executor (`backend/runner/executor.py`)

You own the orchestration layer that spins up the runner container (built by Dev B) and streams results back through the `/run-tests` endpoint you also own.

```python
import docker
import json
from backend.models import TestResult, TestRunEvent, TestRunDoneEvent
from backend.agent.sessions import get_session

async def execute_tests(session_id: str):
    """
    Spin up a runner container, stream test results, clean up.
    Called by POST /run-tests endpoint.
    """
    session = get_session(session_id)
    test_files = _collect_generated_tests(session)

    client = docker.from_env()
    container = client.containers.run(
        "qlankr-test-runner:latest",
        stdin_open=True,
        detach=True,
        mem_limit="512m",
        cpu_period=100000,
        cpu_quota=50000,  # 50% of one core
        network_mode="none",  # no network access
    )

    try:
        config = {
            "repo_url": session.pr_url.rsplit("/pull/", 1)[0],
            "commit_sha": "HEAD",  # TODO: get PR head SHA
            "test_files": test_files,
        }
        container.exec_run(f"echo '{json.dumps(config)}' | python3 /usr/local/bin/run_tests.py")

        totals = {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
        for line in container.logs(stream=True):
            result = json.loads(line.decode())
            test_result = TestResult(**result)
            totals["total"] += 1
            totals[test_result.status] = totals.get(test_result.status, 0) + 1
            yield TestRunEvent(stage=result.get("stage", "unit"), result=test_result)

        yield TestRunDoneEvent(**totals, duration_ms=0)  # TODO: track duration
    finally:
        container.stop(timeout=5)
        container.remove(force=True)
```

Resource limits (enforced here, container image built by Dev B):

| Limit | Value |
|-------|-------|
| Memory | 512 MB |
| CPU | 50% of 1 core |
| Timeout | 300 seconds |
| Network | Disabled |
| Disk | 1 GB |

---

## Acceptance Criteria

- [ ] All new Pydantic models validate correctly (write pytest tests for each)
- [ ] `POST /analyze` accepts `context` and `session_id` without breaking existing callers (both fields optional)
- [ ] `POST /analyze/{session_id}/continue` returns 404 for unknown sessions, streams events for valid ones
- [ ] `GET /analyze/{session_id}/status` returns current stage + partial results
- [ ] All SSE events serialize cleanly via `model_dump_json()`
- [ ] Existing Sprint 1 endpoints (`/index`, `/graph`, `/health`, `/debug/*`) unchanged
- [ ] Phase 4 test execution endpoints stubbed (return 501) until Phase 4 begins
- [ ] `create_session()` / `get_session()` / `update_session()` work correctly (unit tests)
- [ ] Session `to_status_dict()` returns correct fields
- [ ] `execute_tests()` streams `TestRunEvent` per result and `TestRunDoneEvent` at completion
- [ ] Container is destroyed after execution (even on error)
- [ ] Memory/CPU/network limits enforced in container config

---

## Testing

Add to `backend/tests/test_models.py`:
- Validation tests for every new model (valid + invalid payloads)
- `UnitTestSpec` with empty `mocks_needed` and `None` `generated_code`
- `IntegrationTestSpec` risk_level literal validation
- `E2ETestPlan` step ordering
- `AffectedComponent` backward compat (empty `unit_tests`/`integration_tests` lists)
- `ContinueRequest` action literal validation

Add to `backend/tests/test_endpoints.py`:
- `/analyze` with `context` field
- `/analyze/{session_id}/continue` with valid/invalid session
- `/analyze/{session_id}/status` 404 case

Add to `backend/tests/test_sessions.py` (new):
- `create_session()` generates unique IDs
- `get_session()` returns None for unknown IDs
- `update_session()` modifies only specified fields

Add to `backend/tests/test_executor.py` (new, Phase 4):
- Mock docker client, test `execute_tests()` streams events correctly
- Test container cleanup on success and on exception
