"""
LangSmith evaluation runner for the Qlankr Sprint 3 bug reproduction pipeline.

Usage:
    cd backend && python -m evals.run_bug_evals [--dataset DATASET] [--concurrency N]

Dataset:
    qlankr-eval-bugs  (default) — bug examples with ground-truth root cause,
                                  affected files, and expected components.
    Run once to seed: python -m evals.create_dataset

What this runs
──────────────
Deterministic evaluators (no LLM cost, always fast):
  triage_accuracy, mechanics_grounding, reproduction_executability,
  bug_pipeline_health, research_coverage, report_completeness,
  report_actionability, evidence_quality, tool_efficiency, graceful_degradation

LLM-as-judge evaluators (require ANTHROPIC_API_KEY, ~$0.01/example):
  root_cause_quality       — semantic alignment with expected root-cause keywords
  report_coherence         — internal consistency + specificity of the bug report
  reproduction_step_clarity — are the repro steps actually executable?

Improving the judges
────────────────────
All three judge prompts live at the bottom of evals/bug_evaluators.py.
To adjust scoring:
  - Edit the rubric anchors (1.0 / 0.7 / 0.4 / 0.0 bullet points) in each prompt.
  - Add more golden examples to BUG_EXAMPLES in evals/create_dataset.py, then
    re-run `python -m evals.create_dataset` to push them to LangSmith.
  - Compare experiment runs side-by-side in the LangSmith UI.
"""

import argparse
import asyncio
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from langsmith import Client
from langsmith.evaluation import aevaluate

# ── Deterministic evaluators ──────────────────────────────────────────────────
from evals.bug_evaluators import (
    # Stage 1-3
    triage_accuracy,
    mechanics_grounding,
    reproduction_executability,
    # Stage 4-5 + pipeline
    bug_pipeline_health,
    research_coverage,
    report_completeness,
    report_actionability,
    evidence_quality,
    tool_efficiency,
    graceful_degradation,
    # LLM judges
    root_cause_quality,
    report_coherence,
    reproduction_step_clarity,
)

_DETERMINISTIC_EVALUATORS = [
    triage_accuracy,
    mechanics_grounding,
    reproduction_executability,
    bug_pipeline_health,
    research_coverage,
    report_completeness,
    report_actionability,
    evidence_quality,
    tool_efficiency,
    graceful_degradation,
]

_JUDGE_EVALUATORS = [
    root_cause_quality,
    report_coherence,
    reproduction_step_clarity,
]

_ALL_EVALUATORS = _DETERMINISTIC_EVALUATORS + _JUDGE_EVALUATORS

_DEFAULT_DATASET = "qlankr-eval-bugs"


# ── Target: drive the full bug pipeline, auto-approve checkpoints ─────────────

async def bug_target(inputs: dict) -> dict:
    """
    LangSmith target function for the bug reproduction pipeline.

    Drives run_bug_agent() through all checkpoints (auto-approving each one)
    and returns a full_state dict suitable for all evaluators.

    full_state keys used by evaluators:
      triage, mechanics, reproduction_plan, research_findings,
      bug_report, tool_calls_used
    """
    from agent.bug_agent import run_bug_agent, continue_bug_agent, BugResultEvent
    from models import CheckpointEvent, ErrorEvent

    description = inputs.get("description", "")
    environment = inputs.get("environment", "unspecified")
    severity_input = inputs.get("severity_input", "medium")
    repo_name = inputs.get("repo_name")
    session_id = f"eval-{id(inputs)}"

    result_event = None
    error_msg = None
    checkpoint_count = 0
    max_checkpoints = 5

    async def _drain(generator):
        """Consume the event stream; return the first terminal event (result/checkpoint/error)."""
        async for event in generator:
            if isinstance(event, (CheckpointEvent, BugResultEvent, ErrorEvent)):
                return event
        return None

    # Start the pipeline
    terminal = await _drain(run_bug_agent(
        description=description,
        environment=environment,
        severity_input=severity_input,
        repo_name=repo_name,
        session_id=session_id,
    ))

    # Auto-approve every checkpoint until we get a BugResultEvent
    while isinstance(terminal, CheckpointEvent) and checkpoint_count < max_checkpoints:
        checkpoint_count += 1
        terminal = await _drain(continue_bug_agent(
            session_id=terminal.session_id,
            user_response={"action": "approve"},
        ))

    if isinstance(terminal, ErrorEvent):
        error_msg = terminal.message
    elif isinstance(terminal, BugResultEvent):
        result_event = terminal

    if result_event is not None:
        # full_state has all stage outputs — preferred path
        if result_event.full_state:
            return result_event.full_state
        # Fallback: build minimal dict from the result event fields
        br = result_event.bug_report
        if hasattr(br, "model_dump"):
            br = br.model_dump()
        elif not isinstance(br, dict):
            br = {}
        return {"bug_report": br}

    # Pipeline failed — return error signal so evaluators score 0
    return {"error": error_msg or f"no result after {checkpoint_count} checkpoints"}


