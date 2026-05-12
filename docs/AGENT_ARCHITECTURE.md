# Qlankr Agent Architecture

Qlankr is an AI QA assistant for game studios. It exposes two agentic pipelines — **Impact Analysis** (PR analysis) and **Bug Reproduction** — both built on LangGraph StateGraphs with human-in-the-loop checkpoints, MCP tool orchestration, and SSE streaming.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Pipeline 1: Impact Analysis (PR Analysis)](#pipeline-1-impact-analysis)
3. [Pipeline 2: Bug Reproduction](#pipeline-2-bug-reproduction)
4. [Tool System (MCP)](#tool-system-mcp)
5. [Prompts](#prompts)
6. [Session & State Management](#session--state-management)
7. [Data Persistence](#data-persistence)
8. [API Endpoints](#api-endpoints)
9. [Pre-fetch Layer](#pre-fetch-layer)
10. [Evaluations](#evaluations)

---

## System Overview

```
                          ┌──────────────────────────────────────────┐
                          │             FastAPI (main.py)             │
                          │  /analyze  /bug-report  /projects  /index │
                          └──────┬───────────────────┬───────────────┘
                                 │                   │
                    ┌────────────▼───┐     ┌─────────▼────────┐
                    │   agent.py     │     │   bug_agent.py    │
                    │ Impact Graph   │     │ Bug Repro Graph   │
                    └────────┬───────┘     └─────────┬─────────┘
                             │                       │
           ┌─────────────────▼───────────────────────▼──────────────┐
           │                   MCP Tool Layer (tools.py)             │
           │  GitHub · GitNexus · Jira · Notion · Confluence ·      │
           │  Grafana · Kibana · Postman · Sniffer                   │
           └─────────────────────────────────────────────────────────┘
                             │
           ┌─────────────────▼───────────────────────────────────────┐
           │             Supabase (db.py / auth.py)                   │
           │  profiles · projects · pr_analyses · bug_reports ·      │
           │  user_credentials   (all tables RLS-isolated per user)  │
           └─────────────────────────────────────────────────────────┘
```

**Key design decisions:**

- **LangGraph StateGraph**: Each pipeline is a compiled graph with typed state, conditional edges, and `interrupt()` checkpoints for human review.
- **LangChain ReAct sub-agents**: Each stage node spawns its own ReAct agent (`create_react_agent`) with a stage-specific prompt, tool subset, and call budget.
- **MCP (Model Context Protocol)**: All external tools (GitHub, Jira, GitNexus, etc.) are MCP servers. Persistent stdio sessions are opened once per pipeline run and reused across all stages.
- **SSE streaming**: Every tool call and stage transition is streamed to the frontend as Server-Sent Events.
- **Two LLM tiers**: Heavy reasoning stages use `claude-sonnet-4-6`; lightweight stages (triage, report synthesis) use `claude-haiku-4-5` (~37x cheaper).
- **Supabase for persistence**: User-scoped Postgres tables with row-level security. Auth via ES256 JWTs (asymmetric signing, JWKS-verified).

---

## Pipeline 1: Impact Analysis

**Purpose**: Analyze a GitHub PR to identify affected components, generate unit/integration/E2E test specs, and surface risks.

**Entry point**: `POST /analyze` -> `agent.py:run_agent()`

### Graph Topology

```
gather ──► unit_tests ──► checkpoint_unit ──┐
                                            │
                              ┌─────────────┤
                              │ (refine)    │ (approve)
                              ▼             ▼
                         unit_tests      choice ──────────────────┐
                                            │                     │
                               ┌────────────┤                     │
                               │ (integration)           (e2e)    │
                               ▼                                  ▼
                      integration_tests              e2e_checkpoint
                               │                          │
                               │                          ▼
                               │                    e2e_planning
                               │                          │
                               └──────────► submit ◄──────┘
                                              │
                                             END
```

### State (`AnalysisState`)

| Field | Type | Description |
|---|---|---|
| `pr_url` | `str` | GitHub PR URL |
| `repo_name` | `str \| None` | GitNexus repo identifier |
| `user_context` | `str \| None` | Optional user-provided context |
| `session_id` | `str` | Unique thread/session ID |
| `pr_diff` | `str` | Full PR diff text |
| `pr_files` | `list[str]` | List of changed file paths |
| `pr_metadata` | `dict` | PR title, description, author |
| `processes` | `list[dict]` | Pre-fetched execution flows from GitNexus |
| `repo_stats` | `dict` | Node/edge/file/process counts |
| `affected_components` | `list[dict]` | Components with risk, impact, unit tests |
| `integration_tests` | `list[dict]` | Cross-module integration test specs |
| `e2e_test_plans` | `list[dict]` | End-to-end test scenarios |
| `current_stage` | `str` | Active stage name |
| `tool_calls_used` | `int` | Cumulative tool call count |
| `user_choice` | `str \| None` | "integration" or "e2e" — set at choice checkpoint |
| `unit_feedback` | `str \| None` | User feedback for unit test refinement |

### Stages

#### Stage 1: Gather (`stages/gather.py`) — Budget: 15

**Goal**: Fetch PR metadata, group changed files into logical components, enrich with graph data.

**LLM**: claude-sonnet-4-6

**Tools allowed**: `get_pull_request`, `get_pull_request_files`, `get_pull_request_comments`, `get_file_contents`, `list_directory`, `search_code`, `get_commits`, `list_repos`, `impact`, `cypher`, `detect_changes`

**Workflow**:
1. Fetch PR data (2 calls): `get_pull_request` + `get_pull_request_files`
2. Group all changed files into logical components immediately (0 calls)
3. Enrich 2-3 most critical components with graph data (up to 5 calls): `cypher` to find symbols, `impact` for blast radius
4. Call `submit_gather` with all collected data

**Output**: Populates `pr_metadata`, `pr_diff`, `pr_files`, `affected_components`

**Submit schema** (per component):
```json
{
  "component": "Inventory System",
  "files_changed": ["src/inventory.ts", "src/items.ts"],
  "impact_summary": "One sentence max 20 words",
  "impact_detail": "2-4 sentences with specifics",
  "risks": ["null pointer in Foo.bar when inventory empty"],
  "confidence": "high | medium | low"
}
```

#### Stage 2: Unit Tests (`stages/unit.py`) — Budget: 15

**Goal**: Generate unit test specifications for each affected component.

**LLM**: claude-sonnet-4-6

**Tools allowed**: `context`, `cypher`, `get_file_contents`

**Workflow**:
1. For each component: read changed files, get caller/callee context
2. Identify key changed symbols
3. Call `submit_unit_tests` per component with `UnitTestSpec` list

**Submit schema** (per symbol):
```json
{
  "target": "SymbolName.methodName",
  "test_cases": [
    {"name": "test name", "scenario": "setup", "expected": "outcome"}
  ],
  "mocks_needed": ["DepA", "DepB"],
  "priority": "high | medium | low"
}
```

#### Checkpoint: Unit Review (`agent.py:checkpoint_node`)

**Human-in-the-loop**: User reviews generated unit tests.
- **approve** -> proceed to choice node
- **refine** -> loop back to `unit_tests` with feedback

#### Checkpoint: Choice (`agent.py:choice_node`)

**Human-in-the-loop**: User picks the next testing direction.
- **integration** -> `integration_tests` stage
- **e2e** -> `e2e_checkpoint` stage

#### Stage 3a: Integration Tests (`stages/integration.py`) — Budget: 15

**Goal**: Find cross-module integration points and generate test specs.

**LLM**: claude-sonnet-4-6

**Tools allowed**: `impact`, `context`, `query`, `cypher`

**Workflow**:
1. For each changed symbol: get blast radius, map caller/callee chains across module boundaries
2. Group integration points by module pair
3. Call `submit_integration_tests` once

**Submit schema**:
```json
{
  "integration_point": "ModuleA <> ModuleB",
  "modules_involved": ["module_a", "module_b"],
  "test_cases": [{"name": "...", "scenario": "...", "expected": "..."}],
  "data_setup": "preconditions description",
  "risk_level": "CRITICAL | HIGH | MEDIUM | LOW"
}
```

#### Stage 3b: E2E Planning (`stages/e2e.py`) — Budget: 20

**Goal**: Convert execution flows (processes) into user-facing E2E test scenarios.

**LLM**: claude-sonnet-4-6

**Tools allowed**: `impact`, `query`, `cypher`, `list_processes`, `get_process`

**Preceded by**: `e2e_checkpoint` — optional human context input about user flows, bug reports, or edge cases.

**Workflow**:
1. Identify processes affected by the PR
2. Fetch full step-by-step flow for each via `get_process`
3. Convert technical steps into tester-friendly actions
4. Call `submit_e2e_plans` once

**Fallback**: If no processes exist in the graph, generate E2E plans directly from the PR diff and changed files.

**Submit schema**:
```json
{
  "process": "process_name",
  "scenario": "Human-readable scenario title",
  "preconditions": "game state, user role, required data",
  "steps": [{"step": 1, "action": "what the tester does", "expected": "what they see"}],
  "affected_by_pr": ["SymbolA", "SymbolB"],
  "priority": "CRITICAL | HIGH | MEDIUM | LOW",
  "estimated_duration": "5 min"
}
```

#### Submit Node (`agent.py:submit_node`)

Terminal node. Sets `current_stage = "done"`. The graph runner reads `affected_components` and `e2e_test_plans` from final state and emits a `ResultEvent`. The run is persisted to `pr_analyses` in Supabase.

---

## Pipeline 2: Bug Reproduction

**Purpose**: Take a plain-text bug description, trace it through the codebase and external data sources, and produce a structured, actionable bug report.

**Entry point**: `POST /bug-report` -> `bug_agent.py:run_bug_report()`

### Graph Topology

```
triage ──► mechanics_analysis ──► checkpoint_mechanics ──┐
                                                         │
                                         ┌───────────────┤
                                         │ (refine)      │ (approve)
                                         ▼               ▼
                                 mechanics_analysis   reproduction_planning
                                                         │
                                                         ▼
                                                      research ──► checkpoint_research ──┐
                                                                                         │
                                                                         ┌───────────────┤
                                                                         │ (add_context) │ (approve)
                                                                         ▼               ▼
                                                                      research    report_generation
                                                                                         │
                                                                                        END
```

### State (`BugReproductionState`)

| Field | Type | Description |
|---|---|---|
| `description` | `str` | Plain-text bug description from QA |
| `environment` | `str \| None` | OS, build, platform info |
| `severity_input` | `str \| None` | User-provided severity estimate |
| `repo_name` | `str \| None` | GitNexus repo identifier |
| `jira_ticket` | `str \| None` | Existing Jira ticket to update |
| `attachments` | `list[str]` | File paths (HAR files, screenshots, etc.) |
| `session_id` | `str` | Unique session ID |
| `repo_stats` | `dict` | Pre-fetched repo statistics |
| `processes` | `list[dict]` | Pre-fetched execution flows |
| `triage` | `dict` | Stage 1 output: category, keywords, severity, hypotheses |
| `mechanics` | `dict` | Stage 2 output: code paths, affected components, root causes |
| `reproduction_plan` | `dict` | Stage 3 output: steps, prerequisites, environment |
| `research_findings` | `dict` | Stage 4 output: logs, docs, issues, traces |
| `bug_report` | `dict` | Stage 5 output: final synthesized report |
| `current_stage` | `str` | Active stage name |
| `tool_calls_used` | `int` | Cumulative tool call count |
| `available_tools` | `list[str]` | Tool names available in current session |
| `mechanics_feedback` | `str \| None` | User refinement feedback |
| `research_context` | `str \| None` | Additional context from user |

### Stages

#### Stage 1: Triage (`stages/bug_triage.py`) — Budget: 8

**Goal**: Parse, classify, and locate the bug in the codebase.

**LLM**: claude-haiku-4-5 (lightweight — classification task)

**Tools allowed**: `jira_search`, `jira_get_issue`, `jira_get_comments`, `search_code`, `cypher`, `impact`, `list_repos`

**Workflow**:
1. Extract: `bug_category` (crash/gameplay/networking/UI/data/performance/other), `keywords` (3-8 terms), `severity`, `affected_area`
2. Optional: Search Jira for similar issues
3. `search_code` to find relevant files/symbols
4. `cypher` to find symbols defined in relevant files
5. Form 1-3 initial hypotheses
6. Call `submit_triage`

**Output**: Populates `triage` with `{bug_category, keywords, severity, affected_area, similar_issues, affected_files, initial_hypotheses, confidence}`

#### Stage 2: Mechanics Analysis (`stages/bug_mechanics.py`) — Budget: 15

**Goal**: Trace the bug through the codebase, map call chains, produce ranked root cause hypotheses.

**LLM**: claude-sonnet-4-6

**Tools allowed**: `get_file_contents`, `search_code`, `cypher`, `query`, `context`, `impact`, `list_directory`

**Workflow**:
1. Read affected files from triage
2. Find symbols defined in each file via `cypher`
3. Get blast radius (`impact`) and caller/callee chains (`context`) for key symbols
4. Trace full execution path from entry point to failure
5. Rank root cause hypotheses with evidence
6. Call `submit_mechanics`

**Output**: Populates `mechanics` with `{code_paths, affected_components, root_cause_hypotheses}`

#### Checkpoint: Mechanics Review (`bug_agent.py:_checkpoint_mechanics_node`)

**Human-in-the-loop**: User reviews affected components and root cause hypotheses.
- **approve** -> proceed to reproduction planning
- **refine** -> loop back to `mechanics_analysis` with feedback

#### Stage 3: Reproduction Planning (`stages/bug_reproduction.py`) — Budget: 12

**Goal**: Translate code paths into step-by-step QA-friendly reproduction instructions.

**LLM**: claude-sonnet-4-6

**Tools allowed**: `get_file_contents`, `search_code`, `cypher`, `context`, `list_directory`, `list_processes`, `get_process`

**Workflow**:
1. Read mechanics output (code paths, hypotheses)
2. Optionally read files to clarify UI actions or game state
3. Identify prerequisites and environment requirements
4. Write sequential steps: each is a single concrete action + expected result
5. Call `submit_reproduction`

**Key constraint**: Steps must be written for a QA tester, not a developer. No code, no class names, plain language only.

**Output**: Populates `reproduction_plan` with `{steps, prerequisites, environment_requirements, confidence}`

#### Stage 4: Research (`stages/bug_research.py`) — Budget: 20

**Goal**: Query all configured external sources for corroborating evidence.

**LLM**: claude-sonnet-4-6

**Tools allowed**: `cypher`, `query`, `jira_search`, `jira_get_issue`, `jira_get_comments`, `notion_search`, `notion_get_page`, `confluence_search`, `confluence_get_page`, `grafana_query_logs`, `kibana_search`, `sniffer_parse_har`, `sniffer_find_errors`

**Workflow** (each source independent — failures don't block others):
1. **Jira**: Search for similar issues, fetch most relevant
2. **Documentation** (Notion/Confluence): Search for pages about the affected subsystem
3. **Logs/Metrics** (Grafana/Kibana): Query for error messages, stack traces
4. **Network Traces** (Sniffer): Parse HAR files from attachments
5. **Code Graph**: Semantic search over execution flows
6. Call `submit_research`

**Output**: Populates `research_findings` with `{log_entries, doc_references, related_issues, network_traces, code_graph_hits, sources_queried, sources_with_results}`

#### Checkpoint: Research Review (`bug_agent.py:_checkpoint_research_node`)

**Human-in-the-loop**: User reviews evidence summary.
- **approve** -> proceed to report generation
- **add_context** -> loop back to `research` with additional context

#### Stage 5: Report Generation (`stages/bug_report.py`) — Budget: 5

**Goal**: Synthesize all prior stage outputs into a complete, actionable bug report.

**LLM**: claude-haiku-4-5 (lightweight — synthesis, no research)

**Tools allowed**: `jira_create_issue`, `jira_update_issue` (conditional on env vars)

**Workflow**:
1. Read all stage outputs from conversation history
2. Synthesize a `BugReport` with: title, severity, affected_components, root_cause, reproduction_steps, evidence, recommendations
3. Optionally push to Jira (create or update)
4. Call `submit_report`

**Output**: Populates `bug_report` — the final `BugReport` model. The run is persisted to `bug_reports` in Supabase.

**Final `BugReport` schema**:
```json
{
  "title": "Fast Travel wipes equipped items via InventoryManager.reset",
  "severity": "critical | major | minor | trivial",
  "affected_components": [
    {
      "component": "InventoryManager",
      "impact_summary": "One sentence",
      "impact_detail": "2-4 sentences",
      "files_changed": ["..."],
      "risks": ["..."],
      "confidence": "high | medium | low"
    }
  ],
  "root_cause": "One sentence max 25 words",
  "root_cause_detail": "3-5 sentences with evidence",
  "reproduction_steps": [
    {"step": 1, "action": "Open inventory", "expected": "All items visible"}
  ],
  "prerequisites": ["Player must have 6+ items equipped"],
  "environment_requirements": ["Windows 11, build 2.4.1"],
  "evidence": {
    "log_entries": [],
    "doc_references": [],
    "related_issues": [],
    "network_traces": []
  },
  "recommendations": ["Add null-check in X.foo() before calling Y.bar()"],
  "recommendation_details": ["Expanded explanation..."],
  "confidence": "high | medium | low",
  "jira_url": "https://..."
}
```

---

## Tool System (MCP)

All external integrations are MCP (Model Context Protocol) servers managed via `tools.py`. Each pipeline run opens persistent stdio sessions once and reuses them across all stages.

### MCP Servers

| Server | Transport | Command | Required Env Vars | Purpose |
|---|---|---|---|---|
| **GitHub** | stdio | `npx @modelcontextprotocol/server-github` | `GITHUB_TOKEN` | PR data, file contents, code search |
| **GitNexus** | stdio | `gitnexus mcp` | Binary on PATH | Knowledge graph: call graphs, impact, processes |
| **Jira** | stdio | `mcp-atlassian` | `JIRA_URL`, `JIRA_API_TOKEN` | Issue tracking, search, create/update |
| **Notion** | stdio | `npx @notionhq/notion-mcp-server` | `NOTION_API_KEY` | Documentation search |
| **Confluence** | stdio | `mcp-atlassian` | `CONFLUENCE_URL`, `CONFLUENCE_TOKEN` | Documentation search |
| **Grafana** | stdio | `python -m mcp_servers.grafana_server` | `GRAFANA_URL`, `GRAFANA_API_KEY` | Log queries |
| **Kibana** | stdio | `python -m mcp_servers.kibana_server` | `KIBANA_URL`, `KIBANA_TOKEN` | Elasticsearch log queries |
| **Postman** | stdio | `python -m mcp_servers.postman_server` | `POSTMAN_API_KEY` | API collection data |

### Tool Name Normalization

Community MCP servers use varying naming conventions. Qlankr normalizes them to canonical names:

| MCP Native Name | Canonical Name |
|---|---|
| `search_issues` | `jira_search` |
| `get_issue` | `jira_get_issue` |
| `create_issue` | `jira_create_issue` |
| `API-post-search` | `notion_search` |
| `API-retrieve-a-page` | `notion_get_page` |
| `search_pages` | `confluence_search` |
| `get_page_content` | `confluence_get_page` |

### Stage Tool Filtering

Each stage gets only its allowed tools. The `filter_tools(all_tools, stage)` function applies an allowlist per stage:

| Stage | Allowed Tools |
|---|---|
| `gather` | `get_pull_request`, `get_pull_request_files`, `get_pull_request_comments`, `get_file_contents`, `list_directory`, `search_code`, `get_commits`, `list_repos`, `impact`, `cypher`, `detect_changes` |
| `unit` | `context`, `cypher`, `get_file_contents` |
| `integration` | `impact`, `context`, `query`, `cypher` |
| `e2e` | `impact`, `query`, `cypher` + injected `list_processes`, `get_process` |
| `bug_triage` | `jira_search`, `jira_get_issue`, `jira_get_comments`, `search_code`, `cypher`, `impact`, `list_repos` |
| `bug_mechanics` | `get_file_contents`, `search_code`, `cypher`, `query`, `context`, `impact`, `list_directory` |
| `bug_reproduction` | `get_file_contents`, `search_code`, `cypher`, `context`, `list_directory`, `list_processes`, `get_process` |
| `bug_research` | `cypher`, `query`, `jira_search`, `jira_get_issue`, `jira_get_comments`, `notion_search`, `notion_get_page`, `confluence_search`, `confluence_get_page`, `grafana_query_logs`, `kibana_search`, `sniffer_parse_har`, `sniffer_find_errors` |
| `bug_report` | `jira_create_issue`, `jira_update_issue` (if env vars set) |

### Safety & Budget Mechanisms

- **`safe_tools()`**: Wraps each tool so MCP errors become ToolMessages instead of crashing the pipeline.
- **`make_messages_modifier()`**: Pre-model hook that truncates any ToolMessage content >12,000 chars before it reaches the LLM.
- **`make_budget_warning_hook(budget, threshold_pct=0.50)`**: Injects a one-time warning message when 50% of the budget is consumed, telling the LLM to stop research and submit immediately.
- **`fix_dangling_tool_calls()`**: After a budget break, appends synthetic ToolMessages for any unmatched `tool_call_id` so the chat history stays valid.
- **Unicode sanitization** (`_sanitize()`): Translates non-ASCII chars (em dashes, smart quotes, etc.) to ASCII before passing to GitNexus, which requires ASCII-only arguments.

---

## Prompts

All prompts live in `agent/prompts.py` (PROMPT_VERSION = "2.0").

### Architecture

Each stage's ReAct sub-agent receives: `BASE_PROMPT + STAGE_PROMPT` as a `SystemMessage`.

### Base Prompts

| Prompt | Used By | Content |
|---|---|---|
| `BASE_PROMPT` | All Impact stages | Describes Qlankr's role, the GitHub+GitNexus environment, graph schema (nodes: File/Function/Class/Method/Interface/Community/Process, edges: CodeRelation with type property), tool list, and rules (no hallucination, ASCII-only for GitNexus, ground all claims in tool output) |
| `BUG_BASE_PROMPT` | All Bug stages | Same structure as BASE_PROMPT but for bug reproduction. Adds external tool descriptions (Jira, Notion, Confluence, Grafana, Kibana, Sniffer). Rules: write for QA testers, skip unavailable tools, don't retry failures |

### Stage Prompts

| Prompt | Budget | Key Instructions |
|---|---|---|
| `GATHER_PROMPT` | 15 | 4-step workflow: fetch PR -> build components -> enrich with graph -> submit. Keep `impact_summary` to ONE sentence. |
| `UNIT_PROMPT` | 15 | Generate UnitTestSpec per symbol. Must call `submit_unit_tests` once per component. 2-5 test cases per symbol. |
| `INTEGRATION_PROMPT` | 15 | Find cross-module integration points via blast radius and caller/callee chains. Stop at 10 research calls. |
| `E2E_PROMPT` | 20 | Convert processes to user-facing test scenarios. Fallback: generate from PR diff if no processes. Reserve last 5 calls for synthesis. |
| `BUG_TRIAGE_PROMPT` | 8 | Extract category/keywords/severity/area. Search Jira + code. Form 1-3 hypotheses. |
| `BUG_MECHANICS_PROMPT` | 15 | Trace execution paths, map call chains, rank hypotheses with evidence. Stop at 12 research calls. |
| `BUG_REPRODUCTION_PROMPT` | 12 | Translate code paths to QA-friendly steps. No code, plain language. Min 3 steps, ideally 5-8. |
| `BUG_RESEARCH_PROMPT` | 20 | Query all 5 source groups independently. Breadth over depth. Skip unavailable sources. |
| `BUG_REPORT_PROMPT` | 5 | Synthesis only. Assemble BugReport from all stages. Optional Jira push. Keep summaries SHORT. |

### Budget Enforcement

Every prompt explicitly states:
1. The total budget (e.g., "15 tool calls maximum")
2. A stop threshold (e.g., "After 12 calls, stop and submit")
3. A reserve for submit (e.g., "Reserve last 5 for synthesis + submit")

The `make_budget_warning_hook` also injects a runtime warning at 50% budget consumption.

---

## Session & State Management

### In-Memory Sessions

Two session stores exist (both in-memory, keyed by `session_id`):

1. **`agent.py:_sessions`** — Impact analysis metadata: `{pr_url, repo_name}`
2. **`bug_agent.py:_bug_sessions`** — Bug reproduction metadata: `{description, repo_name, emitted_stages}`

### Formal Session Model (`sessions.py`)

```python
SessionType = Enum("IMPACT_ANALYSIS", "BUG_REPRODUCTION")

Session(
    session_id: str,
    session_type: SessionType,
    pr_url: str | None,
    bug_description: str | None,
    created_at: datetime,
    current_stage: str,
    intermediate_result: dict,
    bug_report: BugReport | None,
)
```

**API**: `create_session()`, `get_session()`, `update_session()`

### Graph Checkpointing

Both graphs use `MemorySaver()` (LangGraph's in-memory checkpointer). The graph singleton ensures the same checkpointer instance is shared between `run_*` and `continue_*` calls, so interrupt/resume works correctly.

---

## Data Persistence

**File**: `db.py`

All user data is persisted in Supabase Postgres with row-level security (RLS). The backend uses a `UserScoped` wrapper that injects the authenticated user's ID into every query, enforced at the database level.

### Authentication (`auth.py`)

JWTs are signed with ES256 (asymmetric). The backend verifies tokens by fetching the project's JWKS endpoint at startup — no shared secret required.

```python
# FastAPI dependency injected into all protected endpoints
async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserRecord
```

### Database Tables

| Table | Columns | Purpose |
|---|---|---|
| `profiles` | `id`, `user_id`, `created_at` | Auto-created on signup via trigger |
| `projects` | `id`, `user_id`, `name`, `repo_url`, `owner`, `repo_name`, `index_status`, `graph_stats`, `last_indexed_at`, `index_error` | Project metadata and indexing state |
| `pr_analyses` | `id`, `user_id`, `project_id`, `pr_number`, `pr_url`, `pr_title`, `status`, `final_result`, `failure_reason`, `created_at` | Saved PR analysis runs |
| `bug_reports` | `id`, `user_id`, `project_id`, `bug_description`, `status`, `final_report`, `severity`, `failure_reason`, `completed_at`, `created_at` | Saved bug report runs |
| `user_credentials` | `user_id`, `anthropic_api_key`, `github_token`, `jira`, `notion`, `confluence`, `grafana`, `kibana`, `postman` | Per-user integration credentials (override env vars) |

### Migrations

Run in order from `backend/migrations/`:

1. `0001_initial_schema.sql` — all tables + RLS policies
2. `0002_profile_trigger.sql` — auto-create profile on user insert
3. `0003_project_names.sql` — add `name` column to projects

---

## API Endpoints

### Indexing & Graph

| Method | Path | Description |
|---|---|---|
| `POST` | `/index` | Index a repository. SSE stream. |
| `GET` | `/repos` | List indexed repositories for current user. |
| `GET` | `/graph/{owner}/{repo}` | Fetch knowledge graph nodes/edges. |

### Projects

| Method | Path | Description |
|---|---|---|
| `GET` | `/projects` | List user projects. |
| `POST` | `/projects` | Create a project. |
| `GET` | `/projects/{id}` | Get project detail. |
| `DELETE` | `/projects/{id}` | Delete a project. |
| `GET` | `/projects/{id}/pr-analyses` | List PR analysis runs for a project. |
| `GET` | `/projects/{id}/bug-reports` | List bug report runs for a project. |

### Impact Analysis

| Method | Path | Description |
|---|---|---|
| `POST` | `/analyze` | Start new PR analysis. SSE stream. |
| `POST` | `/analyze/{session_id}/continue` | Resume from checkpoint. SSE stream. |
| `GET` | `/analyze/{session_id}/status` | Get session status. |

### Bug Reproduction

| Method | Path | Description |
|---|---|---|
| `POST` | `/bug-report` | Start new bug analysis. SSE stream. |
| `POST` | `/bug-report/{session_id}/continue` | Resume from checkpoint. SSE stream. |
| `GET` | `/bug-report/{session_id}/status` | Get session status. |
| `POST` | `/bug-report/{session_id}/export` | Export report as Markdown or PDF. |

### Settings & Credentials

| Method | Path | Description |
|---|---|---|
| `GET` | `/settings/integrations` | List all integration statuses (configured, healthy). |
| `POST` | `/settings/integrations` | Configure integration credentials. |
| `GET` | `/settings/credentials` | Check which credentials are set. |
| `POST` | `/settings/credentials` | Update credentials. |

### SSE Event Types

| Event Type | Pipeline | Payload |
|---|---|---|
| `AgentStepEvent` | Both | `{tool, summary, input, output}` — emitted per tool call |
| `StageChangeEvent` | Impact | `{stage, summary}` — emitted when entering a new stage |
| `BugStageChangeEvent` | Bug | `{stage, summary}` — same for bug pipeline |
| `CheckpointEvent` | Impact | `{session_id, stage_completed, interrupt_type, payload}` — paused for human input |
| `BugCheckpointEvent` | Bug | Same structure for bug pipeline |
| `ResearchProgressEvent` | Bug | `{source, finding_count, summary}` — evidence found per source |
| `ResultEvent` | Impact | `{pr_title, pr_url, pr_summary, affected_components, e2e_test_plans, agent_steps}` |
| `BugReportResultEvent` | Bug | `{session_id, report: BugReport, agent_steps, full_state}` |
| `ErrorEvent` | Both | `{message}` |

---

## Pre-fetch Layer

**File**: `agent/prefetch.py`

Before either graph starts, `prefetch_context()` loads baseline data from GitNexus so stage sub-agents don't waste their tool call budgets on basic context:

1. **Repo stats** via `list_repos` — file count, node count, edge count, community count, process count
2. **Process list** via Cypher — `MATCH (p:Process) RETURN p.id, p.label, p.stepCount LIMIT 100`

Returns `{processes: [...], stats: {...}, changed_symbols: []}`. Always returns a valid dict — never raises.

This data is injected into the initial state of both graphs and is available to all stages from the start.

---

## Evaluations

**Files**: `evals/run_evals.py`, `evals/run_bug_evals.py`, `evals/evaluators.py`, `evals/bug_evaluators.py`

Both pipelines have a LangSmith evaluation suite with deterministic checks and LLM-as-judge evaluators.

### Datasets

| Dataset | Examples | Tests |
|---|---|---|
| `qlankr-eval-indexed` | 1 | PR analysis — Qlankr repo, full GitNexus |
| `qlankr-eval-github` | 7 | PR analysis — external repos, GitHub-only |
| `qlankr-eval-bugs` | 5 | Bug reproduction — legacy examples |
| `qlankr-eval-bugs-real` | 6 | Real bugs from OpenTTD, Cataclysm-DDA, osu!, Luanti |
| `qlankr-eval-bugs-synthetic` | 6 | Adversarial examples targeting specific failure modes |

### PR Analysis Evaluators (`evaluators.py`)

**Structural** (free, no LLM): `output_completeness`, `component_count`, `unit_test_structure`, `integration_test_structure`, `e2e_plan_structure`

**Tool usage**: `tool_coverage`, `tool_efficiency`, `gitnexus_usage`, `confidence_calibration`

**Pipeline**: `pipeline_progression`, `no_crash`

**LLM judges** (~$0.01/example): `surface_groundedness` (fetches real PR diff via GitHub API), `depth_groundedness` (reads tool transcripts), `risk_quality`, `component_matching`, `unit_test_quality`, `integration_test_quality`

### Bug Reproduction Evaluators (`bug_evaluators.py`)

**Deterministic**: `triage_accuracy`, `mechanics_grounding`, `reproduction_executability`, `bug_pipeline_health`, `research_coverage`, `report_completeness`, `report_actionability`, `evidence_quality`, `tool_efficiency`, `graceful_degradation`, `keyword_recall`, `affected_file_recall`

**LLM judges**: `root_cause_quality` (semantic alignment with expected root cause), `report_coherence` (internal consistency + specificity), `reproduction_step_clarity` (are steps actually executable?)

### Baselines (`evals/baselines/`)

- **Vanilla Claude** (`vanilla_claude_target.py`): Runs structured QA plans directly against Claude without the pipeline. Benchmark lower bound.
- **Claude Code** (`claude_code_target.py`): Runs full skill prompts without pipeline overhead. Fairer comparison target — isolates prompt quality from infrastructure.
