# Sprint 3 Roadmap v2: Bug Reproduction Pipeline + External Tool Integrations

**Sprint start:** 2026-04-22
**Base branch:** `main`

---

## Team & Assignments

| Person | Skills | Branch | Workstream |
|--------|--------|--------|------------|
| **Person 1** | Agent + backend + frontend | `p1/bug-repro-stages` | StateGraph stages 1-3, tool filtering, evaluators (triage/mechanics/reproduction), BugTraceDrawer |
| **Person 2** | Agent + backend + frontend | `p2/bug-repro-research-report` | StateGraph stages 4-5 + checkpoints + wiring, all prompts, evaluators (research/report), BugCheckpointDialog + ResearchPanel |
| **Person 3** | Backend + frontend | `p3/models-api-integration` | Models (critical path), API endpoints, sessions, export, Jira MCP, settings UI, **final merge integration** |
| **Person 4** | Backend + frontend | `p4/tool-integrations-ui` | Grafana/Kibana custom MCP servers, Notion/Confluence/Postman MCP, sniffer, health checks, BugInputPanel + BugReportView + nav |

> **Golden dataset** (`backend/evals/create_bug_dataset.py`) — built together as a team, not assigned to any single person.

---

## Detailed Scope

### Person 1 — Agent (stages 1-3) + BugTraceDrawer

**Files owned:**
- `backend/agent/stages/bug_triage.py`
- `backend/agent/stages/bug_mechanics.py`
- `backend/agent/stages/bug_reproduction.py`
- `backend/evals/bug_evaluators.py` (partial — triage/mechanics/reproduction evaluators)
- `frontend/src/components/BugTraceDrawer.tsx`

**Scope:**
- Triage stage — classify bug, extract keywords, estimate severity, search similar issues via Jira + code graph (8 tool call budget)
- Mechanics analysis stage — trace code paths, identify components, generate ranked root cause hypotheses (15 tool call budget)
- Reproduction planning stage — translate confirmed code paths into step-by-step QA-readable reproduction steps (12 tool call budget)
- Tool filtering: extend `_STAGE_TOOLS` with `BUG_TRIAGE_TOOLS`, `BUG_MECHANICS_TOOLS`, `BUG_REPRODUCTION_TOOLS` sets in `tools.py`
- Evaluators: `triage_accuracy`, `mechanics_grounding`, `reproduction_executability`
- `BugTraceDrawer` — live stage progress component, maps SSE events to stage indicators (pending / running / checkpoint / completed / error), shows per-tool-call detail under each stage

**Interfaces consumed:**
- `filter_tools()` from `tools.py` (Person 4 extends, Person 1 calls)
- All models from `backend/models.py` (Person 3 defines)
- `BugReproductionState` TypedDict defined together with Person 2

---

### Person 2 — Agent (stages 4-5 + wiring) + Prompts + BugCheckpointDialog + ResearchPanel

**Files owned:**
- `backend/agent/bug_agent.py` — full StateGraph wiring + entry points
- `backend/agent/stages/bug_research.py`
- `backend/agent/stages/bug_report.py`
- `backend/agent/bug_prompts.py` — all prompts (BUG_BASE_PROMPT + all 5 stage prompts)
- `backend/evals/bug_evaluators.py` (partial — research/report evaluators)
- `frontend/src/components/BugCheckpointDialog.tsx`
- `frontend/src/components/ResearchPanel.tsx`

**Scope:**
- Research stage — query all configured external sources (Jira, Notion, Confluence, Grafana, Kibana, Sniffer), emit `ResearchProgressEvent` per source, fail-safe per source (20 tool call budget)
- Report generation stage — assemble `BugReport` from all stage outputs, compute confidence, optionally push to Jira (5 tool call budget)
- `checkpoint_mechanics` node — interrupt, expose components + hypotheses, route to approve or refine
- `checkpoint_research` node — interrupt, expose evidence summary, route to approve or add_context
- Full StateGraph wiring: nodes, edges, conditional edges, `_mechanics_router`, `_research_router`
- `run_bug_agent()` and `continue_bug_agent()` async entry points
- `BUG_BASE_PROMPT` + `BUG_TRIAGE_PROMPT`, `BUG_MECHANICS_PROMPT`, `BUG_REPRODUCTION_PROMPT`, `BUG_RESEARCH_PROMPT`, `BUG_REPORT_PROMPT` — all quick but centralised here
- Evaluators: `bug_pipeline_health`, `research_coverage`, `report_completeness`, `report_actionability`, `evidence_quality`, `tool_efficiency`, `graceful_degradation`
- `BugCheckpointDialog` — two checkpoint variants (post-mechanics: components + hypotheses + approve/refine; post-research: evidence summary + approve/add_context)
- `ResearchPanel` — tabbed view of research findings (Logs / Docs / Issues / Network), per-source counts + empty states

