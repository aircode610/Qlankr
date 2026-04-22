# Sprint 3 Roadmap: Bug Reproduction Pipeline + External Tool Integrations

**Sprint start:** 2026-04-22
**Spec:** `specs/03-bug-reproduction/spec.md`
**Base branch:** `main`

---

## Team & Assignments

| Dev | Role | Branch | Workstream |
|-----|------|--------|------------|
| **Dev A** | Agent architect | `deva/bug-repro-agent` | Bug reproduction StateGraph, stages, prompts, orchestration |
| **Dev B** | MCP / Tools | `devb/tool-integrations` | Jira, Notion, Grafana, Kibana, Postman, sniffer MCP integrations |
| **Dev C** | Models / API | `devc/bug-report-models` | Bug report models, API endpoints, SSE events, report export |
| **Dev D** | Frontend | `devd/bug-repro-ui` | Bug input form, reproduction trace UI, report view, settings panel |

---

## Shared Contracts

### 1. models.py — Dev C owns, merges first

All devs depend on the same Pydantic models. Dev C defines `BugReportRequest`, `BugReport`, `TriageResult`, `MechanicsAnalysis`, `ReproductionPlan`, `ResearchFindings`, SSE events, and all new request/response schemas. Other branches rebase onto Dev C's merged models before opening PRs.

### 2. tools.py — Dev B owns tool config

Dev B adds new MCP server configurations and tool sets. Dev A imports `filter_tools()` with new stage names (`"bug_triage"`, `"bug_mechanics"`, `"bug_reproduction"`, `"bug_research"`, `"bug_report"`). Dev B also creates a `ToolAvailability` helper that reports which integrations are configured.

### 3. Existing pipeline untouched

The Sprint 2 impact analysis pipeline (gather → unit → checkpoint → choice → integration/e2e → submit) remains unchanged. Bug reproduction is a **parallel flow** with its own StateGraph, endpoints, and frontend views. The two pipelines share MCP clients and base models (AffectedComponent, E2ETestStep).

**Rule:** If you need a model change that affects both pipelines, coordinate with Dev C. Do not fork shared models.

---

## Phase Plan

### Phase 1 — Foundation (Week 1)

All four devs start in parallel. Dev C's models land first (day 1-2) so others can rebase.

| Task | Owner | Depends on | Deliverable |
|------|-------|------------|-------------|
| Define all new Pydantic models (bug report, triage, research, etc.) | Dev C | — | `backend/models.py` updated |
| Define new SSE events (BugStageChangeEvent, BugReportResultEvent, ResearchProgressEvent) | Dev C | — | `backend/models.py` |
| New API endpoints: POST /bug-report, /continue, /status, /export | Dev C | models | `backend/main.py` updated |
| Integration settings endpoints: GET/POST /settings/integrations | Dev C | — | `backend/main.py` |
| Jira MCP server config + tool wrappers | Dev B | — | `backend/agent/tools.py` |
| Notion/Confluence MCP server config | Dev B | — | `backend/agent/tools.py` |
| Grafana/Kibana MCP server config | Dev B | — | `backend/agent/tools.py` |
| Design bug reproduction StateGraph skeleton (nodes + edges, no logic) | Dev A | — | `backend/agent/bug_agent.py` scaffold |
| Bug reproduction state schema (BugReproductionState TypedDict) | Dev A | models | `backend/agent/bug_agent.py` |
| Bug input form component | Dev D | — | `frontend/src/components/BugInputPanel.tsx` |
| Settings/integrations UI page | Dev D | — | `frontend/src/components/SettingsPanel.tsx` |

### Phase 2 — Core Implementation (Week 1-2)

| Task | Owner | Depends on | Deliverable |
|------|-------|------------|-------------|
| Implement triage stage (classify, extract keywords, search similar issues) | Dev A | models, Jira tools | `backend/agent/stages/bug_triage.py` |
| Implement mechanics analysis stage (trace code paths, identify components) | Dev A | models, GitNexus tools | `backend/agent/stages/bug_mechanics.py` |
| Implement reproduction planning stage (generate step-by-step plan) | Dev A | mechanics stage | `backend/agent/stages/bug_reproduction.py` |
| Implement research stage (aggregate logs, docs, Jira history) | Dev A + Dev B | all tool integrations | `backend/agent/stages/bug_research.py` |
| Implement report generation stage (assemble structured report) | Dev A | research stage | `backend/agent/stages/bug_report.py` |
| Write bug reproduction prompts (BASE + per-stage) | Dev A + Dev B | all stages | `backend/agent/bug_prompts.py` |
| Postman MCP integration + collection reader | Dev B | — | `backend/agent/tools.py` |
| HAR/pcap sniffer parser tools | Dev B | — | `backend/agent/sniffer.py` |
| Tool filtering per bug reproduction stage | Dev B | stage definitions from Dev A | `backend/agent/tools.py` |
| ToolAvailability helper (which integrations are active) | Dev B | all MCP configs | `backend/agent/tools.py` |
| Bug reproduction trace view (live stage progress) | Dev D | SSE events | `frontend/src/components/BugTraceDrawer.tsx` |
| Research findings panel (logs, docs, issues aggregated) | Dev D | models | `frontend/src/components/ResearchPanel.tsx` |

