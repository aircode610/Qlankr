# Sprint 3 Spec: Bug Reproduction Pipeline + External Tool Integrations

**Sprint start:** 2026-04-22
**Duration:** 4 weeks
**Depends on:** Sprint 2 (multi-stage pipeline, human-in-the-loop, eval framework)
**User stories covered:** 2 (Bug Report Input), 3 (Analyze Mechanics), 4 (Research Support), 5 (Structured Report), 8 (Jira Integration), 10 (Notion/Confluence), 11 (Grafana/Kibana)

---

## Goal

Two deliverables:

1. **External tool integrations** — connect the agent to the tools gaming QA teams actually use: Jira/YouTrack (task tracking), Notion/Confluence (docs/runbooks), Grafana/Kibana (logs/metrics), Postman (API testing), and network sniffers. These tools serve both the existing impact analysis pipeline and the new bug reproduction pipeline.

2. **Bug reproduction pipeline** — a new LangGraph StateGraph that takes a bug description as input, traces the bug through the codebase and external data sources, and produces a structured developer-ready report. The flow: `bug input → triage → mechanics analysis → reproduction planning → research (logs, docs, DB) → report generation`.

---

## Architecture Overview

### New StateGraph: Bug Reproduction

```
bug_input
  ↓
triage
  ↓
mechanics_analysis
  ↓
checkpoint_mechanics  ←──(refine)──┐
  │                                │
  └──(approve)──→ reproduction_planning
                        ↓
                  research
                        ↓
                  checkpoint_research  ←──(add_context)──┐
                        │                                 │
                        └──(approve)──→ report_generation
                                            ↓
                                          submit_report
                                            ↓
                                           END
```

**Stages:**

| Stage | Purpose | External tools used |
|-------|---------|-------------------|
| triage | Classify bug, extract keywords, identify affected area | Jira (linked issues), GitHub (recent commits) |
| mechanics_analysis | Trace affected code paths, identify components and mechanics | GitNexus (impact, context, cypher), GitHub (file contents) |
| checkpoint_mechanics | Human review — confirm component mapping before deep research | — |
| reproduction_planning | Generate step-by-step reproduction plan from code analysis | GitNexus (processes, context), Postman (API flows) |
| research | Aggregate evidence from external sources | Grafana/Kibana (logs), Notion/Confluence (docs), Jira (history), DB queries |
| checkpoint_research | Human review — confirm research completeness, add context | — |
| report_generation | Assemble structured developer-ready bug report | All (for linking) |
| submit_report | Finalize and optionally push to Jira/issue tracker | Jira (create/update issue) |

### External Tool Integration Layer

All new tools follow the existing MCP pattern. Each external service gets a dedicated MCP server configuration in `tools.py`:

```python
_server_config = {
    "github": { ... },       # existing
    "gitnexus": { ... },     # existing
    "jira": { ... },         # NEW — Jira/YouTrack MCP
    "notion": { ... },       # NEW — Notion/Confluence MCP
    "grafana": { ... },      # NEW — Grafana/Kibana MCP
    "postman": { ... },      # NEW — Postman MCP
}
```

Each integration is **optional** — the agent degrades gracefully when a tool is not configured. The `_server_config()` function checks for credentials and only includes servers whose tokens/URLs are present in the environment.

---

## Models Changes

### New Request/Response Models

