import ComponentCard from "./ComponentCard"

/**
 * ImpactSummary renders the final `result` SSE payload.
 *
 * It is intentionally strict to backend schema fields so front and back
 * stay aligned during integration.
 *
 * It also exposes a "Copy Markdown" action which App provides.
 */
export default function ImpactSummary({ result, onCopyMarkdown }) {
  return (
    <section className="rounded-lg border border-slate-700/80 bg-slate-900/60 p-4 space-y-4 shadow-xl backdrop-blur">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Impact Summary</h2>
        <button
          type="button"
          onClick={onCopyMarkdown}
          disabled={!result}
          className="rounded-md border border-slate-600 bg-slate-950/50 px-3 py-1.5 text-sm disabled:opacity-50 hover:border-cyan-400/70 hover:text-cyan-200"
        >
          Copy report as Markdown
        </button>
      </div>

      {!result ? (
        <p className="text-sm text-slate-400">Run PR analysis to see results here.</p>
      ) : (
        <div className="space-y-4">
          <div className="rounded-md bg-slate-950/60 border border-slate-700 p-3 space-y-1">
            <p className="font-semibold">{result.pr_title}</p>
            <a
              href={result.pr_url}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-cyan-300 underline break-all"
            >
              {result.pr_url}
            </a>
            <p className="text-sm text-slate-300">{result.pr_summary}</p>
            <p className="text-xs text-slate-400">Agent steps: {result.agent_steps}</p>
          </div>

          <div className="space-y-3">
            {(result.affected_components || []).map((item, idx) => (
              <ComponentCard key={`${item.component}-${idx}`} item={item} />
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
