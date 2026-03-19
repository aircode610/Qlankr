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
│   ├── main.py                        # Entry point, POST /analyze endpoint, SSE streaming
│   ├── models.py                      # Pydantic models — AnalyzeRequest, AnalyzeResponse, etc.
│   ├── agent/
│   │   ├── agent.py                   # LangGraph ReAct agent, run_agent() entry point
│   │   ├── tools.py                   # GitHub MCP client setup, tool definitions
│   │   ├── prompts.py                 # System prompt (versioned with comments)
│   │   └── output_parser.py           # Extracts and validates JSON from agent's final message
│   └── requirements.txt
├── frontend/                          # React + Vite (JavaScript, not TypeScript)
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── PRInput.jsx            # URL input form
│   │   │   ├── AgentTrace.jsx         # Live feed of agent tool calls while running
│   │   │   ├── ImpactSummary.jsx      # Full result layout
│   │   │   └── ComponentCard.jsx      # One card per affected component
│   │   └── api.js                     # SSE connection + typed fetch to backend
│   └── package.json
├── specs/
│   ├── requirements.md                # Full product requirements and backlog
│   └── 01-impact-analysis-on-pr/
│       └── spec.md                    # Sprint 1 user story spec, API contract, acceptance criteria
├── docs/
│   └── proposal.md                    # Product proposal and market context
└── docker-compose.yml                 # Runs backend + frontend together
```

---

## Tech Stack

| Layer    | Choice                        |
|----------|-------------------------------|
| Frontend | React + JavaScript + Vite + Tailwind CSS |
| Backend  | Python + FastAPI              |
| Agent    | LangGraph ReAct loop + Claude (`claude-sonnet-4-6`) |
| GitHub   | GitHub MCP server (stdio transport) — no custom GitHub client |
| Infra    | Docker Compose                |

**Frontend is JavaScript, not TypeScript.** Do not add `.ts` or `.tsx` files.

---

## Key Architectural Decisions

- **No custom GitHub client.** The AI agent calls GitHub directly through the GitHub MCP server. Do not write wrapper functions that fetch from the GitHub API — let the agent use MCP tools.
- **Agent is a ReAct loop, not a pipeline.** The agent decides what to explore and in what order. Do not hardcode a sequence of steps. The exploration path is determined by what the agent finds.
- **Streaming via SSE.** The backend streams agent events to the frontend in real time (`agent_step`, `result`, `error`). The frontend opens an SSE connection and renders each event as it arrives.
- **No database in Sprint 1.** Results are returned directly to the client. Do not add persistence unless explicitly discussed.

---

## Agent Overview

The impact analysis agent is a LangGraph ReAct loop. Entry point is `run_agent(pr_url)` in `backend/agent/agent.py`. It:
1. Receives a GitHub PR URL
2. Calls GitHub MCP tools autonomously to explore the repo (diff, files, directory structure, code search, etc.)
3. Stops when it has enough context
4. Outputs a structured JSON impact report

See `specs/01-impact-analysis-on-pr/spec.md` for the full output schema and SSE event format.

---

## API

Single endpoint for Sprint 1:

```
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
| Product proposal and market context | `docs/proposal.md` |
| Pydantic models | `backend/models.py` |
| Agent system prompt | `backend/agent/prompts.py` |
| SSE event types | `specs/01-impact-analysis-on-pr/spec.md` → API Contract section |
