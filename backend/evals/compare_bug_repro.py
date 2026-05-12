"""
Side-by-side bug reproduction eval: Qlankr vs Claude SDK.

Runs both on one hard-coded bug example (OpenTTD timetable crash),
scores every result with all bug_evaluators, and pushes both experiments
to LangSmith so they appear under the same dataset for direct comparison.

Architecture note: both pipelines are run directly (outside of aevaluate's
managed task context) to avoid anyio cancel-scope conflicts with the MCP
AsyncExitStack sessions. aevaluate is called with a cached-result wrapper
whose sole job is scoring + LangSmith experiment logging.

Usage:
    cd backend && python -m evals.compare_bug_repro
    cd backend && python -m evals.compare_bug_repro --no-judges
"""

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from langchain_anthropic import ChatAnthropic
from langsmith import Client
from langsmith.evaluation import aevaluate

from evals.bug_evaluators import (
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
    keyword_recall,
    affected_file_recall,
    root_cause_quality,
    report_coherence,
    reproduction_step_clarity,
)

# ── Constants ──────────────────────────────────────────────────────────────────

DATASET_NAME = "qlankr-bug-compare-demo"
SKILL_DIR = Path(__file__).parent / "skills" / "bug_repro"

# ── Hard-coded bug example: OpenTTD timetable crash ───────────────────────────

BUG_INPUTS = {
    "description": (
        'After disabling "Show arrival and departure date on timetable" in '
        "Settings \u2192 Interface \u2192 Timetable settings, opening any vehicle\u2019s "
        'timetable window causes an immediate crash with assertion failure: '
        '"cur_height < max_smallest" at widget.cpp line 1578 inside '
        "NWidgetHorizontal::SetupSmallestSize(). Reproducible 100% on a "
        "fresh game with no mods. Reverting the setting prevents the crash."
    ),
    "environment": "Windows 11, openttd-15.0-beta3",
    "severity_input": "high",
    "repo_name": "OpenTTD",
}

BUG_REFERENCE = {
    "expected_root_cause_keywords": [
        "fallthrough",
        "UpdateWidgetSize",
        "UpdateSelectionStates",
        "FinishInitNested",
        "SetDisplayedPlane",
    ],
    "expected_affected_files": ["src/timetable_gui.cpp", "src/widget.cpp"],
    "expected_affected_components": [
        "TimetableWindow",
        "NWidgetHorizontal",
        "UpdateSelectionStates",
    ],
    "expected_severity": "high",
    "expected_category": "crash",
    "min_reproduction_steps": 3,
}

# ── Evaluator sets ─────────────────────────────────────────────────────────────

_DETERMINISTIC = [
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
    keyword_recall,
    affected_file_recall,
]
_JUDGES = [root_cause_quality, report_coherence, reproduction_step_clarity]
_JUDGE_NAMES = {f.__name__ for f in _JUDGES}

# ── LLM for Claude SDK target ─────────────────────────────────────────────────

_llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    temperature=0,
    max_tokens=4096,
    api_key=(
        os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("ANTHROPIC_API_KEY")
    ),
    base_url=os.environ.get("ANTHROPIC_BASE_URL") or None,
)

# ── JSON extractor (3-strategy) ───────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    try:
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence:
            return json.loads(fence.group(1))
    except Exception:
        pass
    try:
        obj = re.search(r"\{.*\}", text, re.DOTALL)
        if obj:
            return json.loads(obj.group(0))
    except Exception:
        pass
    return {}

# ── LangSmith dataset ─────────────────────────────────────────────────────────

def _ensure_dataset(client: Client) -> None:
    try:
        client.read_dataset(dataset_name=DATASET_NAME)
        print(f"  Dataset '{DATASET_NAME}' already exists — reusing.")
        return
    except Exception:
        pass
    dataset = client.create_dataset(
        DATASET_NAME,
        description=(
            "OpenTTD timetable crash — 1 example for Qlankr vs Claude SDK comparison"
        ),
    )
    client.create_examples(
        dataset_id=dataset.id,
        examples=[{"inputs": BUG_INPUTS, "outputs": BUG_REFERENCE}],
    )
    print(f"  Created dataset '{DATASET_NAME}' with 1 example.")

# ── Pipeline runner 1: Qlankr ─────────────────────────────────────────────────

