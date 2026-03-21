# Spec: Impact Analysis on PR

## User Story

**As a QA tester, I want to connect my repo and run impact analysis on a PR, so that I see which components are affected, what risks are introduced or reintroduced, and get suggestions for which tests to run (skip, important, deeper tests) — grounded in the actual structure and call graph of the codebase.**

---

## Problem

When a new PR lands, QA often has no clear signal for what to test. The diff shows what changed in code — but not what components are affected at the product level, what edge cases might regress, or where to focus testing time. Teams either test everything (slow, expensive) or make gut-call decisions (risky). Critical bugs slip through because no one knew the PR touched a shared subsystem.

Game repos make this worse: codebases with thousands of files, flat directory structures, or multi-language call chains mean a single changed function can cascade into subsystems that aren't obvious from the diff alone. An agent that only reads the diff will miss these chains.

---

## Functional Requirements

- The system shall accept a GitHub repo URL to index and visualize before analysis
- The system shall build a knowledge graph of the repo — file structure, clusters, call chains, and cross-file dependencies — and display it visually
- The system shall accept a PR GitHub URL as input for analysis
- The system shall provide impact analysis: affected components, risks for testing, and suggestions for which tests to run (skip, important, deeper)
- The system shall display traceability for impact analysis — how impact and risks were derived — so the QA tester can verify any claim against the agent's trace

## Non-Functional Requirements

- **Setup:** A QA tester should be able to connect their repo, see the knowledge graph, and run their first impact analysis within 30 minutes
- **Reliability:** If analysis fails or is incomplete, the system must report what was tried and what was unavailable — false confidence is worse than no result
- **Trust / Transparency:** Impact and test suggestions must be traceable to sources. The QA tester must be able to verify any claim against the agent's trace
- **Performance:** Repo indexing is a one-time step per repo (re-run on demand). Analysis for a typical PR should complete within a few minutes, with progress updates during the run

---

## Scope

### In scope

- GitHub repo URL as input for indexing (public repos; private repos with a token)
- Interactive knowledge graph visualization of the indexed repo (clusters, files, dependencies)
- GitHub PR URL as input for analysis
- Agent uses both GitHub MCP tools (diff, files, PR metadata) and GitNexus MCP tools (impact scoring, call chains, cluster context)
- Output: affected components, per-component impact summary, risks, and test suggestions (skip / run / deeper)
- Live agent trace in the UI — user sees what the agent is reading as it works
- Confidence indicator per component (high / medium / low)

### Out of scope

- Branch name as input (URL only)
- Jira / Notion / Grafana as analysis sources
- Saving or exporting reports
- Clickable traceability links in the UI (trace visible in logs only)
- Re-indexing triggered automatically on new commits (manual re-index only)
- Any other user story from the backlog

---

## Architecture

```
Browser (React + JS)
     │ SSE / REST
FastAPI backend
     │
     ├── LangGraph ReAct agent (Claude claude-sonnet-4-6)
     │        │ MCP protocol
     │        ├── GitHub MCP server (stdio)
     │        └── GitNexus MCP server (stdio)
     │
     └── GitNexus CLI (repo indexing subprocess)
              └── Cloned repo on disk (temp, per-index run)
```

**Two-phase flow:**

**Phase 1 — Repo Indexing (one-time per repo)**
The user provides a GitHub repo URL. The backend clones the repo, runs `gitnexus analyze` on it (builds the knowledge graph: file structure, AST parsing, call chain resolution, cluster detection), and registers it in the GitNexus global registry. Progress is streamed via SSE. Once done, the frontend fetches cluster and graph data and renders an interactive visualization using Sigma.js.

**Phase 2 — PR Analysis (per PR)**
The user pastes a PR URL. The LangGraph agent receives the URL plus access to both GitHub MCP tools (for reading the diff, files, PR metadata) and GitNexus MCP tools (for querying the pre-built knowledge graph — impact scoring, blast-radius analysis, call chains). The agent streams tool-call events via SSE. On completion it emits a structured JSON report.

No custom GitHub client — all GitHub access goes through MCP. No custom graph queries except through the GitNexus MCP server.

### Repo structure

