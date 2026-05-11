# Eval Redesign — Overview

**Date:** 2026-05-11
**Scope:** PR analysis (Sprint 2) + Bug reproduction (Sprint 3)
**Goal:** Fix evaluator validity gaps and add a fair Claude Code baseline comparison.

---

## Problem Statement

The current eval has three compounding issues:

1. **Groundedness judge is blind.** It receives only a PR URL, not the actual diff. It scores claims it cannot verify.
2. **Groundedness is unfair to blast-tool findings.** Our agent uses GitNexus (`impact`, `context`, `cypher`) to find transitive dependencies not visible in the diff. A judge reading only the diff would penalize these as hallucinations — but they are legitimate.
3. **Bug dataset is too thin.** One real example is not enough to trust a score. Structural evaluators check field presence, not correctness.

---

## Design Components

| File | What it covers |
|---|---|
| `01-transcript-capture-groundedness.md` | Capturing full tool transcripts; splitting groundedness into surface + depth |
| `02-bug-evaluators.md` | Three deterministic fixes: triage severity check, keyword recall, file recall |
| `03-claude-code-baseline.md` | Skill directory structure; subprocess target; LangSmith experiment naming |
| `04-dataset.md` | 6 real bug examples from calibration repos; 6 synthetic adversarial cases |

---

## Overall Architecture

```
target.py
  ├── Qlankr target          (extended: captures full tool transcripts)
  └── claude_code_target.py  (new: subprocess invoker, chains stage skills)

evaluators.py
  ├── surface_groundedness   (new: diff-aware, both agents)
  └── depth_groundedness     (new: transcript-aware, Qlankr only)

bug_evaluators.py
  ├── triage_accuracy        (updated: + severity match vs reference)
  ├── keyword_recall         (new: deterministic keyword hit rate)
  └── affected_file_recall   (new: deterministic file hit rate)

skills/
  ├── bug_repro/
  │   ├── skill.md           (orchestrator)
  │   ├── triage.md
  │   ├── mechanics.md
  │   ├── reproduction.md
  │   ├── research.md
  │   └── report.md
  └── pr_analysis/
      ├── skill.md           (orchestrator)
      ├── gather.md
      ├── unit_tests.md
      ├── integration.md
      └── e2e.md

create_dataset.py
  ├── qlankr-eval-bugs-real       (new, 6 examples)
  └── qlankr-eval-bugs-synthetic  (new, 6 adversarial examples)
```

---

## Comparison Model

Two LangSmith experiments run per dataset. Evaluators applied to each:

| Evaluator | Qlankr | Claude Code |
|---|---|---|
| `surface_groundedness` | yes | yes |
| `depth_groundedness` | yes | **N/A** (no blast tools) |
| `keyword_recall` | yes | yes |
| `affected_file_recall` | yes | yes |
| `triage_accuracy` | yes | yes |
| `mechanics_grounding` | yes | yes |
| `reproduction_executability` | yes | yes |
| `report_coherence` | yes | yes |
| `root_cause_quality` | yes | yes |

`depth_groundedness` returns `score: None` for Claude Code → LangSmith renders as N/A, not 0.0.

The presentation story: Claude Code scores well on surface claims (it reads the diff). Qlankr matches that *and* adds blast-radius findings via depth groundedness — the value-add of the knowledge graph.
