# Dev A (Danila): Agent Orchestration + Stages

**Branch:** ``
**Depends on:** Dev C's models (rebase once merged)
**Files owned:**
- `backend/agent/agent.py` — rewrite from ReAct to StateGraph
- `backend/agent/prompts.py` — co-owned with Dev B (you define stage structure; Dev B writes stage-specific prompt content)
- `backend/agent/stages/__init__.py` — NEW
- `backend/agent/stages/gather.py` — NEW: context gathering phase
- `backend/agent/stages/unit.py` — NEW: unit test generation stage
- `backend/agent/stages/integration.py` — NEW: integration test generation stage
- `backend/agent/stages/e2e.py` — NEW: E2E test plan stage

**Shared files (coordinate with):**
- `backend/models.py` — owned by Dev C, you import from it
- `backend/agent/tools.py` — owned by Dev B, you call `get_mcp_client()` and use tool subsets
- `backend/agent/prefetch.py` — co-owned with Dev B (they build it, you consume it)
- `backend/agent/sessions.py` — owned by Dev C, you call `create_session()`, `get_session()`, `update_session()`
- `backend/agent/prompts.py` — co-owned with Dev B, you define stage structure; import `BASE_PROMPT`, `GATHER_PROMPT`, etc.

---

## Overview

Replace the single `create_react_agent` ReAct loop with a LangGraph `StateGraph` that has 6 nodes:

```
                                          ┌→ integration_tests ─┐
gather_context → unit_tests → [checkpoint]─┤                     ├→ submit
                                          └→ e2e_planning ───────┘
```

There is **one checkpoint** — after unit tests complete. The user reviews unit results and approves (or re-runs/adds context). Integration and E2E then run **in parallel** since they both work from gather output and don't depend on each other's results. This saves wall-clock time and avoids a second blocking checkpoint.

Each stage is a sub-agent (its own ReAct loop with stage-specific tools and prompt) that writes results into shared state.

---

## Architecture

### State Schema

```python
from typing import TypedDict
from langgraph.graph import MessagesState

class AnalysisState(TypedDict):
    # Input
    pr_url: str
    repo_name: str | None
    user_context: str | None          # optional bug report / scenario
    session_id: str

    # Pre-fetched context (populated by gather stage)
    pr_diff: str                      # full diff text
    pr_files: list[str]               # list of changed file paths
    pr_metadata: dict                 # title, author, description
    processes: list[dict]             # GitNexus process list
    repo_stats: dict                  # files, nodes, edges, communities

    # Stage outputs (populated progressively)
    affected_components: list[dict]   # AffectedComponent dicts with unit_tests
    integration_tests: list[dict]     # IntegrationTestSpec dicts (added to components later)
    e2e_test_plans: list[dict]        # E2ETestPlan dicts

    # Orchestration
    current_stage: str
    tool_calls_used: int
    messages: list                    # LangGraph message history (for sub-agents)
```

### StateGraph Definition

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

def build_analysis_graph():
    graph = StateGraph(AnalysisState)

    graph.add_node("gather", gather_node)
    graph.add_node("unit_tests", unit_tests_node)
    graph.add_node("checkpoint_unit", checkpoint_node)
    graph.add_node("integration_tests", integration_tests_node)
    graph.add_node("e2e_planning", e2e_planning_node)
    graph.add_node("submit", submit_node)

    graph.set_entry_point("gather")
    graph.add_edge("gather", "unit_tests")
    graph.add_edge("unit_tests", "checkpoint_unit")

    # Fan-out: integration and e2e run in parallel after the checkpoint
    graph.add_edge("checkpoint_unit", "integration_tests")
    graph.add_edge("checkpoint_unit", "e2e_planning")

    # Fan-in: submit waits for both to complete
    graph.add_edge("integration_tests", "submit")
    graph.add_edge("e2e_planning", "submit")

    graph.add_edge("submit", END)

    return graph.compile(checkpointer=MemorySaver())
```

**State field ownership (important for parallel nodes):**
- `integration_tests` node writes to `affected_components[i].integration_tests`
- `e2e_planning` node writes to `e2e_test_plans`

These are different state fields so there's no write conflict when they run in parallel. Do not have either node touch the other's field.

### Checkpoint Nodes

Use LangGraph's `interrupt()` to pause the graph and emit a `CheckpointEvent` via SSE:

```python
from langgraph.types import interrupt

def checkpoint_node(state: AnalysisState) -> AnalysisState:
    stage = state["current_stage"]
    # Build intermediate result from state so far
    intermediate = _build_partial_result(state)

    # This pauses the graph — the user must call /continue to resume
    user_response = interrupt({
        "stage_completed": stage,
        "intermediate_result": intermediate,
        "prompt": f"Stage '{stage}' complete. Review results and choose: approve / add_context / skip / rerun",
    })

    # user_response comes from the /continue endpoint
    if user_response["action"] == "add_context":
        state["user_context"] = (state.get("user_context") or "") + "\n" + user_response["additional_context"]

    return state
