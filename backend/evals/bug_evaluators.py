"""
Evaluators for Qlankr Sprint 3 bug reproduction pipeline.

Each evaluator returns:
  {
    "key":     metric name,
    "score":   0.0–1.0,
    "comment": summary line,
    "details": list of {"check", "passed", "value"} — one entry per check
  }

Deterministic evaluators (no LLM cost, run always):
  Person 1 — stages 1-3: triage_accuracy, mechanics_grounding, reproduction_executability
  Person 2 — stages 4-5: bug_pipeline_health, research_coverage, report_completeness,
                          report_actionability, evidence_quality, tool_efficiency,
                          graceful_degradation

LLM-as-judge evaluators (async, require ANTHROPIC_API_KEY):
  root_cause_quality       — does the report root cause match expected keywords?
  report_coherence         — is the report specific, internally consistent, grounded?
  reproduction_step_clarity — are the steps genuinely executable by a developer?
"""

import json
import os
import re

from langchain_anthropic import ChatAnthropic

# ═══════════════════════════════════════════════════════════════════════════════
# Person 1 evaluators — stages 1-3
# ═══════════════════════════════════════════════════════════════════════════════

_VALID_SEVERITIES = {"critical", "high", "medium", "low"}
_VALID_CATEGORIES = {"crash", "gameplay", "networking", "UI", "data", "performance", "other"}


def triage_accuracy(outputs: dict, reference_outputs: dict = None) -> dict:
    """
    Checks structural completeness of the triage stage output.
    Score = fraction of checks passing (4 checks total).
    """
    triage = outputs.get("triage", {})
    if not triage:
        return {"key": "triage_accuracy", "score": 0.0, "comment": "triage dict missing", "details": []}

    bug_category = triage.get("bug_category", "")
    severity = triage.get("severity", "")
    keywords = triage.get("keywords", [])
    hypotheses = triage.get("initial_hypotheses", [])

    details = [
        {
            "check": "bug_category non-empty",
            "passed": bool(bug_category),
            "value": bug_category or "(empty)",
        },
        {
            "check": f"severity in {sorted(_VALID_SEVERITIES)}",
            "passed": severity in _VALID_SEVERITIES,
            "value": severity or "(empty)",
        },
        {
            "check": "keywords >= 1",
            "passed": len(keywords) >= 1,
            "value": f"{len(keywords)} keywords: {keywords}",
        },
        {
            "check": "initial_hypotheses >= 1",
            "passed": len(hypotheses) >= 1,
            "value": f"{len(hypotheses)} hypothesis/es",
        },
    ]

    # 5th check: severity matches expected (only when reference provides it)
    expected_severity = (reference_outputs or {}).get("expected_severity", "")
    if expected_severity:
        details.append({
            "check": f"severity matches expected ({expected_severity})",
            "passed": severity == expected_severity,
            "value": f"got '{severity}', expected '{expected_severity}'",
        })
        total_checks = 5
    else:
        total_checks = 4  # backwards compatible when no reference

    passed = [d for d in details if d["passed"]]
    failed = [d for d in details if not d["passed"]]
    score = len(passed) / total_checks
    comment = "all checks passed" if not failed else f"failed: {', '.join(d['check'] for d in failed)}"
    return {"key": "triage_accuracy", "score": score, "comment": comment, "details": details}


def mechanics_grounding(outputs: dict) -> dict:
    """
    Checks that mechanics findings are grounded in evidence.
    Score = fraction of hypotheses that have a non-empty evidence field.
    """
    mechanics = outputs.get("mechanics", {})
    if not mechanics:
        return {"key": "mechanics_grounding", "score": 0.0, "comment": "mechanics dict missing", "details": []}

    code_paths = mechanics.get("code_paths", [])
    hypotheses = mechanics.get("root_cause_hypotheses", [])

    details = [
        {
            "check": "code_paths >= 1",
            "passed": len(code_paths) >= 1,
            "value": f"{len(code_paths)} path(s)",
        },
        {
            "check": "root_cause_hypotheses >= 1",
            "passed": len(hypotheses) >= 1,
            "value": f"{len(hypotheses)} hypothesis/es",
        },
    ]

    for i, h in enumerate(hypotheses):
        evidence = h.get("evidence", "").strip()
        details.append({
            "check": f"hypothesis[{i}] has evidence",
            "passed": bool(evidence),
            "value": (evidence[:80] + "…") if len(evidence) > 80 else (evidence or "(empty)"),
        })

    passing = [d for d in details if d["passed"]]
    failing = [d for d in details if not d["passed"]]

    if not code_paths:
        score = 0.0
    elif not hypotheses:
        score = 0.0
    else:
        grounded = sum(1 for h in hypotheses if h.get("evidence", "").strip())
        score = grounded / len(hypotheses)

    comment = (
        "all checks passed" if not failing
        else f"failed: {', '.join(d['check'] for d in failing)}"
    )
    return {"key": "mechanics_grounding", "score": score, "comment": comment, "details": details}


