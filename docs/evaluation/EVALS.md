# Qlankr Eval System

All evals run through LangSmith. There are two pipelines: **PR analysis** (Sprint 2) and **bug reproduction** (Sprint 3). Each pipeline has its own target function, evaluator set, and datasets.

---

## Prerequisites

```bash
cd backend
.venv/bin/pip install supabase==2.30.0   # if not already installed
```

`.env` at the repo root needs:

```
ANTHROPIC_API_KEY=...
LANGSMITH_API_KEY=...
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
LANGSMITH_PROJECT=qlankr
GITHUB_TOKEN=...   # needed by surface_groundedness to fetch real PR diffs
```

---

## Seeding Datasets

Run once (or whenever examples change). Deletes and recreates all datasets in LangSmith.

```bash
cd backend
.venv/bin/python -m evals.create_dataset
```

Creates 5 datasets:

| Dataset | Examples | What it tests |
|---|---|---|
| `qlankr-eval-indexed` | 1 | PR analysis on the Qlankr repo — full pipeline with GitNexus |
| `qlankr-eval-github` | 7 | PR analysis on external repos — GitHub-only fallback |
| `qlankr-eval-bugs` | 5 | Bug reproduction — original examples (legacy) |
| `qlankr-eval-bugs-real` | 6 | Bug reproduction — real bugs from OpenTTD, Cataclysm-DDA, osu!, Luanti |
| `qlankr-eval-bugs-synthetic` | 6 | Bug reproduction — adversarial examples targeting specific failure modes |

---

## Running PR Analysis Evals

```bash
cd backend

# Integration test path, external repos (cheapest — no GitNexus needed)
.venv/bin/python -m evals.run_evals --suite integration --dataset github

# E2E test path, external repos
.venv/bin/python -m evals.run_evals --suite e2e --dataset github

# Integration path, Qlankr repo (requires GitNexus indexed)
.venv/bin/python -m evals.run_evals --suite integration --dataset indexed

# Run everything
.venv/bin/python -m evals.run_evals
```

### PR Analysis Evaluators

**Structural** — check field presence and schema validity. Free, always fast.

| Evaluator | What it checks |
|---|---|
| `output_completeness` | Every affected component has all 5 required fields filled |
| `component_count` | Agent found at least `min_components` from the dataset reference |
| `unit_test_structure` | Unit test specs have valid `target`, `test_cases`, `priority` |
| `integration_test_structure` | Integration specs have valid `integration_point`, `modules_involved`, `test_cases` |
| `e2e_plan_structure` | E2E plans have valid `process`, `scenario`, `steps`, `priority` |

**Tool usage** — measure how the agent used its tools.

| Evaluator | What it checks |
|---|---|
| `tool_coverage` | Agent called all `expected_tools` from the dataset reference |
| `tool_efficiency` | Penalises redundant tool calls (same tool called >4 times) |
| `gitnexus_usage` | Agent used ≥2 GitNexus tools when the repo is indexed |
| `confidence_calibration` | Non-indexed repos → all `low`; indexed repos → some `medium`/`high` |

**Pipeline** — did the agent complete?

| Evaluator | What it checks |
|---|---|
| `pipeline_progression` | Agent progressed through expected stages for the chosen path |
| `no_crash` | Agent completed without error |

**LLM judges** — require `ANTHROPIC_API_KEY`, cost ~$0.01/example.

| Evaluator | What it judges |
|---|---|
| `surface_groundedness` | Are claims about directly changed files grounded in the real diff? Fetches the actual PR diff via GitHub API. Applies to both Qlankr and Claude Code. Returns `None` if diff fetch fails. |
| `depth_groundedness` | Are transitive/blast-radius claims consistent with what GitNexus tools actually returned? Reads `tool_transcripts`. Qlankr only — returns `None` (N/A) for Claude Code. |
| `risk_quality` | Did the agent catch the expected risks from the dataset reference? |
| `component_matching` | Do the agent's component names semantically match expected components? |
| `unit_test_quality` | Are generated unit test specs specific, actionable, and well-prioritised? |
| `integration_test_quality` | Are integration specs testing real cross-module boundaries? |

---

## Running Bug Reproduction Evals

```bash
cd backend

# Full eval (deterministic + LLM judges) on real bugs
.venv/bin/python -m evals.run_bug_evals --dataset qlankr-eval-bugs-real

# Adversarial/synthetic bugs
.venv/bin/python -m evals.run_bug_evals --dataset qlankr-eval-bugs-synthetic

# Skip LLM judges — free and instant, deterministic only
.venv/bin/python -m evals.run_bug_evals --dataset qlankr-eval-bugs-real --no-judges

# Legacy dataset
.venv/bin/python -m evals.run_bug_evals --dataset qlankr-eval-bugs
```

### Bug Reproduction Evaluators

**Deterministic** — free, always run.

