# Dev C: Models, API Endpoints, SSE Events, Report Export

**Branch:** `devc/bug-report-models`
**Depends on:** Nothing (merges first)
**Files owned:**
- `backend/models.py` — extend with bug reproduction models + SSE events
- `backend/main.py` — new endpoints for bug reproduction + settings + export
- `backend/export.py` — NEW: Markdown/PDF export for bug reports
- `backend/agent/sessions.py` — extend for bug reproduction sessions

**Shared files (coordinate with):**
- `backend/agent/bug_agent.py` — owned by Dev A, calls your session helpers and imports your models
- `backend/agent/tool_health.py` — owned by Dev B, called from your /settings/integrations endpoint

---

## Overview

Define the data contract for Sprint 3: all Pydantic models, API endpoints, SSE events, and report export logic. You merge first — everyone else rebases onto your branch.

**Three responsibilities:**
1. **Models** — bug reproduction request/response schemas, stage output models, SSE events
2. **API** — endpoints for bug report input, checkpoint continuation, status, export, integration settings
3. **Export** — Markdown and PDF generation from BugReport model

---

## New Models

### Request Models

```python
class BugReportRequest(BaseModel):
    description: str                          # free-text bug description (required)
    environment: str | None = None            # "iOS 17.4, iPhone 15, build 4.2.1"
    severity: Literal["critical", "major", "minor", "trivial"] | None = None
    repo_url: str | None = None               # optional — for code tracing
    jira_ticket: str | None = None            # optional — linked Jira issue key
    attachments: list[str] = Field(default_factory=list)  # URLs to screenshots/videos/logs
    session_id: str | None = None

class BugContinueRequest(BaseModel):
    """Sent to POST /bug-report/{session_id}/continue after a checkpoint."""
    action: Literal["approve", "refine", "add_context"]
    feedback: str | None = None               # for "refine"
    additional_context: str | None = None     # for "add_context"

class ExportRequest(BaseModel):
    format: Literal["markdown", "pdf"] = "markdown"
    push_to_jira: bool = False                # optionally create Jira issue

class IntegrationConfigRequest(BaseModel):
    """Configure an external tool integration."""
    name: str                                 # "jira", "notion", "grafana", etc.
    credentials: dict                         # tool-specific key-value pairs
```

### Stage Output Models

```python
class TriageResult(BaseModel):
    category: str                             # "gameplay", "networking", "UI", "data", ...
    keywords: list[str]                       # extracted search terms
    affected_area: str                        # subsystem or module name
    severity_estimate: Literal["critical", "major", "minor", "trivial"]
    similar_issues: list[dict] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]

class CodePath(BaseModel):
    entry_point: str                          # e.g. "PlayerController.takeDamage"
    path: list[str]                           # ["takeDamage", "checkHealth", "triggerDeath"]
    description: str                          # plain-English description

class MechanicsAnalysis(BaseModel):
    components: list[AffectedComponent]       # reuses existing model
    code_paths: list[CodePath]
    entry_points: list[str]
    root_cause_hypotheses: list[str]          # ranked hypotheses

class ReproductionPlan(BaseModel):
    preconditions: str
    steps: list[E2ETestStep]                  # reuses existing model
    expected_vs_actual: str
    data_requirements: list[str]
    api_calls: list[dict] = Field(default_factory=list)

class LogEntry(BaseModel):
    timestamp: str
    level: str                                # "error", "warn", "info"
    message: str
    source: str                               # "grafana", "kibana"
    labels: dict = Field(default_factory=dict)

class DocReference(BaseModel):
    title: str
    url: str
    source: str                               # "notion", "confluence"
    snippet: str                              # relevant excerpt

class RelatedIssue(BaseModel):
    key: str                                  # e.g. "QA-123"
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
```

### New SSE Events

