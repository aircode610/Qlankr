# Dev A (Danila): Agent Orchestration + Stages

**Branch:** `danila/sprint2`
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

Replace the single `create_react_agent` ReAct loop with a LangGraph `StateGraph` that has 8 nodes:

```
gather → unit_tests → checkpoint_unit ──(approve)──→ choice_node
                           ↑ (rerun)                      ↓           ↓
                                              integration_tests   e2e_checkpoint
                                                      ↓                 ↓ (user provides context)
                                                      ↓            e2e_planning
                                                      ↓                 ↓
                                                        submit
```

**Design decisions (deviates from original spec):**

1. **User picks one stage** — after unit checkpoint is approved, the user explicitly chooses either `integration` or `e2e`. Both do not run automatically. This avoids running expensive stages the user doesn't need.
2. **E2E has its own checkpoint** — before E2E planning starts, the user is asked for any upfront context (bug reports, user flows, edge cases). This is optional but improves E2E quality significantly.
3. **E2E agent can ask mid-run** — the E2E agent has an `ask_user` tool that calls `interrupt()` when it needs specific information it can't determine from the PR alone (e.g., expected UX behavior).
4. **Unit rerun loop** — if the user is unsatisfied with unit test results, they can provide feedback and the unit stage re-runs with that feedback injected into the prompt.

Each stage is a sub-agent (its own ReAct loop with stage-specific tools and prompt) that writes results into shared state.

---

## Architecture

### State Schema

```python
class AnalysisState(TypedDict):
    # Input
    pr_url: str
    repo_name: str | None
    user_context: str | None          # optional bug report / scenario (set at e2e_checkpoint or initial request)
    session_id: str

    # Pre-fetched context (populated by gather stage)
    pr_diff: str                      # full diff text
    pr_files: list[str]               # list of changed file paths
    pr_metadata: dict                 # title, author, description
    processes: list[dict]             # GitNexus process list
    repo_stats: dict                  # files, nodes, edges, communities

    # Stage outputs (populated progressively)
    affected_components: list[dict]   # AffectedComponent dicts with unit_tests + integration_tests
    integration_tests: list[dict]     # IntegrationTestSpec dicts (top-level, distributed back into components)
    e2e_test_plans: list[dict]        # E2ETestPlan dicts

    # Orchestration
    current_stage: str
    tool_calls_used: int
    messages: list

    # Human-in-the-loop
    user_choice: str | None           # "integration" | "e2e" — set by choice_node
    unit_feedback: str | None         # user refinement feedback injected into unit stage on rerun
```

### StateGraph Definition

```python
def _checkpoint_router(state: AnalysisState) -> str:
    """After checkpoint_unit: rerun unit_tests or proceed to choice."""
    return state.get("current_stage", "choice")


def _choice_router(state: AnalysisState) -> str:
    """After choice_node: route to integration_tests or e2e_checkpoint."""
    choice = state.get("user_choice", "integration")
    return "e2e_checkpoint" if choice == "e2e" else "integration_tests"


def build_analysis_graph():
    graph = StateGraph(AnalysisState)

    graph.add_node("gather", gather_node)
    graph.add_node("unit_tests", unit_tests_node)
    graph.add_node("checkpoint_unit", checkpoint_node)
    graph.add_node("choice", choice_node)
    graph.add_node("integration_tests", integration_tests_node)
    graph.add_node("e2e_checkpoint", e2e_checkpoint_node)
    graph.add_node("e2e_planning", e2e_planning_node)
    graph.add_node("submit", submit_node)

    graph.set_entry_point("gather")
    graph.add_edge("gather", "unit_tests")
    graph.add_edge("unit_tests", "checkpoint_unit")

    # After unit checkpoint: approve → choice, refine → back to unit_tests
    graph.add_conditional_edges(
        "checkpoint_unit",
        _checkpoint_router,
        {"unit_tests": "unit_tests", "choice": "choice"},
    )

    # After choice: integration or e2e branch
    graph.add_conditional_edges(
        "choice",
        _choice_router,
        {"integration_tests": "integration_tests", "e2e_checkpoint": "e2e_checkpoint"},
    )

    graph.add_edge("e2e_checkpoint", "e2e_planning")
    graph.add_edge("integration_tests", "submit")
    graph.add_edge("e2e_planning", "submit")
    graph.add_edge("submit", END)

    return graph.compile(checkpointer=MemorySaver())
```

