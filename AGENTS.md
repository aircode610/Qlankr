# AGENTS.md — Qlankr Project Context

This file gives AI coding agents fast context on what this project is, how it's structured, and how to work in it.

---

## What This Project Is

Qlankr is an AI-assisted QA tool for indie game studios. It has two core workflows:

1. **Impact analysis** — given a GitHub PR, show which components are affected, what risks exist, and what test cases to write. Full unit/integration/E2E coverage output with a code knowledge graph.
2. **Bug reproduction** — given a bug description, run a 5-stage AI pipeline (triage → mechanics → reproduction → research → report) and generate a developer-ready bug report with evidence from Jira, Grafana, Kibana, Notion, Confluence, Postman, and HAR/pcap sniffing.

---

## Repo Layout

```
Qlankr/
├── AGENTS.md                                  # This file
├── .env.example                               # All env vars with comments
├── docker-compose.yml
├── backend/
│   ├── main.py                                # FastAPI app — all API endpoints
│   ├── models.py                              # All Pydantic models (impact + bug pipeline)
│   ├── indexer.py                             # Repo indexing: clone, GitNexus CLI, registry
│   ├── export.py                              # Bug report export: Markdown, PDF, Jira push
│   ├── agent/
│   │   ├── agent.py                           # Impact analysis ReAct agent (LangGraph)
│   │   ├── bug_agent.py                       # Bug reproduction pipeline (LangGraph, 5 stages)
│   │   ├── bug_run_registry.py                # Active session registry (session_id → state)
│   │   ├── sessions.py                        # Session management helpers
│   │   ├── tools.py                           # MCP server configs, tool filtering, aliases
│   │   ├── tool_health.py                     # Health checks for all 6 integrations
│   │   ├── sniffer.py                         # Local HAR/pcap parsing tools (no credentials)
│   │   ├── prefetch.py                        # Background MCP prefetch on startup
│   │   ├── prompts.py                         # System prompts (impact analysis + bug pipeline)
│   │   └── stages/
│   │       ├── bug_triage.py                  # Stage 1: classify bug, extract key facts
│   │       ├── bug_mechanics.py               # Stage 2: identify affected code paths (checkpoint)
│   │       ├── bug_reproduction.py            # Stage 3: attempt reproduction, capture steps
│   │       ├── bug_research.py                # Stage 4: query integrations + sniffer for evidence
│   │       ├── bug_report.py                  # Stage 5: compile final structured report
│   │       ├── gather.py                      # Impact: gather PR diffs + code graph data
│   │       ├── unit.py                        # Impact: generate unit test specs
│   │       ├── integration.py                 # Impact: generate integration test specs
│   │       └── e2e.py                         # Impact: generate E2E test plans
│   ├── mcp_servers/                           # Custom Python MCP servers (stdio transport)
│   │   ├── __init__.py
│   │   ├── grafana_server.py                  # Tools: grafana_query_logs, grafana_query_metrics, grafana_get_annotations
│   │   ├── kibana_server.py                   # Tools: kibana_search, kibana_get_log_entry
│   │   └── postman_server.py                  # Tools: postman_list_collections, postman_get_collection, postman_get_request, postman_run_request
│   ├── runner/
│   │   └── executor.py                        # Shared agent execution + SSE streaming
│   ├── evals/                                 # LangSmith evals for both pipelines
│   └── tests/                                 # pytest suite
├── frontend/
│   └── src/
│       ├── App.tsx                            # Root: routing, state, layout for both workflows
│       ├── main.tsx
│       ├── components/
│       │   ├── Navbar.tsx                     # Tab switcher: Graph / Analyze / Bug / Settings
│       │   ├── GraphCanvas.tsx                # Sigma.js knowledge graph visualization
│       │   ├── RepoInput.tsx                  # Repo URL form + indexing trigger
│       │   ├── IndexingPage.tsx               # Indexing progress overlay
│       │   ├── PrAnalysisPanel.tsx            # PR URL input + impact analysis form
│       │   ├── TestPipelineResults.tsx        # Impact analysis results (components, E2E plans)
│       │   ├── AgentTraceDrawer.tsx           # Live agent step feed (impact analysis)
│       │   ├── FileTreePanel.tsx              # File tree with highlight support
│       │   ├── BugInputPanel.tsx              # Bug description form + integration selector chips
│       │   ├── BugReportView.tsx              # Bug report display + export actions
│       │   ├── BugTraceDrawer.tsx             # Live stage feed (bug pipeline)
│       │   ├── BugCheckpointDialog.tsx        # Human-in-the-loop checkpoint modal
│       │   ├── ResearchPanel.tsx              # Research findings tabs (Logs/Docs/Issues/Network)
│       │   ├── SettingsPanel.tsx              # Integration credentials configuration
│       │   ├── CheckpointDialog.tsx           # Generic checkpoint dialog
│       │   ├── ChoiceDialog.tsx               # Generic choice dialog
│       │   ├── StatusBar.tsx                  # Bottom status bar
│       │   └── UnitReviewPanel.tsx            # Unit test review panel
│       ├── services/
│       │   ├── api.ts                         # All API calls + SSE connections
│       │   └── types.ts                       # All TypeScript types
│       ├── hooks/
│       │   ├── useAppState.tsx                # Global app state hook
│       │   └── app-state/graph.tsx            # Graph-specific state
│       ├── core/graph/                        # Graph data model + adapter
│       ├── lib/
│       │   ├── lucide-icons.tsx               # Icon barrel exports
│       │   ├── graph-adapter.ts
│       │   ├── constants.ts
│       │   └── utils.ts
│       └── config/ui-constants.ts
├── docs/
│   ├── proposal.md
│   └── sprint3/
│       └── SETUP.md                           # Sprint 3 env vars, integration setup, health checks
└── specs/
    ├── requirements.md
    └── 01-impact-analysis-on-pr/
        └── spec.md
```