```python
class BugStageChangeEvent(BaseModel):
    type: Literal["bug_stage_change"] = "bug_stage_change"
    stage: str                                # triage, mechanics_analysis, etc.
    summary: str

class BugCheckpointEvent(BaseModel):
    type: Literal["bug_checkpoint"] = "bug_checkpoint"
    session_id: str
    stage_completed: str
    interrupt_type: str = "bug_checkpoint"
    payload: dict = Field(default_factory=dict)

class ResearchProgressEvent(BaseModel):
    type: Literal["research_progress"] = "research_progress"
    source: str                               # "grafana", "kibana", "notion", etc.
    finding_count: int
    summary: str

class BugReportResultEvent(BaseModel):
    type: Literal["bug_result"] = "bug_result"
    session_id: str
    report: BugReport
    agent_steps: int

class ExportReadyEvent(BaseModel):
    type: Literal["export_ready"] = "export_ready"
    format: str                               # "markdown" or "pdf"
    download_url: str                         # relative URL to download
```

### Integration Settings Models

```python
class IntegrationStatus(BaseModel):
    name: str                                 # "jira", "notion", "grafana", etc.
    configured: bool                          # credentials present
    healthy: bool                             # last health check passed
    message: str = ""                         # error message if unhealthy

class IntegrationSettingsResponse(BaseModel):
    integrations: list[IntegrationStatus]
```

---

## API Endpoints

### Bug Report Pipeline

```python
@app.post("/bug-report")
async def create_bug_report(req: BugReportRequest):
    """Start the bug reproduction pipeline. Returns SSE stream."""
    async def generate():
        from agent.bug_agent import run_bug_agent
        async for event in run_bug_agent(
            description=req.description,
            environment=req.environment,
            severity=req.severity,
            repo_url=req.repo_url,
            jira_ticket=req.jira_ticket,
            attachments=req.attachments,
            session_id=req.session_id,
        ):
            yield sse_event(event)
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/bug-report/{session_id}/continue")
async def continue_bug_report(session_id: str, req: BugContinueRequest):
    """Resume bug reproduction after a checkpoint."""
    async def generate():
        from agent.bug_agent import continue_bug_agent
        user_response = {"action": req.action}
        if req.feedback:
            user_response["feedback"] = req.feedback
        if req.additional_context:
            user_response["context"] = req.additional_context
        async for event in continue_bug_agent(session_id, user_response):
            yield sse_event(event)
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/bug-report/{session_id}/status")
async def bug_report_status(session_id: str):
    """Check the current status of a bug reproduction session."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_status_dict()


@app.post("/bug-report/{session_id}/export")
async def export_bug_report(session_id: str, req: ExportRequest):
    """Export a completed bug report as Markdown or PDF."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    bug_report = session.get_bug_report()
    if bug_report is None:
        raise HTTPException(status_code=400, detail="Bug report not yet completed")

    from export import export_markdown, export_pdf
    if req.format == "pdf":
        content, filename = export_pdf(bug_report)
        return Response(content, media_type="application/pdf",
                       headers={"Content-Disposition": f"attachment; filename={filename}"})
    else:
        content, filename = export_markdown(bug_report)
        return Response(content, media_type="text/markdown",
                       headers={"Content-Disposition": f"attachment; filename={filename}"})
```

### Integration Settings

```python
@app.get("/settings/integrations")
async def get_integrations():
    """List all external tool integrations and their status."""
    from agent.tool_health import check_all_integrations
    statuses = await check_all_integrations()
    return IntegrationSettingsResponse(integrations=statuses)


@app.post("/settings/integrations")
async def update_integration(req: IntegrationConfigRequest):
    """Update credentials for an external tool integration.
    Stores in environment (session-scoped, not persisted to disk)."""
    ...
```

---

## Export Module (`backend/export.py`)

### Markdown Export

