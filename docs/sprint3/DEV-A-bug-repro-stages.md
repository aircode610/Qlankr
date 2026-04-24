# Person 1 — Bug Reproduction Stages 1-3 + BugTraceDrawer

**Branch:** `p1/bug-repro-stages`
**Depends on:** Person 3's models branch (rebase before writing any stage code)
**Coordinate with:** Person 4 (`tools.py` tool set additions), Person 2 (`bug_prompts.py` + `BugReproductionState`)

**Files owned:**
- `backend/agent/stages/bug_triage.py` — NEW
- `backend/agent/stages/bug_mechanics.py` — NEW
- `backend/agent/stages/bug_reproduction.py` — NEW
- `backend/agent/tools.py` — extend: add `BUG_TRIAGE_TOOLS`, `BUG_MECHANICS_TOOLS`, `BUG_REPRODUCTION_TOOLS` to `_STAGE_TOOLS`
- `backend/evals/bug_evaluators.py` — NEW (P1 owns top section; P2 adds bottom section)
- `frontend/src/components/BugTraceDrawer.tsx` — NEW

---

## Overview

Build stages 1–3 of the bug reproduction StateGraph. The StateGraph itself is wired by Person 2 (`bug_agent.py`) — your job is to implement the three stage functions that it calls. Follow the exact pattern established in `backend/agent/stages/gather.py`.

**Pipeline position:**
```
triage → mechanics_analysis → checkpoint_mechanics  ← Person 2 owns this checkpoint
  ↑ P1         ↑ P1                  ↑ P2
```

---

## Implementation Pattern

Every stage follows the same structure as `gather.py`. Read it before starting.

```python
# Pattern (from backend/agent/stages/gather.py)
BUDGET = N

async def run_<stage>(state: "BugReproductionState", llm: Any) -> dict:
    client = get_mcp_client()
    all_tools = await client.get_tools()
    stage_tools = safe_tools(filter_tools(all_tools, "<stage_key>"))

    class _Output(BaseModel): ...

    results = []
    def submit_<stage>(...) -> str:
        results.append(_Output(...))
        return "Done."

    submit_tool = StructuredTool.from_function(func=submit_<stage>, name="submit_<stage>", description="...")

    agent = create_react_agent(
        model=llm,
        tools=stage_tools + [submit_tool],
        prompt=SystemMessage(content=f"{BUG_BASE_PROMPT}\n\n{BUG_<STAGE>_PROMPT}"),
    )

    tool_call_count = 0
    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=...)]},
        version="v2",
        config={"recursion_limit": 20},
    ):
        if event["event"] == "on_tool_start":
            tool_call_count += 1
            if event["name"] != "submit_<stage>" and tool_call_count >= BUDGET:
                break

    base_count = state.get("tool_calls_used", 0)
    if not results:
        return {"current_stage": "<next>", "tool_calls_used": base_count + tool_call_count}

    return {"current_stage": "<next>", "<key>": results[-1].dict(), "tool_calls_used": base_count + tool_call_count}
```

**Imports needed:**
```python
from agent.tools import filter_tools, get_mcp_client, safe_tools
from agent.bug_prompts import BUG_BASE_PROMPT, BUG_TRIAGE_PROMPT  # (etc.)
```

---

## Stage 1: `bug_triage.py` — Budget: 8 calls / 60s

**Purpose:** Classify the bug, extract keywords, estimate severity, find similar known issues.

**Tool set key:** `"bug_triage"`

**`_TriageOutput` fields:**
- `bug_category: str` — e.g. "gameplay", "networking", "UI", "data", "crash"
- `keywords: list[str]` — extracted search terms
- `severity: Literal["critical", "high", "medium", "low"]`
- `similar_issues: list[dict]` — each: `{id, title, url, relevance}`
- `affected_files: list[str]`
- `initial_hypotheses: list[str]`

