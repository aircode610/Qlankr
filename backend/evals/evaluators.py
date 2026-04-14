"""
Evaluators for Qlankr Sprint 2 agent.

Evaluator categories:
  1. Structural   — field presence, schema validity (deterministic, free)
  2. Tool usage   — coverage, efficiency, GitNexus usage (deterministic, free)
  3. Pipeline     — stage progression, checkpoint handling (deterministic, free)
  4. Groundedness — are claims backed by tool outputs (LLM judge)
  5. Risk quality — did the agent catch expected risks (LLM judge)
  6. Unit test quality    — are generated specs useful (LLM judge)
  7. Integration test quality — are cross-module specs useful (LLM judge)

Each evaluator is a plain function that LangSmith calls with the agent's
output and (optionally) the reference output from the dataset.

Return format: {"key": "metric_name", "score": 0.0-1.0, "comment": "optional"}
"""

import json
import os
from collections import Counter

from langchain_anthropic import ChatAnthropic

# ═══════════════════════════════════════════════════════════════════════════════
# 1. STRUCTURAL EVALUATORS (deterministic)
# ═══════════════════════════════════════════════════════════════════════════════


def output_completeness(outputs: dict) -> dict:
    """Check that each affected component has all required fields filled."""
    if "error" in outputs:
        return {"key": "output_completeness", "score": 0.0, "comment": outputs["error"]}

    components = outputs.get("affected_components", [])
    if not components:
        return {"key": "output_completeness", "score": 0.0, "comment": "No components"}

    scores = []
    for c in components:
        filled = sum([
            bool(c.get("component")),
            bool(c.get("files_changed")),
            bool(c.get("impact_summary")),
            bool(c.get("risks")),
            c.get("confidence") in ("high", "medium", "low"),
        ])
        scores.append(filled / 5)

    avg = sum(scores) / len(scores)
    return {"key": "output_completeness", "score": avg}


def component_count(outputs: dict, reference_outputs: dict) -> dict:
    """Check that the agent found at least the minimum expected components."""
    if "error" in outputs:
        return {"key": "component_count", "score": 0.0}

    actual = len(outputs.get("affected_components", []))
    minimum = reference_outputs.get("min_components", 1)
    score = min(1.0, actual / minimum) if minimum > 0 else 1.0
    return {
        "key": "component_count",
        "score": score,
        "comment": f"Found {actual}, expected >= {minimum}",
    }


def unit_test_structure(outputs: dict) -> dict:
    """Check that unit test specs have valid structure (target, test_cases, priority)."""
    components = outputs.get("affected_components", [])
    if not components:
        return {"key": "unit_test_structure", "score": 0.0, "comment": "No components"}

    all_specs = []
    for c in components:
        all_specs.extend(c.get("unit_tests", []))

    if not all_specs:
        # Check intermediate results from checkpoint
        for c in outputs.get("unit_intermediate", []):
            all_specs.extend(c.get("unit_tests", []))

    if not all_specs:
        return {"key": "unit_test_structure", "score": 0.0, "comment": "No unit test specs"}

    scores = []
    for spec in all_specs:
        has_target = bool(spec.get("target"))
        has_cases = len(spec.get("test_cases", [])) > 0
        has_priority = spec.get("priority") in ("high", "medium", "low")
        cases_valid = all(
            tc.get("name") and tc.get("expected")
            for tc in spec.get("test_cases", [])
        ) if has_cases else False
        scores.append(sum([has_target, has_cases, has_priority, cases_valid]) / 4)

    avg = sum(scores) / len(scores)
    return {
        "key": "unit_test_structure",
        "score": avg,
        "comment": f"{len(all_specs)} specs checked",
    }