### Interrupt Nodes (Human-in-the-Loop)

There are **four interrupt points** across the graph:

#### 1. `checkpoint_unit` — review unit test results

```python
def checkpoint_node(state: AnalysisState) -> dict:
    response = interrupt({
        "type": "checkpoint",
        "stage_completed": "unit_testing",
        "intermediate_result": {
            "pr_metadata": state.get("pr_metadata", {}),
            "affected_components": [...]   # component name + unit_tests
        },
        "prompt": "Unit tests generated. approve or refine with feedback.",
    })

    if response.get("action") == "refine":
        return {"current_stage": "unit_tests", "unit_feedback": response.get("feedback")}

    return {"current_stage": "choice", "unit_feedback": None}
```

**Possible actions from `/continue`:**
- `approve` → routes to `choice_node`
- `refine` + `feedback` → injects feedback into unit prompt, reruns `unit_tests`

#### 2. `choice_node` — pick next stage

```python
def choice_node(state: AnalysisState) -> dict:
    response = interrupt({
        "type": "choice",
        "options": ["integration", "e2e"],
        "prompt": "Which tests do you want to run? integration or e2e",
    })
    return {"user_choice": response.get("choice"), "current_stage": response.get("choice")}
```

**Possible actions from `/continue`:**
- `choice: "integration"` → routes to `integration_tests`
- `choice: "e2e"` → routes to `e2e_checkpoint`

#### 3. `e2e_checkpoint` — gather upfront E2E context

```python
def e2e_checkpoint_node(state: AnalysisState) -> dict:
    response = interrupt({
        "type": "e2e_context",
        "prompt": "Any context to share before E2E planning? (bug reports, user flows, edge cases — or leave empty)",
    })
    return {"user_context": response.get("context") or state.get("user_context")}
```

**Possible actions from `/continue`:**
- `context: "<text>"` → stored in `user_context`, passed to E2E agent
- `context: ""` → proceeds with no extra context

#### 4. `ask_user` tool (mid-run, inside `e2e_planning`)

The E2E sub-agent has an `ask_user` tool backed by `interrupt()`. When the agent needs information it can't determine from the code (e.g., expected UX behavior, domain rules), it calls this tool:

```python
def ask_user(question: str) -> str:
    response = interrupt({"type": "question", "question": question})
    return response.get("answer", "")
```

The graph pauses, emits the question as an interrupt event, and resumes with the user's answer as the tool return value. The agent then continues its ReAct loop with that information.

---

## Stage Details

### Stage: gather (`backend/agent/stages/gather.py`)

**Purpose:** Pre-fetch all context the other stages need, so they don't waste tool calls on basic info.

**Tools available:** All GitHub MCP tools + `list_repos`, `cypher`, `detect_changes`

**What it does:**
1. Call `get_pull_request` to get PR metadata (title, description, author)
2. Call `get_pull_request_files` to get the diff and changed file list
3. Call `cypher` to find symbols defined in each changed file:
   ```cypher
   MATCH (f:File)-[r:CodeRelation]->(s) WHERE r.type='DEFINES' AND f.filePath='<path>'
   RETURN s.name, labels(s) LIMIT 30
   ```
4. Fetch process list via `list_repos` (stats include process count and names)
5. Write all gathered data into state via `submit_gather` tool

**Budget:** 10 tool calls max
**Timeout:** 60 seconds

**Output into state:**
- `pr_diff`, `pr_files`, `pr_metadata`
- `processes` (list of `{name, description}`)
- Initial `affected_components` list (component names + files, no tests yet)