### Phase 3 — Human-in-the-Loop + Report (Week 2-3)

| Task | Owner | Depends on | Deliverable |
|------|-------|------------|-------------|
| checkpoint_mechanics interrupt (user confirms component mapping) | Dev A + Dev C | mechanics stage | checkpoint logic in bug_agent |
| checkpoint_research interrupt (user confirms research completeness) | Dev A + Dev C | research stage | checkpoint logic in bug_agent |
| Session management for bug reproduction flow | Dev C | StateGraph | `backend/agent/sessions.py` updated |
| Bug report Markdown export | Dev C | BugReport model | `backend/export.py` |
| Bug report PDF export | Dev C | Markdown export | `backend/export.py` |
| Jira push (create issue from BugReport) | Dev B + Dev C | Jira tools + BugReport model | `backend/agent/stages/bug_report.py` |
| Mechanics checkpoint dialog UI | Dev D | checkpoint events | `frontend/src/components/BugCheckpointDialog.tsx` |
| Research checkpoint dialog UI | Dev D | checkpoint events | reuse BugCheckpointDialog |
| Developer-ready report view (full report display) | Dev D | BugReport model | `frontend/src/components/BugReportView.tsx` |
| Report export buttons (Markdown/PDF download) | Dev D | export endpoints | `frontend/src/components/BugReportView.tsx` |

### Phase 4 — Polish + Evaluation (Week 3-4)

| Task | Owner | Depends on | Deliverable |
|------|-------|------------|-------------|
| Per-stage budgets + timeouts for bug reproduction | Dev A | all stages working | budget config in bug_agent |
| Graceful degradation when tools are unconfigured | Dev A + Dev B | tool availability | fallback logic per stage |
| Bug reproduction evaluators (LangSmith) | Dev A | full pipeline working | `backend/evals/bug_evaluators.py` |
| Bug reproduction golden dataset (5-8 real bugs) | Dev A + Dev B | eval framework | `backend/evals/create_bug_dataset.py` |
| Integration health checks (/settings/integrations status) | Dev B | all integrations | health check per MCP server |
| Error handling for external tool failures (timeouts, auth, rate limits) | Dev B + Dev C | all integrations | safe wrappers per tool |
| End-to-end testing (bug input → report, with and without external tools) | Dev C | full pipeline | `backend/tests/agent/test_bug_pipeline.py` |
| Frontend integration tests | Dev D | all UI components | `frontend/src/__tests__/bug-repro.test.tsx` |
| Navigation: switch between Impact Analysis and Bug Reproduction modes | Dev D | both pipelines working | `frontend/src/App.tsx` updated |

---

## Merge Order

```
1. Dev C: models + API endpoints + export        → main
2. Dev B: tool integrations + sniffer + filtering → main (rebase on 1)
3. Dev A: bug reproduction agent + stages         → main (rebase on 1+2)
4. Dev D: frontend                                → main (rebase on 1+2+3)
```

---

## Integration Checkpoints

| When | What | Who |
|------|------|-----|
| End of Phase 1 | Models compile, new endpoints return 422 stubs, Jira/Notion/Grafana MCP tools list, bug input form renders | All |
| End of Phase 2 | Full bug reproduction pipeline runs end-to-end on a test bug (even without all external tools) | Dev A + B |
| End of Phase 3 | Both checkpoints work, report generated and exported as Markdown, Jira push tested | All |
| End of Phase 4 | Eval framework running, graceful degradation tested, both pipelines accessible from UI | All |

---

## Per-Developer Docs

Each developer has a comprehensive doc with their full scope, file ownership, interfaces, and acceptance criteria:

| Doc | Developer |
|-----|-----------|
| [DEV-A-bug-reproduction-agent.md](DEV-A-bug-reproduction-agent.md) | Dev A — Bug reproduction StateGraph, stages, prompts, evaluation |
| [DEV-B-tool-integrations.md](DEV-B-tool-integrations.md) | Dev B — Jira, Notion, Grafana, Kibana, Postman, sniffer MCP integrations |
| [DEV-C-models-api.md](DEV-C-models-api.md) | Dev C — Bug report models, API endpoints, SSE events, export |
| [DEV-D-frontend.md](DEV-D-frontend.md) | Dev D — Bug input, trace, report view, settings, navigation |
