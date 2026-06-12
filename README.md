# Qlankr

**AI-assisted QA for indie game studios.** Qlankr helps QA engineers figure out what to test on each pull request and reproduce bugs faster — two of the biggest time sinks in game studio QA workflows.

It connects to your GitHub repository, builds a live knowledge graph of your codebase, and runs multi-stage AI agents that reason over your code, logs, docs, and issue tracker to produce actionable output: test suggestions and developer-ready bug reports.

---

## Demo

- [QLANK1 demo](docs/vids/QLANK1.mp4)
- [QLANK2 demo](docs/vids/QLANK2.mp4)

---

## The Problem

When a new PR lands, QA engineers often don't know what to test. There's no reliable way to quickly understand which components are affected, what risks are reintroduced, or whether the change is safe to ship. The default answer is "test everything" — which is slow — or "test what seems obvious" — which misses things.

Bug reproduction is similarly painful. To write a good report a QA engineer needs to reproduce the bug reliably, collect logs, check databases, review recent commits, talk to support, and document all of it in a format the developer can actually act on. This process is scattered across tools and takes hours, sometimes days, for a single bug. The result is often a vague report that comes back with "cannot reproduce."

Qlankr automates both workflows.

---

## What It Does

### PR Impact Analysis

Connect a GitHub repository and paste a PR URL. Qlankr fetches the PR, runs it through a multi-stage agent pipeline, and produces:

- **Affected components** — which parts of the codebase are actually touched, not just which files changed
- **Risk assessment** — what's likely to break and why, derived from code relationships in the knowledge graph
- **Test suggestions** — unit tests to write for high-risk changed functions, integration tests for cross-module interactions, and E2E plans for user-facing scenarios

The analysis is interactive. After each stage you can approve the output, add context, or ask the agent to dig deeper. You choose which workflow to pursue: unit + integration tests, or E2E planning.

### Bug Reproduction

Describe a bug in plain text. The agent runs a 5-stage pipeline:

1. **Triage** — classifies severity and identifies which components and game mechanics are involved
2. **Mechanics analysis** — analyzes code paths, call graphs, and root cause hypotheses; you review before it proceeds
3. **Reproduction planning** — generates step-by-step reproduction steps with environment requirements
4. **Research** — aggregates evidence from logs (Grafana, Kibana), docs (Notion, Confluence), and tickets (Jira) in one place; you review and can add context before the final report
5. **Report generation** — synthesizes everything into a structured developer-ready report with reproduction steps, affected components, log references, and severity classification

The final report can be exported as Markdown or PDF, or pushed directly to Jira.

### Knowledge Graph

Before running analysis, Qlankr indexes your repository into a queryable knowledge graph (powered by GitNexus and KuzuDB). The graph captures function-level relationships across your codebase: callers, callees, module boundaries, execution flows. The agent uses this graph — not just file diffs — to understand impact.

The graph is visualized in the UI with Sigma.js and can be explored directly: click nodes, filter by depth, toggle edge types.

### Projects & History

Qlankr is organized around named projects. Each project maps to a GitHub repository. All PR analyses and bug reports are saved per project and can be replayed from the history view. Multiple users can share the same Qlankr instance with full data isolation via row-level security.

---

## Who It's For

Qlankr is built for **QA engineers and QA leads at small indie game studios** (roughly 1–15 person teams) who:

- Don't have a dedicated testing infrastructure team
- Are doing QA manually across multiple tools — GitHub, Jira, Notion, Grafana, Kibana
- Spend significant time on reproduction research rather than finding new bugs
- Receive bug reports back from developers with "cannot reproduce" because the reports lacked enough context

If you're a developer who also handles QA, or a QA lead trying to improve report quality and reduce back-and-forth with your dev team, this tool is for you.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Agent Engine | LangGraph StateGraphs, LangChain ReAct sub-agents, Claude (Anthropic SDK) |
| Knowledge Graph | GitNexus (MCP server), KuzuDB |
| GitHub Integration | GitHub MCP server |
| External Tools | Jira MCP, Notion MCP, Confluence MCP, Grafana MCP, Kibana MCP, Postman MCP |
| Authentication & DB | Supabase (Auth, Postgres, RLS) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS 4 |
| Graph Visualization | Sigma.js v3, Graphology |
| Export | FPDF2 (Markdown → PDF) |
| Observability | LangSmith (optional) |
| Infrastructure | Docker, Docker Compose |

---

## Prerequisites