**Interfaces consumed:**
- `get_available_integrations()` from `tools.py` (Person 4)
- All MCP tools from Person 4's integrations
- All models from Person 3

---

### Person 3 — Models + API + Jira + Settings UI + Merge Integration

**Files owned:**
- `backend/models.py` — all new Pydantic models + SSE events
- `backend/main.py` — new bug report + settings endpoints
- `backend/export.py` — Markdown + PDF export
- `backend/agent/sessions.py` — extend for bug reproduction sessions
- `backend/agent/tools.py` (Jira MCP config only)
- `frontend/src/components/SettingsPanel.tsx`
- `frontend/src/services/api.ts` — new API client functions
- `frontend/src/services/types.ts` — TypeScript types

**Scope:**

*Models (merge first — everyone rebases on this):*
- Request models: `BugReportRequest`, `BugContinueRequest`, `ExportRequest`, `IntegrationConfigRequest`
- Stage output models: `TriageResult`, `CodePath`, `MechanicsAnalysis`, `ReproductionPlan`, `LogEntry`, `DocReference`, `RelatedIssue`, `ResearchFindings`
- Response models: `BugReport`, `BugReportResponse`, `IntegrationStatus`, `IntegrationSettingsResponse`
- SSE events: `BugStageChangeEvent`, `BugCheckpointEvent`, `ResearchProgressEvent`, `BugReportResultEvent`, `ExportReadyEvent`

*API endpoints:*
- `POST /bug-report` — start pipeline, return SSE stream
- `POST /bug-report/{session_id}/continue` — resume after checkpoint
- `GET /bug-report/{session_id}/status` — current session stage
- `POST /bug-report/{session_id}/export` — Markdown or PDF download
- `GET /settings/integrations` — list integration statuses
- `POST /settings/integrations` — update integration credentials

*Sessions:* extend `Session` with `SessionType` enum, `bug_description`, `bug_report` fields, `to_status_dict()`, `get_bug_report()` helpers

*Export:* `export_markdown(report)` and `export_pdf(report)` — full structured document with all report sections

*Jira MCP:* server config (`JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`), tool wrappers: `jira_search`, `jira_get_issue`, `jira_get_comments`, `jira_create_issue`, `jira_update_issue`, tool name alias normalization layer

*Settings UI:* `SettingsPanel` — integration cards per tool (Jira, Notion, Confluence, Grafana, Kibana, Postman), status indicators (connected / misconfigured / not configured), per-integration "Test Connection", masked credential fields, Save All

*TypeScript types:* mirror all new Pydantic models as TS interfaces in `types.ts`; new API client functions in `api.ts`

**Merge integration (final responsibility):**
- After Person 1, 2, 4 open their PRs: review, resolve conflicts, verify the full pipeline runs end-to-end
- Run smoke test: POST /bug-report → SSE stream → both checkpoints → final report → export
- Coordinate rebase order: models branch → integrations → agent → merge all into main

---

### Person 4 — MCP Integrations + Sniffer + Health Checks + BugInputPanel + BugReportView + Nav

**Files owned:**
- `backend/mcp_servers/grafana_server.py` — custom MCP server
- `backend/mcp_servers/kibana_server.py` — custom MCP server
- `backend/mcp_servers/postman_server.py` — custom MCP server
- `backend/mcp_servers/__init__.py`
- `backend/agent/sniffer.py`
- `backend/agent/tool_health.py`
- `backend/agent/tools.py` (Notion, Confluence, Grafana, Kibana, Postman configs + `get_available_integrations()` + `BUG_RESEARCH_TOOLS` + `BUG_REPORT_TOOLS` in `_STAGE_TOOLS`)
- `.env.example`
- `frontend/src/components/BugInputPanel.tsx`
- `frontend/src/components/BugReportView.tsx`
- `frontend/src/App.tsx` — navigation update + `useBugReproState` hook

**Scope:**

*Grafana custom MCP server* — `grafana_query_logs`, `grafana_query_metrics`, `grafana_get_annotations` (Loki/Elasticsearch datasource via `httpx`)

*Kibana custom MCP server* — `kibana_search`, `kibana_get_log_entry`

