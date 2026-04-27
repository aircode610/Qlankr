"""
Markdown and PDF export for bug reports. Markdown is canonical; PDF is derived from it.
"""

import re
from typing import Any

from fpdf import FPDF

from models import BugReport


def _slugify(title: str, max_len: int = 80) -> str:
    s = re.sub(r"[^\w\s-]", "", title)[:max_len]
    s = re.sub(r"[-\s]+", "-", s, flags=re.UNICODE)
    return (s or "bug").strip("-")


def _comp_line(c: Any) -> str:
    if hasattr(c, "model_dump"):
        d = c.model_dump()
    else:
        d = c if isinstance(c, dict) else {}
    name = d.get("component", "Unknown")
    im = d.get("impact_summary", "")
    return f"- **{name}** — {im}"


def export_markdown(report: BugReport) -> tuple[str, str]:
    """Return (markdown_content, filename)."""
    lines: list[str] = []
    lines.append(f"# {report.title}\n")
    lines.append(
        f"**Severity:** {report.severity}  \n"
        f"**Category:** {report.category}  \n"
        f"**Environment:** {report.environment}  \n"
        f"**Confidence:** {report.confidence}\n"
    )
    if report.jira_url:
        lines.append(f"**Jira:** {report.jira_url}\n")

    lines.append("\n## Reproduction steps\n")
    for s in report.reproduction_steps:
        lines.append(f"{s.step}. {s.action}  \n   *Expected:* {s.expected}\n")

    lines.append("\n## Expected vs actual\n")
    lines.append(f"**Expected:** {report.expected_behavior}\n\n")
    lines.append(f"**Actual:** {report.actual_behavior}\n")

    lines.append("\n## Root cause analysis\n")
    lines.append(report.root_cause_analysis + "\n")

    lines.append("\n## Affected components\n")
    for c in report.affected_components:
        lines.append(_comp_line(c) + "\n")

    ev = report.evidence
    lines.append("\n## Evidence\n")
    if ev.evidence_summary:
        lines.append(ev.evidence_summary + "\n\n")
    if ev.log_entries:
        lines.append("### Log entries\n")
        for e in ev.log_entries:
            lines.append(f"- `{e.timestamp}` [{e.level}] {e.message} (source: {e.source})\n")
    if ev.doc_references:
        lines.append("\n### Documentation\n")
        for d in ev.doc_references:
            lines.append(f"- [{d.title}]({d.url}) — {d.snippet[:200]}\n")
    if ev.related_issues:
        lines.append("\n### Related issues\n")
        for i in ev.related_issues:
            lines.append(f"- [{i.key}]({i.url}) {i.summary} ({i.status})\n")
    if ev.db_state:
        lines.append("\n### DB state (structured)\n")
        lines.append("```json\n" + str(ev.db_state) + "\n```\n")
    if ev.admin_notes:
        lines.append("\n### Notes\n")
        for n in ev.admin_notes:
            lines.append(f"- {n}\n")

    lines.append("\n## Recommendations\n")
    for r in report.recommendations:
        lines.append(f"- {r}\n")

    content = "\n".join(lines).strip() + "\n"
    fn = f"bug-report-{_slugify(report.title)}.md"
    return content, fn


class _ReportPDF(FPDF):
    def __init__(self) -> None:
        super().__init__()
        self.set_margins(10, 10, 10)
        self.set_auto_page_break(auto=True, margin=15)
        self.add_page()
        self.set_font("helvetica", size=10)

    def write_text_block(self, text: str) -> None:
        w = self.w - self.l_margin - self.r_margin
        for line in text.splitlines():
            safe = line.encode("latin-1", errors="replace").decode("latin-1")
            self.set_x(self.l_margin)
            self.multi_cell(w, 5, safe or " ", new_x="LMARGIN", new_y="NEXT")


def export_pdf(report: BugReport) -> tuple[bytes, str]:
    """Return (pdf_bytes, filename). Renders from markdown for consistent structure."""
    md, _ = export_markdown(report)
    # Strip markdown # headers to plain line prefixes for FPDF
    simple = re.sub(r"^#+\s*", "", md, flags=re.MULTILINE)
    pdf = _ReportPDF()
    pdf.write_text_block(simple)
    return pdf.output(), f"bug-report-{_slugify(report.title)}.pdf"