async def _run_qlankr(inputs: dict) -> dict:
    """
    Drive the full Qlankr bug pipeline via a checkpoint-free eval graph.

    Avoids the anyio cancel-scope conflict that arises when _start_bug_graph
    (an async generator with an AsyncExitStack inside it) is abandoned mid-run
    after a BugCheckpointEvent, causing its finalizer task to conflict with the
    new MCP sessions opened by _resume_bug_graph.

    Fix: build a graph identical to the production graph but WITHOUT the two
    checkpoint nodes.  Open ONE AsyncExitStack for the entire run, store tools
    in _run_tools[session_id] (where all stage nodes look for them), then call
    ainvoke() — a single awaitable with no intermediate generator abandonment.
    """
    from contextlib import AsyncExitStack

    from langgraph.graph import END, StateGraph

    from agent.agent import BugReproductionState
    from agent.bug_agent import (
        _mechanics_node,
        _reproduction_node,
        _research_node,
        _report_node,
        _triage_node,
        _run_tools,
    )
    from agent.prefetch import prefetch_context
    from agent.tools import get_mcp_client, open_persistent_mcp_sessions

    session_id = f"compare-qlankr-{id(inputs)}"
    print("  [qlankr] opening MCP sessions…")

    async with AsyncExitStack() as stack:
        all_tools = await open_persistent_mcp_sessions(get_mcp_client(), stack)
        _run_tools[session_id] = all_tools
        print(f"  [qlankr] got {len(all_tools)} tools")

        pref = await prefetch_context("", inputs.get("repo_name"), all_tools=all_tools)

        initial_state: BugReproductionState = {
            "description": inputs.get("description", ""),
            "environment": inputs.get("environment"),
            "severity_input": inputs.get("severity_input", "medium"),
            "repo_name": inputs.get("repo_name"),
            "jira_ticket": None,
            "attachments": [],
            "session_id": session_id,
            "repo_stats": pref.get("stats", {}),
            "processes": pref.get("processes", []),
            "triage": {},
            "mechanics": {},
            "reproduction_plan": {},
            "research_findings": {},
            "bug_report": {},
            "current_stage": "triage",
            "tool_calls_used": 0,
            "messages": [],
            "available_tools": [],
            "mechanics_feedback": None,
            "research_context": None,
        }

        # Checkpoint-free eval graph: same stages, no interrupt nodes
        graph = StateGraph(BugReproductionState)
        graph.add_node("triage", _triage_node)
        graph.add_node("mechanics_analysis", _mechanics_node)
        graph.add_node("reproduction_planning", _reproduction_node)
        graph.add_node("research", _research_node)
        graph.add_node("report_generation", _report_node)
        graph.set_entry_point("triage")
        graph.add_edge("triage", "mechanics_analysis")
        graph.add_edge("mechanics_analysis", "reproduction_planning")
        graph.add_edge("reproduction_planning", "research")
        graph.add_edge("research", "report_generation")
        graph.add_edge("report_generation", END)
        eval_graph = graph.compile()  # no checkpointer — single ainvoke

        try:
            print("  [qlankr] starting eval graph (ainvoke)…")
            final_state = await eval_graph.ainvoke(
                initial_state,
                config={"recursion_limit": 100},
            )
            print("  [qlankr] pipeline complete.")
        except Exception as exc:
            import traceback as _tb
            _tb.print_exc()
            return {"error": str(exc)}
        finally:
            _run_tools.pop(session_id, None)

    return {
        k: final_state.get(k, {})
        for k in (
            "triage", "mechanics", "reproduction_plan",
            "research_findings", "bug_report", "tool_calls_used",
        )
    }

# ── Pipeline runner 2: Claude SDK ─────────────────────────────────────────────

async def _run_claude_sdk(inputs: dict) -> dict:
    """
    5-stage pipeline via direct Anthropic API calls, no MCP tools.
    Uses the same skill prompts as the Claude Code CLI target.
    """
    description = inputs.get("description", "")
    environment = inputs.get("environment", "unspecified")

    orchestrator = (SKILL_DIR / "skill.md").read_text()
    base_context = f"Bug description:\n{description}\n\nEnvironment: {environment}"

    prior: dict = {}

    async def _stage(name: str) -> dict:
        skill_text = (SKILL_DIR / f"{name}.md").read_text()
        prior_block = (
            f"\n\nPrior stage outputs:\n{json.dumps(prior, indent=2)}"
            if prior else ""
        )
        prompt = f"{orchestrator}\n\n---\n\n{skill_text}\n\n{base_context}{prior_block}"
        try:
            resp = await _llm.ainvoke([{"role": "user", "content": prompt}])
            result = _extract_json(resp.content)
            if not result:
                print(f"  [claude] WARNING: '{name}' returned no JSON")
            return result
        except Exception as exc:
            print(f"  [claude] ERROR in '{name}': {exc}")
            return {"error": str(exc)}

    output: dict = {"tool_calls_used": 0}
    for stage_file, out_key in [
        ("triage",       "triage"),
        ("mechanics",    "mechanics"),
        ("reproduction", "reproduction_plan"),
        ("research",     "research_findings"),
        ("report",       "bug_report"),
    ]:
        print(f"  [claude] stage '{stage_file}'…")
        result = await _stage(stage_file)
        output[out_key] = result
        prior[out_key] = result

    print("  [claude] all stages complete.")
    return output

