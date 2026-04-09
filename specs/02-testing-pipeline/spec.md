# Sprint 2 Spec: Three-Stage Testing Pipeline + GitNexus UI Integration

**Status:** Draft
**Branch:** `amirali/agent-v2`
**Depends on:** Sprint 1 (impact analysis on PR) — complete

---

## Goals

1. Replace the current Qlankr frontend with the GitNexus web explorer as the UI shell
2. Leverage GitNexus's full MCP tool surface (16 tools) and embedding/process capabilities in the agent
3. Replace the flat "test suggestions" output with a **three-stage testing pipeline**: Unit → Integration → E2E
4. Upgrade the agent from a simple ReAct loop to a multi-phase orchestrator with human-in-the-loop checkpoints
5. (Last step) Make generated tests runnable in an isolated container

---

## Task 1: Switch UI to GitNexus Explorer

### What exists now

- Custom React + Vite + Tailwind frontend (`frontend/src/`)
- Components: `RepoInput`, `KnowledgeGraph` (Sigma.js), `PRInput`, `AgentTrace`, `ImpactSummary`, `ComponentCard`
- SSE streaming from backend (`api.js`)
- Dark theme with purple accent

### What GitNexus web explorer offers

- Client-side graph explorer at `gitnexus.vercel.app` (Tree-sitter WASM + LadybugDB WASM)
- ZIP drag-and-drop upload for repos
- AI chat interface integrated in browser
- **Local Backend Mode** via `gitnexus serve` — auto-discovers locally indexed repos
- Fully client-side: no server needed for code analysis

### What needs to change


| #   | Task                                  | Details                                                                                                                                                                                            | New files/changes                                                                                   |
| --- | ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| 1.1 | **Fork or embed GitNexus web UI**     | Clone the GitNexus web app source. Host it as our frontend shell instead of the current Vite app. Keep the graph explorer + chat panel as-is.                                                      | Replace `frontend/` with GitNexus web source or embed as iframe/microfrontend                       |
| 1.2 | **Add Qlankr panels to the UI**       | Add our QA-specific panels inside the GitNexus shell: PR input, agent trace, testing pipeline results. The graph explorer becomes the primary view, with Qlankr panels as sidebar/drawer overlays. | New components inside the GitNexus app: `PrAnalysisPanel`, `TestPipelinePanel`, `AgentTraceDrawer`  |
| 1.3 | **Connect to Qlankr backend via SSE** | Replace the GitNexus AI chat's backend calls with our FastAPI SSE endpoints (`/index`, `/analyze`, `/graph`). The chat interface becomes the agent interaction surface.                            | Adapter layer that maps GitNexus chat events ↔ Qlankr SSE events                                    |
| 1.4 | **Local Backend Mode integration**    | Use `gitnexus serve` as the local code intelligence backend. Our FastAPI backend calls `gitnexus serve` instead of `gitnexus mcp` for richer interaction (HTTP instead of stdio).                  | Update `backend/agent/tools.py` transport config; update `backend/indexer.py` to use serve endpoint |
| 1.5 | **Preserve repo indexing flow**      | The "index repo" step should work through the new UI — either via the GitNexus ZIP upload or by keeping our URL-based `POST /index` flow and wiring it to a button in the new shell.               | Wire existing `/index` endpoint to new UI entry point                                               |
| 1.6 | **Testing pipeline results view**     | New results panel that shows 3 stages (unit/integration/E2E) as expandable sections with status badges, affected components, and generated test code/plans per stage.                              | New `TestPipelineResults` component replacing `ImpactSummary` + `ComponentCard`                     |


### Acceptance criteria

- A1: User opens the app and sees the GitNexus graph explorer with Qlankr branding
- A2: User can index a repo (URL input or ZIP upload) and see the knowledge graph
- A3: User can enter a PR URL and see the agent working (trace panel)
- A4: Results display in the new 3-stage testing pipeline view
- A5: Graph explorer highlights affected nodes during/after analysis

---

## Task 2: Full GitNexus MCP + Embedding Integration

### What exists now