def reproduction_executability(outputs: dict) -> dict:
    """
    Checks that reproduction steps are complete and actionable.
    Score = fraction of steps where both action and expected_result are non-empty.
    Requires at least 3 steps.
    """
    plan = outputs.get("reproduction_plan", {})
    if not plan:
        return {"key": "reproduction_executability", "score": 0.0, "comment": "reproduction_plan missing", "details": []}

    steps = plan.get("steps", [])
    prerequisites = plan.get("prerequisites", [])

    details = [
        {
            "check": "steps >= 3",
            "passed": len(steps) >= 3,
            "value": f"{len(steps)} step(s)",
        },
        {
            "check": "prerequisites present",
            "passed": len(prerequisites) >= 1,
            "value": f"{len(prerequisites)} prerequisite(s)",
        },
    ]

    for i, s in enumerate(steps):
        action = s.get("action", "").strip()
        expected = s.get("expected_result", "").strip()
        complete = bool(action) and bool(expected)
        details.append({
            "check": f"step[{i+1}] has action + expected_result",
            "passed": complete,
            "value": (
                f"action: {action[:50]}…" if len(action) > 50 else f"action: {action or '(empty)'}"
            ) + (
                f" | expected: {expected[:50]}…" if len(expected) > 50 else f" | expected: {expected or '(empty)'}"
            ),
        })

    failing = [d for d in details if not d["passed"]]

    if len(steps) < 3:
        score = 0.0
    else:
        complete_steps = sum(
            1 for s in steps
            if s.get("action", "").strip() and s.get("expected_result", "").strip()
        )
        score = complete_steps / len(steps)

    comment = (
        "all checks passed" if not failing
        else f"failed: {', '.join(d['check'] for d in failing)}"
    )
    return {"key": "reproduction_executability", "score": score, "comment": comment, "details": details}


# ═══════════════════════════════════════════════════════════════════════════════
# Person 2 evaluators — stages 4-5 + pipeline-level
# ═══════════════════════════════════════════════════════════════════════════════

_TOTAL_BUDGET = 60  # 8 + 15 + 12 + 20 + 5
_VALID_CONFIDENCES = {"high", "medium", "low"}
_MIN_RECOMMENDATION_LENGTH = 30  # chars — filters out "fix the bug" style non-answers


def bug_pipeline_health(outputs: dict) -> dict:
    """
    Checks that every stage produced a non-empty output dict.
    Score = fraction of stages that completed (5 stages total).
    """
    stages = {
        "triage": outputs.get("triage", {}),
        "mechanics": outputs.get("mechanics", {}),
        "reproduction_plan": outputs.get("reproduction_plan", {}),
        "research_findings": outputs.get("research_findings", {}),
        "bug_report": outputs.get("bug_report", {}),
    }

    details = [
        {
            "check": f"{stage} output non-empty",
            "passed": bool(data),
            "value": "present" if data else "missing",
        }
        for stage, data in stages.items()
    ]

    passed = [d for d in details if d["passed"]]
    failed = [d for d in details if not d["passed"]]
    score = len(passed) / len(details)
    comment = "all stages completed" if not failed else f"missing: {', '.join(d['check'].split()[0] for d in failed)}"
    return {"key": "bug_pipeline_health", "score": score, "comment": comment, "details": details}