# ── Comparison runner ─────────────────────────────────────────────────────────

async def run_comparison(judges_enabled: bool = True) -> None:
    client = Client()
    print("\nPreparing dataset…")
    _ensure_dataset(client)

    # ── Step 1: run both pipelines directly ───────────────────────────────────
    print(f"\n{'='*60}")
    print("Step 1 of 2 — running pipelines")
    print(f"{'='*60}")

    print("\n[Qlankr]")
    qlankr_result = await _run_qlankr(BUG_INPUTS)

    print("\n[Claude SDK]")
    claude_result = await _run_claude_sdk(BUG_INPUTS)

    # ── Step 2: score + log to LangSmith via cached wrappers ─────────────────
    print(f"\n{'='*60}")
    print("Step 2 of 2 — scoring and logging to LangSmith")
    print(f"{'='*60}")

    evaluators = _DETERMINISTIC + (_JUDGES if judges_enabled else [])

    experiments = [
        ("Qlankr",     qlankr_result, "qlankr-bug-repro"),
        ("Claude SDK", claude_result, "claude-sdk-bug-repro"),
    ]

    all_scores: dict[str, dict[str, float]] = {}
    langsmith_urls: dict[str, str] = {}

    for label, cached_output, prefix in experiments:
        print(f"\n  Scoring {label} → experiment '{prefix}'")

        # Capture URL from aevaluate output (printed to stdout by LangSmith SDK)
        def _make_cached_target(result: dict):
            async def _target(_inputs: dict) -> dict:
                return result
            return _target

        results = await aevaluate(
            _make_cached_target(cached_output),
            data=DATASET_NAME,
            evaluators=evaluators,
            experiment_prefix=prefix,
            max_concurrency=1,
            metadata={"target": label.lower().replace(" ", "_")},
        )

        run_scores: dict[str, float] = {}
        async for result in results:
            for r in result.get("evaluation_results", {}).get("results", []):
                if r.score is not None:
                    run_scores[r.key] = r.score

        all_scores[label] = run_scores
        non_zero = sum(1 for s in run_scores.values() if s > 0)
        print(f"    {len(run_scores)} metrics scored ({non_zero} non-zero)")

    # ── Side-by-side results table ────────────────────────────────────────────

    labels = [e[0] for e in experiments]
    all_keys = sorted({k for sc in all_scores.values() for k in sc})
    col_w = 12

    print(f"\n\n{'='*60}")
    print("Results")
    print(f"{'='*60}")
    print(f"\n{'Metric':<35}", end="")
    for lbl in labels:
        print(f"  {lbl:>{col_w}}", end="")
    print()
    print("-" * (39 + (col_w + 2) * len(labels)))

    for key in all_keys:
        tag = " [J]" if key in _JUDGE_NAMES else "    "
        print(f"  {key:<33}{tag}", end="")
        for lbl in labels:
            val = all_scores[lbl].get(key)
            cell = f"{val:.2f}" if val is not None else " n/a"
            print(f"  {cell:>{col_w}}", end="")
        print()

    if judges_enabled:
        print("\n  [J] = LLM-as-judge metric")

    # Summary row
    for lbl in labels:
        sc = all_scores.get(lbl, {})
        if sc:
            avg = sum(sc.values()) / len(sc)
            print(f"  {lbl} average: {avg:.2f}")

    print(f"\nDataset : {DATASET_NAME}")
    print("Experiments visible at https://smith.langchain.com")
    print(f"  qlankr-bug-repro  |  claude-sdk-bug-repro")

# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Side-by-side bug repro eval: Qlankr vs Claude SDK"
    )
    parser.add_argument(
        "--no-judges",
        action="store_true",
        help="Skip LLM-as-judge evaluators (faster, no extra API cost)",
    )
    args = parser.parse_args()
    asyncio.run(run_comparison(judges_enabled=not args.no_judges))


if __name__ == "__main__":
    main()