---

### Stage: unit_tests (`backend/agent/stages/unit.py`)

**Purpose:** For each affected component, generate unit test specifications.

**Tools available:** `context`, `cypher`, `get_file_contents`

**What it does:**
1. Receives `pr_diff` directly in the prompt — does NOT call `get_file_contents` unless it needs deeper info
2. Processes components **one at a time** in a single sequential agent (not per-component sub-agents)
3. For each component, calls `submit_unit_tests(component, unit_tests)` before moving to the next
4. If `unit_feedback` is set in state (rerun triggered by user), injects the feedback into the prompt

**On rerun:** `unit_feedback` from the checkpoint response is prepended to the prompt as:
```
## User Feedback (from previous run — address this)
<feedback text>
```

**Budget:** 15 tool calls max (submit calls exempt from budget)
**Timeout:** 90 seconds

**Output into state:**
- Each `affected_components[i].unit_tests` populated with `UnitTestSpec` entries

---

### Stage: integration_tests (`backend/agent/stages/integration.py`)

**Runs after user picks "integration" at the choice node.**
Works entirely from gather stage output — does not read unit test specs.

**Purpose:** Find cross-module integration points and generate integration test specs.

**Tools available:** `impact`, `context`, `query`, `cypher`

**What it does:**
1. For each changed symbol: use `impact` for blast radius, `context` for call chains crossing module boundaries
2. Group integration points by module pair (e.g., "inventory <> crafting")
3. Call `submit_integration_tests` once with all `IntegrationTestSpec` objects
4. Results are distributed back into `affected_components[i].integration_tests` by module name matching

**Budget:** 15 tool calls max (submit calls exempt)
**Timeout:** 90 seconds

**Output into state:**
- Each `affected_components[i].integration_tests` populated
- Does NOT touch `e2e_test_plans`

---

### Stage: e2e_checkpoint + e2e_planning

**e2e_checkpoint** — interrupt node, no tools. Asks user for upfront context before planning starts.

**e2e_planning** (`backend/agent/stages/e2e.py`) — runs after `e2e_checkpoint`.
Works from `processes` and `affected_components` from gather — does not depend on integration output.

**Purpose:** Map affected execution flows (processes) to user-facing E2E test scenarios.

**Tools available:** `impact`, `query`, `cypher`, `list_processes`, `get_process`, `ask_user`, `submit_e2e_plans`

**What it does:**
1. Reads pre-fetched `processes` from state; uses `impact`/`query` to find which are affected
2. Fetches full process flows via `get_process`
3. Translates technical steps into user-facing test actions + expected outcomes
4. If `user_context` is set, uses it to create a focused regression test
5. When stuck on UX behavior the code doesn't reveal, calls `ask_user(question)` to interrupt and ask the human
6. Calls `submit_e2e_plans` with all `E2ETestPlan` objects when done

**Budget:** 20 tool calls max (submit + ask_user calls exempt)
**Timeout:** 120 seconds

**Output into state:**
- `e2e_test_plans` populated with `E2ETestPlan` entries
- Does NOT touch `affected_components`

---

### Stage: submit

**Purpose:** Marks analysis complete. No tool calls — pure state transition.

```python
def submit_node(state: AnalysisState) -> dict:
    return {"current_stage": "done"}
```

The `run_agent()` wrapper reads `affected_components` and `e2e_test_plans` from state after the graph completes and assembles the `ResultEvent`. The `submit_analysis` tool from Sprint 1 is no longer used.

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
    graph = build_analysis_graph()
    thread_id = session_id or str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = AnalysisState(
        pr_url=pr_url,
        repo_name=repo_name,
        user_context=context,
        session_id=thread_id,
        # ... other fields zeroed
    )

    async for event in graph.astream_events(initial_state, version="v2", config=config):
        # on_chain_start with node name → yield StageChangeEvent
        # on_tool_start → yield AgentStepEvent
        # on_interrupt → yield CheckpointEvent with interrupt payload + session_id
        ...