def research_coverage(outputs: dict) -> dict:
    """
    Checks how many sources returned useful data out of those queried.
    Score = sources_with_results / sources_queried.
    Zero sources queried scores 0.0 (research did not run).
    """
    findings = outputs.get("research_findings", {})
    if not findings:
        return {"key": "research_coverage", "score": 0.0, "comment": "research_findings missing", "details": []}

    queried = findings.get("sources_queried", [])
    with_results = findings.get("sources_with_results", [])

    details = [
        {
            "check": "at least one source queried",
            "passed": len(queried) >= 1,
            "value": f"{len(queried)} queried: {queried}",
        },
        {
            "check": "at least one source returned results",
            "passed": len(with_results) >= 1,
            "value": f"{len(with_results)} with results: {with_results}",
        },
    ]

    if not queried:
        score = 0.0
    else:
        score = len(with_results) / len(queried)

    failed = [d for d in details if not d["passed"]]
    comment = (
        f"{len(with_results)}/{len(queried)} sources returned data"
        if queried
        else "no sources were queried"
    )
    return {"key": "research_coverage", "score": score, "comment": comment, "details": details}


def report_completeness(outputs: dict) -> dict:
    """
    Checks that every required field in bug_report is non-empty.
    Score = fraction of required fields present.
    """
    report = outputs.get("bug_report", {})
    if not report:
        return {"key": "report_completeness", "score": 0.0, "comment": "bug_report missing", "details": []}

    required_fields = [
        ("title", lambda v: bool(v)),
        ("severity", lambda v: v in _VALID_SEVERITIES),
        ("root_cause", lambda v: bool(v)),
        ("reproduction_steps", lambda v: len(v) >= 3),
        ("affected_components", lambda v: len(v) >= 1),
        ("recommendations", lambda v: len(v) >= 1),
        ("confidence", lambda v: v in _VALID_CONFIDENCES),
    ]

    details = []
    for field, check in required_fields:
        value = report.get(field)
        passed = check(value) if value is not None else False
        display = str(value)[:80] if value else "(missing)"
        details.append({
            "check": f"{field} valid",
            "passed": passed,
            "value": display,
        })

    passed_count = sum(1 for d in details if d["passed"])
    score = passed_count / len(details)
    failed = [d for d in details if not d["passed"]]
    comment = "all fields present" if not failed else f"failed: {', '.join(d['check'] for d in failed)}"
    return {"key": "report_completeness", "score": score, "comment": comment, "details": details}


def report_actionability(outputs: dict) -> dict:
    """
    Checks that recommendations are specific and actionable (not generic).
    Score = fraction of recommendations exceeding minimum length threshold.
    Requires at least 2 recommendations.
    """
    report = outputs.get("bug_report", {})
    if not report:
        return {"key": "report_actionability", "score": 0.0, "comment": "bug_report missing", "details": []}

    recommendations = report.get("recommendations", [])

    details = [
        {
            "check": "recommendations >= 2",
            "passed": len(recommendations) >= 2,
            "value": f"{len(recommendations)} recommendation(s)",
        }
    ]

    for i, rec in enumerate(recommendations):
        rec_str = str(rec).strip()
        passed = len(rec_str) >= _MIN_RECOMMENDATION_LENGTH
        details.append({
            "check": f"recommendation[{i}] sufficiently specific (>= {_MIN_RECOMMENDATION_LENGTH} chars)",
            "passed": passed,
            "value": (rec_str[:80] + "…") if len(rec_str) > 80 else rec_str,
        })

    if len(recommendations) < 2:
        score = 0.0
    else:
        actionable = sum(1 for r in recommendations if len(str(r).strip()) >= _MIN_RECOMMENDATION_LENGTH)
        score = actionable / len(recommendations)

    failed = [d for d in details if not d["passed"]]
    comment = "all recommendations actionable" if not failed else f"failed: {', '.join(d['check'] for d in failed)}"
    return {"key": "report_actionability", "score": score, "comment": comment, "details": details}


def evidence_quality(outputs: dict) -> dict:
    """
    Checks whether evidence was gathered across categories.
    External categories (from bug_report.evidence): log_entries, doc_references,
    related_issues, network_traces.
    Internal category (from research_findings): code_graph_hits.
    Score = fraction of all 5 categories that contain at least one entry.
    """
    report = outputs.get("bug_report", {})
    if not report:
        return {"key": "evidence_quality", "score": 0.0, "comment": "bug_report missing", "details": []}

    evidence = report.get("evidence", {})
    research = outputs.get("research_findings", {})

    external_categories = ["log_entries", "doc_references", "related_issues", "network_traces"]
    details = [
        {
            "check": f"{cat} non-empty",
            "passed": len(evidence.get(cat, [])) >= 1,
            "value": f"{len(evidence.get(cat, []))} item(s)",
        }
        for cat in external_categories
    ]

    # Code graph hits live in research_findings, not bug_report.evidence
    code_graph_hits = research.get("code_graph_hits", [])
    details.append({
        "check": "code_graph_hits non-empty",
        "passed": len(code_graph_hits) >= 1,
        "value": f"{len(code_graph_hits)} hit(s)",
    })

    filled = [d for d in details if d["passed"]]
    score = len(filled) / len(details)

    comment = (
        f"{len(filled)}/{len(details)} evidence categories populated"
        if filled
        else "no evidence found in any category"
    )
    return {"key": "evidence_quality", "score": score, "comment": comment, "details": details}


