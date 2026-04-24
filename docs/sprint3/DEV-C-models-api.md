# Person 3 — Models, API, Sessions, Export, Jira MCP, Settings UI + Merge Integration

**Branch:** `p3/models-api-integration`
**Depends on:** Nothing — **merges first**. Everyone else rebases on this branch before writing code.
**Final responsibility:** After P1/P2/P4 open PRs, Person 3 reviews, resolves conflicts, smoke-tests end-to-end, and merges all into `main` in order.

**Files owned:**
- `backend/models.py` — extend with all new models + SSE events
- `backend/main.py` — new bug report + settings endpoints
- `backend/export.py` — NEW: Markdown + PDF export
- `backend/agent/sessions.py` — extend for bug reproduction sessions
- `backend/agent/tools.py` — Jira MCP server config + tool aliases only
- `frontend/src/components/SettingsPanel.tsx` — NEW
- `frontend/src/services/api.ts` — new API client functions
- `frontend/src/services/types.ts` — TypeScript types for all new models

---

## Priority: Merge First

The models branch is the foundation for the whole sprint. **Do not delay.** Everyone else scaffolds against the spec below before your branch lands, but they need it merged early in Week 1 to write real code.

**Merge order (Person 3 enforces):**
```
1. models + API stubs + sessions  →  main  (Day 1-2)
2. Person 4: MCP integrations     →  main  (rebase on 1)
3. Person 1: stages 1-3           →  main  (rebase on 1+2)
4. Person 2: stages 4-5 + wiring  →  main  (rebase on 1+2+3)
5. Person 3: final integration pass, smoke test, sign-off
```

---

## New Models (`backend/models.py`)

### Request Models

```python
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
```

### Stage Output Models

```python
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
    components: list[AffectedComponent]    # reuses existing Sprint 2 model
    code_paths: list[CodePath]
    entry_points: list[str]
    root_cause_hypotheses: list[str]

class ReproductionPlan(BaseModel):
    preconditions: str
    steps: list[E2ETestStep]               # reuses existing Sprint 2 model
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
```

### New SSE Events

```python
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
```

### Integration Settings Models

```python
class IntegrationStatus(BaseModel):
    name: str
    configured: bool
    healthy: bool
    message: str = ""

class IntegrationSettingsResponse(BaseModel):
    integrations: list[IntegrationStatus]
```

---

## API Endpoints (`backend/main.py`)

Add below existing Sprint 2 endpoints. Do not modify Sprint 2 routes.

```python
@app.post("/bug-report")
async def create_bug_report(req: BugReportRequest):
    """Start the bug reproduction pipeline. Returns SSE stream."""

@app.post("/bug-report/{session_id}/continue")
async def continue_bug_report(session_id: str, req: BugContinueRequest):
    """Resume after a checkpoint."""

@app.get("/bug-report/{session_id}/status")
async def bug_report_status(session_id: str):
    """Return current session stage and metadata."""

@app.post("/bug-report/{session_id}/export")
async def export_bug_report(session_id: str, req: ExportRequest):
    """Return Markdown or PDF download. Optionally push to Jira."""

@app.get("/settings/integrations")
async def get_integrations():
    """List all integrations and their health status. Calls Person 4's check_all_integrations()."""

@app.post("/settings/integrations")
async def update_integration(req: IntegrationConfigRequest):
    """Write new credentials to environment (session-scoped)."""
```

All `/bug-report` streaming endpoints follow the same `StreamingResponse(generate(), media_type="text/event-stream")` pattern as `/analyze` in `main.py`.

---

## Session Management (`backend/agent/sessions.py`)

Extend the existing `Session` dataclass:

```python
class SessionType(str, Enum):
    IMPACT_ANALYSIS = "impact_analysis"
    BUG_REPRODUCTION = "bug_reproduction"

@dataclass
class Session:
    session_id: str
    session_type: SessionType
    pr_url: str | None
    bug_description: str | None
    created_at: datetime
    current_stage: str = "gathering"
    thread_id: str = ""
    intermediate_result: dict = field(default_factory=dict)
    bug_report: BugReport | None = None

    def to_status_dict(self) -> dict: ...
    def get_bug_report(self) -> BugReport | None:
        return self.bug_report
```

Update `create_session()` to accept `session_type` and `bug_description` parameters.

---

## Export (`backend/export.py`)

```python
def export_markdown(report: BugReport) -> tuple[str, str]:
    """Returns (markdown_content, filename)."""
    # Sections: title, severity/category/env/confidence, reproduction steps,
    # expected vs actual, root cause, affected components, evidence (logs/docs/issues),
    # recommendations, Jira URL if present.

def export_pdf(report: BugReport) -> tuple[bytes, str]:
    """Returns (pdf_bytes, filename). Convert markdown → PDF via fpdf2."""
```

Add `fpdf2` to `requirements.txt`. Keep `export_markdown` as the canonical format; `export_pdf` calls it then converts.

Filenames are slugified: `bug-report-{slugify(report.title)}.md` / `.pdf`.

---

## Jira MCP Config (`backend/agent/tools.py` — Jira section only)

Person 3 owns the Jira MCP server config. Person 4 owns all other MCP server configs.