---

## Tech Stack

| Layer          | Choice                                                                   |
|----------------|--------------------------------------------------------------------------|
| Frontend       | React + **TypeScript** + Vite + Tailwind CSS v4                          |
| Backend        | Python + FastAPI                                                         |
| Impact agent   | LangGraph ReAct loop + Claude (`claude-sonnet-4-6`)                      |
| Bug agent      | LangGraph multi-stage pipeline + Claude (`claude-sonnet-4-6`)            |
| MCP (npm)      | GitHub MCP, GitNexus MCP, Jira (`@modelcontextprotocol/server-atlassian`), Notion (`@notionhq/notion-mcp-server`) |
| MCP (custom)   | Grafana, Kibana, Postman — custom Python stdio MCP servers in `backend/mcp_servers/` |
| Sniffer        | Local `StructuredTool` instances — no credentials, HAR/pcap parsing      |
| Knowledge graph | GitNexus MCP + GitNexus CLI                                             |
| Graph viz      | Sigma.js v3 + Graphology                                                 |
| Observability  | LangSmith (optional)                                                     |
| Infra          | Docker Compose                                                           |

**Frontend is TypeScript (`.tsx`/`.ts`).** Do not create `.jsx` or `.js` files in `frontend/src/`.

---

## Key Architectural Decisions

### Impact Analysis Pipeline
- **Two-phase workflow.** Phase 1: user connects a repo once — backend clones it, runs `gitnexus analyze`, stores in registry. Phase 2: PR analysis agent uses GitHub MCP + GitNexus MCP against the stored graph.
- **Fully autonomous.** No human-in-the-loop. Agent is a ReAct loop (25 tool calls max) that must call `submit_analysis` once to return results.
- **GitNexus tool constraints:** `impact`/`context` take symbol names (not file paths). All graph edges are `[:CodeRelation]` with `type` property. `detect_changes` uses local git diff — skip for remote PRs.

### Bug Reproduction Pipeline
- **5-stage LangGraph pipeline** with checkpoints at stage 2 (mechanics) and stage 4 (research), where a QA engineer can review findings before the pipeline continues.
- **Tool filtering per stage.** `_STAGE_TOOLS` dict in `tools.py` controls which MCP tools each stage can use. `filter_tools()` intersects available tools with the stage allowlist. `_normalize_tool_names()` handles npm MCP server aliases.
- **Integration selector.** QA engineer picks which integrations to use per run from `BugInputPanel`'s chip row. Only configured+healthy integrations are enabled by default. Unconfigured integrations show disabled with a Settings link. This avoids loading unnecessary MCP context.
- **Sniffer tools always available.** `make_sniffer_tools()` in `sniffer.py` returns `StructuredTool` instances injected into the research stage — no credentials needed.
- **Sessions.** Each bug run gets a `session_id`. State lives in `bug_run_registry.py` (in-memory). Checkpoints pause the pipeline until `POST /bug-report/{session_id}/continue`.

### MCP Integration Architecture
| Integration | Approach | Package/Module |
|-------------|----------|----------------|
| Jira | Official npm MCP | `@modelcontextprotocol/server-atlassian` |
| Notion | Official npm MCP | `@notionhq/notion-mcp-server` |
| Confluence | Official npm MCP | `@modelcontextprotocol/server-atlassian` (separate config entry) |
| Grafana | Custom Python MCP | `backend/mcp_servers/grafana_server.py` |
| Kibana | Custom Python MCP | `backend/mcp_servers/kibana_server.py` |
| Postman | Custom Python MCP | `backend/mcp_servers/postman_server.py` |

