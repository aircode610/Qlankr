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


# --- Person 2 evaluators below ---