```python
class BugReportRequest(BaseModel):
    description: str                          # free-text bug description
    environment: str | None = None            # "iOS 17.4, iPhone 15, build 4.2.1"
    severity: Literal["critical", "major", "minor", "trivial"] | None = None
    repo_url: str | None = None               # optional — for code tracing
    jira_ticket: str | None = None            # optional — linked Jira issue key
    attachments: list[str] = []               # URLs to screenshots/videos/logs
    session_id: str | None = None

class TriageResult(BaseModel):
    category: str                             # "gameplay", "networking", "UI", "data", ...
    keywords: list[str]                       # extracted search terms
    affected_area: str                        # subsystem or module name
    severity_estimate: Literal["critical", "major", "minor", "trivial"]
    similar_issues: list[dict] = []           # from Jira search
    confidence: Literal["high", "medium", "low"]

class MechanicsAnalysis(BaseModel):
    components: list[AffectedComponent]       # reuses existing model
    code_paths: list[dict]                    # call chains that could produce the bug
    entry_points: list[str]                   # user-facing entry points (API, UI action, event)
    root_cause_hypotheses: list[str]          # ranked hypotheses

class ReproductionPlan(BaseModel):
    preconditions: str                        # required game state / environment setup
    steps: list[E2ETestStep]                  # reuses existing model
    expected_vs_actual: str                   # what should happen vs what the bug does
    data_requirements: list[str]              # DB records, config flags, feature toggles
    api_calls: list[dict] = []                # Postman-style request specs if relevant

class ResearchFindings(BaseModel):
    log_entries: list[dict]                   # from Grafana/Kibana
    doc_references: list[dict]               # from Notion/Confluence
    related_issues: list[dict]                # from Jira
    db_state: list[dict]                      # relevant DB records/queries
    admin_notes: list[str]                    # from runbooks
    evidence_summary: str                     # one-paragraph synthesis

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
    recommendations: list[str]                # suggested fixes
    confidence: Literal["high", "medium", "low"]
    jira_url: str | None = None               # if pushed to Jira

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

class BugReportResultEvent(BaseModel):
    type: Literal["bug_result"] = "bug_result"
    session_id: str
    report: BugReport

class ResearchProgressEvent(BaseModel):
    type: Literal["research_progress"] = "research_progress"
    source: str          # "grafana" | "kibana" | "notion" | "jira" | "db"
    finding_count: int
    summary: str
```

### New API Endpoints

```
POST   /bug-report                      — start bug reproduction pipeline
POST   /bug-report/{session_id}/continue — resume after checkpoint
GET    /bug-report/{session_id}/status   — check pipeline status
POST   /bug-report/{session_id}/export   — export report as Markdown/PDF
POST   /settings/integrations            — configure external tool credentials
GET    /settings/integrations            — list configured integrations + health
```

---

## External Tool Specifications

### Jira/YouTrack MCP

**Purpose:** Search issues, read ticket details, create/update issues for bug reports.

**Tools exposed:**
- `jira_search(jql: str)` — JQL search, returns issue summaries
- `jira_get_issue(key: str)` — full issue details (description, comments, attachments, history)
- `jira_get_comments(key: str)` — issue comment thread
- `jira_create_issue(project: str, summary: str, description: str, type: str, priority: str)` — create new issue
- `jira_update_issue(key: str, fields: dict)` — update existing issue
- `jira_link_issues(inward: str, outward: str, type: str)` — link two issues

**Config:** `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`

### Notion/Confluence MCP

**Purpose:** Search docs, read runbooks, find relevant documentation for bug context.

**Tools exposed:**
- `notion_search(query: str)` — full-text search across workspace
- `notion_get_page(page_id: str)` — read page content
- `notion_get_database(database_id: str, filter: dict)` — query a Notion database
- `confluence_search(cql: str)` — CQL search across spaces
- `confluence_get_page(page_id: str)` — read page content

**Config:** `NOTION_API_KEY`, `NOTION_WORKSPACE_ID`, `CONFLUENCE_URL`, `CONFLUENCE_TOKEN`

### Grafana/Kibana MCP

**Purpose:** Query logs and metrics to find error traces, performance anomalies, and correlate with bug timing.

**Tools exposed:**
- `grafana_query_logs(datasource: str, query: str, from_ts: str, to_ts: str)` — Loki/Elasticsearch log query
- `grafana_query_metrics(datasource: str, query: str, from_ts: str, to_ts: str)` — Prometheus/InfluxDB metric query
- `grafana_get_annotations(dashboard_id: str, from_ts: str, to_ts: str)` — fetch dashboard annotations
- `kibana_search(index: str, query: str, from_ts: str, to_ts: str)` — Elasticsearch query
- `kibana_get_log_entry(index: str, id: str)` — fetch specific log entry