def tool_efficiency(outputs: dict) -> dict:
    """
    Checks whether the pipeline stayed within the combined tool call budget.
    Combined budget: 8 + 15 + 12 + 20 + 5 = 60 calls.
    Score = 1.0 if within budget, scales linearly to 0.0 at 2x budget (120 calls).
    """
    used = outputs.get("tool_calls_used", 0)

    within_budget = used <= _TOTAL_BUDGET
    details = [
        {
            "check": f"total tool calls <= {_TOTAL_BUDGET}",
            "passed": within_budget,
            "value": f"{used} calls used",
        }
    ]

    if used <= _TOTAL_BUDGET:
        score = 1.0
    elif used >= _TOTAL_BUDGET * 2:
        score = 0.0
    else:
        score = 1.0 - (used - _TOTAL_BUDGET) / _TOTAL_BUDGET

    comment = (
        f"within budget ({used}/{_TOTAL_BUDGET})"
        if within_budget
        else f"over budget ({used}/{_TOTAL_BUDGET})"
    )
    return {"key": "tool_efficiency", "score": round(score, 2), "comment": comment, "details": details}


def graceful_degradation(outputs: dict) -> dict:
    """
    Checks that the pipeline produces a complete report even when external
    sources return no data (zero tools configured or all sources empty).
    Score = 1.0 if bug_report is non-empty regardless of research results.
    """
    report = outputs.get("bug_report", {})
    findings = outputs.get("research_findings", {})

    sources_with_results = findings.get("sources_with_results", [])
    report_present = bool(report)
    research_empty = len(sources_with_results) == 0

    details = [
        {
            "check": "bug_report produced",
            "passed": report_present,
            "value": "present" if report_present else "missing",
        },
        {
            "check": "report present even with no external evidence",
            "passed": report_present and research_empty,
            "value": (
                "report generated with zero external sources"
                if report_present and research_empty
                else "research had results — degradation not tested"
                if report_present
                else "no report generated"
            ),
        },
    ]

    if not report_present:
        score = 0.0
        comment = "pipeline failed to produce a report"
    elif research_empty:
        score = 1.0
        comment = "report produced with zero external evidence — graceful degradation confirmed"
    else:
        score = 0.5
        comment = "report produced but external sources had results — degradation not fully tested"

    return {"key": "graceful_degradation", "score": score, "comment": comment, "details": details}


def keyword_recall(outputs: dict, reference_outputs: dict = None) -> dict:
    """Deterministic: fraction of expected root cause keywords present in root_cause text."""
    root_cause = outputs.get("bug_report", {}).get("root_cause", "").lower()
    keywords = (reference_outputs or {}).get("expected_root_cause_keywords", [])

    if not keywords:
        return {"key": "keyword_recall", "score": 1.0, "comment": "no reference keywords", "details": []}

    details = []
    for kw in keywords:
        hit = kw.lower() in root_cause
        details.append({
            "check": f"keyword '{kw}' present in root_cause",
            "passed": hit,
            "value": "found" if hit else "missing",
        })

    hits = [d for d in details if d["passed"]]
    score = len(hits) / len(details)
    comment = (
        f"{len(hits)}/{len(details)} keywords found"
        if hits else "no expected keywords found in root_cause"
    )
    return {"key": "keyword_recall", "score": score, "comment": comment, "details": details}


def _normalize_path(path: str) -> str:
    """Strip leading directory components for fuzzy matching.
    'src/timetable_gui.cpp' → 'timetable_gui.cpp'
    """
    return path.strip().lower().split("/")[-1]


