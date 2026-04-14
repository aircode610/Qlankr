# Agent Evaluation Guide

This document explains how to evaluate the Qlankr PR analysis agent using LLM-based evaluation. We use **LangSmith** (already integrated) as the primary framework, with optional **agentevals** for trajectory analysis.

---

## Prerequisites

```bash
cd backend
source .venv/bin/activate

# Already installed
pip install langsmith

# New deps for evaluation
pip install agentevals
```

Ensure your `.env` has valid LangSmith keys:

```
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
LANGSMITH_PROJECT=qlankr
```

---

## Overview

The evaluation has three layers:

| Layer | What it checks | Needs LLM judge? |
|-------|---------------|-------------------|
| Structural | Fields present, schema valid, min components | No |
| Tool usage | Right tools called, no wasted calls | No |
| Groundedness | Claims backed by tool outputs / PR diff | Yes |
| Trajectory | Was the tool-call sequence reasonable? | Yes |
| Risk quality | Risks are real and relevant | Yes |

---

## Step 1: Create the Eval Target

The eval target wraps `run_agent()` so LangSmith can call it with dataset inputs and collect outputs.

Create `backend/evals/__init__.py` (empty) and `backend/evals/target.py`:

```python
"""Eval target — wraps run_agent() for LangSmith evaluate()."""

import asyncio
from agent.agent import run_agent


async def agent_target(inputs: dict) -> dict:
    """
    Called by LangSmith's aevaluate() for each dataset example.
    Accepts: {"pr_url": "https://github.com/owner/repo/pull/N"}
    Returns: dict with agent outputs for evaluators to score.
    """
    pr_url = inputs["pr_url"]

    tool_calls = []
    result = None

    async for event in run_agent(pr_url):
        event_data = event.model_dump()
        if event_data.get("type") == "agent_step":
            tool_calls.append(event_data["tool"])
        elif event_data.get("type") == "result":
            result = event_data
        elif event_data.get("type") == "error":
            return {"error": event_data["message"], "tool_calls": tool_calls}

    if result is None:
        return {"error": "no result produced", "tool_calls": tool_calls}

    return {
        "pr_title": result["pr_title"],
        "pr_summary": result["pr_summary"],
        "affected_components": result["affected_components"],
        "agent_steps": result["agent_steps"],
        "tool_calls": tool_calls,
    }
```

---

## Step 2: Create the Golden Dataset

Pick 5-10 real PRs from your repo with diverse characteristics:
- Small bugfix (1-2 files)
- Large feature (10+ files)
- Refactor (moved/renamed code)
- New files only (nothing in graph yet)

Create `backend/evals/create_dataset.py`:

```python
"""Create the golden eval dataset in LangSmith."""

from langsmith import Client

client = Client()

DATASET_NAME = "pr-analysis-evals"

# Delete if it already exists (for re-creation)
for ds in client.list_datasets():
    if ds.name == DATASET_NAME:
        client.delete_dataset(dataset_id=ds.id)
        break

dataset = client.create_dataset(
    DATASET_NAME,
    description="Golden PR examples for Qlankr agent evaluation",
)

# ── Define your golden examples here ──────────────────────────────────────────
# inputs:  what the agent receives
# outputs: what evaluators compare against (the "expected" reference)

examples = [
    {
        "inputs": {
            "pr_url": "https://github.com/aircode610/Qlankr/pull/9",
        },
        "outputs": {
            # Expected affected components (by name)
            "expected_components": [
                "ReAct Agent",
                "Indexer",
                "API Endpoints",
            ],
            # Key risks a good analysis should catch
            "expected_risks": [
                "agent can exhaust tool budget without submitting result",
                "MCP subprocess cold start latency",
                "no auth guard on debug endpoints",
            ],
            # Tools the agent SHOULD call for a thorough analysis
            "expected_tools": [
                "get_pull_request",
                "get_pull_request_files",
                "impact",
                "context",
                "cypher",
            ],
            # Minimum number of components we expect
            "min_components": 2,
        },
    },
    # Add more examples here. For each PR:
    # 1. Read the PR diff yourself
    # 2. Write down what components are affected
    # 3. Write down the key risks you'd flag
    # 4. List which tools should be called
    #
    # Example template:
    # {
    #     "inputs": {"pr_url": "https://github.com/aircode610/Qlankr/pull/XX"},
    #     "outputs": {
    #         "expected_components": ["Component A", "Component B"],
    #         "expected_risks": ["risk 1", "risk 2"],
    #         "expected_tools": ["get_pull_request", "get_pull_request_files", "impact"],
    #         "min_components": 1,
    #     },
    # },
]

client.create_examples(dataset_id=dataset.id, examples=examples)
print(f"Created dataset '{DATASET_NAME}' with {len(examples)} examples")
```

