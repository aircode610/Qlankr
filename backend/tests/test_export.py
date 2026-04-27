"""Export helpers — no LLM, no network."""

from models import AffectedComponent, BugReport, E2ETestStep, ResearchFindings
from export import export_markdown, export_pdf


def _sample_report() -> BugReport:
    return BugReport(
        title="Test crash",
        severity="major",
        category="gameplay",
        environment="Linux",
        reproduction_steps=[
            E2ETestStep(step=1, action="Log in", expected="User sees home screen"),
        ],
        expected_behavior="No crash",
        actual_behavior="Crash on fast travel",
        root_cause_analysis="Hypothesis A; Hypothesis B",
        affected_components=[
            AffectedComponent(
                component="PlayerController",
                files_changed=["a.lua"],
            )
        ],
        evidence=ResearchFindings(
            evidence_summary="Logs show nil ref.",
            log_entries=[],
        ),
        recommendations=["Add null check"],
        confidence="medium",
    )


def test_export_markdown_includes_sections():
    md, fn = export_markdown(_sample_report())
    assert "Test crash" in md
    assert "Reproduction" in md
    assert "Root cause" in md
    assert "Evidence" in md
    assert "Recommendations" in md
    assert fn.endswith(".md")
    assert "bug-report-" in fn


def test_export_pdf_returns_bytes():
    b, fn = export_pdf(_sample_report())
    assert fn.endswith(".pdf")
    assert isinstance(b, (bytes, bytearray))
    assert b.startswith(b"%PDF")
