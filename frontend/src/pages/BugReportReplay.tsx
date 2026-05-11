import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { BugReportView } from "../components/BugReportView";
import { getBugReport, type BugReportRow } from "../services/api";
import type { BugReport } from "../services/types";

type Detail = BugReportRow & Record<string, unknown>;

function extractReport(final_report: unknown): BugReport | null {
  if (!final_report || typeof final_report !== "object") return null;
  const wrapper = final_report as { report?: unknown };
  const report = wrapper.report ?? final_report;
  if (!report || typeof report !== "object") return null;
  const r = report as Partial<BugReport>;
  if (typeof r.title !== "string" || !Array.isArray(r.reproduction_steps)) return null;
  return report as BugReport;
}

export function BugReportReplay() {
  const { id: projectId, runId } = useParams<{ id: string; runId: string }>();
  const [detail, setDetail] = useState<Detail | null>(null);

  useEffect(() => {
    if (!runId) return;
    getBugReport(runId).then(setDetail).catch(console.error);
  }, [runId]);

  if (!detail) return <div className="p-4 text-sm text-gray-500">Loading…</div>;

  const report = extractReport(detail.final_report);

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b border-border-subtle px-4 py-2">
        <Link to={`/projects/${projectId}/history`} className="text-sm underline">← History</Link>
      </div>
      {report ? (
        <div className="min-h-0 flex-1">
          <BugReportView report={report} sessionId={detail.id} />
        </div>
      ) : (
        <div className="p-4 text-sm text-gray-500">
          No final report available for this run.
        </div>
      )}
    </div>
  );
}