```

---

## Stage Details

### Stage: gather_context (`backend/agent/stages/gather.py`)

**Purpose:** Pre-fetch all context the other stages need, so they don't waste tool calls on basic info.

**Tools available:** All GitHub MCP tools + `list_repos`, `cypher`

**What it does:**
1. Call `get_pull_request` to get PR metadata (title, description, author)
2. Call `get_pull_request_files` to get the diff and changed file list
3. Call `cypher` to find symbols defined in each changed file:
   ```cypher
   MATCH (f:File)-[r:CodeRelation]->(s) WHERE r.type='DEFINES' AND f.filePath='<path>'
   RETURN s.name, labels(s) LIMIT 30
   ```
4. Fetch process list from pre-fetched data (via `prefetch.py`, provided by Dev B)
5. Write all gathered data into state

**Budget:** 10 tool calls max
**Timeout:** 60 seconds

**Output into state:**
- `pr_diff`, `pr_files`, `pr_metadata`
- `processes` (from prefetch)
- `repo_stats` (from prefetch)
- Initial `affected_components` list (component names + files, no tests yet)

### Stage: unit_tests (`backend/agent/stages/unit.py`)

**Purpose:** For each affected component, generate unit test specifications.

**Tools available:** `context`, `cypher`, `get_file_contents`

**What it does:**
1. For each affected component from gather stage:
   a. Use `context` on changed symbols to understand their interface (params, return types, dependencies)
   b. Use `get_file_contents` to read the actual function code if needed
   c. Generate `UnitTestSpec` objects: target symbol, test cases, mock dependencies, priority
2. Use a sub-agent with a unit-test-specific prompt:

```
You are generating unit test specifications for QA. For each symbol:
- Identify the function signature and what it does
- List 2-5 test cases covering: happy path, edge cases, error conditions
- Identify which dependencies should be mocked for isolation
- Set priority based on risk (high if the symbol is heavily called, low if leaf)

Output must conform to UnitTestSpec schema. Only reference symbols you found via tools.
```

3. Write `unit_tests` list into each `AffectedComponent` in state

**Budget:** 15 tool calls max
**Timeout:** 90 seconds

**Output into state:**
- Each `affected_components[i].unit_tests` populated with `UnitTestSpec` entries

### Stage: integration_tests (`backend/agent/stages/integration.py`)

**Runs in parallel with e2e_planning** after the unit checkpoint. Works entirely from gather stage output — does not read unit test specs.

**Purpose:** Find cross-module integration points and generate integration test specs.

**Tools available:** `impact`, `context`, `query`, `cypher`

**What it does:**
1. For each changed symbol identified in gather stage:
   a. Use `impact` to get blast radius — which other symbols/modules depend on it
   b. Use `context` to map caller/callee chains crossing module boundaries
   c. Use `query` (semantic search) to find related execution flows
2. Group integration points by module pair (e.g., "inventory <> crafting")
3. For each integration point, generate `IntegrationTestSpec`:
   - What modules are involved
   - Test cases for the interaction (data flow, error propagation, state consistency)
   - Data setup requirements
   - Risk level based on blast radius depth

Sub-agent prompt focus:
```
You are identifying integration risks between modules. For each pair of modules
that interact through a changed symbol:
- Describe the integration surface (what data/events cross the boundary)
- Generate 2-4 test cases that verify the integration still works
- Specify what test data/fixtures are needed
- Rate risk: CRITICAL if the integration is in a hot path, LOW if rarely triggered

Use impact and context tools to ground every claim. Do not guess module boundaries.
```

**Budget:** 15 tool calls max
**Timeout:** 90 seconds

**Output into state:**
- Each `affected_components[i].integration_tests` populated
- Cross-component integration specs added

### Stage: e2e_planning (`backend/agent/stages/e2e.py`)

**Runs in parallel with integration_tests** after the unit checkpoint. Works from `processes` and `affected_components` populated by gather — does not depend on integration test output.

**Purpose:** Map affected processes to user-facing E2E test scenarios.

**Tools available:** `impact`, `query`, process resource URIs, `cypher`

**What it does:**
1. From the `processes` list in state, filter to processes affected by the PR
   (use `impact` affected_processes or match process steps to changed symbols)
2. For each affected process, fetch the full flow via process resource URI
3. Translate the technical flow into a user-facing test scenario:
   - Preconditions (game state, user role, etc.)
   - Step-by-step actions and expected outcomes
   - Which PR changes affect which steps
4. If `user_context` is provided (bug report), trace that scenario through affected processes
   and create a focused regression test plan
5. Prioritize: CRITICAL if the process is a core game loop, LOW if administrative

Sub-agent prompt focus:
```
You are writing E2E test plans for a QA tester who will execute them manually.
For each affected execution flow (process):
- Convert technical steps into user-facing actions
- Write clear preconditions (what state the game needs to be in)
- For each step: what the tester does and what they should see
- Flag which steps are affected by the PR and what could go wrong
- Estimate how long the test takes to run manually

