"""
Evaluators for Qlankr Sprint 3 bug reproduction pipeline.

Each evaluator returns:
  {
    "key":     metric name,
    "score":   0.0–1.0,
    "comment": summary line,
    "details": list of {"check", "passed", "value"} — one entry per check
  }

Person 1 owns: triage_accuracy, mechanics_grounding, reproduction_executability
"""

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

    passed = [d for d in details if d["passed"]]
    failed = [d for d in details if not d["passed"]]
    score = len(passed) / len(details)
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