```

When `interrupt()` fires, the graph pauses mid-stream. The caller receives a `CheckpointEvent` with:
- `session_id` — for the frontend to send to `/continue`
- `type` — "checkpoint" | "choice" | "e2e_context" | "question"
- `payload` — the interrupt value (results, prompt, question, options)

The `/continue` endpoint (owned by Dev C) resumes the graph:
```python
graph.invoke(Command(resume=user_response), config=config)
```

---

## Prompt Structure (`backend/agent/prompts.py`)

**Co-owned with Dev B.** Stage structure defined here; Dev B writes prompt content.

Each stage sub-agent receives `BASE_PROMPT + <STAGE>_PROMPT` as its system message.
Prompts live in `backend/agent/prompts.py`:
- `BASE_PROMPT` — environment, graph schema, rules, tool list
- `GATHER_PROMPT` — gather stage instructions
- `UNIT_PROMPT` — unit stage instructions (includes `submit_unit_tests` requirement)
- `INTEGRATION_PROMPT` — integration stage instructions
- `E2E_PROMPT` — e2e stage instructions (includes `ask_user` and `submit_e2e_plans` requirements)

---

## Interface with Other Devs

### From Dev B (MCP tools):
- `get_mcp_client()` — returns configured `MultiServerMCPClient` (NOT a context manager)
- `filter_tools(all_tools, stage)` — returns tool subset for given stage name
- `make_process_tools(repo_name)` — returns process resource tools for E2E stage

### From Dev C (models + sessions):
- Import all models from `backend/models.py`
- `AnalyzeResponse`, `AffectedComponent`, `UnitTestSpec`, `IntegrationTestSpec`, `E2ETestPlan`
- SSE events: `AgentStepEvent`, `StageChangeEvent`, `CheckpointEvent`, `ResultEvent`, `ErrorEvent`
- `ContinueRequest` for checkpoint resume
- Session helpers: `create_session()`, `get_session()`, `update_session()` from `backend/agent/sessions.py`

### To Dev D (frontend):
- SSE event stream format (documented in Dev C's doc)
- Four interrupt event types the UI must handle:
  - `checkpoint` → show unit test results + approve/refine dialog
  - `choice` → show "integration" vs "e2e" picker
  - `e2e_context` → show free-text context input
  - `question` → show agent question + free-text answer input
- `session_id` is included in every checkpoint event for `/continue` calls

---

## Acceptance Criteria

- [ ] Agent runs as a StateGraph with 8 nodes visible in LangSmith traces
- [ ] Each stage only calls tools from its allowed subset
- [ ] Gather stage pre-populates state with PR data, symbols, and processes
- [ ] Unit stage produces `UnitTestSpec` for every changed symbol, processing components one-at-a-time
- [ ] `checkpoint_unit` pauses graph and emits `CheckpointEvent` with unit results
- [ ] `/continue` with `approve` routes to `choice_node`
- [ ] `/continue` with `refine` + feedback reruns `unit_tests` with feedback injected into prompt
- [ ] `choice_node` pauses and emits a `choice` event with `["integration", "e2e"]` options
- [ ] `/continue` with `choice: "integration"` routes to `integration_tests`
- [ ] `/continue` with `choice: "e2e"` routes to `e2e_checkpoint`
- [ ] `e2e_checkpoint` pauses and asks for upfront context
- [ ] E2E agent calls `ask_user` tool mid-run when it needs information not in the code
- [ ] Integration stage writes only to `affected_components[i].integration_tests`
- [ ] E2E stage writes only to `e2e_test_plans`
- [ ] Per-stage budgets enforced (gather: 10, unit: 15, integration: 15, e2e: 20)
- [ ] Per-stage timeouts enforced (gather: 60s, unit: 90s, integration: 90s, e2e: 120s)
- [ ] Full pipeline completes on a real PR and produces valid output
- [ ] `submit_analysis` tool is no longer used — submit node reads from state directly