If the user provided a bug report or scenario, create a targeted regression test
that traces that specific scenario through the affected code paths.
```

**Budget:** 20 tool calls max
**Timeout:** 120 seconds

**Output into state:**
- `e2e_test_plans` populated with `E2ETestPlan` entries

### Stage: submit

**Purpose:** Assemble final `AnalyzeResponse` from state and yield `ResultEvent`.

No tool calls. Pure assembly:
```python
def submit_node(state: AnalysisState) -> AnalysisState:
    # Validate all components have required fields
    # Build AnalyzeResponse from state
    # The run_agent() wrapper yields this as a ResultEvent
    return state
```

---

## run_agent() Entry Point (rewritten)

```python
async def run_agent(
    pr_url: str,
    context: str | None = None,
    session_id: str | None = None,
) -> AsyncIterator[AgentStepEvent | StageChangeEvent | CheckpointEvent | ResultEvent | ErrorEvent]:
    """
    Entry point. Builds the StateGraph, runs it, yields SSE events.
    If session_id is provided, resumes from checkpoint.
    """
    if session_id:
        session = get_session(session_id)
        # Resume existing graph from checkpoint
        ...
    else:
        session = create_session(pr_url)
        # Start new graph
        ...

    # Pre-fetch (calls Dev B's prefetch module)
    prefetched = await prefetch_context(pr_url, repo_name)

    initial_state = AnalysisState(
        pr_url=pr_url,
        repo_name=repo_name,
        user_context=context,
        session_id=session.session_id,
        processes=prefetched["processes"],
        repo_stats=prefetched["stats"],
        # ... other fields
    )

    graph = build_analysis_graph()

    async for event in graph.astream_events(initial_state, ...):
        # Map LangGraph events to our SSE events
        # Yield StageChangeEvent on node transitions
        # Yield AgentStepEvent on tool calls
        # Yield CheckpointEvent on interrupts
        ...
```

---

## Prompt Structure (`backend/agent/prompts.py`)

**Owned by Dev B.** You define the structural requirements here; Dev B writes the actual prompt content.

Each stage node injects a stage-specific prompt addendum (e.g., `GATHER_PROMPT`, `UNIT_PROMPT`) on top of a shared `BASE_PROMPT`. Import these from `backend/agent/prompts.py` and pass them to the sub-agent for each stage.

---

## Interface with Other Devs

### From Dev B (MCP tools):
- `get_mcp_client()` — returns client with all 16 tools
- `prefetch_context(pr_url, repo_name)` — returns dict with `processes`, `stats`, `pr_data`
- You filter tools per stage using tool name lists

### From Dev C (models + sessions):
- Import all models from `backend/models.py`
- `AnalyzeResponse`, `AffectedComponent`, `UnitTestSpec`, `IntegrationTestSpec`, `E2ETestPlan`
- SSE events: `AgentStepEvent`, `StageChangeEvent`, `CheckpointEvent`, `ResultEvent`, `ErrorEvent`
- `ContinueRequest` for checkpoint resume
- Session helpers: `create_session()`, `get_session()`, `update_session()` from `backend/agent/sessions.py`

### To Dev D (frontend):
- SSE event stream format (documented in Dev C's doc)
- Checkpoint event triggers the `CheckpointDialog` in the UI
- `session_id` is returned in checkpoint events for the frontend to use in `/continue` calls

---

## Acceptance Criteria

- [ ] Agent runs as a StateGraph with 6 nodes visible in LangSmith traces (gather, unit_tests, checkpoint_unit, integration_tests, e2e_planning, submit)
- [ ] Each stage only calls tools from its allowed subset
- [ ] Gather stage pre-populates state with PR data, symbols, and processes
- [ ] Unit stage produces `UnitTestSpec` for every changed symbol found by gather
- [ ] Integration and E2E stages run in parallel after the unit checkpoint
- [ ] Integration stage writes only to `affected_components[i].integration_tests` (no overlap with E2E)
- [ ] E2E stage writes only to `e2e_test_plans` (no overlap with integration)
- [ ] Integration stage produces `IntegrationTestSpec` for cross-module interactions
- [ ] E2E stage produces `E2ETestPlan` for affected processes
- [ ] Single checkpoint (after unit) pauses the graph and emits `CheckpointEvent` via SSE
- [ ] `/continue` with `approve` launches integration + e2e in parallel
- [ ] `/continue` with `add_context` appends user context to state, then launches integration + e2e in parallel
- [ ] `/continue` with `rerun` re-executes the unit stage
- [ ] `/continue` with `skip` goes straight to submit (skips both integration and e2e)
- [ ] Per-stage budgets enforced (gather: 10, unit: 15, integration: 15, e2e: 20)
- [ ] Per-stage timeouts enforced (gather: 60s, unit: 90s, integration: 90s, e2e: 120s)
- [ ] Full pipeline completes on a real PR (Luanti or osu!) and produces valid output
- [ ] `submit_analysis` is no longer a tool — the submit node builds the response directly from state