Run it:

```bash
python -m evals.create_dataset
```

---

## Step 3: Write Evaluators

Create `backend/evals/evaluators.py`:

```python
"""
Evaluators for Qlankr agent.

Each evaluator is a plain function that LangSmith calls with the agent's
output and (optionally) the reference output from the dataset.

Return format: {"key": "metric_name", "score": 0.0-1.0, "comment": "optional"}
"""

import json
from langchain_anthropic import ChatAnthropic

# ── Deterministic evaluators (no LLM needed) ─────────────────────────────────


def output_completeness(outputs: dict) -> dict:
    """Check that each affected component has all required fields filled."""
    components = outputs.get("affected_components", [])
    if not components:
        return {"key": "output_completeness", "score": 0.0, "comment": "No components"}

    scores = []
    for c in components:
        filled = sum([
            bool(c.get("files_changed")),
            bool(c.get("impact_summary")),
            bool(c.get("risks")),
            bool(c.get("test_suggestions", {}).get("run")),
        ])
        scores.append(filled / 4)

    avg = sum(scores) / len(scores)
    return {"key": "output_completeness", "score": avg}


def component_count(outputs: dict, reference_outputs: dict) -> dict:
    """Check that the agent found at least the minimum expected components."""
    actual = len(outputs.get("affected_components", []))
    minimum = reference_outputs.get("min_components", 1)
    score = 1.0 if actual >= minimum else actual / minimum
    return {
        "key": "component_count",
        "score": score,
        "comment": f"Found {actual}, expected >= {minimum}",
    }


def tool_coverage(outputs: dict, reference_outputs: dict) -> dict:
    """Check that the agent called the expected tools."""
    actual = set(outputs.get("tool_calls", []))
    expected = set(reference_outputs.get("expected_tools", []))
    if not expected:
        return {"key": "tool_coverage", "score": 1.0}
    covered = len(actual & expected)
    score = covered / len(expected)
    missing = expected - actual
    return {
        "key": "tool_coverage",
        "score": score,
        "comment": f"Missing: {missing}" if missing else "All expected tools called",
    }


def tool_efficiency(outputs: dict) -> dict:
    """Penalize redundant tool calls (same tool called >3 times)."""
    calls = outputs.get("tool_calls", [])
    if not calls:
        return {"key": "tool_efficiency", "score": 0.0}

    from collections import Counter
    counts = Counter(calls)
    redundant = sum(max(0, v - 3) for v in counts.values())
    score = max(0.0, 1.0 - (redundant / len(calls)))
    return {
        "key": "tool_efficiency",
        "score": score,
        "comment": f"{len(calls)} total calls, {redundant} redundant",
    }


def has_gitnexus_tools(outputs: dict) -> dict:
    """Check that the agent used GitNexus tools, not just GitHub tools."""
    gitnexus_tools = {"impact", "context", "query", "cypher", "list_repos"}
    actual = set(outputs.get("tool_calls", []))
    used = actual & gitnexus_tools
    score = min(1.0, len(used) / 2)  # expect at least 2 GitNexus tools
    return {
        "key": "gitnexus_usage",
        "score": score,
        "comment": f"Used: {used}" if used else "No GitNexus tools used!",
    }


# ── LLM-as-judge evaluators ──────────────────────────────────────────────────

_judge = ChatAnthropic(model="claude-sonnet-4-6", temperature=0, max_tokens=1024)


def _parse_judge_response(content: str) -> dict:
    """Extract JSON score from judge response."""
    try:
        # Handle markdown code blocks
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content.strip())
    except Exception:
        return {"score": 0.5, "reasoning": "Could not parse judge response"}


async def groundedness(inputs: dict, outputs: dict) -> dict:
    """LLM judge: are the agent's claims grounded in real code changes?"""
    components = outputs.get("affected_components", [])
    if not components:
        return {"key": "groundedness", "score": 0.0}

    formatted = _format_components(components)
    prompt = f"""You are evaluating a QA impact analysis of a GitHub pull request.

PR URL: {inputs['pr_url']}

The agent produced this analysis:
{formatted}

Evaluate whether each claim (impact summaries, risks, test suggestions) could
reasonably be determined from the PR diff and codebase. A grounded claim is one
a human reviewer reading the same PR would agree with.

Score 0.0 to 1.0:
- 1.0 = all claims well-supported and specific
- 0.7 = mostly grounded, minor extrapolations
- 0.4 = mix of grounded and speculative
- 0.0 = fabricated or contradicted by the code

Return ONLY a JSON object: {{"score": <float>, "reasoning": "<1-2 sentences>"}}"""

    response = await _judge.ainvoke([{"role": "user", "content": prompt}])
    result = _parse_judge_response(response.content)
    return {
        "key": "groundedness",
        "score": result["score"],
        "comment": result.get("reasoning", ""),
    }


async def risk_quality(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    """LLM judge: did the agent catch the expected risks?"""
    actual_risks = []
    for c in outputs.get("affected_components", []):
        actual_risks.extend(c.get("risks", []))

    expected_risks = reference_outputs.get("expected_risks", [])
    if not expected_risks:
        return {"key": "risk_quality", "score": 1.0}

    prompt = f"""Compare the agent's identified risks against the expected risks.

Agent found these risks:
{json.dumps(actual_risks, indent=2)}

Expected risks (from human review):
{json.dumps(expected_risks, indent=2)}

Score 0.0 to 1.0 based on:
- Recall: did the agent find risks matching the expected ones? (exact wording
  doesn't matter, semantic similarity counts)
- Precision: are the agent's extra risks relevant, not hallucinated?

Return ONLY: {{"score": <float>, "reasoning": "<1-2 sentences>"}}"""

    response = await _judge.ainvoke([{"role": "user", "content": prompt}])
    result = _parse_judge_response(response.content)
    return {
        "key": "risk_quality",
        "score": result["score"],
        "comment": result.get("reasoning", ""),
    }


async def test_suggestion_quality(inputs: dict, outputs: dict) -> dict:
    """LLM judge: are the test suggestions actionable and relevant?"""
    components = outputs.get("affected_components", [])
    if not components:
        return {"key": "test_suggestions", "score": 0.0}

    all_tests = {"skip": [], "run": [], "deeper": []}
    for c in components:
        ts = c.get("test_suggestions", {})
        for key in all_tests:
            all_tests[key].extend(ts.get(key, []))

    prompt = f"""Evaluate the quality of these test suggestions for a PR analysis.

Tests to skip: {all_tests['skip']}
Tests to run: {all_tests['run']}
Tests needing deeper review: {all_tests['deeper']}

Score 0.0 to 1.0:
- Are the "run" tests specific and actionable (not vague like "test the code")?
- Do the "skip" tests make sense to skip?
- Are "deeper" tests appropriately flagged for extra attention?
- Is the categorization (skip vs run vs deeper) reasonable?

Return ONLY: {{"score": <float>, "reasoning": "<1-2 sentences>"}}"""

    response = await _judge.ainvoke([{"role": "user", "content": prompt}])
    result = _parse_judge_response(response.content)
    return {
        "key": "test_suggestions",
        "score": result["score"],
        "comment": result.get("reasoning", ""),
    }


# ── Helper ────────────────────────────────────────────────────────────────────

def _format_components(components: list) -> str:
    lines = []
    for c in components:
        lines.append(f"Component: {c.get('component', 'unnamed')}")
        lines.append(f"  Confidence: {c.get('confidence', '?')}")
        lines.append(f"  Files: {c.get('files_changed', [])}")
        lines.append(f"  Impact: {c.get('impact_summary', '')}")
        lines.append(f"  Risks: {c.get('risks', [])}")
        ts = c.get("test_suggestions", {})
        lines.append(f"  Tests to run: {ts.get('run', [])}")
        lines.append(f"  Deeper tests: {ts.get('deeper', [])}")
        lines.append("")
    return "\n".join(lines)
```