| Evaluator | Stage | What it checks |
|---|---|---|
| `triage_accuracy` | Triage | `bug_category` non-empty; `severity` is valid enum; ≥1 keyword; ≥1 hypothesis; **severity matches reference** (5th check, only when reference provides `expected_severity`) |
| `mechanics_grounding` | Mechanics | ≥1 code path; ≥1 hypothesis; every hypothesis has a non-empty `evidence` field |
| `reproduction_executability` | Reproduction | ≥3 steps; prerequisites present; every step has non-empty `action` + `expected_result` |
| `bug_pipeline_health` | Pipeline | All 5 stage outputs (`triage`, `mechanics`, `reproduction_plan`, `research_findings`, `bug_report`) are non-empty |
| `research_coverage` | Research | `sources_with_results / sources_queried` — penalises querying sources that returned nothing |
| `report_completeness` | Report | All 7 required fields valid: `title`, `severity`, `root_cause`, `reproduction_steps` (≥3), `affected_components` (≥1), `recommendations` (≥1), `confidence` |
| `report_actionability` | Report | ≥2 recommendations; each recommendation is ≥30 characters (filters out "fix the bug") |
| `evidence_quality` | Report | Fraction of 5 evidence categories populated: `log_entries`, `doc_references`, `related_issues`, `network_traces`, `code_graph_hits` |
| `tool_efficiency` | Pipeline | Total tool calls within the 60-call budget (8+15+12+20+5); scales to 0 at 2× budget |
| `graceful_degradation` | Pipeline | Report is produced even when all external research sources returned nothing |
| `keyword_recall` | Report | Fraction of `expected_root_cause_keywords` (from reference) found as substrings in `bug_report.root_cause`. Substring match handles plurals/partial names. Returns 1.0 when no reference keywords exist. |
| `affected_file_recall` | Report | Fraction of `expected_affected_files` (from reference) found in `mechanics.code_paths` or `bug_report.affected_components`. Basename-normalised — `src/widget.cpp` matches `widget.cpp`. Returns 1.0 when no reference files exist. |

**LLM judges** — require `ANTHROPIC_API_KEY`, ~$0.01/example.

| Evaluator | What it judges |
|---|---|
| `root_cause_quality` | Does the root cause name the correct mechanism? When reference has `expected_root_cause_keywords`, the judge checks semantic alignment with those keywords. Without a reference, scores specificity alone. |
| `report_coherence` | Is the report internally consistent? Severity, root cause, affected components, and recommendations should all point to the same underlying problem. Penalises vague or contradictory reports. |
| `reproduction_step_clarity` | Are the steps genuinely executable by a developer who hasn't seen the code? Scores clarity, specificity, correctness, and completeness of prerequisites. |

---

## Dataset Reference Fields

Each example's `outputs` dict provides ground truth for the evaluators that need it.

**Bug datasets** — all optional; evaluators skip gracefully when absent:

| Field | Used by |
|---|---|
| `expected_root_cause_keywords` | `keyword_recall`, `root_cause_quality` |
| `expected_affected_files` | `affected_file_recall` |
| `expected_severity` | `triage_accuracy` (5th check) |
| `expected_category` | not currently evaluated deterministically |
| `min_reproduction_steps` | not currently evaluated deterministically |

**PR analysis datasets:**

| Field | Used by |
|---|---|
| `expected_components` | `component_count`, `component_matching` |
| `expected_risks` | `risk_quality` |
| `expected_tools` | `tool_coverage` |
| `min_components` | `component_count` |
| `expect_gitnexus` | `gitnexus_usage`, `confidence_calibration` |

---

## Synthetic Dataset — What Each Example Tests

The `qlankr-eval-bugs-synthetic` dataset has 6 adversarial examples, each targeting a specific pipeline failure mode:

| Example | Failure mode tested |
|---|---|
| Misleading Stack Trace | Does the agent trace upstream from crash site to real cause? `MemoryPool` crashes but `ZoneTransition` is the root cause. |
| Buried Prerequisites | Does the reproduction plan include ALL 4 conditions? (hard difficulty + two-handed sword + <25% health + Drowned Knight + underwater) |
| Intermittent Race Condition | Does the agent correctly classify as `networking`/`critical` and avoid writing fake deterministic steps? |
| Upstream Cause, Downstream Crash | Does the agent identify the save system as root cause, not the renderer that crashes? |
| Silent Data Corruption | Does the agent classify as `data`/`medium` rather than `crash` or `critical`? |
| Config-Dependent Trigger | Does the mechanics stage find the LOD flag buried in prose? Reproduction plan must include ultra graphics + 200+ NPCs. |

---

## Claude Code Baseline

`claude_code_target.py` drives `claude -p` stage-by-stage for a fair Qlankr vs Claude Code comparison. Each stage gets the orchestrator skill + stage skill as a prompt, with prior stage outputs threaded through as JSON.

```python
# In run_bug_evals.py — swap the target to compare
from evals.claude_code_target import claude_code_target_bug

results = await aevaluate(
    claude_code_target_bug,          # instead of bug_target
    data="qlankr-eval-bugs-real",
    evaluators=evaluators,
    experiment_prefix="claudecode-bugs-real",
)
```

Claude Code always has `has_blast_tools: False` → `depth_groundedness` returns `None` (LangSmith shows N/A, not 0.0). All other evaluators apply equally.

Skill files live in `backend/evals/skills/`:

```
skills/
├── bug_repro/
│   ├── skill.md        ← orchestrator context passed to every stage
│   ├── triage.md
│   ├── mechanics.md
│   ├── reproduction.md
│   ├── research.md
│   └── report.md
└── pr_analysis/
    ├── skill.md
    ├── gather.md
    ├── unit_tests.md
    ├── integration.md
    └── e2e.md
```

---

## File Map

```
backend/evals/
├── run_evals.py           ← CLI for PR analysis evals
├── run_bug_evals.py       ← CLI for bug reproduction evals
├── create_dataset.py      ← seeds all LangSmith datasets
├── target.py              ← Qlankr PR analysis target function
├── evaluators.py          ← PR analysis evaluators
├── bug_evaluators.py      ← bug reproduction evaluators
├── claude_code_target.py  ← Claude Code baseline target (subprocess)
└── skills/                ← stage skill prompts for Claude Code target
```
