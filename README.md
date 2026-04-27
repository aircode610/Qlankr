# Qlankr

**AI-assisted QA for indie game studios.** Qlankr helps QA engineers figure out what to test on each pull request and reproduce bugs faster — two of the biggest time sinks in game studio QA workflows.

It connects to your GitHub repository, builds a live knowledge graph of your codebase, and runs multi-stage AI agents that reason over your code, logs, docs, and issue tracker to produce actionable output: test suggestions and developer-ready bug reports.

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

The analysis is interactive. After each stage you can approve the output, add context, or ask the agent to dig deeper. You choose which workflow to pursue: unit+integration tests, or E2E planning.

### Bug Reproduction

Describe a bug in plain text. The agent runs a 7-stage pipeline:

1. **Triage** — classifies severity and identifies which components and game mechanics are involved
2. **Mechanics analysis** — analyzes code paths, call graphs, and root cause hypotheses; you review before it proceeds
3. **Reproduction planning** — generates step-by-step reproduction steps with environment requirements
4. **Research** — aggregates evidence from logs (Grafana, Kibana), docs (Notion, Confluence), and tickets (Jira) in one place
5. **Research checkpoint** — you review the evidence and can redirect before the final report
6. **Report generation** — synthesizes everything into a structured developer-ready report with reproduction steps, affected components, log references, and severity classification

The final report can be exported as Markdown or PDF.

### Knowledge Graph

Before running analysis, Qlankr indexes your repository into a queryable knowledge graph (powered by GitNexus and KuzuDB). The graph captures function-level relationships across your codebase: callers, callees, module boundaries, execution flows. The agent uses this graph — not just file diffs — to understand impact.

The graph is visualized in the UI with Sigma.js and can be explored directly: click nodes, filter by depth, toggle edge types.

---

## Who It's For

Qlankr is built for **QA engineers and QA leads at small indie game studios** (roughly 1–15 person teams) who:

- Don't have a dedicated testing infrastructure team
- Are doing QA manually across multiple tools — GitHub, Jira, Notion, Grafana, Kibana, Slack
- Spend significant time on reproduction research rather than finding new bugs
- Receive bug reports back from developers with "cannot reproduce" because the reports lacked enough context

If you're a developer who also handles QA, or a QA lead trying to improve report quality and reduce back-and-forth with your dev team, this tool is for you.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Agent Engine | LangGraph, Claude (Anthropic SDK) |
| Knowledge Graph | GitNexus (MCP server), KuzuDB |
| GitHub Integration | GitHub MCP server |
| External Tools | Jira MCP, Notion, Confluence, Grafana, Kibana |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS 4 |
| Graph Visualization | Sigma.js v3, Graphology |
| Export | FPDF2 (Markdown → PDF) |
| Observability | LangSmith (optional) |
| Infrastructure | Docker, Docker Compose |

---

## Prerequisites

