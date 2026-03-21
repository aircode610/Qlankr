# AGENTS.md — Qlankr Project Context

This file gives AI coding agents fast context on what this project is, how it's structured, and how to work in it.

---

## What This Project Is

Qlankr is an AI-assisted QA tool for indie game studios. It has two parts:
1. **Impact analysis** — given a GitHub PR, show which components are affected, what risks exist, and what a QA tester should focus on
2. **Bug reproduction** — given a bug description, help research and reproduce it, then generate a developer-ready report

Sprint 1 is focused entirely on **impact analysis**.

---

## Repo Layout

```
Qlankr/
├── AGENTS.md                          # This file
├── backend/                           # FastAPI app + AI agent (Python)
│   ├── main.py                        # Entry point: POST /index, GET /graph, POST /analyze — SSE streaming
│   ├── models.py                      # Pydantic models — AnalyzeRequest, AnalyzeResponse, etc.
│   ├── indexer.py                     # Repo indexing: clone repo, run GitNexus CLI, store in registry
│   ├── agent/
│   │   ├── agent.py                   # LangGraph structured ReAct agent, run_agent() entry point
│   │   ├── tools.py                   # GitHub MCP + GitNexus MCP client setup, tool definitions
│   │   ├── prompts.py                 # System prompt (versioned with comments) — enforces 3-phase structure
│   │   └── output_parser.py           # Extracts and validates JSON from agent's final message
│   └── requirements.txt
├── frontend/                          # React + Vite (JavaScript, not TypeScript)
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── RepoInput.jsx          # Repo URL input — triggers indexing phase
│   │   │   ├── KnowledgeGraph.jsx     # Sigma.js interactive knowledge graph visualization
│   │   │   ├── PRInput.jsx            # PR URL input form
│   │   │   ├── AgentTrace.jsx         # Live feed of agent tool calls while running
│   │   │   ├── ImpactSummary.jsx      # Full result layout
│   │   │   └── ComponentCard.jsx      # One card per affected component
│   │   └── api.js                     # SSE connection + typed fetch to backend
│   └── package.json
├── specs/
│   ├── requirements.md                # Full product requirements and backlog
│   ├── interview-game-studio.md       # Customer validation interview artifact
│   └── 01-impact-analysis-on-pr/
│       └── spec.md                    # Sprint 1 user story spec, API contract, acceptance criteria
├── docs/
│   └── proposal.md                    # Product proposal and market context
└── docker-compose.yml                 # Runs backend + frontend together
```

---

## Tech Stack

| Layer          | Choice                                                    |
|----------------|-----------------------------------------------------------|
| Frontend       | React + JavaScript + Vite + Tailwind CSS                  |
| Backend        | Python + FastAPI                                          |
| Agent          | LangGraph structured ReAct loop + Claude (`claude-sonnet-4-6`) |
| GitHub         | GitHub MCP server (stdio transport) — no custom GitHub client |
| Knowledge graph | GitNexus MCP server + GitNexus CLI                       |
| Graph viz      | Sigma.js v3 + Graphology (ForceAtlas2 layout)             |
| Infra          | Docker Compose                                            |

**Frontend is JavaScript, not TypeScript.** Do not add `.ts` or `.tsx` files.

---

## Key Architectural Decisions

- **Two-phase workflow.** Phase 1 (repo indexing): user connects a repo once — backend clones it, runs `gitnexus analyze`, builds a knowledge graph, and stores it in a local registry. Phase 2 (PR analysis): agent uses both GitHub MCP tools and GitNexus MCP tools to analyze the PR against the indexed graph.
- **GitNexus is a local code intelligence engine.** No code leaves the machine. Available MCP tools: `impact` (blast radius from changed files), `query` (semantic search over the graph), `context` (node context), `detect_changes` (semantic diff between commits), `cypher` (raw graph queries). See https://github.com/abhigyanpatwari/gitnexus.
- **Agent is a structured ReAct loop, not a plain free-roaming loop.** The system prompt enforces three explicit phases: (1) **Blast radius** — always start with `detect_changes` + `impact` + PR diff; (2) **Depth analysis** — use `context`, `cypher`, and GitHub file reads only where GitNexus context is ambiguous; (3) **Synthesis** — produce the JSON output and hard-stop. A max-steps budget (30 tool calls) forces synthesis with a lower confidence score if exhausted.
- **Fully autonomous — no human-in-the-loop.** All agent tools are read-only. The output is a structured report, not an action. Latency matters (QA tester is waiting). The cost of a wrong analysis is a missed test case, not an irreversible system action.
- **No custom GitHub client.** The AI agent calls GitHub directly through the GitHub MCP server. Do not write wrapper functions that fetch from the GitHub API — let the agent use MCP tools.
- **Streaming via SSE.** The backend streams agent events to the frontend in real time (`agent_step`, `result`, `error`). The frontend opens an SSE connection and renders each event as it arrives.
- **No database in Sprint 1.** Results are returned directly to the client. Do not add persistence unless explicitly discussed.

---

## Agent Overview

The impact analysis agent is a LangGraph structured ReAct loop. Entry point is `run_agent(pr_url)` in `backend/agent/agent.py`. It:
1. Receives a GitHub PR URL
2. **Phase 1 — Blast radius:** Calls `detect_changes` + `impact` + GitHub PR diff to map which graph nodes and files are affected
3. **Phase 2 — Depth analysis:** Uses `context`, `cypher`, and targeted GitHub file reads to assess risk severity and test surface for each impacted node
4. **Phase 3 — Synthesis:** Outputs a structured JSON impact report and stops (hard limit: 30 tool calls)

Both GitHub MCP tools and GitNexus MCP tools (`impact`, `query`, `context`, `detect_changes`, `cypher`) are available to the agent.

See `specs/01-impact-analysis-on-pr/spec.md` for the full output schema and SSE event format.

---

## API

Three endpoints for Sprint 1:

```
POST /index
Body: { "repo_url": "https://github.com/owner/repo" }
Response: SSE stream of indexing progress events (clone, analyze, store)

GET /graph/{owner}/{repo}
Response: JSON with nodes, edges, clusters for Sigma.js visualization

POST /analyze
Body: { "pr_url": "https://github.com/owner/repo/pull/42" }
Response: SSE stream of agent_step / result / error events
```

Full contract (request shape, SSE event shapes, response JSON schema) is in `specs/01-impact-analysis-on-pr/spec.md`.

---

## Environment Variables

```
ANTHROPIC_API_KEY   # Required — Claude API key
GITHUB_TOKEN        # Required — GitHub PAT (public_repo scope minimum)
VITE_API_URL        # Frontend — defaults to http://localhost:8000
```

Copy `.env.example` to `.env` and fill in before running.

---

## Running Locally

```bash
docker compose up
# Frontend: http://localhost:5173
# Backend:  http://localhost:8000
```

Run the agent standalone (for prompt dev/debugging):
```bash
cd backend
python -m agent.agent "https://github.com/owner/repo/pull/42"
```

---

## Where to Find Things

| What you're looking for | Where |
|-------------------------|-------|
| Full product requirements and backlog | `specs/requirements.md` |
| Sprint 1 user story, tasks, acceptance criteria, API contract | `specs/01-impact-analysis-on-pr/spec.md` |
| Customer validation interview | `specs/interview-game-studio.md` |
| Product proposal and market context | `docs/proposal.md` |
| Pydantic models | `backend/models.py` |
| Agent system prompt | `backend/agent/prompts.py` |
| SSE event types | `specs/01-impact-analysis-on-pr/spec.md` → API Contract section |
| GitNexus MCP tools reference | `backend/agent/tools.py` |