- Docker & Docker Compose
- A free [Supabase](https://supabase.com/) project (for auth + persistence)
- An [Anthropic API key](https://console.anthropic.com/)
- A GitHub Personal Access Token (minimum `public_repo` scope)

---

## Setup

**1. Create a Supabase project.**

Sign up at https://supabase.com, create a project, and from **Project Settings → API** copy:
- *Project URL* → `SUPABASE_URL` and `VITE_SUPABASE_URL`
- *Publishable key* (`sb_publishable_…`) → `SUPABASE_ANON_KEY` and `VITE_SUPABASE_ANON_KEY`
- *Secret key* (`sb_secret_…`) → `SUPABASE_SERVICE_ROLE_KEY` (backend only — never expose to frontend)

**2. Apply the database migrations.** In the Supabase dashboard SQL Editor, run these files in order:

- `backend/migrations/0001_initial_schema.sql`
- `backend/migrations/0002_profile_trigger.sql`
- `backend/migrations/0003_project_names.sql`

Confirm the five tables (`profiles`, `projects`, `pr_analyses`, `bug_reports`, `user_credentials`) appear in the Table Editor with RLS lock icons.

**3. Configure environment:**

```bash
git clone https://github.com/<your-org>/qlankr.git
cd qlankr
cp .env.example .env
# fill in the Supabase values from step 1, plus ANTHROPIC_API_KEY and GITHUB_TOKEN
```

Note: JWTs are signed with ES256 (asymmetric); no `SUPABASE_JWT_SECRET` is needed — the backend fetches the project's public key from the JWKS endpoint.

**4. Start:**

```bash
docker compose up
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000

Sign up via the frontend, then open **Settings** to add your Anthropic API key, GitHub token, and any integration credentials (Jira, Notion, Grafana, etc.).

---

## Local Development (without Docker)

**Backend:**

```bash
cd backend
pip install -r requirements.txt
./start_local.sh        # Sources .env and starts uvicorn on :8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev             # Vite dev server on :5173
```

---

## Usage

### Step 1 — Create a project and index your repository

After signing up, create a project and enter your GitHub repository URL. Qlankr clones the repo, runs `gitnexus analyze`, and builds the knowledge graph. This takes a few minutes and is one-time per repository. Once done, the graph is visible in the UI and the repository is ready for analysis.

### Step 2 — Analyze a pull request

Paste a GitHub PR URL into the Analyze panel. The agent will:

- Fetch the PR diff, changed files, and metadata via GitHub
- Query the knowledge graph to identify blast radius and cross-module impact
- Generate unit test specs for changed functions with the highest risk
- Ask you to review and approve before proceeding
- Let you choose between integration tests or E2E planning for the next stage

Each stage streams its reasoning live in the Agent Trace drawer so you can follow what it's doing and why. Completed runs are saved to the project history and can be replayed later.

### Step 3 — Reproduce a bug

Switch to the Bug tab. Describe the bug — what happened, where, what you were doing, any attachments or Jira ticket references. The agent will run through triage, mechanics analysis, reproduction planning, and evidence research, pausing at two checkpoints for your review. The final output is a structured bug report ready to send to your dev team or push directly to Jira.

### Step 4 — Configure integrations

Open Settings from the navbar to connect external tools. Each integration shows its connection status. Connecting Jira, Grafana, Confluence, etc. makes the bug research stage substantially richer — the agent can pull in real log data, search your docs, and cross-reference tickets automatically.

Supported: **Jira**, **Notion**, **Confluence**, **Grafana**, **Kibana**, **Postman**

---

## Project Structure

```
Qlankr/
├── backend/
│   ├── main.py                 # FastAPI entry point & all API endpoints
│   ├── models.py               # Pydantic request/response/SSE models
│   ├── db.py                   # Supabase client wrapper (user-scoped queries)
│   ├── auth.py                 # JWT verification via JWKS (ES256)
│   ├── projects.py             # Project CRUD & repo URL parsing
│   ├── credentials.py          # Per-user integration credential storage
│   ├── indexer.py              # Repo clone → GitNexus → graph pipeline
│   ├── export.py               # Markdown & PDF export for bug reports
│   ├── startup.py              # Lifecycle hooks (orphaned run cleanup)
│   ├── graph_paths.py          # Filesystem layout for clones/graphs
│   ├── agent/
│   │   ├── agent.py            # LangGraph orchestration (PR analysis)
│   │   ├── bug_agent.py        # LangGraph orchestration (bug reproduction)
│   │   ├── tools.py            # MCP tool init, filtering, safety wrappers
│   │   ├── tool_health.py      # Integration health checks & credential sync
│   │   ├── prompts.py          # All system prompts (PROMPT_VERSION="2.0")
│   │   ├── sessions.py         # Session/checkpoint state management
│   │   ├── prefetch.py         # Background MCP context pre-loading
│   │   ├── sniffer.py          # HAR/pcap file parsing
│   │   ├── bug_run_registry.py # Active bug session tracking
│   │   └── stages/             # Per-stage sub-agents
│   │       ├── gather.py           # PR context (GitHub MCP)
│   │       ├── unit.py             # Unit test generation
│   │       ├── integration.py      # Integration test generation
│   │       ├── e2e.py              # E2E test planning
│   │       ├── bug_triage.py       # Bug severity & component classification
│   │       ├── bug_mechanics.py    # Code path & root cause analysis
│   │       ├── bug_reproduction.py # Reproduction step planning
│   │       ├── bug_research.py     # Evidence from logs, docs, Jira, etc.
│   │       └── bug_report.py       # Final report synthesis
│   ├── evals/                  # LangSmith evaluation suite
│   │   ├── run_evals.py            # PR analysis evaluator runner
│   │   ├── run_bug_evals.py        # Bug reproduction evaluator runner
│   │   ├── evaluators.py           # Structural + LLM-as-judge evaluators
│   │   ├── bug_evaluators.py       # Stage-specific bug evaluators
│   │   ├── create_dataset.py       # LangSmith dataset seeding
│   │   └── baselines/              # Claude Code + vanilla Claude baselines
│   ├── migrations/             # Supabase SQL migrations (run in order)
│   │   ├── 0001_initial_schema.sql
│   │   ├── 0002_profile_trigger.sql
│   │   └── 0003_project_names.sql
│   └── mcp_servers/            # Custom MCP server implementations
│       ├── grafana_server.py
│       ├── kibana_server.py
│       └── postman_server.py
├── frontend/src/
│   ├── App.tsx                 # Root routing (protected + public routes)
│   ├── auth/                   # Supabase auth context & route guards
│   ├── pages/
│   │   ├── ProjectsListPage    # Project list & navigation
│   │   ├── LegacyApp.tsx       # Main workspace (Graph/Analyze/Bug/Settings)
│   │   ├── HistoryList.tsx     # Saved runs history
│   │   ├── PrAnalysisReplay    # Replay a saved PR analysis
│   │   └── BugReportReplay     # Replay a saved bug report
│   ├── components/
│   │   ├── GraphCanvas.tsx         # Sigma.js knowledge graph
│   │   ├── PrAnalysisPanel         # PR analysis input
│   │   ├── TestPipelineResults     # Impact analysis results
│   │   ├── AgentTraceDrawer        # Live agent reasoning stream
│   │   ├── CheckpointDialog        # Human-in-the-loop approvals
│   │   ├── BugInputPanel           # Bug description form
│   │   ├── BugReportView           # Final bug report display
│   │   ├── BugTraceDrawer          # Live bug pipeline stream
│   │   ├── BugCheckpointDialog     # Bug pipeline approvals
│   │   ├── ResearchPanel           # Evidence tabs (Logs/Docs/Issues)
│   │   └── SettingsPanel           # Integration credential configuration
│   ├── hooks/                  # useAppState (Context API), useTheme
│   └── services/               # API client (SSE), Supabase client, types
├── specs/                      # Product specs & sprint reports
└── docker-compose.yml
```

---

## API Reference

### Repository & Graph

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/index` | Index a repository (SSE stream) |
| `GET` | `/repos` | List indexed repositories for current user |
| `GET` | `/graph/{owner}/{repo}` | Fetch knowledge graph for visualization |

### Projects

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/projects` | List user projects |
| `POST` | `/projects` | Create a project |
| `GET` | `/projects/{id}` | Get project detail |
| `DELETE` | `/projects/{id}` | Delete a project |
| `GET` | `/projects/{id}/pr-analyses` | List PR analysis runs for a project |
| `GET` | `/projects/{id}/bug-reports` | List bug report runs for a project |

### PR Analysis

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/analyze` | Start PR impact analysis (SSE stream) |
| `POST` | `/analyze/{session_id}/continue` | Resume after a checkpoint |
| `GET` | `/analyze/{session_id}/status` | Check session status |

### Bug Reproduction

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/bug-report` | Start bug reproduction run (SSE stream) |
| `POST` | `/bug-report/{session_id}/continue` | Resume after a checkpoint |
| `GET` | `/bug-report/{session_id}/status` | Check session status |
| `POST` | `/bug-report/{session_id}/export` | Export report as Markdown or PDF |

### Settings & Credentials

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/settings/integrations` | List integrations with health status |
| `POST` | `/settings/integrations` | Update integration credentials |
| `GET` | `/settings/credentials` | Check which credentials are configured |
| `POST` | `/settings/credentials` | Update credentials |

### SSE Event Types

All streaming endpoints emit Server-Sent Events. Event types:

| Event | When | Payload |
|---|---|---|
| `agent_step` | Each tool call in PR analysis | `{ tool, summary, stage }` |
| `stage_change` | Stage transition (PR analysis) | `{ stage, message }` |
| `checkpoint` | Human approval needed (PR analysis) | `{ type, message, options }` |
| `result` | PR analysis complete | Full `AnalyzeResponse` |
| `bug_stage_change` | Stage transition (bug pipeline) | `{ stage, message }` |
| `bug_checkpoint` | Human approval needed (bug pipeline) | `{ type, message, data }` |
| `research_progress` | Evidence found during research | `{ source, finding_count, summary }` |
| `bug_result` | Bug report complete | Full `BugReport` |
| `index_step` | Indexing progress | `{ message, progress }` |
| `index_done` | Indexing complete | `{ graph }` |
| `error` | Any failure | `{ message }` |

---

## Evaluations

Qlankr ships a LangSmith-based evaluation suite covering both pipelines.

### Datasets (seed with `python -m evals.create_dataset`)

| Dataset | Examples | Tests |
|---|---|---|
| `qlankr-eval-indexed` | 1 | PR analysis on the Qlankr repo (full GitNexus) |
| `qlankr-eval-github` | 7 | PR analysis on external repos (GitHub-only) |
| `qlankr-eval-bugs` | 5 | Bug reproduction — legacy examples |
| `qlankr-eval-bugs-real` | 6 | Real bugs from OpenTTD, Cataclysm-DDA, osu!, Luanti |
| `qlankr-eval-bugs-synthetic` | 6 | Adversarial examples targeting specific failure modes |

### Running Evals

```bash
cd backend

# PR analysis — integration path, external repos
.venv/bin/python -m evals.run_evals --suite integration --dataset github

# PR analysis — E2E path
.venv/bin/python -m evals.run_evals --suite e2e --dataset github

# Bug reproduction — real bugs
.venv/bin/python -m evals.run_bug_evals --dataset qlankr-eval-bugs-real

# Bug reproduction — adversarial
.venv/bin/python -m evals.run_bug_evals --dataset qlankr-eval-bugs-synthetic

# Skip LLM judges (free, instant)
.venv/bin/python -m evals.run_bug_evals --no-judges
```

---

## Running Tests

```bash
# Backend
docker compose run --rm backend-test

# Frontend
docker compose run --rm frontend-test

# Backend locally
cd backend && ./test.sh
```

---

## Environment Variables

### Required

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `GITHUB_TOKEN` | GitHub PAT (`public_repo` scope minimum) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase publishable key (also used by backend) |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase secret key (backend only — never expose to frontend) |
| `VITE_SUPABASE_URL` | Supabase URL for the frontend |
| `VITE_SUPABASE_ANON_KEY` | Supabase publishable key for the frontend |
| `VITE_API_URL` | Backend URL seen by the frontend |

### Optional — Observability

| Variable | Description |
|---|---|
| `LANGSMITH_API_KEY` | LangSmith tracing key |
| `LANGSMITH_TRACING` | `true` to enable LangSmith tracing |
| `LANGSMITH_ENDPOINT` | LangSmith API endpoint |
| `LANGSMITH_PROJECT` | LangSmith project name (default: `qlankr`) |

### Optional — Integrations

| Variable | Description |
|---|---|
| `JIRA_URL` | Jira instance URL |
| `JIRA_API_TOKEN` | Jira API token |
| `NOTION_API_KEY` | Notion integration token |
| `CONFLUENCE_URL` | Confluence instance URL |
| `CONFLUENCE_TOKEN` | Confluence API token |
| `GRAFANA_URL` | Grafana instance URL |
| `GRAFANA_API_KEY` | Grafana API key |
| `KIBANA_URL` | Kibana instance URL |
| `KIBANA_TOKEN` | Kibana API token |
| `POSTMAN_API_KEY` | Postman API key |

### Optional — Dev

| Variable | Description |
|---|---|
| `VITE_USE_MOCK_SSE` | `true` to stub SSE responses in frontend development |