```python
if os.environ.get("JIRA_URL") and os.environ.get("JIRA_API_TOKEN"):
    config["jira"] = {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-atlassian"],
        "env": {
            **utf8_env,
            "JIRA_URL": os.environ["JIRA_URL"],
            "JIRA_EMAIL": os.environ.get("JIRA_EMAIL", ""),
            "JIRA_API_TOKEN": os.environ["JIRA_API_TOKEN"],
        },
    }
```

**Tool alias normalization** — community MCP servers may expose tools under different names. Add a `_normalize_tool_names(tools)` helper called after `client.get_tools()`:

```python
JIRA_TOOL_ALIASES = {
    "search_issues": "jira_search",
    "get_issue": "jira_get_issue",
    "create_issue": "jira_create_issue",
    "update_issue": "jira_update_issue",
    "get_comments": "jira_get_comments",
}
```

**Env vars:** `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`

---

## Settings UI (`frontend/src/components/SettingsPanel.tsx`)

Integration cards for: Jira, Notion, Confluence, Grafana, Kibana, Postman.

**On mount:** `GET /settings/integrations` → render status per card.

**Per card:**
- Status indicator: green (connected), yellow (configured but unhealthy), gray (not configured)
- Credential fields (masked after save)
- "Test Connection" button → `POST /settings/integrations` with that tool's credentials → re-fetch status

**"Save All"** → sends all dirty credentials in batch.

Reference `CheckpointDialog.tsx` for modal/overlay pattern if needed.

---

## TypeScript Types (`frontend/src/services/types.ts`)

Add interfaces mirroring all new Pydantic models. Key types:

```typescript
interface BugReportRequest { description: string; environment?: string; severity?: ...; repo_url?: string; jira_ticket?: string; attachments?: string[]; session_id?: string; }
interface BugReport { title: string; severity: ...; category: string; environment: string; reproduction_steps: E2ETestStep[]; expected_behavior: string; actual_behavior: string; root_cause_analysis: string; affected_components: AffectedComponent[]; evidence: ResearchFindings; recommendations: string[]; confidence: ...; jira_url?: string; }
interface ResearchFindings { log_entries: LogEntry[]; doc_references: DocReference[]; related_issues: RelatedIssue[]; db_state: Record<string, unknown>[]; admin_notes: string[]; evidence_summary: string; }
interface IntegrationStatus { name: string; configured: boolean; healthy: boolean; message: string; }
// SSE events
interface BugStageChangeEvent { type: "bug_stage_change"; stage: string; summary: string; }
interface BugCheckpointEvent { type: "bug_checkpoint"; session_id: string; stage_completed: string; payload: Record<string, unknown>; }
interface ResearchProgressEvent { type: "research_progress"; source: string; finding_count: number; summary: string; }
interface BugReportResultEvent { type: "bug_result"; session_id: string; report: BugReport; agent_steps: number; }
```

Add corresponding API functions to `frontend/src/services/api.ts`:
```typescript
export async function startBugReport(req: BugReportRequest, callbacks: BugReproCallbacks): Promise<void>
export async function continueBugReport(sessionId: string, req: BugContinueRequest, callbacks: BugReproCallbacks): Promise<void>
export async function exportBugReport(sessionId: string, format: "markdown" | "pdf"): Promise<Blob>
export async function getIntegrations(): Promise<IntegrationStatus[]>
export async function updateIntegration(name: string, credentials: Record<string, string>): Promise<void>
```

---

## Final Merge Integration

After P1/P2/P4 open PRs against `main`:

1. Review each PR for interface compliance (models imported correctly, stage names match, SSE events typed correctly).
2. Merge in order: P4 → P1 → P2 (P3 models are already on main).
3. Run smoke test:
   ```
   POST /bug-report  →  SSE stream  →  checkpoint_mechanics  →  continue approve
     →  checkpoint_research  →  continue approve  →  bug_result event  →  BugReport
     →  POST /bug-report/{id}/export?format=markdown  →  .md file download
   ```
4. Confirm `GET /analyze` (Sprint 2) still works — impact analysis pipeline must be untouched.
5. Tag the merged commit and notify team.

---

## Acceptance Criteria

- [ ] All new Pydantic models importable from `backend/models.py`
- [ ] `POST /bug-report` returns SSE stream
- [ ] `POST /bug-report/{id}/continue` resumes at checkpoint
- [ ] `GET /bug-report/{id}/status` returns session info
- [ ] `POST /bug-report/{id}/export` returns .md file; `format=pdf` returns .pdf
- [ ] `GET /settings/integrations` returns all integration statuses
- [ ] Session supports both `impact_analysis` and `bug_reproduction` types
- [ ] Markdown export produces all sections (repro steps, root cause, evidence, recommendations)
- [ ] PDF export produces valid PDF bytes
- [ ] Jira MCP config generated only when env vars present; aliases normalize tool names
- [ ] `SettingsPanel` shows all 6 integrations with status + test connection
- [ ] TypeScript types mirror all Pydantic models
- [ ] All Sprint 2 endpoints unchanged and working
- [ ] End-to-end smoke test passes after final merge