```
backend/
├── main.py               # FastAPI app, POST /index, POST /analyze, GET /graph, SSE streaming
├── models.py             # Pydantic models — shared contract with frontend
├── indexer.py            # Clones repo, runs gitnexus analyze, streams progress events
└── agent/
    ├── agent.py          # LangGraph ReAct agent, run_agent() entry point
    ├── tools.py          # GitHub MCP + GitNexus MCP client setup
    ├── prompts.py        # System prompt (versioned with comments)
    └── output_parser.py  # Extracts and validates JSON from agent's final message
frontend/
├── src/
│   ├── App.jsx
│   ├── api.js            # SSE connection + fetch to backend
│   └── components/
│       ├── RepoInput.jsx       # Repo URL input, index button, index status
│       ├── KnowledgeGraph.jsx  # Sigma.js interactive graph visualization
│       ├── PRInput.jsx         # PR URL input form, disable on submit
│       ├── AgentTrace.jsx      # Live feed of agent tool calls
│       ├── ImpactSummary.jsx   # Full result layout
│       └── ComponentCard.jsx   # One card per affected component
└── package.json
```

### Tech stack

| Layer    | Choice |
|----------|--------|
| Frontend | React + JavaScript + Vite + Tailwind CSS |
| Backend  | Python + FastAPI |
| Agent    | LangGraph ReAct + Claude (`claude-sonnet-4-6`) |
| GitHub   | GitHub MCP server (stdio transport) |
| Knowledge graph | GitNexus MCP server (stdio transport) + GitNexus CLI |
| Graph viz | Sigma.js v3 + Graphology (ForceAtlas2 layout) |
| Infra    | Docker Compose |

Frontend is JavaScript, not TypeScript.

---

## GitNexus

