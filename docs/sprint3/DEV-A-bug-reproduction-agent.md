# Dev A: Bug Reproduction Agent — StateGraph + Stages

**Branch:** `deva/bug-repro-agent`
**Depends on:** Dev C's models (rebase once merged), Dev B's tool integrations (for research stage)
**Files owned:**
- `backend/agent/bug_agent.py` — NEW: Bug reproduction StateGraph + orchestration
- `backend/agent/bug_prompts.py` — NEW: Base + per-stage prompts for bug reproduction
- `backend/agent/stages/bug_triage.py` — NEW: Bug triage stage
- `backend/agent/stages/bug_mechanics.py` — NEW: Mechanics analysis stage
- `backend/agent/stages/bug_reproduction.py` — NEW: Reproduction planning stage
- `backend/agent/stages/bug_research.py` — NEW: Research aggregation stage
- `backend/agent/stages/bug_report.py` — NEW: Report generation stage
- `backend/evals/bug_evaluators.py` — NEW: LangSmith evaluators for bug reproduction
- `backend/evals/create_bug_dataset.py` — NEW: Golden dataset builder for bugs

**Shared files (coordinate with):**
- `backend/models.py` — owned by Dev C, you import from it
- `backend/agent/tools.py` — owned by Dev B, you call `filter_tools()` with new stage names
- `backend/agent/sessions.py` — owned by Dev C, you call session helpers
- `backend/agent/bug_prompts.py` — co-owned with Dev B (you define stage structure; Dev B writes tool-specific prompt content)

---

## Overview

Build a new LangGraph `StateGraph` for bug reproduction, parallel to (not replacing) the existing impact analysis graph. The bug reproduction graph has 8 nodes:

```
triage → mechanics_analysis → checkpoint_mechanics ──(approve)──→ reproduction_planning
                                    ↑ (refine)                             ↓
                                                                      research
                                                                         ↓
                                                          checkpoint_research ──(approve)──→ report_generation
                                                                ↑ (add_context)                    ↓
                                                                                             submit_report
                                                                                                   ↓
                                                                                                  END
```

**Design decisions:**

1. **Two checkpoints** — one after mechanics analysis (user confirms the agent identified the right components) and one after research (user confirms enough evidence was gathered or adds context).
2. **Graceful degradation** — each stage checks which external tools are available and adapts. If Grafana is not configured, the research stage skips log queries and notes this in the report. The pipeline must produce a useful report even with zero external tools configured.
3. **Reuse existing models** — `AffectedComponent` and `E2ETestStep` from Sprint 2 are reused for mechanics analysis and reproduction steps. New models from Dev C extend these.
4. **Separate from impact analysis** — different entry point (`run_bug_agent`), different StateGraph, different endpoints. Shares MCP clients and base prompt.

---

## State Schema

```python
class BugReproductionState(TypedDict):
    # Input
    description: str                     # free-text bug description
    environment: str | None              # device/OS/build info
    severity_input: str | None           # user-provided severity
    repo_name: str | None                # indexed repo (if available)
    jira_ticket: str | None              # linked Jira issue key
    attachments: list[str]               # URLs to screenshots/videos/logs
    session_id: str

    # Pre-fetched context
    repo_stats: dict
    processes: list[dict]

    # Stage outputs
    triage: dict                         # TriageResult
    mechanics: dict                      # MechanicsAnalysis
    reproduction_plan: dict              # ReproductionPlan
    research_findings: dict              # ResearchFindings
    bug_report: dict                     # BugReport (final output)

    # Orchestration
    current_stage: str
    tool_calls_used: int
    messages: list
    available_tools: list[str]           # which integrations are active

    # Human-in-the-loop
    mechanics_feedback: str | None       # user refinement after mechanics checkpoint
    research_context: str | None         # additional context added at research checkpoint
```

---

## Stage Details

### Stage: triage (`backend/agent/stages/bug_triage.py`)

**Purpose:** Classify the bug, extract keywords, estimate severity, search for similar known issues.

**Tools available:** `get_commits`, `search_code`, `cypher`, `jira_search`, `jira_get_issue`

