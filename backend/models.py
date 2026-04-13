from typing import Literal

from pydantic import BaseModel, Field


# ─── Requests ────────────────────────────────────────────────────────────────


class IndexRequest(BaseModel):
    repo_url: str  # e.g. https://github.com/owner/repo


class AnalyzeRequest(BaseModel):
    pr_url: str
    context: str | None = None  # optional bug report or user scenario for E2E stage
    session_id: str | None = None  # set when resuming after a checkpoint


class ContinueRequest(BaseModel):
    """Sent to POST /analyze/{session_id}/continue after a checkpoint pause."""

    action: Literal["approve", "add_context", "skip", "rerun"]
    additional_context: str | None = None


# ─── Stage 1: Unit Tests ─────────────────────────────────────────────────────


class UnitTestCase(BaseModel):
    name: str  # e.g. "rejects when inventory full"
    scenario: str  # setup / input description
    expected: str  # expected outcome


class UnitTestSpec(BaseModel):
    target: str  # symbol under test, e.g. "PlayerInventory.addItem"
    test_cases: list[UnitTestCase]
    mocks_needed: list[str] = Field(default_factory=list)
    priority: Literal["high", "medium", "low"]
    generated_code: str | None = None  # Phase 4: actual executable test code


# ─── Stage 2: Integration Tests ──────────────────────────────────────────────


class IntegrationTestCase(BaseModel):
    name: str
    scenario: str
    expected: str


class IntegrationTestSpec(BaseModel):
    integration_point: str  # e.g. "PlayerInventory <> CraftingSystem"
    modules_involved: list[str]  # e.g. ["inventory", "crafting"]
    test_cases: list[IntegrationTestCase]
    data_setup: str  # preconditions / fixture description
    risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    generated_code: str | None = None


# ─── Stage 3: E2E Test Plan ──────────────────────────────────────────────────


class E2ETestStep(BaseModel):
    step: int
    action: str
    expected: str


class E2ETestPlan(BaseModel):
    process: str  # GitNexus process name
    scenario: str  # human-readable scenario title
    steps: list[E2ETestStep]
    preconditions: str
    affected_by_pr: list[str] = Field(default_factory=list)
    priority: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    estimated_duration: str  # e.g. "5 min"


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
    intermediate_result: dict  # partial AnalyzeResponse serialized
    prompt: str  # question for the user


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
    __test__ = False

    test_name: str
    status: Literal["pass", "fail", "error", "skip"]
    duration_ms: int
    output: str = ""  # stdout/stderr


class TestRunEvent(BaseModel):
    __test__ = False  # not a pytest class (name starts with Test)

    type: Literal["test_result"] = "test_result"
    stage: Literal["unit", "integration"]
    result: TestResult


class TestRunDoneEvent(BaseModel):
    __test__ = False  # not a pytest class (name starts with Test)

    type: Literal["test_run_done"] = "test_run_done"
    total: int
    passed: int
    failed: int
    errors: int
    skipped: int
    duration_ms: int
