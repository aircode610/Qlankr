/**
 * ComponentCard renders one item from AnalyzeResponse.affected_components.
 *
 * This mirrors backend model fields directly:
 * - component
 * - files_changed
 * - impact_summary
 * - risks
 * - test_suggestions.skip/run/deeper
 * - confidence
 */
export default function ComponentCard({ item }) {
  return (
    <article className="rounded-md border border-slate-700 p-4 space-y-3 bg-slate-950/40">
      <div className="flex items-center justify-between">
        <h4 className="font-semibold">{item.component}</h4>
        <span className="rounded bg-slate-800 px-2 py-1 text-xs uppercase text-slate-200">
          {item.confidence}
        </span>
      </div>

      <details>
        <summary className="cursor-pointer text-sm font-medium">Files changed</summary>
        <ul className="mt-2 text-sm list-disc ml-5">
          {(item.files_changed || []).map((file) => (
            <li key={file}>{file}</li>
          ))}
        </ul>
      </details>

      <div>
        <p className="text-sm font-medium">Impact summary</p>
        <p className="text-sm text-slate-300">{item.impact_summary}</p>
      </div>

      <div>
        <p className="text-sm font-medium">Risks</p>
        <div className="mt-1 flex flex-wrap gap-2">
          {(item.risks || []).map((risk, idx) => (
            <span key={`${risk}-${idx}`} className="rounded bg-red-500/20 text-red-200 px-2 py-1 text-xs">
              {risk}
            </span>
          ))}
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-3 text-sm">
        <div className="rounded bg-slate-800/70 p-2">
          <p className="font-medium">Skip</p>
          <ul className="list-disc ml-5">
            {(item.test_suggestions?.skip || []).map((s, idx) => (
              <li key={`skip-${idx}`}>{s}</li>
            ))}
          </ul>
        </div>
        <div className="rounded bg-emerald-500/20 p-2">
          <p className="font-medium">Run</p>
          <ul className="list-disc ml-5">
            {(item.test_suggestions?.run || []).map((s, idx) => (
              <li key={`run-${idx}`}>{s}</li>
            ))}
          </ul>
        </div>
        <div className="rounded bg-orange-500/20 p-2">
          <p className="font-medium">Deeper</p>
          <ul className="list-disc ml-5">
            {(item.test_suggestions?.deeper || []).map((s, idx) => (
              <li key={`deeper-${idx}`}>{s}</li>
            ))}
          </ul>
        </div>
      </div>
    </article>
  )
}
