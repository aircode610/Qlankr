"""
Main evaluation runner for the Qlankr Sprint 2 agent.

Usage:
    cd backend && python -m evals.run_evals [--suite SUITE] [--dataset DATASET]

Suites:
    integration — full pipeline, integration path
    e2e         — full pipeline, e2e path
    all         — both suites (default)

Datasets:
    indexed     — qlankr-eval-indexed (Qlankr repo, full pipeline with GitNexus)
    github      — qlankr-eval-github  (external repos, GitHub-only)
    all         — both datasets (default)

Examples:
    python -m evals.run_evals                        # run everything
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
) -> None:
    """Run a single suite against a single dataset."""
    suite = SUITES[suite_name]
    experiment_name = f"{suite['experiment_prefix']}-{dataset_name}"

    print(f"\n{'='*60}")
    print(f"Suite:   {suite_name} — {suite['description']}")
    print(f"Dataset: {dataset_name} ({DATASETS[dataset_name]})")
    print(f"Experiment: {experiment_name}")
    print(f"{'='*60}")

    results = await aevaluate(
        suite["target"],
        data=DATASETS[dataset_name],
        evaluators=suite["evaluators"],
        experiment_prefix=experiment_name,
        max_concurrency=max_concurrency,
        metadata={
            "suite": suite_name,
            "dataset": dataset_name,
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
) -> None:
    """Run the selected suites × datasets combinations."""
    tasks = [
        run_suite(suite, dataset, max_concurrency)
        for suite in suites
        for dataset in datasets
    ]
    for task in tasks:
        await task


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Qlankr agent evals")
    parser.add_argument(
        "--suite",
        choices=["integration", "e2e", "all"],
        default="all",
        help="Which eval suite to run (default: all)",
    )
    parser.add_argument(
        "--dataset",
        choices=["indexed", "github", "all"],
        default="all",
        help="Which dataset to evaluate on (default: all)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="Max parallel eval runs (default: 2)",
    )
    args = parser.parse_args()

    suites = list(SUITES.keys()) if args.suite == "all" else [args.suite]
    datasets = list(DATASETS.keys()) if args.dataset == "all" else [args.dataset]

    # Verify datasets exist in LangSmith
    client = Client()
    existing = {ds.name for ds in client.list_datasets()}
    missing = [DATASETS[d] for d in datasets if DATASETS[d] not in existing]
    if missing:
        print(f"ERROR: These datasets don't exist in LangSmith: {missing}")
        print("Run first:  cd backend && python -m evals.create_dataset")
        sys.exit(1)

    print(f"Running suites: {suites}")
    print(f"On datasets:    {datasets}")
    print(f"Concurrency:    {args.concurrency}")

    asyncio.run(run_all(suites, datasets, args.concurrency))
    print("\nDone. View results at https://smith.langchain.com")


if __name__ == "__main__":
    main()