**Config:** `GRAFANA_URL`, `GRAFANA_API_KEY`, `KIBANA_URL`, `KIBANA_TOKEN`

### Postman MCP

**Purpose:** Test API endpoints related to the bug, replay request sequences.

**Tools exposed:**
- `postman_list_collections()` — list available Postman collections
- `postman_get_collection(collection_id: str)` — fetch collection with all requests
- `postman_get_request(collection_id: str, request_id: str)` — single request details
- `postman_run_request(collection_id: str, request_id: str, variables: dict)` — execute a request and return response

**Config:** `POSTMAN_API_KEY`, `POSTMAN_WORKSPACE_ID`

### Network Sniffer Integration

**Purpose:** Parse captured network traffic (pcap/HAR files) to identify request/response anomalies.

**Tools exposed:**
- `sniffer_parse_har(file_path: str)` — parse HAR file, return request/response summary
- `sniffer_parse_pcap(file_path: str, filter: str)` — parse pcap with optional BPF filter
- `sniffer_find_errors(file_path: str)` — extract HTTP errors, timeouts, malformed responses

**Implementation:** Local Python tools (not MCP servers) — `pyshark` for pcap, standard JSON for HAR. These are lightweight parsers, not live capture tools.

---

## Tool Filtering by Stage (Bug Reproduction)

| Stage | GitHub | GitNexus | Jira | Notion | Grafana | Postman | Sniffer |
|-------|--------|----------|------|--------|---------|---------|---------|
| triage | get_commits, search_code | cypher | jira_search, jira_get_issue | - | - | - | - |
| mechanics | get_file_contents | impact, context, cypher | - | - | - | - | - |
| reproduction | get_file_contents | impact, context, cypher, list_processes, get_process | - | - | - | postman_get_collection, postman_get_request | - |
| research | - | cypher | jira_search, jira_get_issue, jira_get_comments | notion_search, notion_get_page, confluence_search, confluence_get_page | grafana_query_logs, kibana_search | - | sniffer_parse_har, sniffer_find_errors |
| report | - | - | jira_create_issue, jira_update_issue | - | - | - | - |

---

## Acceptance Criteria

### Bug Reproduction Pipeline
- [ ] Agent accepts free-text bug description and produces a structured BugReport
- [ ] Triage stage classifies bug category and severity with >70% accuracy
- [ ] Mechanics analysis identifies at least one relevant code path per component
- [ ] Reproduction plan produces executable steps (manually verifiable by a QA tester)
- [ ] Research stage aggregates findings from all configured external sources
- [ ] Two human-in-the-loop checkpoints (post-mechanics, post-research) work via /continue
- [ ] Report generation produces a complete BugReport with all required fields
- [ ] Full pipeline completes within 5 minutes on a realistic bug description
- [ ] Pipeline degrades gracefully when external tools are not configured (uses available tools only)

### External Tool Integrations
- [ ] Each integration is independently configurable via environment variables
- [ ] Each integration has a health check endpoint (/settings/integrations)
- [ ] Agent can search Jira issues and read ticket details
- [ ] Agent can search Notion/Confluence docs and read pages
- [ ] Agent can query Grafana/Kibana logs within a time range
- [ ] Agent can list and read Postman collections
- [ ] Agent can parse HAR files for network error patterns
- [ ] Missing credentials skip the integration (no crash, reduced capability)
- [ ] Integration tools appear in /debug/mcp/tools when configured

### Report & Export
- [ ] Bug report includes: title, severity, category, environment, reproduction steps, root cause, evidence, recommendations
- [ ] Export to Markdown produces a valid .md file
- [ ] Optional push to Jira creates an issue with all report fields mapped