def affected_file_recall(outputs: dict, reference_outputs: dict = None) -> dict:
    """Deterministic: fraction of expected files mentioned anywhere in the agent output."""
    expected = (reference_outputs or {}).get("expected_affected_files", [])
    if not expected:
        return {"key": "affected_file_recall", "score": 1.0, "comment": "no reference files", "details": []}

    # Collect files from mechanics.code_paths and bug_report.affected_components
    found_files: set[str] = set()

    mechanics = outputs.get("mechanics", {})
    for path in mechanics.get("code_paths", []):
        f = path.get("file", "") if isinstance(path, dict) else str(path)
        found_files.add(_normalize_path(f))

    report = outputs.get("bug_report", {})
    for comp in report.get("affected_components", []):
        if isinstance(comp, dict):
            for f in comp.get("files", []):
                found_files.add(_normalize_path(f))
        else:
            found_files.add(_normalize_path(str(comp)))

    details = []
    for expected_file in expected:
        norm = _normalize_path(expected_file)
        hit = any(norm in found or found.endswith(norm) for found in found_files)
        details.append({
            "check": f"'{expected_file}' in agent output",
            "passed": hit,
            "value": "found" if hit else "missing",
        })

    hits = [d for d in details if d["passed"]]
    score = len(hits) / len(details)
    comment = f"{len(hits)}/{len(details)} expected files found"
    return {"key": "affected_file_recall", "score": score, "comment": comment, "details": details}


# ═══════════════════════════════════════════════════════════════════════════════
# LLM-AS-JUDGE EVALUATORS
# ═══════════════════════════════════════════════════════════════════════════════

_judge = ChatAnthropic(
    model="claude-sonnet-4-6",
    temperature=0,
    max_tokens=512,
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
)


def _parse_judge_response(content: str) -> dict:
    """Extract JSON score block from judge response.

    Tries three strategies in order:
      1. Direct parse (model returned bare JSON).
      2. Extract from a fenced code block (```json ... ```).
      3. Regex scan for the first {...} object in the text.
    Falls back to score=0.5 only if all three fail.
    """
    text = content.strip()

    # Strategy 1: bare JSON
    try:
        return json.loads(text)
    except Exception:
        pass

    # Strategy 2: fenced code block
    try:
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence:
            return json.loads(fence.group(1))
    except Exception:
        pass

    # Strategy 3: first JSON object anywhere in the text
    try:
        obj = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if obj:
            return json.loads(obj.group(0))
    except Exception:
        pass

    return {"score": 0.5, "reasoning": "Could not parse judge response"}


async def root_cause_quality(inputs: dict, outputs: dict, reference_outputs: dict = None) -> dict:
    """LLM judge: does the final report's root cause capture the real underlying cause?

    When reference_outputs contains expected_root_cause_keywords, the judge checks
    semantic alignment with those keywords. Without a reference it evaluates whether
    the root cause is specific, mechanistic, and non-generic.
    """
    report = outputs.get("bug_report", {})
    root_cause = report.get("root_cause", "")
    if not root_cause:
        return {"key": "root_cause_quality", "score": 0.0, "comment": "root_cause field missing"}

    description = inputs.get("description", "")
    keywords = (reference_outputs or {}).get("expected_root_cause_keywords", [])

    if keywords:
        reference_section = f"""
Expected root cause keywords (from human review — any subset counts):
{json.dumps(keywords, indent=2)}

Score based on semantic alignment:
- 1.0 = agent's root cause covers the same underlying mechanism as the keywords
- 0.5 = partially correct — hits some keywords but misses key steps
- 0.2 = describes symptoms rather than the mechanism
- 0.0 = wrong component, wrong mechanism, or hallucinated
"""
    else:
        reference_section = """
No golden reference is available. Score based on quality alone:
- 1.0 = specific, mechanistic, names exact code paths or invariants violated
- 0.8 = mostly specific, minor vagueness
- 0.4 = describes symptoms or general area without identifying the true cause
- 0.0 = generic ("null pointer", "logic error") or contradicted by the description
"""

    prompt = f"""You are a QA engineering expert evaluating an AI-generated bug report.

Bug description submitted by user:
{description}

Agent's root cause analysis:
{root_cause}
{reference_section}
Return ONLY a JSON object: {{"score": <float 0.0-1.0>, "reasoning": "<1-2 sentences>"}}"""

    response = await _judge.ainvoke([{"role": "user", "content": prompt}])
    result = _parse_judge_response(response.content)
    return {
        "key": "root_cause_quality",
        "score": result.get("score", 0.5),
        "comment": result.get("reasoning", ""),
    }


