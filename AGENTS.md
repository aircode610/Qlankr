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
│   │   └── prompts.py                 # System prompt (versioned) — environment-orientation approach
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
- **GitNexus is a local code intelligence engine.** No code leaves the machine. Available MCP tools: `impact` (symbol blast radius — takes a **symbol name**, not a file path), `query` (semantic search, param is `query`), `context` (caller/callee for a symbol), `cypher` (raw Cypher against the KuzuDB graph), `list_repos`. `detect_changes` uses local git diff only — not useful for remote PRs. See https://github.com/abhigyanpatwari/gitnexus.
- **Agent is a ReAct loop oriented around its environment, not rigid phases.** The system prompt describes the three resources available (PR via GitHub MCP, knowledge graph via GitNexus MCP, repo name) and the goal (QA impact report). The agent decides its own tool call sequence. Budget is 25 tool calls; it must call `submit_analysis` as its final action — that is its only way to return a result.
- **Fully autonomous — no human-in-the-loop.** All agent tools are read-only. The output is a structured report, not an action. Latency matters (QA tester is waiting). The cost of a wrong analysis is a missed test case, not an irreversible system action.
- **No custom GitHub client.** The AI agent calls GitHub directly through the GitHub MCP server. Do not write wrapper functions that fetch from the GitHub API — let the agent use MCP tools.
- **Streaming via SSE.** The backend streams agent events to the frontend in real time (`agent_step`, `result`, `error`). The frontend opens an SSE connection and renders each event as it arrives.
- **No database in Sprint 1.** Results are returned directly to the client. Do not add persistence unless explicitly discussed.

---

## Agent Overview

The impact analysis agent is a LangGraph ReAct loop. Entry point is `run_agent(pr_url)` in `backend/agent/agent.py`. It:
1. Receives a GitHub PR URL and (if indexed) the GitNexus repo name
2. Freely uses GitHub MCP tools to read the PR diff, files, and comments
3. Uses GitNexus MCP tools to assess blast radius and call graph impact for changed symbols
4. Calls `submit_analysis` exactly once when done — this is the only way to return a result (hard limit: 25 tool calls)

Key constraints for GitNexus tools:
- `impact` and `context` take a **symbol name** (function/class), NOT a file path
- To resolve a file path to symbol names: `MATCH (f:File)-[r:CodeRelation]->(s) WHERE r.type='DEFINES' AND f.filePath='<path>' RETURN s.name LIMIT 20`
- All graph edges are `[:CodeRelation]` with a `type` property — filter with `WHERE r.type='...'`
- `detect_changes` uses local git diff only — skip it for remote GitHub PRs

Both GitHub MCP tools and GitNexus MCP tools are available. If the repo is not indexed, the agent falls back to GitHub tools only and sets all confidence to "low".

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

Debug endpoints (dev only):

```
GET  /debug/mcp/tools           # List all MCP tools visible to the backend
GET  /debug/mcp/repos           # Call list_repos and return raw response
POST /debug/mcp/call            # Call any MCP tool: { "tool": "<name>", "args": {...} }
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
| Agent system prompt (v1.3) | `backend/agent/prompts.py` |
| SSE event types | `specs/01-impact-analysis-on-pr/spec.md` → API Contract section |
| GitNexus MCP client setup | `backend/agent/tools.py` |
| Debug MCP endpoints | `GET /debug/mcp/tools`, `GET /debug/mcp/repos`, `POST /debug/mcp/call` |
