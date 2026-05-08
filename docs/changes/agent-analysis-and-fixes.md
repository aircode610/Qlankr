# PR Analysis Agent — Full Audit & Fixes

## Pipeline Architecture Overview

The PR analysis agent is a LangGraph `StateGraph` with this flow:

```
gather → unit_tests → checkpoint_unit → choice → (integration_tests | e2e_planning) → submit → END
```

Each stage spawns a ReAct sub-agent with:
- **Filtered MCP tools** (per-stage allowlist in `tools.py`)
- **A submit tool** (StructuredTool closure capturing a result holder)
- **A tool call budget** (enforced via event counting)
- **A forced-submit fallback** (when budget exhausts before submit)

The user interacts via SSE-streamed events and human-in-the-loop checkpoints
(approve unit tests → choose integration or e2e → optionally provide e2e context).

---

## Vulnerabilities & Problems Found

### CRITICAL — Fixed

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 1 | **MCP client spawned per process-tool call** | `tools.py:make_process_tools` | Every call to `list_processes` / `get_process` called `get_mcp_client()` → `get_tools()`, spawning ALL MCP server subprocesses (GitHub, GitNexus, Jira, etc.) just to use the `cypher` tool. With 3-4 calls in an E2E stage, that's 12-28 leaked subprocesses per run. |
| 2 | **Cypher string injection** | `tools.py:_cypher_fallback_get_process` | Process names injected into Cypher via f-string: `{name: '{process_name}'}`. Names with single quotes (e.g. `Player's Quest`) break the query syntax silently. |
| 3 | **Forced-submit wastes tool calls** | `e2e.py`, `integration.py` | When budget exhausted, a full ReAct agent was created with only the submit tool. This costs 2+ LLM calls (think → act → think → respond) for what is a single structured-output call. |
| 4 | **Integration test distribution drops specs** | `integration.py:162-168` | Pure substring matching (`"UI" in "AudioUI"` matches, `"inventory system" in "Inventory"` doesn't). Specs that match no component were silently lost. |
| 5 | **Submit rejection breaks event loop** | `e2e.py:175`, `integration.py:147` | Event loop breaks on ANY `submit_e2e_plans` / `submit_integration_tests` tool end — even when rejected with empty args. The agent never gets a chance to retry with the rejection guidance. The LLM commonly calls submit with `{}` first (especially when process graph is empty), gets a helpful rejection message, but the loop exits before the agent sees it. Gather stage already handles this correctly with `if results: break`. |

### HIGH — Fixed

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 5 | **Dead code** — `_make_submit_tool` / `_AnalysisResult` | `agent.py:330-372` | Sprint 1 vestige. Never called — the graph assembles results from state, not from a submit tool. Confusing for maintainers. |
| 6 | **Mutable default arguments** | `gather.py`, `integration.py`, `e2e.py` | `list = []` defaults in submit functions. Classic Python anti-pattern — shared across calls. Benign here (read-only check), but a latent bug waiting to happen. |
| 7 | **Stale tests** | `test_tools.py`, `test_prompts.py` | Tests expected `list_processes`/`get_process` in `E2E_TOOLS` and budget `"10"` in `GATHER_PROMPT` — both changed in prior commits but tests weren't updated. |

### MEDIUM — Documented (not changed)

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 8 | **MCP client not cached across stages** | All stage files | Each stage calls `get_mcp_client()` → `get_tools()` separately. A pipeline run spawns 3-5 MCP client instances. A shared client per run would reduce subprocess churn. |
| 9 | **Budget counts submit tool calls** | All stages | The submit tool itself counts against the research budget. Effective research budget is `BUDGET - 1` (or more if submit is rejected). |
| 10 | **`create_react_agent` deprecation warning** | `gather.py:165` | LangGraph v1.0 moved `create_react_agent` to `langchain.agents`. Current import still works but emits a deprecation warning. |
| 11 | **Generic error messages from `safe_tools`** | `tools.py:safe_tools` | `"Tool error: {e}"` doesn't tell the LLM what went wrong or whether to retry. Could waste budget on repeated failing calls. |

---

## Fixes Applied

### 1. Process tools reuse existing MCP tools (`tools.py`)

**Before:** `make_process_tools(repo_name)` — closures called `get_mcp_client()` on every invocation.

**After:** `make_process_tools(repo_name, all_tools=all_tools)` — accepts the already-loaded tool list from the stage. Builds a tool map once, reuses the `cypher` tool directly. Falls back to spawning a new client only if `all_tools` is `None` (backward compat).

### 2. Cypher string escaping (`tools.py`)

Added `_escape_cypher_string()` that escapes `\` and `'` before embedding in Cypher literals. Applied to `process_name` in `get_process`.

### 3. Structured output replaces forced-submit agents (`integration.py`, `e2e.py`)

**Before:** Budget exhaustion created a `create_react_agent(tools=[submit_tool])` — 2+ LLM calls.

**After:** `llm.with_structured_output(Schema).ainvoke(messages)` — 1 LLM call, Pydantic-validated, no tool overhead. Defined `_IntegrationOutput` and `_E2EOutput` schemas.

### 4. Token-based integration test distribution (`integration.py`)

**Before:** `m.lower() in comp_name or comp_name in m.lower()` — pure substring.

**After:** Tokenize both sides (split on word boundaries, normalize `_` and `-`), match on set intersection. Unmatched specs are attached to ALL components with a log warning — nothing is silently dropped.

### 5. Dead code removed (`agent.py`)

Removed `_make_submit_tool`, `_AnalysisResult`, unused imports (`Annotated`, `BaseModel`, `Field`, `StructuredTool`, `AffectedComponent`, `AnalyzeResponse`, `sys`). Added actual submit tool names to `_tool_summary` for proper SSE trace display.

### 6. Mutable defaults fixed (`gather.py`, `integration.py`, `e2e.py`)

Changed `list = []` to `list | None = None` with explicit `None` → `[]` normalization.

### 8. Submit rejection no longer breaks event loop (`e2e.py`, `integration.py`)

**Before:** Event loop broke on ANY `submit_e2e_plans` / `submit_integration_tests` tool end, including rejections. The LLM called submit with `{}`, got a rejection with retry guidance, but the loop exited before the agent could see the rejection and self-correct.

**After:** Applies the same pattern as the gather stage: only break if results were actually recorded (`if e2e_results: break`). Rejected submits increment a counter; after 3 rejections, fall through to the structured output fallback. This gives the agent up to 3 chances to self-correct before giving up.

### 9. Tests updated (`test_tools.py`, `test_prompts.py`)

- `test_filter_tools_e2e` — expects `{impact, query, cypher}` (process tools are injected, not filtered)
- `test_e2e_includes_process_tools` → `test_e2e_process_tools_not_in_static_set` — asserts the opposite
- `test_budget_mentioned_in_stage_prompt` — gather budget `"10"` → `"15"`

---

## Test Results

```
137 passed, 0 failed, 1 deselected (pre-existing indexer test), 5 warnings
```

The deselected test (`test_embeddings_flag_passed`) is a pre-existing indexer issue unrelated to agent changes.
