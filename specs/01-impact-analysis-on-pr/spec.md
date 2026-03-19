# Spec: Impact Analysis on PR

## User Story

**As a QA tester, I want to run impact analysis when I get a new PR (e.g. by URL or branch), so that I see which components are affected, what risks are introduced or reintroduced, and get suggestions for which tests to run (skip, important, deeper tests).**

---

## Problem

When a new PR lands, QA often has no clear signal for what to test. The diff shows what changed in code — but not what components are affected at the product level, what edge cases might regress, or where to focus testing time. Teams either test everything (slow, expensive) or make gut-call decisions (risky). Critical bugs slip through because no one knew the PR touched a shared subsystem.

---

## Functional Requirements

- The system shall accept a PR GitHub URL as input
- The system shall provide impact analysis: affected components, risks for testing, and suggestions for which tests to run (skip, important, deeper)
- The system shall display traceability for impact analysis — how impact and risks were derived — so the QA tester can verify any claim against the agent's trace

## Non-Functional Requirements

- **Setup:** A QA tester should be able to connect their repo and run their first impact analysis within 30 minutes
- **Reliability:** If analysis fails or is incomplete, the system must report what was tried and what was unavailable — false confidence is worse than no result
- **Trust / Transparency:** Impact and test suggestions must be traceable to sources. The QA tester must be able to verify any claim against the agent's trace
- **Performance:** Analysis for a typical PR should complete within a few minutes, with progress updates during the run

---

## Scope

### In scope

- GitHub PR URL as input (public repos; private repos with a token)
- Autonomous agent exploration of the repo using GitHub MCP tools
- Output: affected components, per-component impact summary, risks, and test suggestions (skip / run / deeper)
- Live agent trace in the UI — user sees what the agent is reading as it works
- Confidence indicator per component (high / medium / low)

### Out of scope

- Branch name as input (URL only)
- Jira / Notion / Grafana as analysis sources
- Saving or exporting reports
- Clickable traceability links in the UI (trace visible in logs only)
- Any other user story from the backlog

---

## Architecture

```
Browser (React + JS)
     │ SSE
FastAPI backend
     │
LangGraph ReAct agent (Claude claude-sonnet-4-6)
     │ MCP protocol
GitHub MCP server
```

The backend accepts a PR URL, starts the agent, and streams events back via SSE. The agent uses GitHub MCP tools to explore the repo autonomously. No custom GitHub client — all GitHub access goes through MCP.

### Repo structure

```
backend/
├── main.py               # FastAPI app, POST /analyze, SSE streaming
├── models.py             # Pydantic models — shared contract with frontend
└── agent/
    ├── agent.py          # LangGraph ReAct agent, run_agent() entry point
    ├── tools.py          # GitHub MCP client setup
    ├── prompts.py        # System prompt (versioned with comments)
    └── output_parser.py  # Extracts and validates JSON from agent's final message
frontend/
├── src/
│   ├── App.jsx
│   ├── api.js            # SSE connection + fetch to backend
│   └── components/
│       ├── PRInput.jsx       # URL input form
│       ├── AgentTrace.jsx    # Live feed of agent tool calls
│       ├── ImpactSummary.jsx # Full result layout
│       └── ComponentCard.jsx # One card per affected component
└── package.json
```

### Tech stack

| Layer    | Choice |
|----------|--------|
| Frontend | React + JavaScript + Vite + Tailwind CSS |
| Backend  | Python + FastAPI |
| Agent    | LangGraph ReAct + Claude (`claude-sonnet-4-6`) |
| GitHub   | GitHub MCP server (stdio transport) |
| Infra    | Docker Compose |

Frontend is JavaScript, not TypeScript.

---

## Agent Design

The agent is a ReAct-style tool-calling loop — not a fixed pipeline. Claude receives the PR URL, a system prompt, and GitHub MCP tools. It decides what to look at next each turn until it has enough to produce the report.

```
User: "Analyze https://github.com/owner/repo/pull/42"

Turn 1:  get_pull_request(owner, repo, 42)       → reads title, description, changed files
Turn 2:  list_directory(owner, repo, "/")         → understands top-level structure
Turn 3:  get_file_contents(owner, repo, "src/auth/tokens.py")
Turn 4:  search_code(owner, repo, "refresh_token")
Turn N:  enough context → outputs structured JSON report
```

The path varies per PR. The system prompt sets the goal and output format; the agent figures out how to get there.

### GitHub MCP tools available to the agent

| Tool | What it gives |
|------|---------------|
| `get_pull_request` | PR metadata, description, diff stats, changed files |
| `get_pull_request_files` | Per-file diffs with patch hunks |
| `get_pull_request_comments` | Review comments and discussion |
| `get_file_contents` | Full content of any file in the repo |
| `list_directory` | Directory listing at any path |
| `get_commits` | Recent commit history |
| `search_code` | Search repo for a string or symbol |

### Guards

- Max 20 tool calls per run — if hit, agent is prompted to summarize what it has
- 3-minute timeout — returns error SSE event if exceeded

---

## Output Schema