---

## Step 4: Run the Evaluation

Create `backend/evals/run_evals.py`:

```python
"""Run the full evaluation suite."""

import asyncio
import sys
import os

# Ensure backend is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from langsmith import aevaluate
from evals.target import agent_target
from evals.evaluators import (
    # Deterministic
    output_completeness,
    component_count,
    tool_coverage,
    tool_efficiency,
    has_gitnexus_tools,
    # LLM-as-judge
    groundedness,
    risk_quality,
    test_suggestion_quality,
)

DATASET = "pr-analysis-evals"


async def main():
    experiment = await aevaluate(
        agent_target,
        data=DATASET,
        evaluators=[
            # Deterministic (fast, no cost)
            output_completeness,
            component_count,
            tool_coverage,
            tool_efficiency,
            has_gitnexus_tools,
            # LLM judges (slower, costs API calls)
            groundedness,
            risk_quality,
            test_suggestion_quality,
        ],
        experiment_prefix="qlankr-sprint1",
        max_concurrency=1,  # keep at 1 — each run spawns MCP subprocesses
    )
    print(f"\nExperiment complete. View results at: {experiment.url}")


if __name__ == "__main__":
    asyncio.run(main())
```

Run it:

```bash
cd backend
python -m evals.run_evals
```

---

## Step 5: View Results