def integration_test_structure(outputs: dict) -> dict:
    """Check that integration test specs have valid structure."""
    components = outputs.get("affected_components", [])
    all_specs = []
    for c in components:
        all_specs.extend(c.get("integration_tests", []))

    if not all_specs:
        path = outputs.get("path_taken", "")
        if path == "e2e" or path == "gather_only":
            return {"key": "integration_test_structure", "score": 1.0, "comment": "N/A (e2e path)"}
        return {"key": "integration_test_structure", "score": 0.0, "comment": "No integration specs"}

    scores = []
    for spec in all_specs:
        has_point = bool(spec.get("integration_point"))
        has_modules = len(spec.get("modules_involved", [])) >= 2
        has_cases = len(spec.get("test_cases", [])) > 0
        has_risk = spec.get("risk_level") in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
        scores.append(sum([has_point, has_modules, has_cases, has_risk]) / 4)

    avg = sum(scores) / len(scores)
    return {
        "key": "integration_test_structure",
        "score": avg,
        "comment": f"{len(all_specs)} specs checked",
    }


def e2e_plan_structure(outputs: dict) -> dict:
    """Check that E2E test plans have valid structure."""
    plans = outputs.get("e2e_test_plans", [])
    if not plans:
        path = outputs.get("path_taken", "")
        if path == "integration" or path == "gather_only":
            return {"key": "e2e_plan_structure", "score": 1.0, "comment": "N/A (integration path)"}
        return {"key": "e2e_plan_structure", "score": 0.0, "comment": "No E2E plans"}

    scores = []
    for plan in plans:
        has_process = bool(plan.get("process"))
        has_scenario = bool(plan.get("scenario"))
        has_steps = len(plan.get("steps", [])) > 0
        has_priority = plan.get("priority") in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
        scores.append(sum([has_process, has_scenario, has_steps, has_priority]) / 4)

    avg = sum(scores) / len(scores)
    return {
        "key": "e2e_plan_structure",
        "score": avg,
        "comment": f"{len(plans)} plans checked",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 2. TOOL USAGE EVALUATORS (deterministic)
# ═══════════════════════════════════════════════════════════════════════════════


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
    """Penalize redundant tool calls (same tool called >4 times)."""
    calls = outputs.get("tool_calls", [])
    if not calls:
        return {"key": "tool_efficiency", "score": 0.0}

    counts = Counter(calls)
    # Allow submit tools to be called multiple times (retries)
    submit_keys = [k for k in counts if "submit" in k]
    for k in submit_keys:
        del counts[k]

    redundant = sum(max(0, v - 4) for v in counts.values())
    score = max(0.0, 1.0 - (redundant / max(len(calls), 1)))
    return {
        "key": "tool_efficiency",
        "score": score,
        "comment": f"{len(calls)} total calls, {redundant} redundant",
    }


def gitnexus_usage(outputs: dict, reference_outputs: dict) -> dict:
    """Check that the agent used GitNexus tools when the repo is indexed."""
    expect = reference_outputs.get("expect_gitnexus", False)
    if not expect:
        return {"key": "gitnexus_usage", "score": 1.0, "comment": "N/A (GitHub-only)"}

    gitnexus_tools = {"impact", "context", "query", "cypher", "list_repos"}
    actual = set(outputs.get("tool_calls", []))
    used = actual & gitnexus_tools
    score = min(1.0, len(used) / 2)  # expect at least 2 GitNexus tools
    return {
        "key": "gitnexus_usage",
        "score": score,
        "comment": f"Used: {used}" if used else "No GitNexus tools used!",
    }


def confidence_calibration(outputs: dict, reference_outputs: dict) -> dict:
    """Check that confidence levels are appropriate.
    Non-indexed repos should have low confidence; indexed repos can be higher."""
    components = outputs.get("affected_components", [])
    if not components:
        return {"key": "confidence_calibration", "score": 0.0}

    expect_gitnexus = reference_outputs.get("expect_gitnexus", False)

    if not expect_gitnexus:
        # GitHub-only: all confidence should be low
        low_count = sum(1 for c in components if c.get("confidence") == "low")
        score = low_count / len(components)
        return {
            "key": "confidence_calibration",
            "score": score,
            "comment": f"{low_count}/{len(components)} are 'low' (expected for non-indexed repo)",
        }
    else:
        # Indexed repo: at least some should be medium or high
        non_low = sum(1 for c in components if c.get("confidence") in ("medium", "high"))
        score = min(1.0, non_low / max(1, len(components) // 2))
        return {
            "key": "confidence_calibration",
            "score": score,
            "comment": f"{non_low}/{len(components)} are medium/high",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PIPELINE EVALUATORS (deterministic)
# ═══════════════════════════════════════════════════════════════════════════════


def pipeline_progression(outputs: dict) -> dict:
    """Check that the agent progressed through expected stages."""
    stages = outputs.get("stages_seen", [])
    if not stages:
        return {"key": "pipeline_progression", "score": 0.0, "comment": "No stages seen"}

    path = outputs.get("path_taken", "integration")

    if path == "gather_only":
        expected = ["gather"]
    elif path == "integration":
        expected = ["gather", "unit_tests", "integration_tests"]
    elif path == "e2e":
        expected = ["gather", "unit_tests", "e2e_planning"]
    else:
        expected = ["gather"]

    seen = set(stages)
    hit = sum(1 for e in expected if e in seen)
    score = hit / len(expected)
    missing = [e for e in expected if e not in seen]
    return {
        "key": "pipeline_progression",
        "score": score,
        "comment": f"Missing stages: {missing}" if missing else f"All {len(expected)} stages hit",
    }


def no_crash(outputs: dict) -> dict:
    """Basic check: did the agent complete without error?"""
    if "error" in outputs:
        return {"key": "no_crash", "score": 0.0, "comment": outputs["error"]}
    if outputs.get("affected_components"):
        return {"key": "no_crash", "score": 1.0}
    return {"key": "no_crash", "score": 0.5, "comment": "Completed but no components"}


# ═══════════════════════════════════════════════════════════════════════════════
# 4. LLM-AS-JUDGE EVALUATORS
# ═══════════════════════════════════════════════════════════════════════════════

_judge = ChatAnthropic(
    model="claude-sonnet-4-6",
    temperature=0,
    max_tokens=1024,
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
)


def _parse_judge_response(content: str) -> dict:
    """Extract JSON score from judge response."""
    try:
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

Evaluate whether each claim (impact summaries, risks) could reasonably be
determined from the PR diff and codebase. A grounded claim is one a human
reviewer reading the same PR would agree with.

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

    prompt = f"""Compare the agent's identified risks against the expected risks for this PR.

PR URL: {inputs['pr_url']}

Agent found these risks:
{json.dumps(actual_risks, indent=2)}

Expected risks (from human review):
{json.dumps(expected_risks, indent=2)}

Score 0.0 to 1.0 based on:
- Recall: did the agent find risks semantically matching the expected ones?
  (exact wording doesn't matter — if the agent identified the same underlying
  concern in different words, that counts)
- Precision: are the agent's extra risks relevant, not hallucinated?
- Penalty: deduct if the agent missed critical risks entirely

Return ONLY: {{"score": <float>, "reasoning": "<1-2 sentences>"}}"""

    response = await _judge.ainvoke([{"role": "user", "content": prompt}])
    result = _parse_judge_response(response.content)
    return {
        "key": "risk_quality",
        "score": result["score"],
        "comment": result.get("reasoning", ""),
    }


async def component_matching(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    """LLM judge: do the agent's component names match the expected ones?
    We use an LLM because exact name matching would be too strict —
    'ReAct Agent Core' should match 'ReAct Agent'."""
    actual = [c.get("component", "") for c in outputs.get("affected_components", [])]
    expected = reference_outputs.get("expected_components", [])
    if not expected:
        return {"key": "component_matching", "score": 1.0}

    prompt = f"""Compare the agent's identified components against the expected components.

Agent found: {json.dumps(actual)}
Expected:    {json.dumps(expected)}

Score 0.0 to 1.0:
- 1.0 = all expected components found (possibly under different names)
- Partial credit for each expected component that has a semantic match
- Small bonus if agent found additional legitimate components
- Deduct if agent hallucinated components that don't relate to the PR

Return ONLY: {{"score": <float>, "reasoning": "<1-2 sentences>"}}"""

    response = await _judge.ainvoke([{"role": "user", "content": prompt}])
    result = _parse_judge_response(response.content)
    return {
        "key": "component_matching",
        "score": result["score"],
        "comment": result.get("reasoning", ""),
    }


async def unit_test_quality(inputs: dict, outputs: dict) -> dict:
    """LLM judge: are the generated unit test specs useful and actionable?"""
    all_specs = []
    for c in outputs.get("affected_components", []):
        all_specs.extend(c.get("unit_tests", []))
    # Also check intermediate results
    for c in outputs.get("unit_intermediate", []):
        all_specs.extend(c.get("unit_tests", []))

    if not all_specs:
        return {"key": "unit_test_quality", "score": 0.0, "comment": "No unit test specs"}

    # Limit to first 10 specs to keep judge cost reasonable
    sample = all_specs[:10]

    prompt = f"""Evaluate the quality of these unit test specifications for a PR analysis.

PR URL: {inputs['pr_url']}

Unit test specs (showing {len(sample)} of {len(all_specs)}):
{json.dumps(sample, indent=2, default=str)}

Score 0.0 to 1.0:
- Are test targets specific real symbols (not vague like "the function")?
- Do test cases cover meaningful scenarios (happy path, edge cases, error cases)?
- Are the expected outcomes concrete and verifiable?
- Are mocks_needed appropriate (mocking external deps, not internal logic)?
- Are priorities reasonable (high for critical paths, low for utilities)?

Return ONLY: {{"score": <float>, "reasoning": "<1-2 sentences>"}}"""

    response = await _judge.ainvoke([{"role": "user", "content": prompt}])
    result = _parse_judge_response(response.content)
    return {
        "key": "unit_test_quality",
        "score": result["score"],
        "comment": result.get("reasoning", ""),
    }


async def integration_test_quality(inputs: dict, outputs: dict) -> dict:
    """LLM judge: are integration test specs useful?"""
    all_specs = []
    for c in outputs.get("affected_components", []):
        all_specs.extend(c.get("integration_tests", []))

    path = outputs.get("path_taken", "")
    if not all_specs:
        if path == "e2e" or path == "gather_only":
            return {"key": "integration_test_quality", "score": 1.0, "comment": "N/A"}
        return {"key": "integration_test_quality", "score": 0.0, "comment": "No specs"}

    sample = all_specs[:10]

    prompt = f"""Evaluate the quality of these integration test specifications.

PR URL: {inputs['pr_url']}

Integration test specs ({len(sample)} of {len(all_specs)}):
{json.dumps(sample, indent=2, default=str)}

Score 0.0 to 1.0:
- Do integration points identify real cross-module boundaries?
- Are the modules_involved correct (at least 2 distinct modules)?
- Do test cases describe data/events that cross the boundary?
- Is data_setup specific enough to reproduce the scenario?
- Is risk_level appropriate (CRITICAL for hot paths, LOW for admin)?

Return ONLY: {{"score": <float>, "reasoning": "<1-2 sentences>"}}"""

    response = await _judge.ainvoke([{"role": "user", "content": prompt}])
    result = _parse_judge_response(response.content)
    return {
        "key": "integration_test_quality",
        "score": result["score"],
        "comment": result.get("reasoning", ""),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def _format_components(components: list) -> str:
    lines = []
    for c in components:
        lines.append(f"Component: {c.get('component', 'unnamed')}")
        lines.append(f"  Confidence: {c.get('confidence', '?')}")
        lines.append(f"  Files: {c.get('files_changed', [])}")
        lines.append(f"  Impact: {c.get('impact_summary', '')}")
        lines.append(f"  Risks: {c.get('risks', [])}")
        ut = c.get("unit_tests", [])
        if ut:
            lines.append(f"  Unit tests: {len(ut)} specs")
        it = c.get("integration_tests", [])
        if it:
            lines.append(f"  Integration tests: {len(it)} specs")
        lines.append("")
    return "\n".join(lines)
