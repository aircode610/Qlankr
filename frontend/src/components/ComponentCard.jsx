import { useState } from "react"
import { AlertTriangle, FileCode, FlaskConical, X, ChevronRight, Crosshair } from "lucide-react"

const CONFIDENCE_STYLE = {
  HIGH:     { bg: "bg-red-500/15",     border: "border-red-500/30",    text: "text-red-300"    },
  MEDIUM:   { bg: "bg-amber-500/15",   border: "border-amber-500/30",  text: "text-amber-300"  },
  LOW:      { bg: "bg-emerald-500/15", border: "border-emerald-500/30",text: "text-emerald-300" },
  CRITICAL: { bg: "bg-red-600/20",     border: "border-red-500/50",    text: "text-red-200"    },
}

function TestActionsModal({ item, onClose }) {
  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-void/80 backdrop-blur-sm animate-fade-in"
        onClick={onClose}
      />
      {/* Panel */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div className="pointer-events-auto w-full max-w-lg rounded-xl border border-border-default bg-surface shadow-glow animate-slide-up overflow-hidden">
          {/* Modal header */}
          <div className="flex items-center gap-3 px-5 py-4 border-b border-border-subtle">
            <FlaskConical size={15} className="text-accent flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-text-primary truncate">Test Actions</p>
              <p className="text-xs text-text-muted truncate">{item.component}</p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="ml-auto p-1 rounded-lg text-text-muted hover:text-text-primary hover:bg-hover transition-all flex-shrink-0"
            >
              <X size={14} />
            </button>
          </div>

          {/* Modal body */}
          <div className="p-5 space-y-4 max-h-[70vh] overflow-y-auto scrollbar-thin">
            {/* Skip */}
            <div className="rounded-lg border border-border-subtle bg-deep overflow-hidden">
              <div className="flex items-center gap-2 px-3 py-2 border-b border-border-subtle bg-elevated">
                <span className="w-2 h-2 rounded-full bg-text-muted flex-shrink-0" />
                <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Skip</p>
                <span className="ml-auto text-[10px] font-mono text-text-muted">
                  {(item.test_suggestions?.skip || []).length} items
                </span>
              </div>
              <ul className="p-3 space-y-1.5">
                {(item.test_suggestions?.skip || []).length === 0 ? (
                  <li className="text-xs text-text-muted italic">Nothing to skip</li>
                ) : (
                  (item.test_suggestions.skip).map((s, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-text-secondary">
                      <span className="text-text-muted mt-0.5 flex-shrink-0">·</span>
                      {s}
                    </li>
                  ))
                )}
              </ul>
            </div>

            {/* Run */}
            <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 overflow-hidden">
              <div className="flex items-center gap-2 px-3 py-2 border-b border-emerald-500/20 bg-emerald-500/10">
                <span className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0" />
                <p className="text-xs font-semibold text-emerald-400/80 uppercase tracking-wider">Run</p>
                <span className="ml-auto text-[10px] font-mono text-emerald-400/50">
                  {(item.test_suggestions?.run || []).length} items
                </span>
              </div>
              <ul className="p-3 space-y-1.5">
                {(item.test_suggestions?.run || []).length === 0 ? (
                  <li className="text-xs text-text-muted italic">Nothing to run</li>
                ) : (
                  (item.test_suggestions.run).map((s, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-text-secondary">
                      <span className="text-emerald-500/70 mt-0.5 flex-shrink-0">✓</span>
                      {s}
                    </li>
                  ))
                )}
              </ul>
            </div>

            {/* Deeper */}
            <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 overflow-hidden">
              <div className="flex items-center gap-2 px-3 py-2 border-b border-amber-500/20 bg-amber-500/10">
                <span className="w-2 h-2 rounded-full bg-amber-400 flex-shrink-0" />
                <p className="text-xs font-semibold text-amber-400/80 uppercase tracking-wider">Deeper Investigation</p>
                <span className="ml-auto text-[10px] font-mono text-amber-400/50">
                  {(item.test_suggestions?.deeper || []).length} items
                </span>
              </div>
              <ul className="p-3 space-y-1.5">
                {(item.test_suggestions?.deeper || []).length === 0 ? (
                  <li className="text-xs text-text-muted italic">Nothing here</li>
                ) : (
                  (item.test_suggestions.deeper).map((s, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-text-secondary">
                      <span className="text-amber-500/70 mt-0.5 flex-shrink-0">→</span>
                      {s}
                    </li>
                  ))
                )}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

export default function ComponentCard({ item, isActive, onFocusFiles }) {
  const [modalOpen, setModalOpen] = useState(false)
  const conf = CONFIDENCE_STYLE[item.confidence?.toUpperCase()] || CONFIDENCE_STYLE.LOW
  const fileCount = (item.files_changed || []).length
  const hasTestActions = item.test_suggestions &&
    ((item.test_suggestions.skip?.length || 0) +
     (item.test_suggestions.run?.length || 0) +
     (item.test_suggestions.deeper?.length || 0)) > 0

  return (
    <>
      <article
        className={`rounded-xl border overflow-hidden transition-all ${
          isActive
            ? "border-accent/50 bg-accent/5 shadow-glow-soft"
            : "border-border-default bg-elevated"
        }`}
      >
        {/* Card header row */}
        <div className="px-4 py-3 flex items-center gap-3 border-b border-border-subtle">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="font-semibold text-sm text-text-primary">{item.component}</h4>
              <span className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full border ${conf.bg} ${conf.border} ${conf.text}`}>
                {item.confidence}
              </span>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Focus in graph */}
            {fileCount > 0 && (
              <button
                type="button"
                onClick={onFocusFiles}
                title="Highlight these files in the graph"
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border transition-all ${
                  isActive
                    ? "bg-accent/20 border-accent/40 text-accent"
                    : "bg-deep border-border-default text-text-muted hover:border-accent/40 hover:text-accent"
                }`}
              >
                <Crosshair size={11} />
                <span className="hidden sm:inline">{fileCount} file{fileCount !== 1 ? "s" : ""}</span>
              </button>
            )}

            {/* Test actions modal trigger */}
            {hasTestActions && (
              <button
                type="button"
                onClick={() => setModalOpen(true)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border border-border-default bg-deep text-text-secondary hover:border-accent/40 hover:text-accent transition-all"
              >
                <FlaskConical size={11} />
                <span className="hidden sm:inline">Test Actions</span>
                <ChevronRight size={10} />
              </button>
            )}
          </div>
        </div>

        {/* Card body */}
        <div className="px-4 py-3 space-y-3">
          {/* What changed & what it impacts */}
          <p className="text-sm text-text-secondary leading-relaxed">{item.impact_summary}</p>

          {/* Files changed — subtle, not a big deal */}
          {fileCount > 0 && (
            <details className="group">
              <summary className="flex items-center gap-1.5 cursor-pointer text-xs text-text-muted hover:text-text-secondary transition-colors list-none select-none">
                <FileCode size={11} />
                {fileCount} file{fileCount !== 1 ? "s" : ""} changed
                <span className="ml-1 opacity-50 group-open:hidden">▸</span>
                <span className="ml-1 opacity-50 hidden group-open:inline">▾</span>
              </summary>
              <ul className="mt-2 space-y-1 pl-1">
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

          {/* Risks — compact pills */}
          {(item.risks || []).length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <AlertTriangle size={11} className="text-amber-400 flex-shrink-0" />
              {item.risks.map((risk, idx) => (
                <span
                  key={`${risk}-${idx}`}
                  className="text-[11px] px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-300"
                >
                  {risk}
                </span>
              ))}
            </div>
          )}
        </div>
      </article>

      {/* Test actions modal */}
      {modalOpen && (
        <TestActionsModal item={item} onClose={() => setModalOpen(false)} />
      )}
    </>
  )
}
