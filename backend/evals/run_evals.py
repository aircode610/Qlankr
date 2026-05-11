"""
Main evaluation runner for the Qlankr agent (PR analysis + bug reproduction).

Usage:
    cd backend && python -m evals.run_evals [--suite SUITE] [--dataset DATASET]

Suites:
    integration — PR impact analysis, integration test path
    e2e         — PR impact analysis, E2E test path
    bug         — bug reproduction pipeline (deterministic + LLM judges)
    all         — all three suites (default)

Datasets (PR analysis):
    indexed     — qlankr-eval-indexed (Qlankr repo, full pipeline with GitNexus)
    github      — qlankr-eval-github  (external repos, GitHub-only)

Dataset (bug):
    qlankr-eval-bugs  (fixed, seeded by evals/create_dataset.py)

Examples:
    python -m evals.run_evals                              # run everything
    python -m evals.run_evals --suite bug                  # bug repro only
    python -m evals.run_evals --suite integration --dataset indexed
    python -m evals.run_evals --suite e2e --dataset github
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from langsmith import Client
from langsmith.evaluation import aevaluate

from evals.evaluators import (
    # Structural
    output_completeness,
    component_count,
    unit_test_structure,
    integration_test_structure,
    e2e_plan_structure,
    # Tool usage
    tool_coverage,
    tool_efficiency,
    gitnexus_usage,
    confidence_calibration,
    # Pipeline
    pipeline_progression,
    no_crash,
    # LLM judges
    groundedness,
    risk_quality,
    component_matching,
    unit_test_quality,
    integration_test_quality,
)
from evals.target import (
    agent_target_integration,
    agent_target_e2e,
)
from evals.run_bug_evals import run_eval as _run_bug_eval

# ── Evaluator sets per suite ──────────────────────────────────────────────────

# Always run these on every suite
_BASE_EVALUATORS = [
    no_crash,
    pipeline_progression,
    tool_efficiency,
    tool_coverage,
    gitnexus_usage,
    component_count,
    output_completeness,
    confidence_calibration,
    component_matching,
    risk_quality,
    groundedness,
]

# Unit test evaluators (always included — both paths generate unit tests)
_UNIT_EVALUATORS = [
    unit_test_structure,
    unit_test_quality,
]

# Additional evaluators for the integration path
_INTEGRATION_EVALUATORS = [
    integration_test_structure,
    integration_test_quality,
]

# Additional evaluators for the e2e path
_E2E_EVALUATORS = [
    e2e_plan_structure,
]

# Subset that applies to external baselines (e.g. vanilla Claude) — only
# content-level evaluators that don't depend on Qlankr's tool trace, stages,
# or test specs. Same metrics the Qlankr agent is scored on, so side-by-side
# comparisons are apples-to-apples.
_BASELINE_EVALUATORS = [
    output_completeness,
    component_count,
    component_matching,
    risk_quality,
    groundedness,
]


# ── Suite definitions ─────────────────────────────────────────────────────────

SUITES = {
    "integration": {
        "target": agent_target_integration,
        "evaluators": _BASE_EVALUATORS + _UNIT_EVALUATORS + _INTEGRATION_EVALUATORS,
        "experiment_prefix": "integration",
        "description": "Full pipeline → integration tests path",
    },
    "e2e": {
        "target": agent_target_e2e,
        "evaluators": _BASE_EVALUATORS + _UNIT_EVALUATORS + _E2E_EVALUATORS,
        "experiment_prefix": "e2e",
        "description": "Full pipeline → E2E planning path",
    },
}

DATASETS = {
    "indexed": "qlankr-eval-indexed",
    "github": "qlankr-eval-github",
}


# ── Runner ────────────────────────────────────────────────────────────────────


async def run_suite(
    suite_name: str,
    dataset_name: str,
    max_concurrency: int = 2,
    target_name: str = "qlankr",
) -> None:
    """Run a single suite against a single dataset for the chosen target system."""
    suite = SUITES[suite_name]

    if target_name == "vanilla":
        from evals.baselines.vanilla_claude_target import vanilla_claude_target
        target = vanilla_claude_target
        evaluators = _BASELINE_EVALUATORS
        experiment_name = f"vanilla-{dataset_name}"
    else:
        target = suite["target"]
        evaluators = suite["evaluators"]
        experiment_name = f"{suite['experiment_prefix']}-{dataset_name}"

    print(f"\n{'='*60}")
    print(f"Target:  {target_name}")
    print(f"Suite:   {suite_name} — {suite['description']}")
    print(f"Dataset: {dataset_name} ({DATASETS[dataset_name]})")
    print(f"Experiment: {experiment_name}")
    print(f"{'='*60}")

    results = await aevaluate(
        target,
        data=DATASETS[dataset_name],
        evaluators=evaluators,
        experiment_prefix=experiment_name,
        max_concurrency=max_concurrency,
        metadata={
            "suite": suite_name,
            "dataset": dataset_name,
            "target": target_name,
        },
    )

    # Print a brief summary
    print(f"\nResults for {experiment_name}:")
    score_map: dict[str, list[float]] = {}

    async for result in results:
        for eval_result in result.get("evaluation_results", {}).get("results", []):
            key = eval_result.key
            score = eval_result.score
            if score is not None:
                score_map.setdefault(key, []).append(score)

    if score_map:
        print(f"{'Metric':<35} {'Mean':>6}  {'Min':>6}  {'Max':>6}")
        print("-" * 55)
        for metric, scores in sorted(score_map.items()):
            mean = sum(scores) / len(scores)
            print(f"  {metric:<33} {mean:>6.2f}  {min(scores):>6.2f}  {max(scores):>6.2f}")
    else:
        print("  (no scores returned — check LangSmith UI)")


async def run_all(
    suites: list[str],
    datasets: list[str],
    max_concurrency: int = 2,
    target_name: str = "qlankr",
) -> None:
    """Run the selected suites × datasets combinations."""
    tasks = [
        run_suite(suite, dataset, max_concurrency, target_name)
        for suite in suites
        for dataset in datasets
    ]
    for task in tasks:
        await task


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Qlankr agent evals")
    parser.add_argument(
        "--suite",
        choices=["integration", "e2e", "bug", "all"],
        default="all",
        help="Which eval suite to run (default: all)",
    )
    parser.add_argument(
        "--dataset",
        choices=["indexed", "github", "all"],
        default="all",
        help="PR-analysis dataset (default: all). Ignored when --suite bug.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="Max parallel eval runs (default: 2). Bug suite defaults to 1.",
    )
    parser.add_argument(
        "--no-judges",
        action="store_true",
        help="Skip LLM-as-judge evaluators in the bug suite (faster, no API cost).",
    )
    parser.add_argument(
        "--target",
        choices=["qlankr", "vanilla"],
        default="qlankr",
        help=(
            "Which system to evaluate (default: qlankr). "
            "'vanilla' runs Claude Sonnet 4.6 on just the PR diff — no tools, no "
            "knowledge graph — as a baseline to measure Qlankr's pipeline value-add."
        ),
    )
    args = parser.parse_args()

    client = Client()

    run_pr_suites = args.suite in ("integration", "e2e", "all")
    run_bug_suite = args.suite in ("bug", "all") and args.target == "qlankr"

    def _dataset_exists(name: str) -> bool:
        # Use read_dataset(dataset_name=...) rather than list_datasets() —
        # list_datasets returns empty for some PATs depending on workspace
        # scope, but read_dataset works on direct name lookup.
        try:
            client.read_dataset(dataset_name=name)
            return True
        except Exception:
            return False

    # ── PR analysis suites ────────────────────────────────────────────────────
    if run_pr_suites:
        pr_suite_names = [
            s for s in SUITES
            if args.suite == "all" or s == args.suite
        ]
        datasets = list(DATASETS.keys()) if args.dataset == "all" else [args.dataset]

        missing = [DATASETS[d] for d in datasets if not _dataset_exists(DATASETS[d])]
        if missing:
            print(f"ERROR: These datasets don't exist in LangSmith: {missing}")
            print("Run first:  cd backend && python3 -m evals.create_dataset")
            sys.exit(1)

        # Vanilla baseline: collapse to a single suite pass — vanilla has no
        # integration/e2e split and produces unit + integration + e2e specs
        # from one LLM call.
        if args.target == "vanilla":
            pr_suite_names = ["integration"]

        print(f"Target:            {args.target}")
        print(f"Running PR suites: {pr_suite_names}")
        print(f"On datasets:       {datasets}")
        asyncio.run(run_all(pr_suite_names, datasets, args.concurrency, args.target))

    # ── Bug reproduction suite ────────────────────────────────────────────────
    # Vanilla baseline doesn't apply to bug reproduction — skip silently
    # when --target vanilla is combined with --suite all.
    if run_bug_suite:
        bug_dataset = "qlankr-eval-bugs"
        if not _dataset_exists(bug_dataset):
            print(f"ERROR: Dataset '{bug_dataset}' not found in LangSmith.")
            print("Run first:  cd backend && python3 -m evals.create_dataset")
            sys.exit(1)

        # Bug pipeline is expensive — default to concurrency=1 unless raised.
        bug_concurrency = 1 if args.concurrency == 2 else args.concurrency
        asyncio.run(_run_bug_eval(
            dataset_name=bug_dataset,
            judges_enabled=not args.no_judges,
            max_concurrency=bug_concurrency,
        ))

    print("\nDone. View results at https://smith.langchain.com")


if __name__ == "__main__":
    main()