**Human message to agent:**
```python
f"Bug description: {state['description']}\n"
f"Environment: {state.get('environment', 'unknown')}\n"
f"Severity hint: {state.get('severity_input', 'not specified')}\n"
f"Linked Jira ticket: {state.get('jira_ticket', 'none')}\n"
f"Repo: {state.get('repo_name', 'not indexed')}"
```

**Return delta:**
```python
{"current_stage": "mechanics_analysis", "triage": results[-1].dict(), "tool_calls_used": ...}
```

---

## Stage 2: `bug_mechanics.py` — Budget: 15 calls / 90s

**Purpose:** Trace affected code paths, identify components, produce ranked root cause hypotheses.

**Tool set key:** `"bug_mechanics"`

**`_MechanicsOutput` fields:**
- `code_paths: list[dict]` — each: `{path: str, description: str, confidence: str}`
- `affected_components: list[str]`
- `root_cause_hypotheses: list[dict]` — each: `{hypothesis: str, confidence: str, evidence: str}`

If `state.get("mechanics_feedback")` is set (user refined from checkpoint), prepend it to the human message:
```python
feedback_section = ""
if state.get("mechanics_feedback"):
    feedback_section = f"\n\n## QA Tester Feedback (address this):\n{state['mechanics_feedback']}\n"
```

**Human message:** triage keywords + affected files + bug description + feedback section + repo name.

**Return delta:**
```python
{"current_stage": "checkpoint_mechanics", "mechanics": results[-1].dict(), "tool_calls_used": ...}
```

---

## Stage 3: `bug_reproduction.py` — Budget: 12 calls / 90s

**Purpose:** Translate confirmed code paths into QA-readable step-by-step reproduction instructions.

**Tool set key:** `"bug_reproduction"`

**`_ReproductionOutput` fields:**
- `steps: list[dict]` — each: `{step_number: int, action: str, expected_result: str}`
- `prerequisites: list[str]`
- `environment_requirements: list[str]`
- `confidence: Literal["high", "medium", "low"]`

**Human message:** mechanics dict (components + code_paths + hypotheses) + original bug description.

**Return delta:**
```python
{"current_stage": "research", "reproduction_plan": results[-1].dict(), "tool_calls_used": ...}
```

---

## Tool Set Additions (`backend/agent/tools.py`)

Add after the existing `E2E_TOOLS` block (line ~46). Coordinate with Person 4 who adds `BUG_RESEARCH_TOOLS` and `BUG_REPORT_TOOLS` to the same dict:

```python
BUG_TRIAGE_TOOLS: set[str] = {
    "jira_search",
    "jira_get_issue",
    "jira_get_comments",
    "search_code",
    "get_file_contents",
    "cypher",
    "impact",
    "list_repos",
}

BUG_MECHANICS_TOOLS: set[str] = {
    "get_file_contents",
    "search_code",
    "cypher",
    "context",
    "impact",
    "detect_changes",
    "list_directory",
}

BUG_REPRODUCTION_TOOLS: set[str] = {
    "get_file_contents",
    "search_code",
    "cypher",
    "context",
    "list_directory",
    "list_processes",
    "get_process",
}
```

Register in `_STAGE_TOOLS`:
```python
"bug_triage":       BUG_TRIAGE_TOOLS,
"bug_mechanics":    BUG_MECHANICS_TOOLS,
"bug_reproduction": BUG_REPRODUCTION_TOOLS,
```

> `jira_*` tools are configured by Person 3. Include them in the set — `filter_tools()` silently skips missing tools, so no conditional logic is needed.

---

## Evaluators (`backend/evals/bug_evaluators.py`) — P1 section

Follow the exact pattern from `backend/evals/evaluators.py`. Return `{"key": str, "score": float, "comment": str}`.

Leave a clear marker comment for Person 2 to append below:
```python
# ─── Person 2 evaluators below ────────────────────────────────────────────────
```