Custom Python servers give exact tool names matching `BUG_RESEARCH_TOOLS` — no aliases needed. npm servers expose generic names and require alias dicts (`JIRA_TOOL_ALIASES`, `NOTION_TOOL_ALIASES`, `CONFLUENCE_TOOL_ALIASES`, merged into `ALL_TOOL_ALIASES`).

### Streaming
All long-running operations (indexing, impact analysis, bug pipeline) stream via SSE. The frontend connects with `EventSource` or `fetch` with `ReadableStream`. Event types for the bug pipeline: `bug_stage_change`, `bug_checkpoint`, `research_progress`, `bug_result`, `bug_error`.

---

## API

### Impact Analysis
```
POST /index                        # Index a repo; SSE stream of indexing events
GET  /graph/{owner}/{repo}         # Knowledge graph JSON for Sigma.js
POST /analyze                      # Analyze a PR; SSE stream of agent steps + result
```

### Bug Reproduction (Sprint 3)
```
POST /bug-report                   # Start a bug run; body: BugReportRequest; SSE stream
POST /bug-report/{session_id}/continue   # Send checkpoint response to resume pipeline
GET  /bug-report/{session_id}/export     # Export report: ?format=markdown|pdf&push_to_jira=true
```

### Settings & Integrations (Sprint 3)
```
GET  /settings/integrations        # Returns configured/healthy status for all 6 integrations
POST /settings/integrations        # Save integration credentials (writes to env)
```

### Debug (dev only)
```
GET  /debug/mcp/tools              # List all MCP tools visible to the backend
GET  /debug/mcp/repos              # Call list_repos and return raw response
POST /debug/mcp/call               # Call any MCP tool: { "tool": "<name>", "args": {...} }
```

---

## Environment Variables

See `docs/sprint3/SETUP.md` for the full guide with where to get each credential and health check endpoints.

```bash
# Core (required)
ANTHROPIC_API_KEY=
GITHUB_TOKEN=
VITE_API_URL=http://localhost:8000

# Observability (optional)
LANGSMITH_API_KEY=
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=qlankr

# Jira (optional)
JIRA_URL=
JIRA_EMAIL=
JIRA_API_TOKEN=
JIRA_PROJECT_KEY=

# Notion (optional)
NOTION_API_KEY=
NOTION_WORKSPACE_ID=

# Confluence (optional)
CONFLUENCE_URL=
CONFLUENCE_TOKEN=
CONFLUENCE_SPACE_KEY=

# Grafana (optional)
GRAFANA_URL=
GRAFANA_API_KEY=

# Kibana / Elasticsearch (optional)
KIBANA_URL=
KIBANA_TOKEN=

# Postman (optional)
POSTMAN_API_KEY=
POSTMAN_WORKSPACE_ID=
```

All integrations are optional — the pipeline falls back to GitHub-only analysis if none are configured. Set only the ones relevant to your studio's stack.

---

## Running Locally

```bash
cp .env.example .env
# Fill in ANTHROPIC_API_KEY, GITHUB_TOKEN, and any optional integrations

docker compose up
# Frontend: http://localhost:5173
# Backend:  http://localhost:8000
```

Verify integration health:
```bash
curl http://localhost:8000/settings/integrations | python3 -m json.tool
curl http://localhost:8000/debug/mcp/tools | python3 -m json.tool | grep '"name"'
```

Run backend standalone (for debugging):
```bash
cd backend
python -m uvicorn main:app --reload
```

Run tests:
```bash
cd backend
python -m pytest tests/ -v
```

---

## Where to Find Things

| What you're looking for | Where |
|-------------------------|-------|
| All env vars + integration setup | `docs/sprint3/SETUP.md` |
| Product requirements + backlog | `specs/requirements.md` |
| Sprint 1 spec + API contract | `specs/01-impact-analysis-on-pr/spec.md` |
| Pydantic models (all) | `backend/models.py` |
| MCP server configs + tool filtering | `backend/agent/tools.py` |
| Integration health checks | `backend/agent/tool_health.py` |
| Bug pipeline entry point | `backend/agent/bug_agent.py` |
| Impact analysis entry point | `backend/agent/agent.py` |
| All API endpoints | `backend/main.py` |
| Bug report export logic | `backend/export.py` |
| Custom MCP servers | `backend/mcp_servers/` |
| Sniffer (HAR/pcap) tools | `backend/agent/sniffer.py` |
| Frontend types | `frontend/src/services/types.ts` |
| Frontend API calls | `frontend/src/services/api.ts` |
| Icon exports | `frontend/src/lib/lucide-icons.tsx` |
| Tailwind theme tokens | `frontend/src/config/ui-constants.ts` |
| Debug endpoints | `GET /debug/mcp/tools`, `GET /debug/mcp/repos`, `POST /debug/mcp/call` |
