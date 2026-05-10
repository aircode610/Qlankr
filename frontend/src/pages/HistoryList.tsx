import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  BugReportRow,
  listBugReports,
  listPrAnalyses,
  PrAnalysisRow,
} from "../services/api";

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
    <div className="space-y-6">
      <section>
        <h2 className="mb-2 font-semibold">PR analyses</h2>
        <ul className="space-y-1">
          {pr.map((row) => (
            <li key={row.id} className="rounded border p-2 text-sm">
              <Link to={`/projects/${id}/history/pr/${row.id}`} className="underline">
                {row.pr_title ?? row.pr_url}
              </Link>
              <span className="ml-2 text-xs text-gray-500">{row.status} · {row.created_at}</span>
            </li>
          ))}
          {pr.length === 0 && <li className="text-sm text-gray-500">No PR analyses yet.</li>}
        </ul>
      </section>

      <section>
        <h2 className="mb-2 font-semibold">Bug reports</h2>
        <ul className="space-y-1">
          {bugs.map((row) => (
            <li key={row.id} className="rounded border p-2 text-sm">
              <Link to={`/projects/${id}/history/bug/${row.id}`} className="underline">
                {row.bug_description.slice(0, 80)}
              </Link>
              <span className="ml-2 text-xs text-gray-500">{row.status} · {row.created_at}</span>
            </li>
          ))}
          {bugs.length === 0 && <li className="text-sm text-gray-500">No bug reports yet.</li>}
        </ul>
      </section>
    </div>
  );
}