async def report_coherence(inputs: dict, outputs: dict) -> dict:
    """LLM judge: is the final bug report internally consistent, specific, and well-grounded?

    No reference output needed — scores the logical quality of the report given the
    original bug description. Penalises generic advice, contradictions, and off-topic
    components.
    """
    report = outputs.get("bug_report", {})
    if not report:
        return {"key": "report_coherence", "score": 0.0, "comment": "bug_report missing"}

    description = inputs.get("description", "")

    report_summary = {
        "title": report.get("title", ""),
        "severity": report.get("severity", ""),
        "root_cause": report.get("root_cause", ""),
        "affected_components": [
            c if isinstance(c, str) else c.get("component", str(c))
            for c in report.get("affected_components", [])
        ],
        "recommendations": report.get("recommendations", []),
        "confidence": report.get("confidence", ""),
    }

    prompt = f"""You are a QA engineering expert reviewing an AI-generated bug report for internal consistency and quality.

Original bug description:
{description}

Generated bug report (key fields):
{json.dumps(report_summary, indent=2, default=str)}

Evaluate:
1. Internal consistency — do severity, root cause, affected components, and recommendations all point to the same underlying problem?
2. Specificity — does the report name real code-level things (files, classes, functions, invariants), or is it vague?
3. Groundedness — are the recommendations actionable for this specific bug, not generic advice?
4. Scope — are affected components actually relevant to the reported symptoms?

Score 0.0 to 1.0:
- 1.0 = fully coherent, specific, well-scoped
- 0.7 = mostly coherent with minor inconsistencies or vague sections
- 0.3 = some contradictions or significant vagueness
- 0.0 = incoherent, contradictory, or entirely generic

Return ONLY: {{"score": <float 0.0-1.0>, "reasoning": "<1-2 sentences>"}}"""

    response = await _judge.ainvoke([{"role": "user", "content": prompt}])
    result = _parse_judge_response(response.content)
    return {
        "key": "report_coherence",
        "score": result.get("score", 0.5),
        "comment": result.get("reasoning", ""),
    }


async def reproduction_step_clarity(inputs: dict, outputs: dict) -> dict:
    """LLM judge: are the reproduction steps genuinely executable by a developer?

    Deterministic checks count steps and verify field presence, but cannot tell
    whether the actions make sense or are specific enough to follow. This judge
    fills that gap.
    """
    report = outputs.get("bug_report", {})
    if not report:
        return {"key": "reproduction_step_clarity", "score": 0.0, "comment": "bug_report missing"}

    steps = report.get("reproduction_steps", [])
    if not steps:
        return {"key": "reproduction_step_clarity", "score": 0.0, "comment": "reproduction_steps empty"}

    description = inputs.get("description", "")
    environment = inputs.get("environment", "unspecified")

    steps_display = []
    for s in steps:
        if isinstance(s, dict):
            steps_display.append({
                "step": s.get("step", s.get("step_number", "?")),
                "action": s.get("action", ""),
                "expected": s.get("expected", s.get("expected_result", "")),
            })
        else:
            steps_display.append(str(s))

    prompt = f"""You are a QA engineer evaluating whether these reproduction steps are genuinely executable.

Bug description:
{description}

Environment: {environment}

Reproduction steps from the bug report:
{json.dumps(steps_display, indent=2, default=str)}

Evaluate:
1. Clarity — could a developer unfamiliar with the codebase follow each step?
2. Specificity — are actions concrete (specific menu names, settings, actions) or vague ("open the thing")?
3. Correctness — do the steps plausibly lead to the described symptom?
4. Completeness — are necessary prerequisites and expected outcomes stated?

Score 0.0 to 1.0:
- 1.0 = steps are clear, specific, correct, and immediately usable
- 0.8 = mostly followable but some steps need clarification
- 0.4 = steps are vague or partially incorrect — would require guesswork
- 0.0 = steps cannot be followed, are wrong, or are missing entirely

Return ONLY: {{"score": <float 0.0-1.0>, "reasoning": "<1-2 sentences>"}}"""

    response = await _judge.ainvoke([{"role": "user", "content": prompt}])
    result = _parse_judge_response(response.content)
    return {
        "key": "reproduction_step_clarity",
        "score": result.get("score", 0.5),
        "comment": result.get("reasoning", ""),
    }