- Agent uses 5 GitNexus tools: `impact`, `context`, `query`, `cypher`, `detect_changes` + `list_repos`
- MCP transport: stdio (`gitnexus mcp`)
- Embedding: whatever gitnexus indexes by default (may not include semantic embeddings)
- No multi-repo support

### What GitNexus actually offers (16 tools)

- **Per-repo (11):** `query`, `context`, `impact`, `detect_changes`, `rename`, `cypher`, + resource URIs for processes, files, symbols
- **Multi-repo (5):** `group_list`, `group_sync`, `group_contracts`, `group_query`, `group_status`
- **Embeddings:** opt-in via `gitnexus analyze --embeddings` — enables hybrid BM25 + semantic + RRF search
- **Processes:** pre-computed execution flows (entry point → full call chain)

### What needs to change


| #   | Task                                                | Details                                                                                                                                                                                                                       | New files/changes                                                                               |
| --- | --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 2.1 | **Enable semantic embeddings at index time**        | Change `indexer.py` to run `gitnexus analyze --embeddings` instead of bare `gitnexus analyze`. This gives the agent much better `query` results for finding related execution flows.                                          | `backend/indexer.py`: add `--embeddings` flag                                                   |
| 2.2 | **Expose process resources to the agent**           | GitNexus exposes `gitnexus://repo/{name}/processes` and `gitnexus://repo/{name}/process/{name}` resource URIs. The agent should be able to list and inspect execution flows directly.                                         | `backend/agent/tools.py`: register resource URIs as tools or use MCP resource reads             |
| 2.3 | **Use all available MCP tools**                     | Currently we filter to ~6 tools. Expose all 16 tools to the agent, especially `rename` (for refactor PRs) and group tools (for mono-repo or multi-repo setups).                                                               | `backend/agent/tools.py`: remove tool filtering; `backend/agent/prompts.py`: document new tools |
| 2.4 | **Update system prompt with new tool descriptions** | The agent prompt must describe the new tools and when to use them — especially process inspection for E2E test planning, and embeddings-powered `query` for finding related code.                                             | `backend/agent/prompts.py`: expand tool documentation section                                   |
| 2.5 | **Pre-fetch process list before agent runs**        | When analysis starts, fetch `gitnexus://repo/{name}/processes` and inject the list of known execution flows into the agent's initial context. This saves tool calls and helps the agent map affected components to processes. | `backend/agent/agent.py`: fetch processes in `_run_agent_inner`, add to HumanMessage            |


### Acceptance criteria

- B1: `POST /index` runs with `--embeddings` and `query` tool returns semantically ranked results
- B2: Agent can list and inspect individual processes from the knowledge graph
- B3: All 16 GitNexus MCP tools are available to the agent
- B4: System prompt documents all new tools with usage guidance
- B5: Process list is injected into agent context at analysis start

---

## Task 3: Three-Stage Testing Pipeline

This is the core deliverable. Replace the current flat `test_suggestions` (skip/run/deeper) with a structured three-stage output.

### Current output structure

```
AffectedComponent:
  test_suggestions:
    skip: ["..."]
    run: ["..."]
    deeper: ["..."]
```

### New output structure

#### Stage 1 — Unit Tests

For each changed component, generate **concrete unit test specifications** that test the component in isolation.

- **Input:** PR diff + symbol-level impact from GitNexus
- **What the agent does:**
  1. Identify all changed functions/methods/classes from the PR diff
  2. For each changed symbol, use `context` to understand its interface (inputs, outputs, dependencies)
  3. Generate specific test cases: function name, input scenarios, expected behavior, edge cases
  4. Flag mockable dependencies (what to stub out for isolation)
- **Output per component:**
  ```
  unit_tests: [
    {
      target: "PlayerInventory.addItem",
      test_cases: [
        { name: "adds item to empty inventory", scenario: "...", expected: "..." },
        { name: "rejects when inventory full", scenario: "...", expected: "..." }
      ],
      mocks_needed: ["DatabaseConnection", "EventBus"],
      priority: "high" | "medium" | "low"
    }
  ]
  ```

#### Stage 2 — Integration Tests

Find modules that interact with changed components and test the **integration points**.

