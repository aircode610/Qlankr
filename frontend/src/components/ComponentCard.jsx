import { ChevronDown, FileCode, AlertTriangle, FlaskConical } from "lucide-react"

const CONFIDENCE_STYLE = {
  HIGH:     { bg: "bg-red-500/15",    border: "border-red-500/30",    text: "text-red-300"    },
  MEDIUM:   { bg: "bg-amber-500/15",  border: "border-amber-500/30",  text: "text-amber-300"  },
  LOW:      { bg: "bg-emerald-500/15",border: "border-emerald-500/30",text: "text-emerald-300" },
  CRITICAL: { bg: "bg-red-600/20",    border: "border-red-500/50",    text: "text-red-200"    },
}

export default function ComponentCard({ item }) {
  const conf = CONFIDENCE_STYLE[item.confidence?.toUpperCase()] || CONFIDENCE_STYLE.LOW

  return (
    <article className="rounded-xl border border-border-default bg-elevated overflow-hidden animate-fade-in">
      {/* Card header */}
      <div className="px-4 py-3 flex items-center justify-between gap-3 border-b border-border-subtle">
        <h4 className="font-semibold text-sm text-text-primary">{item.component}</h4>
        <span className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full border ${conf.bg} ${conf.border} ${conf.text}`}>
          {item.confidence}
        </span>
      </div>

      <div className="p-4 space-y-4">
        {/* Impact summary */}
        <p className="text-sm text-text-secondary leading-relaxed">{item.impact_summary}</p>

        {/* Files changed */}
        {(item.files_changed || []).length > 0 && (
          <details className="group">
            <summary className="flex items-center gap-2 cursor-pointer text-xs font-medium text-text-secondary hover:text-text-primary transition-colors list-none">
              <FileCode size={12} className="text-text-muted" />
              {item.files_changed.length} file{item.files_changed.length !== 1 ? "s" : ""} changed
              <ChevronDown size={11} className="ml-auto text-text-muted group-open:rotate-180 transition-transform" />
            </summary>
            <ul className="mt-2 space-y-1">
              {item.files_changed.map((file) => (
                <li
                  key={file}
                  className="text-[11px] font-mono text-text-muted px-2 py-0.5 rounded bg-deep border border-border-subtle truncate"
                  title={file}
                >
                  {file}
                </li>
              ))}
            </ul>
          </details>
        )}

        {/* Risks */}
        {(item.risks || []).length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <AlertTriangle size={11} className="text-amber-400" />
              <p className="text-xs font-medium text-text-secondary">Risks</p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {item.risks.map((risk, idx) => (
                <span
                  key={`${risk}-${idx}`}
                  className="text-[11px] px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/25 text-amber-300"
                >
                  {risk}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Test suggestions */}
        {item.test_suggestions && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <FlaskConical size={11} className="text-text-muted" />
              <p className="text-xs font-medium text-text-secondary">Test suggestions</p>
            </div>
            <div className="grid gap-2 sm:grid-cols-3">
              {/* Skip */}
              <div className="rounded-lg bg-deep border border-border-subtle p-2.5">
                <p className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">Skip</p>
                <ul className="space-y-1">
                  {(item.test_suggestions.skip || []).map((s, idx) => (
                    <li key={idx} className="text-[11px] text-text-secondary flex items-start gap-1">
                      <span className="text-text-muted mt-0.5 flex-shrink-0">·</span>
                      {s}
                    </li>
                  ))}
                  {!(item.test_suggestions.skip?.length) && (
                    <li className="text-[11px] text-text-muted italic">None</li>
                  )}
                </ul>
              </div>
              {/* Run */}
              <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-2.5">
                <p className="text-[10px] font-semibold text-emerald-400/70 uppercase tracking-wider mb-1.5">Run</p>
                <ul className="space-y-1">
                  {(item.test_suggestions.run || []).map((s, idx) => (
                    <li key={idx} className="text-[11px] text-text-secondary flex items-start gap-1">
                      <span className="text-emerald-500/60 mt-0.5 flex-shrink-0">·</span>
                      {s}
                    </li>
                  ))}
                  {!(item.test_suggestions.run?.length) && (
                    <li className="text-[11px] text-text-muted italic">None</li>
                  )}
                </ul>
              </div>
              {/* Deeper */}
              <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-2.5">
                <p className="text-[10px] font-semibold text-amber-400/70 uppercase tracking-wider mb-1.5">Deeper</p>
                <ul className="space-y-1">
                  {(item.test_suggestions.deeper || []).map((s, idx) => (
                    <li key={idx} className="text-[11px] text-text-secondary flex items-start gap-1">
                      <span className="text-amber-500/60 mt-0.5 flex-shrink-0">·</span>
                      {s}
                    </li>
                  ))}
                  {!(item.test_suggestions.deeper?.length) && (
                    <li className="text-[11px] text-text-muted italic">None</li>
                  )}
                </ul>
              </div>
            </div>
          </div>
        )}
      </div>
    </article>
  )
}
