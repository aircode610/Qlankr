#report #sprint_2

Qlankr — Sprint 2 Report

🔹 Goal
Turn the working prototype into a measurable, iterable system by replacing the single ReAct loop with a multi-stage pipeline, adding human-in-the-loop checkpoints, and building an evaluation framework.

🔹 What Was Done
- StateGraph pipeline: gather → unit_tests → checkpoint → choice → integration/e2e → submit [done]
- Human-in-the-loop: unit test review, integration vs E2E choice, E2E context prompt [done]
- Per-stage sub-agents with filtered tools and budget enforcement [done]
- MCP improvements: safe_tools() error wrapper, Cypher fallback, prefetch_context(), --embeddings flag [done]
- Frontend rewrite: checkpoint/choice dialogs, trace drawer, pipeline results panel, SSE client [done]
- LangSmith eval: 8-PR golden dataset, 15 evaluators, run_evals.py [done]

🔹 Key Decisions
- StateGraph over ReAct — LangGraph's interrupt() + MemorySaver enables checkpoint resume across HTTP requests.
- Per-stage submit tools — eliminates Sprint 1 validation failures; each stage independently debuggable.
- Removed ask_user from E2E — interrupt() inside an inner agent without a checkpointer caused infinite restarts; user context now collected before the stage runs.

🔹 Eval Results (integration-github, 7 PRs)
- Pipeline health: 1.00
- Tool efficiency: 0.89
- Groundedness: 0.72
- Risk quality: 0.66
- Integration test structure: 0.29

🔹 Next Sprint
- Improve risk recall and integration test quality against LangSmith baseline
- Build Phase 4 container test runner (Dockerfile.runner, run_tests.py, TestExecutionPanel)
- Eval consistency (feedback: Pavel): LLM-as-judge scores vary across runs for the same input — add multi-run evaluation (run N times, report average + variance) to measure and enforce consistency
- Weighted scoring (feedback: Pavel): consider weighting evaluator scores by importance instead of plain averages