- **Input:** Stage 1 results + GitNexus `impact` blast radius + `context` callers/callees
- **What the agent does:**
  1. For each changed symbol, use `impact` to find all dependent symbols (depth 1-2)
  2. Use `context` to map caller → callee chains that cross module boundaries
  3. Identify integration surfaces: API boundaries, shared state, event flows, database interactions
  4. Generate integration test specs that test the interaction between the changed and dependent modules
- **Output per integration point:**
  ```
  integration_tests: [
    {
      integration_point: "PlayerInventory ↔ CraftingSystem",
      modules_involved: ["inventory", "crafting"],
      test_cases: [
        { name: "crafting consumes correct inventory items", scenario: "...", expected: "..." },
        { name: "crafting fails gracefully when item removed mid-craft", scenario: "..." }
      ],
      data_setup: "Requires: player with 5 wood, 3 iron in inventory",
      risk_level: "HIGH"
    }
  ]
  ```

#### Stage 3 — End-to-End Test Plan

Provide a complete E2E testing plan based on **affected processes** (execution flows from GitNexus).

- **Input:** Stage 2 results + GitNexus processes (`gitnexus://repo/{name}/processes`) + optional user context (e.g., bug report, user scenario)
- **What the agent does:**
  1. List all processes affected by the PR (via `impact` affected_processes field)
  2. For each affected process, fetch the full execution flow via `gitnexus://repo/{name}/process/{name}`
  3. Map the process steps to user-facing scenarios (e.g., "Player opens inventory → selects item → crafts weapon")
  4. If user provides context (bug report, feature description), trace that scenario through the affected processes
  5. Produce a prioritized E2E test plan with step-by-step manual test scripts
- **Output:**
  ```
  e2e_test_plan: [
    {
      process: "item_crafting_flow",
      scenario: "Player crafts a weapon using inventory items",
      steps: [
        { step: 1, action: "Open inventory", expected: "Inventory panel shows current items" },
        { step: 2, action: "Select crafting recipe", expected: "Required materials highlighted" },
        ...
      ],
      preconditions: "Player has required materials in inventory",
      affected_by_pr: ["addItem change may affect material count validation"],
      priority: "CRITICAL",
      estimated_duration: "5 min"
    }
  ]
  ```

### What needs to change


| #   | Task                                          | Details                                                                                                                                                                                                  | New files/changes                                                                    |
| --- | --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| 3.1 | **New Pydantic models for 3-stage output**    | Replace `TestSuggestions` (skip/run/deeper) with `UnitTest`, `IntegrationTest`, `E2ETestPlan` models. Keep backward compatibility by keeping `AffectedComponent` but replacing `test_suggestions` field. | `backend/models.py`: new models + updated `AffectedComponent`                        |
| 3.2 | **Update `submit_analysis` tool schema**      | The agent's final submission must include all three stages. Update `_AnalysisResult` and the tool description accordingly.                                                                               | `backend/agent/agent.py`: update schema + validation                                 |
| 3.3 | **Update system prompt for 3-stage workflow** | The prompt must instruct the agent to work through all three stages sequentially, using specific tools at each stage.                                                                                    | `backend/agent/prompts.py`: major rewrite of task section                            |
| 3.4 | **Accept optional user context**              | The `POST /analyze` endpoint should accept optional `context` field (bug report, user scenario) that gets injected into the agent's prompt for E2E planning.                                             | `backend/models.py`: update `AnalyzeRequest`; `backend/agent/agent.py`: pass context |
| 3.5 | **New SSE event types for stage transitions** | Emit `stage_change` events so the frontend can show which stage the agent is on: `unit_testing` → `integration_testing` → `e2e_planning`.                                                                | `backend/models.py`: new `StageChangeEvent`; `backend/agent/agent.py`: emit events   |
| 3.6 | **Increase tool call budget**                 | 25 calls won't be enough for 3 stages. Increase to 50 or make it per-stage (e.g., 15/15/20).                                                                                                             | `backend/agent/agent.py`: adjust `MAX_TOOL_CALLS`                                    |


### Acceptance criteria

