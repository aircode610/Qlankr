#report #sprint_2

# Qlankr — Sprint 2 Report

🔹 Context
Sprint 2 replaced the single ReAct loop with a structured multi-stage pipeline, added human-in-the-loop checkpoints, expanded the MCP layer, rewrote the frontend, and built a full evaluation framework. The main goal was turning a working prototype into something measurable and iterable.

🔹 Planned / Done
- StateGraph pipeline: gather → unit_tests → checkpoint_unit → choice → integration_tests | e2e_planning → submit [done]
- Human-in-the-loop: unit test review (approve / refine), integration vs E2E choice, E2E context prompt [done]
- Per-stage sub-agents with filtered tool subsets and budget enforcement [done]
- Sprint 2 models: UnitTestSpec, IntegrationTestSpec, E2ETestPlan, CheckpointEvent + /continue and /status endpoints [done]
- MCP layer: safe_tools() error wrapper, make_process_tools() with Cypher fallback, prefetch_context() before graph start, --embeddings flag in indexer [done]
- Frontend rewrite: CheckpointDialog, ChoiceDialog, UnitReviewPanel, AgentTraceDrawer, TestPipelineResults + continueAnalysis() SSE client [done]
- LangSmith eval framework: 8-PR golden dataset, 15 evaluators across 3 layers, run_evals.py [done]

🔹 Key Decisions
- **StateGraph over extended ReAct**: the single loop had no way to pause mid-run; LangGraph's interrupt() + MemorySaver singleton enables checkpoint resume across HTTP requests without losing state.
- **Per-stage submit tools**: each stage has its own typed submit tool — eliminates the Sprint 1 submit_analysis validation failure and makes each stage independently debuggable in LangSmith.
- **safe_tools() content_and_artifact fix**: MCP tools require coroutines to return a (content, artifact) tuple; catching exceptions and returning a plain string raised a ValueError that crashed all e2e runs.
- **Removed ask_user from E2E**: calling interrupt() inside an inner agent with no checkpointer caused the outer graph to restart e2e_planning_node from scratch on every resume — infinite loop. User context is now collected at e2e_checkpoint_node before the stage runs.
- **LangSmith over Langfuse/W&B**: native LangGraph integration, built-in dataset management, and plain Python evaluators made it the fastest path to a working eval loop.

🔹 Problems & Next Steps
- Integration agent exhausted its 15-call budget without calling submit — fixed with prompt discipline; confidence calibration low (0.18) for non-indexed repos — prompt-level enforcement added
- Eval results (integration-github, 7 PRs): pipeline health 1.00, tool_efficiency 0.89, groundedness 0.72, risk_quality 0.66, integration_test_structure 0.29 — pipeline is solid, quality layer is the next target
- Next sprint focus: improve risk recall and integration test quality against the LangSmith baseline; build Phase 4 container test runner (Dockerfile.runner, run_tests.py, TestExecutionPanel)
