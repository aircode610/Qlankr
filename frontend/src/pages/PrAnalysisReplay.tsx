import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { TestPipelineResults } from "../components/TestPipelineResults";
import { getPrAnalysis, type PrAnalysisRow } from "../services/api";
import type { AnalyzeResult } from "../services/types";

type Detail = PrAnalysisRow & Record<string, unknown>;

function extractResult(final_result: unknown): AnalyzeResult | null {
  if (!final_result || typeof final_result !== "object") return null;
  const r = final_result as Partial<AnalyzeResult>;
  if (typeof r.pr_url !== "string" || !Array.isArray(r.affected_components)) return null;
  return final_result as AnalyzeResult;
}

export function PrAnalysisReplay() {
  const { id: projectId, runId } = useParams<{ id: string; runId: string }>();
  const [detail, setDetail] = useState<Detail | null>(null);

  useEffect(() => {
    if (!runId) return;
    getPrAnalysis(runId).then(setDetail).catch(console.error);
  }, [runId]);

  if (!detail) return <div className="p-4 text-sm text-gray-500">Loading…</div>;

  const result = extractResult(detail.final_result);

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b border-border-subtle px-4 py-2">
        <Link to={`/projects/${projectId}/history`} className="text-sm underline">← History</Link>
      </div>
      {result ? (
        <div className="min-h-0 flex-1">
          <TestPipelineResults result={result} onHighlightFiles={() => {}} />
        </div>
      ) : (
        <div className="p-4 text-sm text-gray-500">
          No final result available for this run.
        </div>
      )}
    </div>
  );
}
