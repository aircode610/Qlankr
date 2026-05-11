import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getBugReport } from "../services/api";

type Detail = {
  id: string;
  bug_description: string;
  severity: string | null;
  status: string;
  triage_output: unknown;
  mechanics_output: unknown;
  reproduction_output: unknown;
  research_output: unknown;
  report_output: unknown;
  final_report: unknown;
  created_at: string;
  completed_at: string | null;
};

function Section({ title, value }: { title: string; value: unknown }) {
  if (value == null) return null;
  return (
    <section className="rounded border p-3">
      <h3 className="mb-2 font-medium">{title}</h3>
      <pre className="overflow-x-auto whitespace-pre-wrap text-xs">{JSON.stringify(value, null, 2)}</pre>
    </section>
  );
}

export function BugReportReplay() {
  const { id: projectId, runId } = useParams<{ id: string; runId: string }>();
  const [detail, setDetail] = useState<Detail | null>(null);

  useEffect(() => {
    if (!runId) return;
    getBugReport(runId).then((d) => setDetail(d as Detail)).catch(console.error);
  }, [runId]);

  if (!detail) return <div className="p-4 text-sm text-gray-500">Loading…</div>;

  return (
    <div className="space-y-3">
      <Link to={`/projects/${projectId}/history`} className="text-sm underline">← History</Link>
      <h2 className="text-lg font-semibold">Bug: {detail.bug_description.slice(0, 100)}</h2>
      <p className="text-xs text-gray-500">{detail.status} · {detail.severity ?? "no severity"} · {detail.created_at}</p>
      <Section title="Triage" value={detail.triage_output} />
      <Section title="Mechanics" value={detail.mechanics_output} />
      <Section title="Reproduction" value={detail.reproduction_output} />
      <Section title="Research" value={detail.research_output} />
      <Section title="Report" value={detail.report_output} />
      <Section title="Final report" value={detail.final_report} />
    </div>
  );
}
