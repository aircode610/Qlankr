import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getPrAnalysis } from "../services/api";

type Detail = {
  id: string;
  pr_url: string;
  pr_title: string | null;
  status: string;
  gather_output: unknown;
  unit_output: unknown;
  integration_output: unknown;
  e2e_output: unknown;
  final_result: unknown;
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

export function PrAnalysisReplay() {
  const { id: projectId, runId } = useParams<{ id: string; runId: string }>();
  const [detail, setDetail] = useState<Detail | null>(null);

  useEffect(() => {
    if (!runId) return;
    getPrAnalysis(runId).then((d) => setDetail(d as Detail)).catch(console.error);
  }, [runId]);

  if (!detail) return <div className="p-4 text-sm text-gray-500">Loading…</div>;

  return (
    <div className="space-y-3">
      <Link to={`/projects/${projectId}/history`} className="text-sm underline">← History</Link>
      <h2 className="text-lg font-semibold">{detail.pr_title ?? detail.pr_url}</h2>
      <p className="text-xs text-gray-500">{detail.status} · {detail.created_at}</p>
      <Section title="Gather" value={detail.gather_output} />
      <Section title="Unit tests" value={detail.unit_output} />
      <Section title="Integration tests" value={detail.integration_output} />
      <Section title="E2E plan" value={detail.e2e_output} />
      <Section title="Final result" value={detail.final_result} />
    </div>
  );
}