*Notion MCP* — community server config, `notion_search`, `notion_get_page`, `notion_get_database`

*Confluence MCP* — community server config, `confluence_search`, `confluence_get_page`

*Postman custom MCP server* — `postman_list_collections`, `postman_get_collection`, `postman_get_request`, `postman_run_request` (marked `requires_confirmation: true`)

*Sniffer tools* — `sniffer_parse_har`, `sniffer_find_errors`, `sniffer_parse_pcap` (stdlib JSON for HAR, `pyshark` optional for pcap)

*Tool health checks* — `check_integration_health(name)` and `check_all_integrations()` per integration (lightweight HTTP ping per service)

*`get_available_integrations()`* — returns list of configured + reachable integration names, called by Person 2's research stage

*Tool filtering* — extend `_STAGE_TOOLS` with `BUG_RESEARCH_TOOLS` and `BUG_REPORT_TOOLS`

*`.env.example`* — add all new env vars (JIRA, NOTION, CONFLUENCE, GRAFANA, KIBANA, POSTMAN)

*`BugInputPanel`* — bug description form (description, environment, severity, repo URL, Jira ticket, attachments), integration availability dots, validation, submit triggers SSE stream

*`BugReportView`* — full report display (reproduction steps, root cause, evidence tabs, affected components, recommendations), Export Markdown / Export PDF / Push to Jira buttons, copy-to-clipboard per section

*`App.tsx`* — tab navigation between Impact Analysis and Bug Reproduction modes, shared graph canvas, `useBugReproState` hook (manages mode / sessionId / stages / checkpointData / researchProgress / report / error)

---

## Merge Order

```
1. Person 3: models + API endpoints + sessions + export   → main  (day 1-2, everyone rebases on this)
2. Person 4: all MCP integrations + sniffer + health      → main  (rebase on 1)
3. Person 1: stages 1-3 + tool filtering + evaluators     → main  (rebase on 1+2)
4. Person 2: stages 4-5 + checkpoints + wiring + prompts  → main  (rebase on 1+2+3)
5. Person 3: final integration pass                        → main  (smoke test, conflict resolution, sign-off)
```

---

## Shared Contracts

### BugReproductionState (co-owned by P1 + P2, defined in bug_agent.py)

```python
class BugReproductionState(TypedDict):
    description: str
    environment: str | None
    severity_input: str | None
    repo_name: str | None
    jira_ticket: str | None
    attachments: list[str]
    session_id: str
    repo_stats: dict
    processes: list[dict]
    triage: dict
    mechanics: dict
    reproduction_plan: dict
    research_findings: dict
    bug_report: dict
    current_stage: str
    tool_calls_used: int
    messages: list
    available_tools: list[str]
    mechanics_feedback: str | None
    research_context: str | None
```

### Stage tool budgets

| Stage | Budget | Timeout |
|-------|--------|---------|
| triage | 8 calls | 60s |
| mechanics_analysis | 15 calls | 90s |
| reproduction_planning | 12 calls | 90s |
| research | 20 calls | 120s |
| report_generation | 5 calls | 60s |

### SSE event ownership

| Event | Emitted by | Consumed by |
|-------|-----------|-------------|
| `bug_stage_change` | P1/P2 agent stages | P4 BugTraceDrawer |
| `agent_step` | P1/P2 agent stages | P4 BugTraceDrawer |
| `research_progress` | P2 research stage | P4 BugTraceDrawer |
| `bug_checkpoint` | P2 checkpoint nodes | P2 BugCheckpointDialog |
| `bug_result` | P2 report stage | P4 BugReportView |
| `export_ready` | P3 export endpoint | P4 BugReportView |

---

## Phase Plan

### Phase 1 — Foundation (Week 1, days 1-3)

Person 3 lands models first. Everyone else scaffolds against the spec.

| Task | Owner | Deliverable |
|------|-------|-------------|
| All new Pydantic models + SSE events | P3 | `backend/models.py` |
| API endpoint stubs (return 501) | P3 | `backend/main.py` |
| Session management extension | P3 | `backend/agent/sessions.py` |
| StateGraph skeleton + `BugReproductionState` | P1 + P2 | `backend/agent/bug_agent.py` scaffold |
| Triage stage shell | P1 | `bug_triage.py` scaffold |
| Grafana + Kibana custom MCP servers | P4 | `mcp_servers/grafana_server.py`, `kibana_server.py` |
| Notion + Confluence MCP config | P4 | `tools.py` |
| `BugInputPanel` component | P4 | `BugInputPanel.tsx` |
| `SettingsPanel` component | P3 | `SettingsPanel.tsx` |
| TypeScript types + API client stubs | P3 | `types.ts`, `api.ts` |