- Docker & Docker Compose
- An [Anthropic API key](https://console.anthropic.com/)
- A GitHub Personal Access Token (minimum `public_repo` scope)

---

## Setup

**1. Clone and configure:**

```bash
git clone https://github.com/<your-org>/qlankr.git
cd qlankr
cp .env.example .env
```

**2. Fill in `.env`:**

```bash
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...
VITE_API_URL=http://localhost:8000

# Optional — enables LangSmith tracing
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_PROJECT=qlankr
```

Third-party integrations (Jira, Notion, Confluence, Grafana, Kibana) are configured at runtime through the Settings UI — no environment variables needed for those.

**3. Start:**

```bash
docker compose up
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000

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

### Step 1 — Index your repository

On first launch, enter your GitHub repository URL. Qlankr clones the repo, runs `gitnexus analyze`, and builds the knowledge graph. This takes a few minutes and is one-time per repository. Once done, the graph is visible in the UI and the repository is ready for analysis.

### Step 2 — Analyze a pull request

Paste a GitHub PR URL into the Analyze panel. The agent will:

- Fetch the PR diff, changed files, and metadata via GitHub
- Query the knowledge graph to identify blast radius and cross-module impact
- Generate unit test specs for changed functions with the highest risk
- Ask you to review and approve before proceeding
- Let you choose between integration tests or E2E planning for the next stage

Each stage streams its reasoning live in the Agent Trace drawer so you can follow what it's doing and why.

### Step 3 — Reproduce a bug

Switch to the Research view. Describe the bug — what happened, where, what you were doing, any attachments or Jira ticket references. The agent will run through triage, mechanics analysis, reproduction planning, and evidence research, pausing at two checkpoints for your review. The final output is a structured bug report ready to send to your dev team.

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
│   ├── indexer.py              # Repo clone → GitNexus → graph pipeline
│   ├── export.py               # Markdown & PDF export for bug reports
│   ├── agent/
│   │   ├── agent.py            # LangGraph orchestration (PR analysis)
│   │   ├── bug_agent.py        # LangGraph orchestration (bug reproduction)
│   │   ├── tools.py            # MCP tool initialization, filtering, wrapping
│   │   ├── tool_health.py      # Integration health checks & credential sync
│   │   ├── prompts.py          # System prompts
│   │   ├── sessions.py         # Session/checkpoint persistence
│   │   ├── bug_run_registry.py # Active bug session registry
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
│   └── evals/                  # Evaluation suite
├── frontend/
│   └── src/
│       ├── App.tsx
│       ├── components/
│       │   ├── GraphCanvas.tsx       # Sigma.js knowledge graph
│       │   ├── PrAnalysisPanel.tsx   # PR analysis input
│       │   ├── AgentTraceDrawer.tsx  # Live agent reasoning
│       │   ├── TestPipelineResults.tsx
│       │   ├── CheckpointDialog.tsx  # Human-in-the-loop approvals
│       │   ├── BugCheckpointDialog.tsx
│       │   ├── BugTraceDrawer.tsx
│       │   ├── ResearchPanel.tsx     # Bug research findings
│       │   ├── SettingsPanel.tsx     # Integration configuration
│       │   └── Navbar.tsx
│       ├── hooks/                # useAppState (Context API)
│       └── services/             # API client (SSE), TypeScript types
├── shared/                     # Shared TypeScript package (types, constants)
├── specs/                      # Product specs & acceptance criteria
└── docker-compose.yml
```

---

## API Reference

### Repository & Graph

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/index` | Index a repository (SSE stream) |
| `GET` | `/graph/{owner}/{repo}` | Fetch knowledge graph for visualization |

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

### Settings

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/settings/integrations` | List integrations with health status |
| `POST` | `/settings/integrations` | Update credentials and test connection |

### SSE Event Types

All streaming endpoints emit Server-Sent Events. Event types:

| Event | When | Payload |
|---|---|---|
| `agent_step` | Each tool call in PR analysis | `{ tool, summary, stage }` |
| `stage_change` | Stage transition | `{ stage, message }` |
| `checkpoint` | Human approval needed | `{ type, message, options }` |
| `result` | PR analysis complete | Full `AnalyzeResponse` |
| `bug_stage_change` | Bug pipeline stage transition | `{ stage, message }` |
| `bug_checkpoint` | Bug workflow approval needed | `{ type, message, data }` |
| `research_progress` | Evidence found during research | `{ source, status, findings }` |
| `bug_result` | Bug report complete | Full `BugReport` |
| `index_step` | Indexing progress | `{ message, progress }` |
| `index_done` | Indexing complete | `{ graph }` |
| `error` | Any failure | `{ message }` |

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

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `GITHUB_TOKEN` | Yes | GitHub PAT (`public_repo` scope minimum) |
| `VITE_API_URL` | Yes | Backend URL seen by the frontend |
| `LANGSMITH_API_KEY` | No | LangSmith tracing key |
| `LANGSMITH_TRACING` | No | `true` to enable LangSmith tracing |
| `LANGSMITH_ENDPOINT` | No | LangSmith API endpoint |
| `LANGSMITH_PROJECT` | No | LangSmith project name (default: `qlankr`) |
| `VITE_USE_MOCK_SSE` | No | `true` to stub SSE responses in frontend dev |
