# Bug Reproduction Comparison Eval — Design

**Date:** 2026-05-12  
**Script:** `backend/evals/compare_bug_repro.py`

## Summary

Single self-contained script that runs both Qlankr and the Claude SDK (Anthropic API, stage-by-stage) on one hard-coded bug example, evaluates both with the full `bug_evaluators.py` suite, and reports results in LangSmith.

## Bug Example

OpenTTD timetable crash (example #1 from `create_dataset.py`):
- **Description:** Widget layout assertion crash after disabling "Show arrival/departure date" setting
- **Ground truth:** keywords, affected files, expected severity

## Targets

**Qlankr:** `run_bug_agent()` → auto-approve both checkpoints → `BugResultEvent.full_state`

**Claude SDK:** 5 sequential `claude-sonnet-4-6` API calls using skill prompts from `evals/skills/bug_repro/`. Each stage's JSON output is threaded as context to the next. No MCP tools — research stage reasons about what sources would contain without live access.

## LangSmith

- Dataset: `qlankr-bug-compare-demo` (created idempotently, 1 example)
- Experiments: `qlankr-bug-repro` and `claude-sdk-bug-repro` — both under same dataset, directly comparable in LangSmith UI

## Evaluators

All 15 evaluators from `bug_evaluators.py`:
- 12 deterministic (pipeline health, completeness, keyword/file recall, etc.)
- 3 LLM-as-judge (root_cause_quality, report_coherence, reproduction_step_clarity)

## Output

Side-by-side terminal score table + LangSmith URLs.
