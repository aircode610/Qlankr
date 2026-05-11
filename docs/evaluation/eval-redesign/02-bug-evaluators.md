# Bug Evaluator Improvements

Three deterministic fixes. No LLM cost. All run on every bug eval example.

---

## Fix 1 — `triage_accuracy`: Add Severity Match Against Reference

### Current

Checks `severity in {"critical", "high", "medium", "low"}` — valid enum only.
Does not verify severity matches ground truth from `reference_outputs`.

### Change

Add a 5th check when `reference_outputs` is provided:

```python
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

score = len([d for d in details if d["passed"]]) / total_checks
```

**Why this matters:** An agent that classifies every bug as `high` passes the enum check but fails on examples where ground truth is `medium` or `critical`. This check catches that.

---

## Fix 2 — `keyword_recall`: New Deterministic Evaluator

`expected_root_cause_keywords` exists in reference outputs but is only used by the LLM judge `root_cause_quality`. Adding a deterministic companion catches cases where the judge gives 0.7 ("sounds plausible") but the agent never actually named the specific function or invariant.

```python
def keyword_recall(outputs: dict, reference_outputs: dict = None) -> dict:
    """Deterministic: fraction of expected root cause keywords present in root_cause text."""
    root_cause = outputs.get("bug_report", {}).get("root_cause", "").lower()
    keywords = (reference_outputs or {}).get("expected_root_cause_keywords", [])

    if not keywords:
        return {"key": "keyword_recall", "score": 1.0, "comment": "no reference keywords"}

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
```

**Note:** Matching is substring (`kw.lower() in root_cause`), not exact word boundary, to handle plurals and partial names. If false positive rate is high in practice, switch to word-boundary regex.

---

## Fix 3 — `affected_file_recall`: New Deterministic Evaluator

`expected_affected_files` exists in reference outputs but is completely unused today. Adds a ground-truth file coverage check.

```python
def affected_file_recall(outputs: dict, reference_outputs: dict = None) -> dict:
    """Deterministic: fraction of expected files mentioned anywhere in the agent output."""
    expected = (reference_outputs or {}).get("expected_affected_files", [])
    if not expected:
        return {"key": "affected_file_recall", "score": 1.0, "comment": "no reference files"}

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


def _normalize_path(path: str) -> str:
    """Strip leading directory components for fuzzy matching.
    'src/timetable_gui.cpp' → 'timetable_gui.cpp'
    """
    return path.strip().lower().split("/")[-1]
```

**Why basename normalization:** The agent might output `timetable_gui.cpp` while the reference has `src/timetable_gui.cpp`. Stripping to basename avoids false negatives from path prefix differences.

---

## Updated Evaluator Summary

| Evaluator | Type | Stage | New/Changed |
|---|---|---|---|
| `triage_accuracy` | deterministic | triage | updated (+severity match) |
| `mechanics_grounding` | deterministic | mechanics | unchanged |
| `reproduction_executability` | deterministic | reproduction | unchanged |
| `keyword_recall` | deterministic | report | **new** |
| `affected_file_recall` | deterministic | report | **new** |
| `bug_pipeline_health` | deterministic | pipeline | unchanged |
| `research_coverage` | deterministic | research | unchanged |
| `report_completeness` | deterministic | report | unchanged |
| `report_actionability` | deterministic | report | unchanged |
| `evidence_quality` | deterministic | report | unchanged |
| `tool_efficiency` | deterministic | pipeline | unchanged |
| `graceful_degradation` | deterministic | pipeline | unchanged |
| `root_cause_quality` | LLM judge | report | unchanged |
| `report_coherence` | LLM judge | report | unchanged |
| `reproduction_step_clarity` | LLM judge | reproduction | unchanged |