- C1: Agent produces unit test specs for every changed symbol
- C2: Agent identifies cross-module integration points and produces integration test specs
- C3: Agent maps affected GitNexus processes to E2E test scenarios with step-by-step plans
- C4: Optional user context (bug report) is used to focus E2E test planning
- C5: Frontend displays all 3 stages with expandable sections and status badges
- C6: Stage transitions are streamed via SSE

---

## Task 4: Agent Architecture Upgrade

### What exists now

- Single ReAct loop (`create_react_agent` from LangGraph)
- Flat tool list (all tools available at all times)
- No human-in-the-loop
- No state persistence between stages
- 25 tool call budget, 180s timeout
- Single `submit_analysis` call at the end

### What needs to change


| #   | Task                              | Details                                                                                                                                                                                                                                                                                                                       | New files/changes                                                                                                                                                                         |
| --- | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 4.1 | **Multi-phase agent graph**       | Replace single ReAct loop with a LangGraph **StateGraph** that has explicit nodes for each stage: `gather_context` → `unit_tests` → `integration_tests` → `e2e_planning` → `submit`. Each node is its own sub-agent or tool-calling step with stage-specific instructions.                                                    | `backend/agent/agent.py`: rewrite as StateGraph; new `backend/agent/stages/` directory with `unit.py`, `integration.py`, `e2e.py`                                                         |
| 4.2 | **Human-in-the-loop checkpoints** | After each stage completes, the agent pauses and presents intermediate results to the user. The user can: (a) approve and continue, (b) provide additional context/corrections, (c) skip to next stage, (d) re-run the stage with different parameters. Implement via LangGraph `interrupt()` or SSE-based checkpoint events. | `backend/agent/agent.py`: add checkpoint logic; `backend/models.py`: new `CheckpointEvent`, `CheckpointResponse` models; `backend/main.py`: new `/analyze/{session_id}/continue` endpoint |
| 4.3 | **Session state persistence**     | Each analysis session needs persistent state so the user can interact across multiple requests. Store the agent's intermediate state (gathered context, stage results) in memory (dict keyed by session_id) for now.                                                                                                          | `backend/agent/sessions.py`: session store; `backend/models.py`: session models                                                                                                           |
| 4.4 | **Stage-specific tool access**    | Each stage should only see relevant tools: Stage 1 (unit) uses `context`, `cypher`, GitHub file tools. Stage 2 (integration) adds `impact`, `query`. Stage 3 (E2E) adds process resources. This reduces confusion and token waste.                                                                                            | `backend/agent/stages/*.py`: each stage defines its tool subset                                                                                                                           |
| 4.5 | **Richer resource gathering**     | Before the agent starts, pre-fetch: (a) PR diff + file list from GitHub, (b) process list from GitNexus, (c) repository stats. Inject as structured context so the agent doesn't waste calls on basic info.                                                                                                                   | `backend/agent/agent.py`: pre-fetch in `_run_agent_inner`; new `backend/agent/prefetch.py`                                                                                                |
| 4.6 | **Budget per stage**              | Instead of one flat budget, allocate per stage: ~15 calls for gather+unit, ~15 for integration, ~20 for E2E. Each stage has its own timeout.                                                                                                                                                                                  | `backend/agent/stages/*.py`: per-stage budgets                                                                                                                                            |


### Acceptance criteria

- D1: Agent executes as a multi-phase graph with distinct stages visible in traces
- D2: User can pause between stages and provide additional context
- D3: Session state persists across checkpoint interactions
- D4: Each stage only has access to relevant tools
- D5: Pre-fetched context reduces unnecessary tool calls
- D6: LangSmith traces show clear stage boundaries

---

## Task 5: Containerized Test Execution (Last Step)

### What this is