**What it does:**
1. Parse the bug description to extract: category (gameplay/networking/UI/data/etc.), keywords, affected subsystem
2. If Jira is configured: search for similar issues using extracted keywords (`jira_search`)
3. If repo is indexed: use `cypher` to find symbols matching keywords
4. Use `search_code` to find relevant recent commits
5. Estimate severity based on bug description + similar issue patterns
6. Call `submit_triage` with the TriageResult

**Budget:** 8 tool calls max
**Timeout:** 60 seconds

**Output into state:**
- `triage` — TriageResult dict
- `current_stage` → `"mechanics_analysis"`

### Stage: mechanics_analysis (`backend/agent/stages/bug_mechanics.py`)

**Purpose:** Trace affected code paths, identify which components and mechanics produce the described behavior.

**Tools available:** `get_file_contents`, `impact`, `context`, `cypher`

**What it does:**
1. Use keywords from triage to find entry points in the code graph
2. For each suspected entry point, call `impact` to trace downstream effects
3. Call `context` on key symbols to understand caller/callee chains
4. Map code paths to game mechanics (e.g., "player takes damage → health check → death handler")
5. Generate root cause hypotheses ranked by likelihood
6. Call `submit_mechanics` with MechanicsAnalysis

**On rerun (refine from checkpoint):** `mechanics_feedback` from checkpoint is prepended:
```
## QA Tester Feedback (from previous run — address this)
<feedback text>
```

**Budget:** 15 tool calls max
**Timeout:** 90 seconds

**Output into state:**
- `mechanics` — MechanicsAnalysis dict (components, code_paths, entry_points, hypotheses)
- `current_stage` → `"checkpoint_mechanics"`

### Stage: checkpoint_mechanics

**Purpose:** Human review — user confirms or refines the component mapping and hypotheses before expensive research.

```python
def checkpoint_mechanics_node(state: BugReproductionState) -> dict:
    response = interrupt({
        "type": "bug_checkpoint",
        "stage_completed": "mechanics_analysis",
        "intermediate_result": {
            "components": state.get("mechanics", {}).get("components", []),
            "hypotheses": state.get("mechanics", {}).get("root_cause_hypotheses", []),
            "code_paths": state.get("mechanics", {}).get("code_paths", []),
        },
        "prompt": (
            "Mechanics analysis complete. Review the components and hypotheses above.\n"
            "  approve — proceed to reproduction planning + research\n"
            "  refine  — provide feedback to improve the analysis"
        ),
    })

    if response.get("action") == "refine":
        return {"current_stage": "mechanics_analysis", "mechanics_feedback": response.get("feedback", "")}
    return {"current_stage": "reproduction_planning", "mechanics_feedback": None}
```

### Stage: reproduction_planning (`backend/agent/stages/bug_reproduction.py`)

**Purpose:** Generate step-by-step reproduction instructions from the mechanics analysis.

**Tools available:** `get_file_contents`, `impact`, `context`, `cypher`, `list_processes`, `get_process`, `postman_get_collection`, `postman_get_request`

**What it does:**
1. Take the confirmed components and hypotheses from mechanics analysis
2. For each hypothesis, trace the execution flow through `get_process` (if processes exist)
3. Translate technical code paths into user-facing reproduction steps
4. If API calls are involved and Postman is configured: pull relevant request specs from collections
5. Define preconditions (game state, data requirements, config flags)
6. Call `submit_reproduction` with ReproductionPlan

**Budget:** 12 tool calls max
**Timeout:** 90 seconds

**Output into state:**
- `reproduction_plan` — ReproductionPlan dict
- `current_stage` → `"research"`

### Stage: research (`backend/agent/stages/bug_research.py`)

**Purpose:** Aggregate evidence from all available external sources.

**Tools available:** `cypher`, `jira_search`, `jira_get_issue`, `jira_get_comments`, `notion_search`, `notion_get_page`, `confluence_search`, `confluence_get_page`, `grafana_query_logs`, `kibana_search`, `sniffer_parse_har`, `sniffer_find_errors`

