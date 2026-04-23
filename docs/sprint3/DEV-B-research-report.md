# Person 2 — Research + Report Stages + Graph Wiring + Prompts + BugCheckpointDialog + ResearchPanel

**Branch:** `p2/bug-repro-research-report`
**Depends on:** Person 3's models branch (rebase first), Person 4's MCP integrations (research stage calls P4's tools)
**Coordinate with:** Person 1 (`BugReproductionState` co-definition), Person 4 (`get_available_integrations()`)

**Files owned:**
- `backend/agent/bug_agent.py` — NEW: full StateGraph wiring + entry points
- `backend/agent/stages/bug_research.py` — NEW
- `backend/agent/stages/bug_report.py` — NEW
- `backend/agent/bug_prompts.py` — NEW: all prompts
- `backend/evals/bug_evaluators.py` — NEW (P2 adds bottom section after P1's evaluators)
- `frontend/src/components/BugCheckpointDialog.tsx` — NEW
- `frontend/src/components/ResearchPanel.tsx` — NEW

---

## Overview

Person 2 owns the two final stages of the pipeline plus the orchestration layer that ties all five stages together. Person 1's stages must be callable before you wire the graph, but you can scaffold `bug_agent.py` early with stub nodes.

**Full graph:**
```
triage → mechanics_analysis → checkpoint_mechanics ──(approve)──→ reproduction_planning
              ↑ P1                    ↑ P2          (refine↑)            ↑ P1
                                                                          ↓
                                                                       research
                                                                          ↓
                                                            checkpoint_research ──(approve)──→ report_generation → END
                                                                    ↑ P2         (add_ctx↑)          ↑ P2
```

---

## StateGraph Wiring (`backend/agent/bug_agent.py`)

### `BugReproductionState` TypedDict (co-define with Person 1)

```python
class BugReproductionState(TypedDict):
    # Input
    description: str
    environment: str | None
    severity_input: str | None
    repo_name: str | None
    jira_ticket: str | None
    attachments: list[str]
    session_id: str
    # Pre-fetched
    repo_stats: dict
    processes: list[dict]
    # Stage outputs
    triage: dict
    mechanics: dict
    reproduction_plan: dict
    research_findings: dict
    bug_report: dict
    # Orchestration
    current_stage: str
    tool_calls_used: int
    messages: list
    available_tools: list[str]
    # Human-in-the-loop
    mechanics_feedback: str | None
    research_context: str | None
```

### Node stubs (for early scaffolding)

```python
async def triage_node(state: BugReproductionState) -> dict:
    from agent.stages.bug_triage import run_triage
    return await run_triage(state, _llm)

async def mechanics_analysis_node(state: BugReproductionState) -> dict:
    from agent.stages.bug_mechanics import run_mechanics
    return await run_mechanics(state, _llm)

# ... and so on for all 5 stages
```

### Checkpoint nodes

```python
def checkpoint_mechanics_node(state: BugReproductionState) -> dict:
    response = interrupt({
        "type": "bug_checkpoint",
        "stage_completed": "mechanics_analysis",
        "intermediate_result": {
            "components": state.get("mechanics", {}).get("affected_components", []),
            "hypotheses": state.get("mechanics", {}).get("root_cause_hypotheses", []),
            "code_paths": state.get("mechanics", {}).get("code_paths", []),
        },
        "prompt": (
            "Mechanics analysis complete.\n"
            "  approve — proceed to reproduction planning\n"
            "  refine  — provide feedback to improve the analysis"
        ),
    })
    if response.get("action") == "refine":
        return {"current_stage": "mechanics_analysis", "mechanics_feedback": response.get("feedback", "")}
    return {"current_stage": "reproduction_planning", "mechanics_feedback": None}


def checkpoint_research_node(state: BugReproductionState) -> dict:
    findings = state.get("research_findings", {})
    response = interrupt({
        "type": "bug_checkpoint",
        "stage_completed": "research",
        "intermediate_result": {
            "log_entries_count": len(findings.get("log_entries", [])),
            "doc_references_count": len(findings.get("doc_references", [])),
            "related_issues_count": len(findings.get("related_issues", [])),
            "evidence_summary": findings.get("evidence_summary", ""),
        },
        "prompt": (
            "Research complete.\n"
            "  approve     — proceed to report generation\n"
            "  add_context — provide additional context or evidence"
        ),
    })
    if response.get("action") == "add_context":
        return {"current_stage": "research", "research_context": response.get("context", "")}
    return {"current_stage": "report_generation", "research_context": None}
```

### Routers and graph compilation

```python
def _mechanics_router(state: BugReproductionState) -> str:
    return state.get("current_stage", "reproduction_planning")

def _research_router(state: BugReproductionState) -> str:
    return state.get("current_stage", "report_generation")

def build_bug_reproduction_graph():
    graph = StateGraph(BugReproductionState)

    graph.add_node("triage", triage_node)
    graph.add_node("mechanics_analysis", mechanics_analysis_node)
    graph.add_node("checkpoint_mechanics", checkpoint_mechanics_node)
    graph.add_node("reproduction_planning", reproduction_planning_node)
    graph.add_node("research", research_node)
    graph.add_node("checkpoint_research", checkpoint_research_node)
    graph.add_node("report_generation", report_generation_node)
    graph.add_node("submit_report", submit_report_node)

    graph.set_entry_point("triage")
    graph.add_edge("triage", "mechanics_analysis")
    graph.add_edge("mechanics_analysis", "checkpoint_mechanics")
    graph.add_conditional_edges(
        "checkpoint_mechanics", _mechanics_router,
        {"mechanics_analysis": "mechanics_analysis", "reproduction_planning": "reproduction_planning"},
    )
    graph.add_edge("reproduction_planning", "research")
    graph.add_edge("research", "checkpoint_research")
    graph.add_conditional_edges(
        "checkpoint_research", _research_router,
        {"research": "research", "report_generation": "report_generation"},
    )
    graph.add_edge("report_generation", "submit_report")
    graph.add_edge("submit_report", END)

    return graph.compile(checkpointer=MemorySaver())
```

### Entry points

```python
async def run_bug_agent(
    description: str,
    environment: str | None = None,
    severity: str | None = None,
    repo_url: str | None = None,
    jira_ticket: str | None = None,
    attachments: list[str] = [],
    session_id: str | None = None,
) -> AsyncIterator[...]:
    """Start a new bug reproduction session. Mirrors run_agent() in agent.py."""
    ...

async def continue_bug_agent(
    session_id: str,
    user_response: dict,
) -> AsyncIterator[...]:
    """Resume after a checkpoint interrupt. Mirrors continue_agent() in agent.py."""
    ...
```

Follow the exact same `_start_graph` / `_resume_graph` / `_stream_graph` pattern from `agent/agent.py`. The bug agent streams `BugStageChangeEvent` and `AgentStepEvent` (from Person 3's models) instead of `StageChangeEvent`.

At startup call `get_available_integrations()` (Person 4) and store the result in `BugReproductionState.available_tools`.

---

## Stage 4: `bug_research.py` — Budget: 20 calls / 120s

**Purpose:** Query all configured external sources and synthesize evidence.

**Tool set key:** `"bug_research"` (defined by Person 4 in `tools.py`)

**`_ResearchOutput` fields:**
- `log_entries: list[dict]` — each: `{timestamp, level, message, source, labels}`
- `doc_references: list[dict]` — each: `{title, url, source, snippet}`
- `related_issues: list[dict]` — each: `{key, summary, status, url}`
- `evidence_summary: str`

**Key behavior:**
- Read `state["available_tools"]` at the start of the agent prompt to tell Claude which sources are configured.
- Emit a `ResearchProgressEvent` SSE after each source completes (handled in `_stream_graph` by detecting tool call completions for source-specific tool names).
- Each source is independent — tool errors must not stop the stage. `safe_tools()` handles this automatically.

**Additional context injection:** If `state.get("research_context")` is set (user added context at checkpoint), prepend it to the human message.

**Return delta:**
```python
{"current_stage": "checkpoint_research", "research_findings": results[-1].dict(), "tool_calls_used": ...}
```

---

## Stage 5: `bug_report.py` — Budget: 5 calls / 60s

**Purpose:** Assemble all stage outputs into a final `BugReport`.

**Tool set key:** `"bug_report"` (defined by Person 4 in `tools.py`)

**`_ReportOutput` fields:** mirrors Person 3's `BugReport` model (all fields required).

**What the agent does:**
1. Take all stage outputs from state (triage, mechanics, reproduction_plan, research_findings).
2. Derive: title (from triage category + affected components), severity (from triage, escalated by research), root cause analysis (mechanics hypotheses + research evidence).
3. Compute confidence: `high` if reproduction steps are complete + evidence exists; `medium` if partial; `low` if hypothesis only.
4. If Jira is in `available_tools` and `jira_ticket` is set: call `jira_update_issue` to link the report.
5. Call `submit_bug_report` with the assembled `BugReport`.

**Return delta:**
```python
{"current_stage": "done", "bug_report": results[-1].dict(), "tool_calls_used": ...}
```

---

## Prompts (`backend/agent/bug_prompts.py`)

Define all six prompts. Follow the same structure as `backend/agent/prompts.py`.

```python
PROMPT_VERSION = "3.0"

BUG_BASE_PROMPT = f"""You are Qlankr, an AI QA assistant for game studios. You help reproduce
and document bugs by tracing them through the codebase and external data sources.
[PROMPT VERSION: {PROMPT_VERSION}]

## Your Environment
1. The bug description provided by a QA tester.
2. The GitNexus knowledge graph (same tools as impact analysis).
3. External tools — only use tools listed in available_tools in your prompt.
   If a tool is not in the list, it is not configured. Do not call it.

## Rules
- Ground every claim in tool output or the bug description. Never invent data.
- Write reproduction steps for a QA tester, not a developer. Plain language.
- CRITICAL: GitNexus tools only accept ASCII. Sanitize inputs before calling.
"""

BUG_TRIAGE_PROMPT = """..."""   # goal, task steps, output schema, allowed tools, budget
BUG_MECHANICS_PROMPT = """..."""
BUG_REPRODUCTION_PROMPT = """..."""
BUG_RESEARCH_PROMPT = """..."""  # include available_tools injection here
BUG_REPORT_PROMPT = """..."""
```

Each stage prompt lists: goal, numbered task steps, output schema, allowed tool names, budget.

---

## Evaluators (`backend/evals/bug_evaluators.py`) — P2 section

Add below Person 1's section (after the marker comment). Return `{"key": str, "score": float, "comment": str}`.

| Evaluator | Type | Logic |
|-----------|------|-------|
| `bug_pipeline_health(outputs)` | Structural | Score 1.0 if no `"error"` key, else 0.0 |
| `research_coverage(outputs)` | Structural | `len(sources_queried) / len(available_tools_in_state)` |
| `report_completeness(outputs)` | Structural | Fraction of required `BugReport` fields non-empty |
| `report_actionability(outputs, reference_outputs)` | LLM judge | Can a developer act on the report without asking follow-up questions? |
| `evidence_quality(outputs, reference_outputs)` | LLM judge | Is evidence relevant to and correctly cited in the root cause analysis? |
| `tool_efficiency(outputs)` | Structural | `1.0 - (tool_calls_used / total_budget)`, clamped to [0, 1] |
| `graceful_degradation(outputs)` | Structural | Score 1.0 if pipeline completed (`bug_report` non-empty) with `available_tools == []` |

LLM judge pattern — use `ChatAnthropic` (same import as `evaluators.py`), call once with a structured prompt, parse score 0–1 from response.

---

## Frontend: `BugCheckpointDialog.tsx`

Reuse the structure of `CheckpointDialog.tsx` from Sprint 2. Render different content based on `stage_completed` in the checkpoint payload.

### Post-mechanics variant (`stage_completed === "mechanics_analysis"`)
- List of affected components with confidence badges
- Root cause hypotheses (numbered, ranked)
- Collapsible code paths section
- Actions: **Approve** or **Refine** (shows feedback textarea on click)
- On Approve: `POST /bug-report/{sessionId}/continue` `{action: "approve"}`
- On Refine: `POST /bug-report/{sessionId}/continue` `{action: "refine", feedback: "..."}`

### Post-research variant (`stage_completed === "research"`)
- Evidence summary paragraph
- Counts: N log entries, N docs, N related issues
- Expandable sections per evidence type
- Actions: **Approve** or **Add Context** (shows textarea on click)
- On Approve: `POST /bug-report/{sessionId}/continue` `{action: "approve"}`
- On Add Context: `POST /bug-report/{sessionId}/continue` `{action: "add_context", additional_context: "..."}`

---

## Frontend: `ResearchPanel.tsx`

Tabbed view of research findings. Receives `ResearchFindings` as prop.

**Tabs:** Logs | Docs | Issues | Network

Each tab shows:
- Count badge on tab header
- If `count === 0` and source was configured: "No findings"
- If source was not configured: "Not configured" (gray, no badge)
- Populated: a scrollable list with relevant fields per source type

**Props:**
```typescript
interface ResearchPanelProps {
  findings: ResearchFindings;
  availableTools: string[];
}
```

---

## Interfaces Consumed

| What | From | Where |
|------|------|-------|
| `get_available_integrations()` | Person 4 | `backend/agent/tools.py` |
| All MCP tools for research/report stages | Person 4 | `backend/agent/tools.py` |
| `BugReport`, `ResearchFindings`, `BugStageChangeEvent`, `BugCheckpointEvent` | Person 3 | `backend/models.py` |
| `create_session()`, `get_session()`, `update_session()` | Person 3 | `backend/agent/sessions.py` |
| `run_triage`, `run_mechanics`, `run_reproduction` | Person 1 | `backend/agent/stages/` |

---

## Acceptance Criteria

- [ ] `build_bug_reproduction_graph()` compiles; 8 nodes visible in LangSmith traces
- [ ] `checkpoint_mechanics` pauses graph and emits `BugCheckpointEvent` with components + hypotheses
- [ ] `checkpoint_research` pauses graph and emits `BugCheckpointEvent` with evidence summary
- [ ] Both checkpoints resume correctly (approve → next stage, refine/add_context → same stage)
- [ ] `run_bug_agent()` and `continue_bug_agent()` stream correct SSE event types
- [ ] Research stage queries all configured sources and skips unconfigured ones silently
- [ ] Research stage emits `ResearchProgressEvent` per source
- [ ] Report stage assembles a complete `BugReport` from state
- [ ] `BugCheckpointDialog` shows correct content for both checkpoint variants
- [ ] `ResearchPanel` tabs render correct counts and empty states
- [ ] All 7 P2 evaluators return valid score dicts
- [ ] `graceful_degradation` evaluator confirms pipeline completes with 0 external tools
