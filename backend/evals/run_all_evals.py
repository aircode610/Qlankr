"""
Run ALL Qlankr evaluations in sequence.

Covers:
  PR analysis:      integration + e2e suites × {indexed, github} datasets
  Bug reproduction: qlankr-eval-bugs + qlankr-eval-bugs-real + qlankr-eval-bugs-synthetic

Targets:
  qlankr       — full Qlankr agentic pipeline (default)
  vanilla      — Claude Sonnet on diff only, no tools (PR only)
  claude_code  — Claude Code CLI, stage-by-stage (PR + bugs)

Usage:
    cd backend && python -m evals.run_all_evals [options]

Examples:
    python -m evals.run_all_evals                              # everything, qlankr target
    python -m evals.run_all_evals --no-judges                  # skip LLM judges (faster)
    python -m evals.run_all_evals --skip-pr                    # bugs only
    python -m evals.run_all_evals --skip-bugs                  # PR only
    python -m evals.run_all_evals --target claude_code         # Claude Code baseline
    python -m evals.run_all_evals --target vanilla --skip-bugs # vanilla PR baseline
    python -m evals.run_all_evals --concurrency 3              # higher parallelism
"""

import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from langsmith import Client
from langsmith.evaluation import aevaluate

from evals.evaluators import (
    output_completeness,
    component_count,
    unit_test_structure,
    integration_test_structure,
    e2e_plan_structure,
    tool_coverage,
    tool_efficiency,
    gitnexus_usage,
    confidence_calibration,
    pipeline_progression,
    no_crash,
    surface_groundedness,
    depth_groundedness,
    risk_quality,
    component_matching,
    unit_test_quality,
    integration_test_quality,
)
from evals.bug_evaluators import (
    triage_accuracy,
    mechanics_grounding,
    reproduction_executability,
    bug_pipeline_health,
    research_coverage,
    report_completeness,
    report_actionability,
    evidence_quality,
    tool_efficiency as bug_tool_efficiency,
    graceful_degradation,
    keyword_recall,
    affected_file_recall,
    root_cause_quality,
    report_coherence,
    reproduction_step_clarity,
)

# ── Evaluator sets ─────────────────────────────────────────────────────────────

_PR_BASE = [
    no_crash, pipeline_progression, tool_efficiency, tool_coverage,
    gitnexus_usage, component_count, output_completeness, confidence_calibration,
    component_matching, risk_quality, surface_groundedness, depth_groundedness,
]
_PR_UNIT = [unit_test_structure, unit_test_quality]
_PR_INTEGRATION = [integration_test_structure, integration_test_quality]
_PR_E2E = [e2e_plan_structure]

_PR_BASELINE = [
    output_completeness, component_count, component_matching, risk_quality,
    surface_groundedness, unit_test_structure, unit_test_quality,
    integration_test_structure, integration_test_quality, e2e_plan_structure,
]

_BUG_DETERMINISTIC = [
    triage_accuracy, mechanics_grounding, reproduction_executability,
    bug_pipeline_health, research_coverage, report_completeness,
    report_actionability, evidence_quality, bug_tool_efficiency,
    graceful_degradation, keyword_recall, affected_file_recall,
]
_BUG_JUDGES = [root_cause_quality, report_coherence, reproduction_step_clarity]

# ── Dataset names ──────────────────────────────────────────────────────────────

PR_DATASETS = {
    "indexed": "qlankr-eval-indexed",
    "github":  "qlankr-eval-github",
}

BUG_DATASETS = [
    "qlankr-eval-bugs",
    "qlankr-eval-bugs-real",
    "qlankr-eval-bugs-synthetic",
]


# ── PR analysis runner ─────────────────────────────────────────────────────────

async def _run_pr_suite(
    suite: str,
    dataset_key: str,
    target_name: str,
    max_concurrency: int,
) -> dict[str, list[float]]:
    dataset_name = PR_DATASETS[dataset_key]

    if target_name == "vanilla":
        from evals.baselines.vanilla_claude_target import vanilla_claude_target
        target = vanilla_claude_target
        evaluators = _PR_BASELINE
        experiment_prefix = f"vanilla-{dataset_key}"
    elif target_name == "claude_code":
        from evals.claude_code_target import (
            claude_code_target_pr_integration,
            claude_code_target_pr_e2e,
        )
        target = claude_code_target_pr_integration if suite == "integration" else claude_code_target_pr_e2e
        evaluators = _PR_BASELINE
        experiment_prefix = f"claude-code-{suite}-{dataset_key}"
    else:
        from evals.target import agent_target_integration, agent_target_e2e
        target = agent_target_integration if suite == "integration" else agent_target_e2e
        evaluators = (
            _PR_BASE + _PR_UNIT + _PR_INTEGRATION
            if suite == "integration"
            else _PR_BASE + _PR_UNIT + _PR_E2E
        )
        experiment_prefix = f"{suite}-{dataset_key}"

    print(f"\n{'='*60}")
    print(f"PR eval  |  target={target_name}  suite={suite}  dataset={dataset_key}")
    print(f"Experiment prefix: {experiment_prefix}")
    print(f"{'='*60}")

    results = await aevaluate(
        target,
        data=dataset_name,
        evaluators=evaluators,
        experiment_prefix=experiment_prefix,
        max_concurrency=max_concurrency,
        metadata={"suite": suite, "dataset": dataset_key, "target": target_name},
    )

    score_map: dict[str, list[float]] = {}
    async for result in results:
        for r in result.get("evaluation_results", {}).get("results", []):
            if r.score is not None:
                score_map.setdefault(r.key, []).append(r.score)

    _print_scores(score_map, judge_keys=set())
    return score_map


# ── Bug reproduction runner ────────────────────────────────────────────────────

