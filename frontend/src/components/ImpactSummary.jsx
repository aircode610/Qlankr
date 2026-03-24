import { ClipboardCopy, Zap, ExternalLink } from "lucide-react"
import ComponentCard from "./ComponentCard"

export default function ImpactSummary({ result, onCopyMarkdown, focusedFiles, onFocusFiles }) {
  return (
    <section className="rounded-xl border border-border-default bg-surface overflow-hidden animate-slide-up">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-border-subtle flex items-center gap-2.5">
        <Zap size={14} className="text-accent flex-shrink-0" />
        <h2 className="text-sm font-semibold text-text-primary">Impact Summary</h2>
        <button
          type="button"
          onClick={onCopyMarkdown}
          disabled={!result}
          className="ml-auto flex items-center gap-1.5 rounded-lg border border-border-default bg-elevated px-3 py-1.5 text-xs text-text-secondary disabled:opacity-30 hover:border-accent/40 hover:text-accent transition-all"
        >
          <ClipboardCopy size={11} />
          Copy as Markdown
        </button>
      </div>

      <div className="p-5">
        {!result ? (
          <p className="text-xs text-text-muted">
            Run a PR analysis above to see the impact report here.
          </p>
        ) : (
          <div className="space-y-5 animate-fade-in">
            {/* PR meta */}
            <div className="rounded-lg border border-border-default bg-deep p-4 space-y-2">
              <p className="font-semibold text-text-primary">{result.pr_title}</p>
              <a
                href={result.pr_url}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 text-xs text-accent hover:text-accent/80 transition-colors break-all"
              >
                <ExternalLink size={11} className="flex-shrink-0" />
                {result.pr_url}
              </a>
              <p className="text-sm text-text-secondary leading-relaxed">{result.pr_summary}</p>
              <p className="text-[11px] text-text-muted font-mono">
                {result.agent_steps} agent steps
              </p>
            </div>

            {/* Affected components */}
            <div className="space-y-3">
              <p className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
                Affected Components ({(result.affected_components || []).length})
              </p>
              {(result.affected_components || []).map((item, idx) => {
                const isActive = focusedFiles &&
                  item.files_changed?.some(f => focusedFiles.includes(f))
                return (
                  <ComponentCard
                    key={`${item.component}-${idx}`}
                    item={item}
                    isActive={isActive}
                    onFocusFiles={() => onFocusFiles(item.files_changed || [])}
                  />
                )
              })}
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