**What it does:**
1. Check `available_tools` in state to know which integrations are active
2. For each available source, run targeted queries:
   - **Jira:** Search for related issues, read comment threads on linked ticket
   - **Notion/Confluence:** Search for docs/runbooks matching affected components
   - **Grafana/Kibana:** Query logs around the time of the bug (if timestamp available)
   - **Sniffer:** Parse any attached HAR files for network errors
3. Synthesize findings into a coherent evidence summary
4. Emit `ResearchProgressEvent` SSE events as each source completes
5. Call `submit_research` with ResearchFindings

**Important:** Each source query is independent — if one fails, continue with others. Never let a single tool failure block the entire research stage.

**Budget:** 20 tool calls max
**Timeout:** 120 seconds

**Output into state:**
- `research_findings` — ResearchFindings dict
- `current_stage` → `"checkpoint_research"`

### Stage: checkpoint_research

**Purpose:** Human review — user confirms research is sufficient or adds more context.

```python
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
            "Research complete. Review the evidence summary above.\n"
            "  approve      — proceed to report generation\n"
            "  add_context  — provide additional context or evidence"
        ),
    })

    if response.get("action") == "add_context":
        return {"current_stage": "research", "research_context": response.get("context", "")}
    return {"current_stage": "report_generation", "research_context": None}
```

### Stage: report_generation (`backend/agent/stages/bug_report.py`)

**Purpose:** Assemble everything into a structured developer-ready BugReport.

**Tools available:** `jira_create_issue`, `jira_update_issue` (if Jira configured and user opts in)

**What it does:**
1. Assemble all stage outputs into a BugReport:
   - Title derived from triage + mechanics
   - Severity from triage (may be escalated by research findings)
   - Reproduction steps from reproduction_plan
   - Root cause analysis from mechanics hypotheses + research evidence
   - Evidence from research_findings
   - Recommendations: suggested fixes based on code paths and root cause
2. Compute confidence: high (evidence + reproduction confirmed), medium (partial evidence), low (hypothesis only)
3. Optionally push to Jira (if configured and user approved)
4. Call `submit_bug_report` with final BugReport

**Budget:** 5 tool calls max (mostly synthesis, minimal tool use)
**Timeout:** 60 seconds

**Output into state:**
- `bug_report` — BugReport dict
- `current_stage` → `"done"`

---

## Graph Wiring

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
        "checkpoint_mechanics",
        _mechanics_router,
        {"mechanics_analysis": "mechanics_analysis", "reproduction_planning": "reproduction_planning"},
    )

    graph.add_edge("reproduction_planning", "research")
    graph.add_edge("research", "checkpoint_research")

    graph.add_conditional_edges(
        "checkpoint_research",
        _research_router,
        {"research": "research", "report_generation": "report_generation"},
    )

    graph.add_edge("report_generation", "submit_report")
    graph.add_edge("submit_report", END)

    return graph.compile(checkpointer=MemorySaver())
```

---

## Entry Points

```python
async def run_bug_agent(
    description: str,
    environment: str | None = None,
    severity: str | None = None,
    repo_url: str | None = None,
    jira_ticket: str | None = None,
    attachments: list[str] = [],
    session_id: str | None = None,
) -> AsyncIterator[BugStageChangeEvent | AgentStepEvent | CheckpointEvent | BugReportResultEvent | ErrorEvent]:
    ...

async def continue_bug_agent(
    session_id: str,
    user_response: dict,
) -> AsyncIterator[...]:
    ...
```

---

## Prompt Architecture (`backend/agent/bug_prompts.py`)

```python
BUG_BASE_PROMPT = """You are Qlankr, an AI QA assistant for game studios. You help reproduce
and document bugs by tracing them through the codebase and external data sources.
[PROMPT VERSION: 3.0]

## Your Environment
1. The bug description — provided by a QA tester in plain text.
2. The knowledge graph — via GitNexus MCP tools (same as impact analysis).
3. External tools (when configured):
   - Jira/YouTrack — search issues, read tickets
   - Notion/Confluence — search docs, read runbooks
   - Grafana/Kibana — query logs
   - Postman — read API collections
   - Sniffer — parse network captures

## Rules
- Ground every claim in tool output or the bug description. Never invent data.
- If an external tool is not configured, note it in the report and work with what's available.
- Write reproduction steps for a QA tester, not a developer. Plain language.
- Always check available_tools before calling an external tool.
"""