```python
def export_markdown(report: BugReport) -> tuple[str, str]:
    """Generate a Markdown bug report. Returns (content, filename)."""
    filename = f"bug-report-{slugify(report.title)}.md"
    lines = [
        f"# Bug Report: {report.title}",
        "",
        f"**Severity:** {report.severity.upper()}",
        f"**Category:** {report.category}",
        f"**Environment:** {report.environment}",
        f"**Confidence:** {report.confidence}",
        "",
        "## Reproduction Steps",
        "",
    ]
    for step in report.reproduction_steps:
        lines.append(f"{step.step}. **{step.action}** — Expected: {step.expected}")
    lines += [
        "",
        "## Expected vs Actual Behavior",
        f"**Expected:** {report.expected_behavior}",
        f"**Actual:** {report.actual_behavior}",
        "",
        "## Root Cause Analysis",
        report.root_cause_analysis,
        "",
        "## Affected Components",
    ]
    for comp in report.affected_components:
        lines.append(f"- **{comp.component}** — {comp.impact_summary}")
    lines += [
        "",
        "## Evidence",
    ]
    if report.evidence.log_entries:
        lines.append("### Log Entries")
        for entry in report.evidence.log_entries:
            lines.append(f"- `[{entry.timestamp}] [{entry.level}]` {entry.message}")
    if report.evidence.doc_references:
        lines.append("### Documentation")
        for doc in report.evidence.doc_references:
            lines.append(f"- [{doc.title}]({doc.url}) ({doc.source}): {doc.snippet}")
    if report.evidence.related_issues:
        lines.append("### Related Issues")
        for issue in report.evidence.related_issues:
            lines.append(f"- [{issue.key}]({issue.url}): {issue.summary} ({issue.status})")
    lines += [
        "",
        "## Recommendations",
    ]
    for rec in report.recommendations:
        lines.append(f"- {rec}")
    if report.jira_url:
        lines += ["", f"**Jira:** {report.jira_url}"]

    return "\n".join(lines), filename
```

### PDF Export

Use `markdown` + `weasyprint` (or `fpdf2` as a lighter alternative):

```python
def export_pdf(report: BugReport) -> tuple[bytes, str]:
    """Generate a PDF bug report. Returns (content_bytes, filename)."""
    md_content, _ = export_markdown(report)
    # Convert markdown to HTML, then HTML to PDF
    ...
```

**Dependencies:** Add `fpdf2` to `requirements.txt` (lighter than weasyprint, no system deps).

---

## Session Management Updates

Extend `backend/agent/sessions.py` to support bug reproduction sessions:

```python
class SessionType(str, Enum):
    IMPACT_ANALYSIS = "impact_analysis"
    BUG_REPRODUCTION = "bug_reproduction"

class Session:
    session_id: str
    session_type: SessionType
    created_at: datetime
    current_stage: str
    pr_url: str | None = None           # impact analysis
    bug_description: str | None = None  # bug reproduction
    bug_report: BugReport | None = None # final output

    def to_status_dict(self) -> dict: ...
    def get_bug_report(self) -> BugReport | None: ...
```

---

## Testing

### Model Tests (`backend/tests/api/test_bug_models.py`)

- All new models validate correctly (required fields, optional fields, defaults)
- BugReport serializes to JSON and deserializes back
- Nested models (ResearchFindings → LogEntry, DocReference) validate
- Export models handle edge cases (empty lists, None fields)

### Endpoint Tests (`backend/tests/api/test_bug_endpoints.py`)

- POST /bug-report returns SSE stream
- POST /bug-report with missing description returns 422
- POST /bug-report/{session_id}/continue resumes after checkpoint
- GET /bug-report/{session_id}/status returns current stage
- POST /bug-report/{session_id}/export returns Markdown/PDF content
- GET /settings/integrations returns integration list
- 404 for unknown session IDs

### Export Tests (`backend/tests/test_export.py`)

- Markdown export produces valid markdown with all sections
- Markdown export handles empty evidence (no log entries, no docs)
- PDF export produces valid PDF bytes
- Filenames are URL-safe (slugified)

---

## Acceptance Criteria

- [ ] All new Pydantic models defined and importable from `backend/models.py`
- [ ] POST /bug-report accepts BugReportRequest and returns SSE stream
- [ ] POST /bug-report/{session_id}/continue resumes bug reproduction
- [ ] GET /bug-report/{session_id}/status returns session info
- [ ] POST /bug-report/{session_id}/export returns Markdown file
- [ ] POST /bug-report/{session_id}/export?format=pdf returns PDF file
- [ ] GET /settings/integrations returns configured integration statuses
- [ ] Session management supports both impact analysis and bug reproduction
- [ ] All SSE events (BugStageChangeEvent, BugCheckpointEvent, ResearchProgressEvent, BugReportResultEvent) serialize correctly
- [ ] Export produces a complete, readable Markdown document
- [ ] Model validation rejects invalid inputs with clear error messages
- [ ] All existing Sprint 2 endpoints still work unchanged
