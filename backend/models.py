from typing import Any, Literal

from pydantic import BaseModel, Field


# ─── Requests ────────────────────────────────────────────────────────────────


class IndexRequest(BaseModel):
    repo_url: str  # e.g. https://github.com/owner/repo


class AnalyzeRequest(BaseModel):
    pr_url: str
    context: str | None = None      # optional bug report or user scenario for E2E stage
    session_id: str | None = None   # set when resuming after a checkpoint


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
    impact_summary: str = ""
    risks: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "low"
    unit_tests: list[UnitTestSpec] = Field(default_factory=list)
    integration_tests: list[IntegrationTestSpec] = Field(default_factory=list)


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
    stage: str  # graph node name: gather, unit_tests, checkpoint_unit, choice, etc.
    summary: str


class CheckpointEvent(BaseModel):
    type: Literal["checkpoint"] = "checkpoint"
    session_id: str
    stage_completed: str
    interrupt_type: str = "checkpoint"  # "checkpoint" | "choice" | "e2e_context" | "question"
    payload: dict = Field(default_factory=dict)  # interrupt data (intermediate_result, prompt, options, etc.)


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


# ─── Sprint 3: Bug pipeline requests / outputs ───────────────────────────────

class BugReportRequest(BaseModel):
    description: str
    environment: str | None = None
    severity: Literal["critical", "major", "minor", "trivial"] | None = None
    repo_url: str | None = None
    jira_ticket: str | None = None
    attachments: list[str] = Field(default_factory=list)
    session_id: str | None = None


class BugContinueRequest(BaseModel):
    action: Literal["approve", "refine", "add_context"]
    feedback: str | None = None
    additional_context: str | None = None


class ExportRequest(BaseModel):
    format: Literal["markdown", "pdf"] = "markdown"
    push_to_jira: bool = False


class IntegrationConfigRequest(BaseModel):
    name: str
    credentials: dict


class TriageResult(BaseModel):
    category: str
    keywords: list[str]
    affected_area: str
    severity_estimate: Literal["critical", "major", "minor", "trivial"]
    similar_issues: list[dict] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]


class CodePath(BaseModel):
    entry_point: str
    path: list[str]
    description: str


class MechanicsAnalysis(BaseModel):
    components: list[AffectedComponent]
    code_paths: list[CodePath]
    entry_points: list[str]
    root_cause_hypotheses: list[str]


class ReproductionPlan(BaseModel):
    preconditions: str
    steps: list[E2ETestStep]
    expected_vs_actual: str
    data_requirements: list[str]
    api_calls: list[dict] = Field(default_factory=list)


class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    source: str
    labels: dict = Field(default_factory=dict)


class DocReference(BaseModel):
    title: str
    url: str
    source: str
    snippet: str


class RelatedIssue(BaseModel):
    key: str
    summary: str
    status: str
    url: str


class ResearchFindings(BaseModel):
    log_entries: list[LogEntry] = Field(default_factory=list)
    doc_references: list[DocReference] = Field(default_factory=list)
    related_issues: list[RelatedIssue] = Field(default_factory=list)
    db_state: list[dict] = Field(default_factory=list)
    admin_notes: list[str] = Field(default_factory=list)
    evidence_summary: str = ""


class BugReport(BaseModel):
    title: str
    severity: Literal["critical", "major", "minor", "trivial"]
    category: str
    environment: str
    reproduction_steps: list[E2ETestStep]
    expected_behavior: str
    actual_behavior: str
    root_cause_analysis: str
    affected_components: list[AffectedComponent]
    evidence: ResearchFindings
    recommendations: list[str]
    confidence: Literal["high", "medium", "low"]
    jira_url: str | None = None


class BugReportResponse(BaseModel):
    session_id: str
    bug_report: BugReport
    agent_steps: int


# ─── Sprint 3: Bug SSE events ──────────────────────────────────────────────────

class BugStageChangeEvent(BaseModel):
    type: Literal["bug_stage_change"] = "bug_stage_change"
    stage: str
    summary: str


class BugCheckpointEvent(BaseModel):
    type: Literal["bug_checkpoint"] = "bug_checkpoint"
    session_id: str
    stage_completed: str
    interrupt_type: str = "bug_checkpoint"
    payload: dict = Field(default_factory=dict)


class ResearchProgressEvent(BaseModel):
    type: Literal["research_progress"] = "research_progress"
    source: str
    finding_count: int
    summary: str


class BugReportResultEvent(BaseModel):
    type: Literal["bug_result"] = "bug_result"
    session_id: str
    report: BugReport
    agent_steps: int


class ExportReadyEvent(BaseModel):
    type: Literal["export_ready"] = "export_ready"
    format: str
    download_url: str


# ─── Sprint 3: Integration settings ───────────────────────────────────────────

class IntegrationStatus(BaseModel):
    name: str
    configured: bool
    healthy: bool
    message: str = ""


class IntegrationSettingsResponse(BaseModel):
    integrations: list[IntegrationStatus]