BUG_TRIAGE_PROMPT = """..."""
BUG_MECHANICS_PROMPT = """..."""
BUG_REPRODUCTION_PROMPT = """..."""
BUG_RESEARCH_PROMPT = """..."""
BUG_REPORT_PROMPT = """..."""
```

Each stage sub-agent receives `BUG_BASE_PROMPT + <STAGE>_PROMPT` as its system message, same pattern as Sprint 2.

---

## Evaluation Framework

### New Evaluators (`backend/evals/bug_evaluators.py`)

| Evaluator | Type | What it measures |
|-----------|------|-----------------|
| `bug_pipeline_health` | Structural | Pipeline completes without crash |
| `triage_accuracy` | LLM judge | Does triage correctly classify the bug? |
| `mechanics_grounding` | LLM judge | Are identified components grounded in tool output? |
| `reproduction_executability` | LLM judge | Can a human follow the reproduction steps? |
| `research_coverage` | Structural | How many configured sources were actually queried? |
| `report_completeness` | Structural | Are all BugReport fields populated? |
| `report_actionability` | LLM judge | Can a developer act on this report without clarification? |
| `evidence_quality` | LLM judge | Is evidence relevant and correctly linked to claims? |
| `tool_efficiency` | Structural | Tool calls used vs budget |
| `graceful_degradation` | Structural | Does pipeline complete with 0 external tools? |

### Golden Dataset (`backend/evals/create_bug_dataset.py`)

Build a dataset of 5-8 real or realistic bugs from open-source games (same repos as Sprint 2 eval):
- Cataclysm-DDA, OpenTTD, osu!, Luanti
- Each entry: bug description + expected triage + expected affected components + expected report fields
- Include at least 2 bugs where external tools (Jira, logs) would add value

---

## Interface with Other Devs

### From Dev B (MCP tools):
- `filter_tools(all_tools, stage)` — extended with new stage names: `"bug_triage"`, `"bug_mechanics"`, `"bug_reproduction"`, `"bug_research"`, `"bug_report"`
- `get_available_integrations()` — returns list of configured integration names
- Tool wrappers: `safe_tools()` applies to all new MCP tools

### From Dev C (models + sessions):
- Import all new models from `backend/models.py`
- Session helpers: `create_session()`, `get_session()`, `update_session()` extended for bug reproduction sessions
- Export helpers: `export_markdown(bug_report)`, `export_pdf(bug_report)`

### To Dev D (frontend):
- SSE event stream (same format as impact analysis, new event types)
- Two checkpoint events the UI must handle:
  - `bug_checkpoint` after mechanics — show components + hypotheses + approve/refine
  - `bug_checkpoint` after research — show evidence summary + approve/add_context
- `session_id` included in every checkpoint event

---

## Acceptance Criteria

- [ ] Bug reproduction runs as a separate StateGraph with 8 nodes visible in LangSmith traces
- [ ] Each stage only calls tools from its allowed subset
- [ ] Triage stage classifies bug and extracts keywords
- [ ] Mechanics stage traces code paths and produces hypotheses
- [ ] checkpoint_mechanics pauses and emits CheckpointEvent with components + hypotheses
- [ ] Reproduction stage produces executable step-by-step plan
- [ ] Research stage queries all configured external sources
- [ ] checkpoint_research pauses and allows adding context
- [ ] Report stage assembles complete BugReport
- [ ] Pipeline completes with zero external tools configured (graceful degradation)
- [ ] Pipeline completes within 5 minutes on a realistic bug
- [ ] Per-stage budgets enforced (triage: 8, mechanics: 15, reproduction: 12, research: 20, report: 5)
- [ ] LangSmith evaluators run and produce baseline metrics
- [ ] Golden dataset of 5+ bugs created