### `triage_accuracy(outputs, reference_outputs) -> dict`
- `triage["bug_category"]` non-empty → +1
- `triage["severity"]` in `{"critical","high","medium","low"}` → +1
- `triage["keywords"]` has ≥1 entry → +1
- `triage["affected_files"]` has ≥1 entry → +1
- Score = passing checks / 4

### `mechanics_grounding(outputs) -> dict`
- `mechanics["code_paths"]` has ≥1 entry → required
- `mechanics["root_cause_hypotheses"]` has ≥1 entry → required
- Score = fraction of hypotheses where `evidence` field is non-empty

### `reproduction_executability(outputs) -> dict`
- `reproduction_plan["steps"]` has ≥3 entries → required
- Score = fraction of steps where both `action` and `expected_result` are non-empty

---

## Frontend: `BugTraceDrawer.tsx`

Enhanced version of `AgentTraceDrawer.tsx` — read it first (`frontend/src/components/AgentTraceDrawer.tsx`).

### Types

```typescript
type BugStage = 'triage' | 'mechanics_analysis' | 'reproduction_planning' | 'research' | 'report_generation';
type StageStatus = 'pending' | 'running' | 'checkpoint' | 'completed' | 'error';

interface BugStageInfo {
  stage: BugStage;
  status: StageStatus;
  toolCalls: { tool: string; summary: string }[];
}

interface BugTraceDrawerProps {
  stages: BugStageInfo[];
  analyzing: boolean;
  currentStage: BugStage | null;
}
```

### Render logic

- Vertical list of 5 stage rows in order: triage → mechanics → reproduction → research → report.
- Status icon per stage using Lucide icons (match `AgentTraceDrawer.tsx` icon import style):
  - `pending` → `Circle` (gray)
  - `running` → `Loader2 animate-spin` (accent color)
  - `checkpoint` → `PauseCircle` (yellow)
  - `completed` → `CheckCircle` (emerald)
  - `error` → `XCircle` (red)
- Click on `running` or `completed` stage toggles expansion showing tool call cards (same `rounded border border-border-subtle bg-elevated/60` style as `AgentTraceDrawer.tsx:77`).
- `useEffect` + `scrollIntoView` on running stage (same pattern as `AgentTraceDrawer.tsx:38`).
- Footer: total tool calls summed across all stages.

### SSE event wiring (done by parent component, not this component)

| SSE event | Action |
|-----------|--------|
| `bug_stage_change` | Parent updates `stages[n].status` |
| `agent_step` | Parent pushes into `stages[n].toolCalls` |

---

## Interfaces Consumed

| What | From | Where defined |
|------|------|---------------|
| `filter_tools(all_tools, stage)` | Person 4 extends, P1 calls | `backend/agent/tools.py:126` |
| `get_mcp_client()` | Existing | `backend/agent/tools.py:87` |
| `safe_tools(tools)` | Existing | `backend/agent/tools.py:98` |
| `BugReproductionState` TypedDict | Co-owned with Person 2 | `backend/agent/bug_agent.py` |
| All new Pydantic models | Person 3 | `backend/models.py` |
| `BUG_BASE_PROMPT`, `BUG_TRIAGE_PROMPT`, etc. | Person 2 | `backend/agent/bug_prompts.py` |
| Lucide icons | Existing pattern | `frontend/src/lib/lucide-icons` |

---

## Acceptance Criteria

- [ ] `run_triage()`, `run_mechanics()`, `run_reproduction()` importable and callable
- [ ] Each stage returns the correct `current_stage` value pointing to the next node
- [ ] Budget enforced: stage breaks out of event loop at limit (submit tool exempt)
- [ ] `filter_tools(all_tools, "bug_triage")` returns only `BUG_TRIAGE_TOOLS` intersection
- [ ] All three evaluators return `{"key", "score", "comment"}` for valid and empty outputs
- [ ] `BugTraceDrawer` renders 5 stage rows with correct status icons
- [ ] Stage expansion shows tool call cards on click
- [ ] Pipeline works with zero external tools configured (triage + mechanics still run on code graph alone)
