# Sprint 2 Roadmap: Three-Stage Testing Pipeline + GitNexus UI

**Sprint start:** 2026-04-09
**Spec:** `specs/02-testing-pipeline/spec.md`
**Base branch:** `main`

---

## Team & Assignments

| Dev | Role | Branch | Workstream |
|-----|------|--------|------------|
| **Dev A — Amirali** | Agent architect | `amirali/agent-v2` | Agent StateGraph rewrite, session management, orchestration |
| **Dev B** | Backend / MCP | `devb/mcp-tools` | GitNexus MCP integration, embeddings, process resources, prefetch |
| **Dev C** | Backend / Models | `devc/testing-models` | Shared Pydantic models, API endpoints, SSE events, submit_analysis schema |
| **Dev D** | Frontend | `devd/gitnexus-ui` | GitNexus UI integration, Qlankr panels, results view, checkpoint dialog |

---

## Shared Contract: models.py

All four developers depend on the same Pydantic models. **Dev C owns `backend/models.py`** and merges first. All other branches rebase onto Dev C's merged models before opening their PRs.

The canonical model definitions are documented in:
- `docs/sprint2/DEV-C-models-api.md` (full schemas)
- `specs/02-testing-pipeline/spec.md` (Models Changes section)

**Rule:** If you need a model change, open a PR against Dev C's branch or coordinate synchronously. Do not create local copies of shared models.

---

## Phase Plan

### Phase 1 — Shared Foundation (Week 1)

All four devs start in parallel. Dev C's models land first (day 1-2) so others can rebase.

| Task | Owner | Depends on | Deliverable |
|------|-------|------------|-------------|
| Define all new Pydantic models + SSE events | Dev C | — | `backend/models.py` updated |
| Update API endpoints (analyze, continue, status) | Dev C | models | `backend/main.py` updated |
| Enable `--embeddings` in indexer | Dev B | — | `backend/indexer.py` |
| Expose all 16 MCP tools + process resources | Dev B | — | `backend/agent/tools.py` |
| Design StateGraph skeleton (nodes + edges, no logic) | Dev A | — | `backend/agent/agent.py` scaffold |
| Fork GitNexus web UI, set up build pipeline | Dev D | — | `frontend/` replaced |

### Phase 2 — Core Implementation (Week 1-2)

| Task | Owner | Depends on | Deliverable |
|------|-------|------------|-------------|
| Implement gather stage + prefetch | Dev A + Dev B | Phase 1 | `backend/agent/stages/gather.py`, `backend/agent/prefetch.py` |
| Implement unit test stage | Dev A | models, MCP tools | `backend/agent/stages/unit.py` |
| Implement integration test stage | Dev A | unit stage | `backend/agent/stages/integration.py` |
| Implement E2E test plan stage | Dev A | integration stage | `backend/agent/stages/e2e.py` |
| Update system prompt for 3-stage workflow | Dev A + Dev B | all stages | `backend/agent/prompts.py` |
| Add Qlankr panels to GitNexus UI | Dev D | models (SSE events) | `PrAnalysisPanel`, `AgentTraceDrawer` |
| 3-stage results view component | Dev D | models | `TestPipelineResults` |

### Phase 3 — Human-in-the-Loop + Polish (Week 2-3)

| Task | Owner | Depends on | Deliverable |
|------|-------|------------|-------------|
| Session state persistence | Dev A | StateGraph | `backend/agent/sessions.py` |
| Checkpoint events + /continue endpoint | Dev A + Dev C | sessions, models | checkpoint logic in agent + endpoint |
| Stage-specific tool filtering | Dev A + Dev B | all stages | tool subsets per stage |
| Per-stage budgets + timeouts | Dev A | stages | budget config |
| Checkpoint dialog UI | Dev D | checkpoint events | `CheckpointDialog` component |
| Graph highlighting of affected nodes | Dev D | results data | KnowledgeGraph update |
| Optional user context for E2E | Dev C + Dev A | models | `AnalyzeRequest.context` wired through |

### Phase 4 — Container Execution (Week 3-4, after everything else works)

| Task | Owner | Depends on | Deliverable |
|------|-------|------------|-------------|
| Test code generation in unit + integration stages | Dev A | stages working | `generated_code` field populated |
| Test runner container spec | Dev B | — | `backend/runner/Dockerfile.runner` |
| Container orchestration + executor | Dev B | runner container | `backend/runner/executor.py` |
| /run-tests endpoint + SSE stream | Dev C | executor | endpoint in `main.py` |
| Test execution results UI | Dev D | SSE stream | `TestExecutionPanel` component |
| Container cleanup + resource limits | Dev B | executor | cleanup logic |

---

## Merge Order

```
1. Dev C: models + API endpoints         → main
2. Dev B: MCP tools + embeddings          → main (rebase on 1)
3. Dev A: agent StateGraph + stages       → main (rebase on 1+2)
4. Dev D: frontend                        → main (rebase on 1+2+3)
5. All: Phase 4 container work            → main (after 1-4 stable)
```

---

## Integration Checkpoints

| When | What | Who |
|------|------|-----|
| End of Phase 1 | Models compile, endpoints return 422 stubs, MCP tools list, UI builds | All |
| End of Phase 2 | Full analysis runs with 3-stage output on a test PR (Luanti or osu!) | Dev A + B |
| End of Phase 3 | Human-in-the-loop works end-to-end through the UI | All |
| End of Phase 4 | Generated tests run in container, results stream to UI | All |

---

## Per-Developer Docs

Each developer has a comprehensive doc with their full scope, file ownership, interfaces, and acceptance criteria:

| Doc | Developer |
|-----|-----------|
| [DEV-A-agent-orchestration.md](DEV-A-agent-orchestration.md) | Amirali — Agent StateGraph, stages, sessions, prompts |
| [DEV-B-mcp-integration.md](DEV-B-mcp-integration.md) | Dev B — GitNexus MCP, embeddings, processes, container runner |
| [DEV-C-models-api.md](DEV-C-models-api.md) | Dev C — Shared models, API endpoints, SSE events |
| [DEV-D-frontend.md](DEV-D-frontend.md) | Dev D — GitNexus UI, Qlankr panels, results view |