After the agent generates test specs (stages 1-3), the user should be able to **run** the generated unit and integration tests in an isolated container. E2E tests remain manual (they're test plans, not executable code).

### What needs to be built


| #   | Task                           | Details                                                                                                                                                                                                                   | New files/changes                                                                      |
| --- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| 5.1 | **Test code generation**       | Extend stages 1 and 2 to produce **executable test code** (not just specs). The agent generates actual test files in the project's test framework (pytest, jest, gtest, etc.) based on the repo's existing test patterns. | `backend/agent/stages/unit.py`, `integration.py`: add code generation prompts          |
| 5.2 | **Test runner container spec** | Define a Docker container that: (a) clones the repo at the PR's head commit, (b) installs dependencies, (c) drops in the generated test files, (d) runs the test suite, (e) streams results back.                         | New `backend/runner/Dockerfile.runner`, `backend/runner/run_tests.py`                  |
| 5.3 | **Test execution API**         | New endpoint `POST /run-tests` that accepts a session_id (with generated tests) and spins up the container. Streams test results via SSE.                                                                                 | `backend/main.py`: new endpoint; `backend/runner/executor.py`: container orchestration |
| 5.4 | **Results display**            | Frontend shows test execution results: pass/fail per test, stdout/stderr, duration. Green/red status per stage.                                                                                                           | New UI component for test execution results                                            |
| 5.5 | **Container cleanup**          | Containers are ephemeral — auto-destroyed after results are collected. Resource limits (CPU, memory, timeout) to prevent runaway tests.                                                                                   | `backend/runner/executor.py`: cleanup + resource limits                                |


### Acceptance criteria

- E1: Generated unit tests are syntactically valid for the repo's test framework
- E2: Container clones repo, installs deps, runs tests, and streams results
- E3: Test results are displayed in the UI with pass/fail per test
- E4: Containers are cleaned up after execution
- E5: Resource limits prevent runaway containers

---

## New Files Summary

```
backend/
  agent/
    agent.py                    ← Major rewrite: StateGraph, sessions, checkpoints
    prompts.py                  ← Major rewrite: 3-stage instructions, new tools
    tools.py                    ← Update: all 16 tools, serve transport
    prefetch.py                 ← NEW: pre-fetch PR + processes + stats
    sessions.py                 ← NEW: session state store
    stages/
      __init__.py               ← NEW
      gather.py                 ← NEW: context gathering phase
      unit.py                   ← NEW: unit test generation
      integration.py            ← NEW: integration test generation
      e2e.py                    ← NEW: E2E test plan generation
  runner/
    Dockerfile.runner           ← NEW: test execution container (Task 5)
    executor.py                 ← NEW: container orchestration (Task 5)
    run_tests.py                ← NEW: in-container test runner (Task 5)
  models.py                     ← Update: new test models, stage events, sessions
  main.py                       ← Update: session endpoints, test execution
  indexer.py                    ← Update: --embeddings flag

frontend/                       ← Replace with GitNexus web explorer shell
  (GitNexus source + Qlankr panels)
  PrAnalysisPanel               ← NEW: PR input + analysis trigger
  TestPipelineResults           ← NEW: 3-stage results view
  AgentTraceDrawer              ← NEW: live agent trace overlay
  CheckpointDialog              ← NEW: human-in-the-loop interaction
  TestExecutionPanel            ← NEW: container test results (Task 5)
```

## Models Changes (backend/models.py)

### New models

```python
# Stage 1 - Unit Tests
class UnitTestCase(BaseModel):
    name: str
    scenario: str
    expected: str

class UnitTestSpec(BaseModel):
    target: str                              # symbol being tested
    test_cases: list[UnitTestCase]
    mocks_needed: list[str]
    priority: Literal["high", "medium", "low"]
    generated_code: str | None = None        # Task 5: actual test code

# Stage 2 - Integration Tests
class IntegrationTestCase(BaseModel):
    name: str
    scenario: str
    expected: str

class IntegrationTestSpec(BaseModel):
    integration_point: str                   # "ModuleA ↔ ModuleB"
    modules_involved: list[str]
    test_cases: list[IntegrationTestCase]
    data_setup: str
    risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    generated_code: str | None = None        # Task 5

# Stage 3 - E2E Test Plan
class E2ETestStep(BaseModel):
    step: int
    action: str
    expected: str

class E2ETestPlan(BaseModel):
    process: str                             # GitNexus process name
    scenario: str
    steps: list[E2ETestStep]
    preconditions: str
    affected_by_pr: list[str]
    priority: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    estimated_duration: str

# Updated component model
class AffectedComponent(BaseModel):
    component: str
    files_changed: list[str]
    impact_summary: str
    risks: list[str]
    confidence: Literal["high", "medium", "low"]
    unit_tests: list[UnitTestSpec]
    integration_tests: list[IntegrationTestSpec]

# Updated response
class AnalyzeResponse(BaseModel):
    pr_title: str
    pr_url: str
    pr_summary: str
    affected_components: list[AffectedComponent]
    e2e_test_plans: list[E2ETestPlan]
    agent_steps: int

# New SSE events
class StageChangeEvent(BaseModel):
    type: Literal["stage_change"] = "stage_change"
    stage: Literal["gathering", "unit_testing", "integration_testing", "e2e_planning", "submitting"]
    summary: str

class CheckpointEvent(BaseModel):
    type: Literal["checkpoint"] = "checkpoint"
    session_id: str
    stage_completed: str
    intermediate_result: dict              # partial results so far
    prompt: str                            # what we're asking the user

# Updated request
class AnalyzeRequest(BaseModel):
    pr_url: str
    context: str | None = None             # optional bug report or scenario
    session_id: str | None = None          # for resuming after checkpoint

class ContinueRequest(BaseModel):
    action: Literal["approve", "add_context", "skip", "rerun"]
    additional_context: str | None = None
```

## API Changes (backend/main.py)


| Endpoint                              | Method           | Change                                                                                    |
| ------------------------------------- | ---------------- | ----------------------------------------------------------------------------------------- |
| `POST /analyze`                       | Updated          | Accepts optional `context` and `session_id`; emits `stage_change` and `checkpoint` events |
| `POST /analyze/{session_id}/continue` | **NEW**          | Resume analysis after human-in-the-loop checkpoint                                        |
| `GET /analyze/{session_id}/status`    | **NEW**          | Get current session state and intermediate results                                        |
| `POST /run-tests`                     | **NEW** (Task 5) | Trigger container test execution for a session                                            |
| `GET /run-tests/{session_id}/stream`  | **NEW** (Task 5) | SSE stream of test execution results                                                      |


---

## Implementation Order

```
Phase A: Foundation (Tasks 2 + 3.1-3.3)
  ├─ Enable embeddings in indexer
  ├─ Expose all GitNexus MCP tools
  ├─ Define new Pydantic models for 3-stage output
  ├─ Update system prompt for 3-stage workflow
  └─ Update submit_analysis schema

Phase B: Agent Architecture (Tasks 4.1-4.6)
  ├─ Rewrite agent as LangGraph StateGraph
  ├─ Implement stage-specific sub-agents
  ├─ Add pre-fetch logic
  ├─ Add session state persistence
  ├─ Add per-stage tool access + budgets
  └─ Validate with LangSmith traces

Phase C: Human-in-the-Loop (Tasks 4.2-4.3 + 3.4-3.6)
  ├─ Implement checkpoint events
  ├─ Add /continue endpoint
  ├─ Wire optional user context into E2E stage
  └─ Stage transition SSE events

Phase D: UI Integration (Tasks 1.1-1.6)
  ├─ Fork/embed GitNexus web explorer
  ├─ Add Qlankr panels (PR input, trace, results)
  ├─ Connect SSE endpoints
  ├─ 3-stage results view
  └─ Checkpoint dialog

Phase E: Container Execution (Tasks 5.1-5.5)
  ├─ Test code generation in stages 1-2
  ├─ Runner container + executor
  ├─ /run-tests endpoint
  ├─ Results streaming
  └─ Cleanup + resource limits
```

---

## Open Questions

1. **GitNexus web source licensing** — Can we fork/embed the gitnexus.vercel.app source? Need to check the license. Alternative: keep our React app but adopt the GitNexus visual style and use `gitnexus serve` as the backend.
2. **Embedding indexing time** — `--embeddings` is slower. How much slower for large game repos (Luanti, Cataclysm-DDA)? Need to benchmark.
3. **Test framework detection** — For Task 5 code generation, how does the agent know which test framework the repo uses? We may need a pre-analysis step that detects pytest/jest/gtest/etc.
4. **Container security** — Running user-provided repo code in containers requires sandboxing. Scope the security model before implementing Task 5.
5. **Human-in-the-loop UX** — How long should we wait for user input at checkpoints? Auto-continue after timeout? Make stages optional?