```json
{
  "pr_title": "string",
  "pr_url": "string",
  "pr_summary": "string — one paragraph plain English",
  "affected_components": [
    {
      "component": "string",
      "files_changed": ["string"],
      "impact_summary": "string",
      "risks": ["string"],
      "test_suggestions": {
        "skip": ["string"],
        "run": ["string"],
        "deeper": ["string"]
      },
      "confidence": "high | medium | low"
    }
  ],
  "agent_steps": "integer"
}
```

---

## API Contract

### Request

```
POST /analyze
Content-Type: application/json

{ "pr_url": "https://github.com/owner/repo/pull/42" }
```

### Response (SSE stream)

```
event: agent_step
data: { "tool": "get_pull_request", "summary": "Reading PR #42 from owner/repo..." }

event: agent_step
data: { "tool": "get_file_contents", "summary": "Reading src/auth/tokens.py..." }

event: result
data: { ...AnalyzeResponse }

--- or ---

event: error
data: { "message": "Could not fetch PR: repository not found or token missing" }
```

---

## UI Flow

```
[Empty state]
  └── paste PR URL → click Analyze

[Agent trace — live]
  ├── "Reading PR #42 from owner/repo..."
  ├── "Browsing /src/auth/..."
  ├── "Reading src/auth/tokens.py..."
  └── ...

[Result]
  ├── PR title + link
  ├── Plain-English summary
  └── Component cards
        ├── Component name + changed files (collapsible)
        ├── Impact summary
        ├── Risks (badges)
        └── Test suggestions: Skip (gray) / Run (green) / Deeper (orange)
```

---

## Task Breakdown

Four parallel tracks. Work independently until Day 3 integration.

**Person A — Backend & API**
- A1: FastAPI scaffold — `POST /analyze`, stub response, CORS, `/health`
- A2: SSE streaming — `StreamingResponse`, define `agent_step` / `result` / `error` event shapes
- A3: Pydantic models in `models.py` — write on Day 1, this is the shared contract
- A4: Wire `run_agent()` into the endpoint, forward events to SSE stream

**Person B — Agent**
- B1: GitHub MCP client + tool setup in `tools.py`, verify each tool with a standalone script
- B2: LangGraph ReAct agent in `agent.py`, max iteration guard, event emission per tool call
- B3: System prompt in `prompts.py` — goal, output schema, reasoning guidance, stop condition
- B4: Output parser in `output_parser.py` — extract JSON, validate against Pydantic model, one retry on malformed output
- B5: `async def run_agent(pr_url) -> AsyncIterator[AgentEvent]` — the only interface Person A needs

**Person C — Frontend**
- C1: Vite + React (JS) scaffold, Tailwind, `api.js` with SSE connection, env var for API URL
- C2: `PRInput.jsx` — URL input, basic validation, disable on submit
- C3: `AgentTrace.jsx` — live step feed, auto-scroll
- C4: `ImpactSummary.jsx` + `ComponentCard.jsx` — full result view, color-coded test suggestions
- C5: Empty state, error state, copy-to-clipboard (Markdown)

**Person D — Integration & Lead**
- D1: Docker Compose — backend + frontend, GitHub MCP as subprocess inside backend container, shared `.env`
- D2: `.env.example` with all vars documented
- D3: Write `models.py` on Day 1 and share — unblocks B and C immediately
- D4: End-to-end integration test (`pytest`) + Playwright smoke test once A4 and B5 are done
- D5: Find 2–3 demo PRs, validate agent output, prepare 5-minute walkthrough

### Schedule

| Day | Milestone |
|-----|-----------|
| 1 | D3: shared models written. Scaffolds up (A1, B1, C1). Docker works (D1). |
| 2 | MCP tools wired (B1). Agent loop running (B2). SSE streaming (A2). UI components (C2–C3). |
| 3 | System prompt tuned (B3). Output parser (B4). `run_agent` exposed (B5). Wired to endpoint (A4). SSE consumed in frontend (C4). |
| 4 | Integration tests (D4). Bug fixes. Prompt tuning. Polish (C5). |
| 5 | Demo prep (D5). Buffer. Final run-through. |

---

## Environment Variables

```
ANTHROPIC_API_KEY   # Claude API key
GITHUB_TOKEN        # GitHub PAT — public_repo scope minimum, repo scope for private repos
VITE_API_URL        # Defaults to http://localhost:8000
```

## Running Locally

```bash
cp .env.example .env
# fill in ANTHROPIC_API_KEY and GITHUB_TOKEN
docker compose up
# frontend: http://localhost:5173
```

Agent standalone (for prompt dev):
```bash
cd backend
python -m agent.agent "https://github.com/owner/repo/pull/42"
```

---

## Acceptance Criteria

1. QA tester pastes a GitHub PR URL and submits it
2. Live agent trace appears while the agent runs — each tool call shown in order
3. On completion: PR title + summary + component cards (name, files, impact, risks, test suggestions, confidence)
4. On failure: clear error message, no stuck spinner
5. Two real PRs from different repos produce coherent, non-hallucinated output
6. Agent tool calls visible in backend logs for traceability
7. `docker compose up` starts everything with no manual steps

---

## Open Questions

- Large PRs (100+ files): agent still runs but notes lower confidence in output
- Agent trace persistence: in-memory only, not saved