# ── Runner ────────────────────────────────────────────────────────────────────

async def run_eval(
    dataset_name: str = _DEFAULT_DATASET,
    judges_enabled: bool = True,
    max_concurrency: int = 1,
) -> None:
    evaluators = _ALL_EVALUATORS if judges_enabled else _DETERMINISTIC_EVALUATORS
    label = "full (deterministic + judges)" if judges_enabled else "deterministic only"
    experiment_prefix = "bug-repro-full" if judges_enabled else "bug-repro-det"

    print(f"\n{'='*60}")
    print(f"Bug reproduction eval — {label}")
    print(f"Dataset:     {dataset_name}")
    print(f"Evaluators:  {len(evaluators)} ({len(_DETERMINISTIC_EVALUATORS)} det + "
          f"{len(_JUDGE_EVALUATORS) if judges_enabled else 0} judges)")
    print(f"Concurrency: {max_concurrency}")
    print(f"{'='*60}")

    results = await aevaluate(
        bug_target,
        data=dataset_name,
        evaluators=evaluators,
        experiment_prefix=experiment_prefix,
        max_concurrency=max_concurrency,
        metadata={
            "pipeline": "bug_reproduction",
            "judges_enabled": judges_enabled,
        },
    )

    # Print summary table
    score_map: dict[str, list[float]] = {}
    async for result in results:
        for eval_result in result.get("evaluation_results", {}).get("results", []):
            key = eval_result.key
            score = eval_result.score
            if score is not None:
                score_map.setdefault(key, []).append(score)

    if score_map:
        print(f"\n{'Metric':<35} {'Mean':>6}  {'Min':>6}  {'Max':>6}")
        print("-" * 57)
        det_keys = {f.__name__ for f in _DETERMINISTIC_EVALUATORS}
        for metric, scores in sorted(score_map.items()):
            mean = sum(scores) / len(scores)
            tag = "     " if metric in det_keys else " [J] "  # [J] = LLM judge
            print(f"  {metric:<33}{tag}{mean:>6.2f}  {min(scores):>6.2f}  {max(scores):>6.2f}")
        print("\n  [J] = LLM-as-judge metric")
    else:
        print("  (no scores returned — check LangSmith UI)")

    print("\nDone. View full results at https://smith.langchain.com")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Qlankr bug reproduction evals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dataset",
        default=_DEFAULT_DATASET,
        help=f"LangSmith dataset name (default: {_DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--no-judges",
        action="store_true",
        help="Skip LLM-as-judge evaluators (free, fast, deterministic only)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Max parallel pipeline runs (default: 1 — bug pipeline is expensive)",
    )
    args = parser.parse_args()

    # Verify the dataset exists
    client = Client()
    existing = {ds.name for ds in client.list_datasets()}
    if args.dataset not in existing:
        print(f"ERROR: Dataset '{args.dataset}' not found in LangSmith.")
        print("Run first:  cd backend && python -m evals.create_dataset")
        sys.exit(1)

    asyncio.run(run_eval(
        dataset_name=args.dataset,
        judges_enabled=not args.no_judges,
        max_concurrency=args.concurrency,
    ))


if __name__ == "__main__":
    main()
