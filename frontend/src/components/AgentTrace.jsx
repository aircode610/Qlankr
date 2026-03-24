import { useEffect, useRef } from "react"
import { Bot, Loader2, Wrench } from "lucide-react"

export default function AgentTrace({ steps, loading }) {
  const listRef = useRef(null)

  useEffect(() => {
    if (!listRef.current) return
    listRef.current.scrollTop = listRef.current.scrollHeight
  }, [steps])

  return (
    <section className="rounded-xl border border-border-default bg-surface overflow-hidden animate-slide-up">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-border-subtle flex items-center gap-2.5">
        <Bot size={14} className="text-accent flex-shrink-0" />
        <h2 className="text-sm font-semibold text-text-primary">Agent Trace</h2>
        {loading && (
          <div className="ml-auto flex items-center gap-1.5 text-xs text-accent">
            <Loader2 size={11} className="animate-spin" />
            Running
          </div>
        )}
      </div>

      {/* Log */}
      <div
        ref={listRef}
        className="p-4 h-44 overflow-y-auto scrollbar-thin space-y-2"
      >
        {steps.length === 0 ? (
          <p className="text-xs text-text-muted font-mono">No agent steps yet. Run analysis to see live tool calls here.</p>
        ) : (
          steps.map((step, idx) => (
            <div
              key={`${step.tool}-${idx}`}
              className="flex items-start gap-2.5 animate-fade-in"
            >
              <div className="mt-0.5 flex-shrink-0 p-1 rounded bg-accent/15 border border-accent/20">
                <Wrench size={9} className="text-accent" />
              </div>
              <div className="min-w-0">
                <span className="text-xs font-semibold text-accent font-mono">{step.tool}</span>
                <span className="text-xs text-text-muted mx-1">·</span>
                <span className="text-xs text-text-secondary">{step.summary}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  )
}