Open the LangSmith dashboard:
1. Go to your project (`qlankr`)
2. Click **Experiments** in the sidebar
3. Find the experiment prefixed with `qlankr-sprint1`
4. You'll see per-example scores for each evaluator
5. Click into any example to see the judge's reasoning

---

## Step 6 (Optional): Trajectory Evaluation

If you want to evaluate whether the agent's tool-call *sequence* was smart
(not just which tools, but in what order and with what arguments):

```bash
pip install agentevals
```

Add to `evaluators.py`:

```python
from agentevals.trajectory.llm import (
    create_trajectory_llm_as_judge,
    TRAJECTORY_ACCURACY_PROMPT,
)

_trajectory_judge = create_trajectory_llm_as_judge(
    model="claude-sonnet-4-6",
    prompt=TRAJECTORY_ACCURACY_PROMPT,
)


async def trajectory_quality(outputs: dict) -> dict:
    """Judge whether the agent's tool-call sequence was reasonable."""
    tool_calls = outputs.get("tool_calls", [])
    if not tool_calls:
        return {"key": "trajectory", "score": 0.0}

    # Format as the trajectory evaluator expects
    trajectory_str = "\n".join(f"{i+1}. {t}" for i, t in enumerate(tool_calls))
    result = _trajectory_judge(outputs={"trajectory": trajectory_str})
    return {
        "key": "trajectory",
        "score": 1.0 if result.get("score") else 0.0,
        "comment": result.get("comment", ""),
    }
```

Then add `trajectory_quality` to the evaluators list in `run_evals.py`.

---

## Step 7: Iterate

After the first run, look at which scores are lowest:

| Low score on... | What to fix |
|----------------|-------------|
| `output_completeness` | Agent is producing sparse components — improve the system prompt to require all fields |
| `tool_coverage` | Agent isn't using key tools — check if the prompt mentions them clearly |
| `gitnexus_usage` | Agent only using GitHub tools — check that repo indexing works and repo name is passed |
| `groundedness` | Agent is hallucinating — tighten the "ground every claim" rule in the prompt |
| `risk_quality` | Agent misses important risks — add examples of good risk identification to the prompt |
| `test_suggestions` | Tests are vague — add examples of good test suggestions in the prompt |
| `tool_efficiency` | Too many redundant calls — add a budget warning or reduce MAX_TOOL_CALLS |
| `trajectory` | Tool order is wrong (e.g. impact before reading diff) — reorder instructions in prompt |

Re-run evals after each change to track improvement. LangSmith keeps all
experiment history so you can compare across runs.

---

## File Structure

After setup, you'll have:

```
backend/
  evals/
    __init__.py          # empty
    create_dataset.py    # run once to create golden dataset
    target.py            # wraps run_agent() for evaluation
    evaluators.py        # all evaluator functions
    run_evals.py         # main entry point
```

---

## Cost Estimate

Per evaluation run (assuming 5 golden examples):

| Item | Calls | Est. cost |
|------|-------|-----------|
| Agent runs (5 PRs x ~20 tool calls) | 5 Claude Sonnet calls | ~$0.50 |
| Groundedness judge (5 examples) | 5 Claude Sonnet calls | ~$0.05 |
| Risk quality judge (5 examples) | 5 Claude Sonnet calls | ~$0.05 |
| Test suggestion judge (5 examples) | 5 Claude Sonnet calls | ~$0.05 |
| **Total per eval run** | | **~$0.65** |

The deterministic evaluators (completeness, tool coverage, efficiency) are free.