async def _run_bug_suite(
    dataset_name: str,
    target_name: str,
    judges_enabled: bool,
    max_concurrency: int,
) -> dict[str, list[float]]:
    if target_name == "claude_code":
        from evals.claude_code_target import claude_code_target_bug
        target = claude_code_target_bug
        experiment_prefix = f"claude-code-bug-repro"
    else:
        from evals.run_bug_evals import bug_target
        target = bug_target
        experiment_prefix = "bug-repro-full" if judges_enabled else "bug-repro-det"

    evaluators = (
        _BUG_DETERMINISTIC + _BUG_JUDGES if judges_enabled
        else _BUG_DETERMINISTIC
    )

    label = "full" if judges_enabled else "det-only"
    ds_short = dataset_name.replace("qlankr-eval-", "")
    print(f"\n{'='*60}")
    print(f"Bug eval  |  target={target_name}  dataset={ds_short}  judges={judges_enabled}")
    print(f"Experiment prefix: {experiment_prefix}")
    print(f"{'='*60}")

    results = await aevaluate(
        target,
        data=dataset_name,
        evaluators=evaluators,
        experiment_prefix=experiment_prefix,
        max_concurrency=max_concurrency,
        metadata={
            "pipeline": "bug_reproduction",
            "dataset": dataset_name,
            "target": target_name,
            "judges_enabled": judges_enabled,
        },
    )

    judge_keys = {f.__name__ for f in _BUG_JUDGES}
    score_map: dict[str, list[float]] = {}
    async for result in results:
        for r in result.get("evaluation_results", {}).get("results", []):
            if r.score is not None:
                score_map.setdefault(r.key, []).append(r.score)

    _print_scores(score_map, judge_keys=judge_keys)
    return score_map


# ── Helpers ────────────────────────────────────────────────────────────────────

def _print_scores(score_map: dict[str, list[float]], judge_keys: set[str]) -> None:
    if not score_map:
        print("  (no scores — check LangSmith UI)")
        return
    print(f"\n{'Metric':<35} {'Mean':>6}  {'Min':>6}  {'Max':>6}")
    print("-" * 57)
    for metric, scores in sorted(score_map.items()):
        mean = sum(scores) / len(scores)
        tag = " [J]" if metric in judge_keys else "    "
        print(f"  {metric:<33}{tag} {mean:>6.2f}  {min(scores):>6.2f}  {max(scores):>6.2f}")
    if judge_keys & score_map.keys():
        print("  [J] = LLM-as-judge metric")


def _check_datasets(client: Client, names: list[str]) -> None:
    existing: set[str] = set()
    try:
        existing = {ds.name for ds in client.list_datasets()}
    except Exception:
        # Some PATs can't list; fall back to per-name read
        pass

    missing = []
    for name in names:
        if name in existing:
            continue
        try:
            client.read_dataset(dataset_name=name)
        except Exception:
            missing.append(name)

    if missing:
        print(f"\nERROR: These datasets don't exist in LangSmith:")
        for m in missing:
            print(f"  - {m}")
        print("\nCreate them first:")
        print("  cd backend && python -m evals.create_dataset")
        sys.exit(1)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run all Qlankr evaluations (PR analysis + bug reproduction)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--target",
        choices=["qlankr", "vanilla", "claude_code"],
        default="qlankr",
        help="System to evaluate (default: qlankr)",
    )
    parser.add_argument(
        "--no-judges",
        action="store_true",
        help="Skip LLM-as-judge evaluators (faster, no API cost)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="Max parallel runs for PR suites (default: 2). Bug suite always uses 1.",
    )
    parser.add_argument(
        "--skip-pr",
        action="store_true",
        help="Skip all PR analysis suites",
    )
    parser.add_argument(
        "--skip-bugs",
        action="store_true",
        help="Skip all bug reproduction suites",
    )
    args = parser.parse_args()

    if args.skip_pr and args.skip_bugs:
        print("ERROR: --skip-pr and --skip-bugs together leaves nothing to run.")
        sys.exit(1)

    # vanilla doesn't apply to bugs; claude_code applies to both
    if args.target == "vanilla" and not args.skip_bugs:
        print("NOTE: vanilla target does not support bug reproduction — skipping bug suites.")
        args.skip_bugs = True

    client = Client()

    # Verify all needed datasets exist upfront
    needed: list[str] = []
    if not args.skip_pr:
        needed += list(PR_DATASETS.values())
    if not args.skip_bugs:
        needed += BUG_DATASETS
    _check_datasets(client, needed)

    start = time.time()
    print(f"\nQlankr full eval run")
    print(f"  target     : {args.target}")
    print(f"  judges     : {'yes' if not args.no_judges else 'no'}")
    print(f"  concurrency: {args.concurrency} (PR) / 1 (bugs)")

    # ── PR analysis ────────────────────────────────────────────────────────────
    if not args.skip_pr:
        suites = ["integration", "e2e"]
        # vanilla collapses to integration only (it's a single LLM call, no path split)
        if args.target == "vanilla":
            suites = ["integration"]

        for suite in suites:
            for dataset_key in PR_DATASETS:
                asyncio.run(_run_pr_suite(suite, dataset_key, args.target, args.concurrency))

    # ── Bug reproduction ───────────────────────────────────────────────────────
    if not args.skip_bugs:
        for dataset_name in BUG_DATASETS:
            asyncio.run(_run_bug_suite(
                dataset_name=dataset_name,
                target_name=args.target,
                judges_enabled=not args.no_judges,
                max_concurrency=1,
            ))

    elapsed = time.time() - start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    print(f"\n{'='*60}")
    print(f"All evals complete in {minutes}m {seconds}s.")
    print(f"View results at https://smith.langchain.com")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