### Phase 2 — Core Implementation (Week 1-2)

| Task | Owner | Depends on |
|------|-------|------------|
| Triage stage full implementation | P1 | models, Jira tools |
| Mechanics analysis stage | P1 | models |
| Reproduction planning stage | P1 | mechanics stage |
| Tool filtering for all 5 bug stages | P1 + P4 | stage definitions |
| Research stage | P2 | all MCP tools from P4 |
| Report generation stage | P2 | research stage |
| Both checkpoint nodes | P2 | mechanics + research stages |
| Graph wiring + entry points | P2 | all stages |
| All bug prompts | P2 | stage definitions |
| Postman MCP server | P4 | — |
| Sniffer tools (HAR + pcap) | P4 | — |
| `get_available_integrations()` | P4 | all MCP configs |
| Jira MCP + tool aliases | P3 | — |
| `BugTraceDrawer` | P1 | SSE events defined |
| `BugCheckpointDialog` | P2 | checkpoint events |
| `ResearchPanel` | P2 | models |

### Phase 3 — Polish + Integration (Week 2-3)

| Task | Owner | Depends on |
|------|-------|------------|
| Export: Markdown + PDF | P3 | BugReport model |
| Jira push from report stage | P3 + P2 | Jira tools + BugReport |
| Health checks (`tool_health.py`) | P4 | all integrations |
| `/settings/integrations` endpoint wired | P3 | health checks from P4 |
| `BugReportView` full implementation | P4 | BugReport model, export endpoints |
| App.tsx navigation + `useBugReproState` | P4 | both pipelines |
| Per-stage budgets + timeouts enforced | P1 + P2 | stages working |
| Graceful degradation (zero tools) | P1 + P2 + P4 | tool availability |
| LangSmith evaluators | P1 (triage/mechanics/repro) + P2 (research/report) | full pipeline |

### Phase 4 — Merge + Sign-off (Week 3)

| Task | Owner |
|------|-------|
| Golden dataset (5-8 bugs) | **Team together** |
| End-to-end smoke test | P3 (integration lead) |
| Conflict resolution across all branches | P3 |
| Final merge to main in order | P3 |
| Verify Sprint 2 impact analysis pipeline untouched | P3 |

---

## Integration Checkpoints

| When | What | Who verifies |
|------|------|-------------|
| End of Phase 1 | Models compile, endpoint stubs return 501, at least one MCP tool visible in `/debug/mcp/tools`, bug input form renders | P3 |
| End of Phase 2 | Full pipeline runs on a test bug (zero external tools), both checkpoints fire, report generated | P1 + P2 |
| End of Phase 3 | Markdown export downloads, Jira push creates issue, all integration health checks return status, full UI flow works | P3 |
| End of Phase 4 | Evaluators run in LangSmith, golden dataset loaded, Sprint 2 pipeline unchanged, clean merge to main | P3 (integration lead) |

---

## Acceptance Criteria Summary

**Pipeline:**
- [ ] Bug reproduction StateGraph with 8 nodes visible in LangSmith traces
- [ ] Each stage only calls tools from its allowed subset
- [ ] Per-stage tool budgets enforced
- [ ] Both checkpoints pause and resume correctly
- [ ] Pipeline completes with zero external tools configured
- [ ] Pipeline completes within 5 minutes on a realistic bug

**Output:**
- [ ] `BugReport` contains all fields (title, severity, steps, root cause, evidence, recommendations, confidence)
- [ ] Markdown export produces a complete readable document
- [ ] PDF export produces valid PDF bytes
- [ ] Jira push creates an issue and returns the URL

**Integrations:**
- [ ] Jira, Notion, Confluence, Grafana, Kibana, Postman — each optional, silently skipped if not configured
- [ ] Health checks surface status at `/settings/integrations`
- [ ] Sniffer parses HAR files and extracts HTTP errors

**Frontend:**
- [ ] Bug input form → trace drawer → checkpoints → report view full flow works
- [ ] Research stage shows per-source progress
- [ ] Export buttons trigger correct downloads
- [ ] Navigation between Impact Analysis and Bug Reproduction preserves state
- [ ] Sprint 2 UI unchanged

**Evaluators:**
- [ ] All 10 evaluators run and produce baseline metrics in LangSmith
- [ ] Graceful degradation evaluator confirms pipeline completes with 0 tools
