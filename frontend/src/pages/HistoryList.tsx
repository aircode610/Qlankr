import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { BugReportRow, listBugReports, listPrAnalyses, PrAnalysisRow } from "../services/api";

const STATUS_STYLES: Record<string, string> = {
  completed: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400",
  running:   "border-blue-500/25 bg-blue-500/10 text-blue-400",
  failed:    "border-red-500/25 bg-red-500/10 text-red-400",
  cancelled: "border-border-default bg-elevated text-text-muted",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${STATUS_STYLES[status] ?? STATUS_STYLES.cancelled}`}>
      {status}
    </span>
  );
}

export function HistoryList() {
  const { id } = useParams<{ id: string }>();
  const [pr, setPr] = useState<PrAnalysisRow[]>([]);
  const [bugs, setBugs] = useState<BugReportRow[]>([]);

  useEffect(() => {
    if (!id) return;
    listPrAnalyses(id).then(setPr).catch(console.error);
    listBugReports(id).then(setBugs).catch(console.error);
  }, [id]);

  return (
    <div className="mx-auto max-w-3xl space-y-8 px-6 py-8">
      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">PR Analyses</h2>
        <ul className="space-y-1.5">
          {pr.map((row) => (
            <li key={row.id}>
              <Link
                to={`/projects/${id}/history/pr/${row.id}`}
                className="flex items-center gap-3 rounded-lg border border-border-subtle bg-elevated px-4 py-3 transition-colors hover:border-border-default hover:bg-hover"
              >
                <span className="min-w-0 flex-1 truncate text-sm text-text-primary">
                  {row.pr_title ?? row.pr_url}
                </span>
                <StatusBadge status={row.status} />
                <span className="shrink-0 text-xs text-text-muted">{row.created_at.slice(0, 10)}</span>
              </Link>
            </li>
          ))}
          {pr.length === 0 && (
            <li className="py-6 text-center text-sm text-text-muted">No PR analyses yet.</li>
          )}
        </ul>
      </section>

      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">Bug Reports</h2>
        <ul className="space-y-1.5">
          {bugs.map((row) => (
            <li key={row.id}>
              <Link
                to={`/projects/${id}/history/bug/${row.id}`}
                className="flex items-center gap-3 rounded-lg border border-border-subtle bg-elevated px-4 py-3 transition-colors hover:border-border-default hover:bg-hover"
              >
                <span className="min-w-0 flex-1 truncate text-sm text-text-primary">
                  {row.bug_description.slice(0, 80)}
                </span>
                <StatusBadge status={row.status} />
                <span className="shrink-0 text-xs text-text-muted">{row.created_at.slice(0, 10)}</span>
              </Link>
            </li>
          ))}
          {bugs.length === 0 && (
            <li className="py-6 text-center text-sm text-text-muted">No bug reports yet.</li>
          )}
        </ul>
      </section>
    </div>
  );
}