GitNexus (https://github.com/abhigyanpatwari/gitnexus) is a local code intelligence engine that indexes a codebase into a knowledge graph — every dependency, call chain, cluster, and execution flow — and exposes it via an MCP server.

### How it works

GitNexus runs a 6-stage indexing pipeline on a local directory:

1. **Structure** — file/folder mapping
2. **Parsing** — AST extraction via Tree-sitter (supports C++, C#, Python, Go, JS/TS, Rust, Java, Lua, and more)
3. **Resolution** — cross-file import and call chain linking
4. **Clustering** — community detection via the Leiden algorithm (grouping semantically related files)
5. **Processes** — execution flow tracing (entry points → full call graphs)
6. **Search indexing** — BM25 + semantic embeddings (local, no API key required)

The graph is stored locally in `.gitnexus/` and registered in `~/.gitnexus/registry.json`. All processing is fully local — no code leaves the machine.

### GitNexus MCP tools available to the agent

| Tool | What it gives |
|------|---------------|
| `impact` | Given a file or symbol, returns blast-radius analysis: risk level (LOW / MEDIUM / HIGH / CRITICAL), affected processes, affected modules, depth breakdown |
| `query` | Semantic search over execution flows — returns ranked processes, definitions, and symbol context |
| `context` | 360° caller/callee view for a symbol — all incoming and outgoing edges in the call graph |
| `detect_changes` | Compares changed files against the graph — returns which symbols changed, which processes are affected |
| `cypher` | Raw Cypher query against the graph database — for custom lookups |

### Integration pattern

GitNexus is installed inside the backend container (`npm install -g gitnexus`). The MCP server is started as a subprocess alongside the GitHub MCP server and kept alive for the session:

```
gitnexus mcp   # stdio, registered in the agent's MCP client
```

When a repo is indexed (`POST /index`), the backend:
1. Clones the repo to a temp directory (or a persistent volume for re-use)
2. Runs `gitnexus analyze` on it
3. The indexed repo is now queryable by the already-running GitNexus MCP server via the global registry

---

## Agent Design

The agent is a ReAct-style tool-calling loop — not a fixed pipeline. Claude receives the PR URL, a system prompt, and both GitHub and GitNexus MCP tools. It decides what to look at next each turn until it has enough to produce the report.

```
User: "Analyze https://github.com/owner/repo/pull/42"

Turn 1:  get_pull_request(owner, repo, 42)          → reads title, description, changed files
Turn 2:  get_pull_request_files(owner, repo, 42)    → per-file diffs with patch hunks
Turn 3:  detect_changes(scope: "compare", ...)      → maps changed files to affected symbols and processes
Turn 4:  impact(target: "src/auth/tokens.py", direction: "downstream", maxDepth: 3)
                                                    → blast-radius: risk=HIGH, affected_processes=[...]
Turn 5:  context(name: "refresh_token")             → all callers and callees of the changed function
Turn 6:  get_file_contents(owner, repo, "src/auth/middleware.py")
                                                    → reads a high-impact caller identified by the graph
Turn N:  enough context → outputs structured JSON report
```

The path varies per PR. GitHub MCP tools are used for PR metadata and file content. GitNexus MCP tools are used to understand blast radius and call chains without reading every file manually. The system prompt sets the goal and output format; the agent figures out how to get there.

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

- Max 25 tool calls per run — if hit, agent is prompted to summarize what it has
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

### Repo Indexing

```
POST /index
Content-Type: application/json

{ "repo_url": "https://github.com/owner/repo" }
```

SSE stream:
```
event: index_step
data: { "stage": "clone", "summary": "Cloning owner/repo..." }

event: index_step
data: { "stage": "analyze", "summary": "Building knowledge graph (parsing)..." }

event: index_step
data: { "stage": "analyze", "summary": "Building knowledge graph (clustering)..." }

event: index_done
data: { "repo": "owner/repo", "files": 2341, "clusters": 18, "symbols": 14200 }

--- or ---

event: error
data: { "message": "Could not clone repository: not found or token missing" }
```

### Graph Data

```
GET /graph/{owner}/{repo}
```

Returns cluster and node data for the frontend visualization:
```json
{
  "nodes": [{ "id": "string", "label": "string", "type": "file | cluster", "cluster": "string" }],
  "edges": [{ "source": "string", "target": "string", "type": "CALLS | IMPORTS" }],
  "clusters": [{ "id": "string", "label": "string", "size": "integer" }]
}
```

### PR Analysis

```
POST /analyze
Content-Type: application/json

{ "pr_url": "https://github.com/owner/repo/pull/42" }
```

SSE stream:
```
event: agent_step
data: { "tool": "get_pull_request", "summary": "Reading PR #42 from owner/repo..." }

event: agent_step
data: { "tool": "impact", "summary": "Checking blast radius for src/auth/tokens.py..." }

event: result
data: { ...AnalyzeResponse }

--- or ---

event: error
data: { "message": "Could not fetch PR: repository not found or token missing" }
```

---

## UI Flow

```
[Empty state — Step 1]
  └── paste repo URL → click Connect
      → indexing progress bar with stage labels
      → on complete: knowledge graph visualization

[Knowledge Graph]
  ├── Interactive Sigma.js canvas
  │     ├── Nodes: files and clusters (ForceAtlas2 layout)
  │     ├── Edges: call/import relationships
  │     └── Click cluster → highlight files in that cluster
  └── "Analyze a PR" button → proceed to Step 2

[Step 2 — PR Analysis]
  └── paste PR URL → click Analyze

[Agent trace — live]
  ├── "Reading PR #42 from owner/repo..."
  ├── "Checking blast radius for src/auth/tokens.py..."
  ├── "Context: all callers of refresh_token..."
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
- A1: FastAPI scaffold — `POST /index`, `POST /analyze`, `GET /graph`, stub responses, CORS, `/health`
- A2: SSE streaming — `StreamingResponse`, define `index_step` / `index_done` / `agent_step` / `result` / `error` event shapes
- A3: Pydantic models in `models.py` — write on Day 1, this is the shared contract
- A4: `indexer.py` — clone repo to temp dir, run `gitnexus analyze` as subprocess, stream progress events, expose graph data via `GET /graph`
- A5: Wire `run_agent()` into `POST /analyze`, forward events to SSE stream

**Person B — Agent**
- B1: GitHub MCP + GitNexus MCP client setup in `tools.py`, verify each tool with a standalone script
- B2: LangGraph ReAct agent in `agent.py`, max iteration guard, event emission per tool call
- B3: System prompt in `prompts.py` — goal, tool usage guidance (when to use gitnexus vs. GitHub tools), output schema, reasoning guidance, stop condition
- B4: Output parser in `output_parser.py` — extract JSON, validate against Pydantic model, one retry on malformed output
- B5: `async def run_agent(pr_url) -> AsyncIterator[AgentEvent]` — the only interface Person A needs

**Person C — Frontend**
- C1: Vite + React (JS) scaffold, Tailwind, `api.js` with SSE connection, env var for API URL
- C2: `RepoInput.jsx` — repo URL input, index button, progress display
- C3: `KnowledgeGraph.jsx` — Sigma.js interactive graph; nodes = files/clusters, edges = call/import relations; ForceAtlas2 layout; click to highlight cluster
- C4: `PRInput.jsx` — PR URL input, basic validation, disable on submit
- C5: `AgentTrace.jsx` — live step feed, auto-scroll
- C6: `ImpactSummary.jsx` + `ComponentCard.jsx` — full result view, color-coded test suggestions
- C7: Empty state, error state, copy-to-clipboard (Markdown)

**Person D — Integration & Lead**
- D1: Docker Compose — backend + frontend, GitHub MCP + GitNexus MCP as subprocesses inside backend container, shared `.env`
- D2: `.env.example` with all vars documented
- D3: Write `models.py` on Day 1 and share — unblocks B and C immediately
- D4: End-to-end integration test (`pytest`) + Playwright smoke test once A5 and B5 are done
- D5: Find 2–3 demo PRs on indexed repos, validate agent output, prepare 5-minute walkthrough

### Schedule

| Day | Milestone |
|-----|-----------|
| 1 | D3: shared models written. Scaffolds up (A1, B1, C1). Docker works (D1). GitNexus CLI verified in container. |
| 2 | Indexer working (A4). GitNexus MCP wired to agent (B1). SSE streaming (A2). Repo input + basic graph viz (C2–C3). |
| 3 | System prompt tuned with gitnexus tools (B3). Output parser (B4). `run_agent` exposed (B5). Wired to endpoint (A5). SSE consumed in frontend (C5–C6). |
| 4 | Integration tests (D4). Bug fixes. Prompt tuning. Polish (C7). |
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

Indexer standalone:
```bash
cd backend
python -m indexer "https://github.com/owner/repo"
```

---

## Acceptance Criteria

1. QA tester pastes a GitHub repo URL and clicks Connect — indexing runs and a knowledge graph appears
2. Knowledge graph shows clusters and file nodes with call/import edges — interactive (pan, zoom, click cluster to highlight)
3. QA tester pastes a GitHub PR URL and submits it
4. Live agent trace appears while the agent runs — each tool call shown in order, including GitNexus tool calls
5. On completion: PR title + summary + component cards (name, files, impact, risks, test suggestions, confidence)
6. On failure: clear error message, no stuck spinner
7. Two real PRs from different repos produce coherent, non-hallucinated output
8. Agent tool calls visible in backend logs for traceability
9. `docker compose up` starts everything with no manual steps

---

## Open Questions

- Large PRs (100+ files): agent still runs but notes lower confidence in output
- Agent trace persistence: in-memory only, not saved
- GitNexus indexing for large repos (50K+ files like Cataclysm-DDA): indexing may take several minutes; progress must be visible and cancellable
- Graph data size for `GET /graph`: for very large repos, the node/edge list may be large — may need to return only cluster-level nodes by default, with drill-down per cluster

---

## Calibration Repos

Four open-source game repos to use for evaluating and calibrating the agent. Together they cover flat vs. structured directories, three languages, PR volumes from ~6K to ~50K, and different labeling systems that serve as ground truth for checking agent output.

---

### 1. Cataclysm: Dark Days Ahead

**Repo:** https://github.com/CleverRaven/Cataclysm-DDA
**Language:** C++ / JSON
**Merged PRs:** ~50,000+
**Source files:** ~700 C++ files (flat `src/`) + thousands of JSON content files

**Why it's useful.** The largest PR dataset of any game repo on GitHub. Every PR uses a structured template and a bot auto-labels them with subsystem tags (`Map / Mapgen`, `Vehicles`, `Monsters`, `Items`, etc.) — this auto-labeling is built-in ground truth to check the agent's component classification against. The key challenge: `src/` is completely flat with no subdirectories, so the agent cannot rely on directory structure and must infer components semantically from file names and content. GitNexus's Leiden clustering should group vehicle-related files even without directory cues.

**Evaluation ideas**
- **Semantic component detection:** pick a PR labeled `Vehicles` by the bot, run the agent, check if it identifies the vehicle system — both from the knowledge graph clusters and from the diff
- **Data-vs-code distinction:** ~30–50% of PRs are JSON-only content changes (new items, recipes). Check that the agent correctly identifies these as low-risk data additions vs. code changes
- **Scale stress test:** compare agent output on a 2-file JSON PR vs. a 50+ file C++ refactor — does confidence scoring and depth of analysis scale appropriately?
- **Label accuracy benchmark:** run 10 labeled PRs, score how often the agent's component list matches the bot's ground-truth tags

---

### 2. OpenTTD

**Repo:** https://github.com/OpenTTD/OpenTTD
**Language:** C++
**Merged PRs:** ~5,500–6,000
**Source files:** ~1,500–2,000, organized into clear subsystem directories

**Why it's useful.** The most disciplined PR conventions of the four. Every commit uses structured prefixes (`Fix:`, `Feature:`, `Add:`, `Codechange:`) and PR templates include checklists for savegame format changes, Script API changes, and translation impact — metadata that directly names affected subsystems. The `src/` directory is well-organized into distinct folders (network, AI, video, audio, pathfinding, GUI, economy), making it ideal for testing whether the agent correctly maps files to components when directory structure is clear. GitNexus clusters should align well with these directories.

**Evaluation ideas**
- **Directory-to-component mapping:** pick a PR that touches `src/network/` and `src/saveload/` — does the agent correctly identify both the network subsystem and savegame compatibility as affected?
- **Commit prefix vs. agent classification:** for `Fix:` PRs, check the agent marks risk as localized; for `Feature:` PRs, check it flags broader regression risk
- **Cross-subsystem detection:** find PRs that touch the GUI and an underlying game system — does the agent flag both layers or just the surface change?
- **Precision baseline:** because PR quality is highest here, use OpenTTD as the precision benchmark — results on this repo should be most reliable

---

### 3. osu!

**Repo:** https://github.com/ppy/osu
**Language:** C#
**Merged PRs:** ~12,000–14,000
**Source files:** ~5,000–7,000 across separate .NET projects

**Why it's useful.** Every PR gets two labels: a **size label** (XS, S, M, L, XL by file count) and **area labels** (`area:gameplay`, `area:editor`, `area:ui`, `ruleset/osu!`, etc.). This dual-axis labeling is the best ground truth of the four for checking both scope and component accuracy. The .NET solution structure creates hard subsystem boundaries — each ruleset and game area is a separate project — which tests whether the agent understands project-level architecture. GitNexus's cross-project call chain resolution is specifically useful here.

**Evaluation ideas**
- **Size-based calibration:** run one PR from each size tier (XS through XL), plot how agent confidence, step count, and output depth change with PR size — this directly tells you how the agent scales
- **Area label accuracy:** score how often the agent's components match the area labels; `ruleset/osu!` vs. `ruleset/mania` distinctions test fine-grained component resolution
- **Cross-ruleset impact:** find PRs that change `osu.Game` (core) — does the agent flag that all four rulesets may be affected even if only core files changed?
- **Language diversity check:** since osu! is C#, run the same PR types as C++ repos and compare agent behavior — does it reason differently about .NET project references vs. C++ `#include`s?

---

### 4. Luanti (formerly Minetest)

**Repo:** https://github.com/luanti-org/luanti
**Language:** C++ / Lua
**Merged PRs:** ~7,000–7,500
**Source files:** ~2,500–3,000 across well-named subsystem directories

**Why it's useful.** The most balanced repo of the four — non-trivial size without overwhelming volume, clear directory structure (`src/client/`, `src/network/`, `src/mapgen/`, `src/script/`, `builtin/`), and two-dimensional PR labels (area tags + type tags). Its dual-language architecture (C++ engine + Lua scripting layer) creates a natural cross-layer impact pattern: a gameplay change may touch Lua scripts in `builtin/`, C++ API bindings in `src/script/`, and rendering code in `src/client/` — exactly the kind of chain the agent needs to detect. GitNexus supports both C++ and Lua in its Tree-sitter parser, making it well-suited for tracing these cross-language call chains.

**Evaluation ideas**
- **Cross-layer impact detection:** find PRs that touch both `src/script/` (C++ Lua bindings) and `builtin/` (Lua game logic) — does the agent identify the full chain from engine to script layer?
- **Type label vs. risk assessment:** for `Bugfix 🐛` PRs, check the agent produces narrower test suggestions than for `Feature ✨` PRs of the same file count
- **Balanced baseline:** use Luanti as the default demo repo — it's approachable enough that reviewers can sanity-check agent output without deep game knowledge
- **Rendering vs. logic separation:** find a client rendering PR (`src/client/`) and a server logic PR (`src/server*.cpp`) of similar size — does the agent correctly identify them as non-overlapping components?

---

### Summary

| | Cataclysm-DDA | OpenTTD | osu! | Luanti |
|---|---|---|---|---|
| **Primary test** | Semantic component detection (flat dirs) | Precision baseline (structured dirs) | Size calibration (XS–XL labels) | Cross-layer impact (C++ + Lua) |
| **Ground truth** | Bot auto-labels | Commit prefix + PR checklist | Size + area labels | Area + type labels |
| **Volume** | Stress (~50K PRs) | Focused (~6K PRs) | Medium (~13K PRs) | Balanced (~7K PRs) |
| **Language** | C++ / JSON | C++ | C# | C++ / Lua |
