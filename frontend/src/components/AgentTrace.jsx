import { useEffect, useRef } from "react"

/**
 * AgentTrace renders the live stream of `agent_step` events.
 *
 * Data contract:
 * - `steps` is an array where each item comes from backend SSE payload:
 *   { tool: string, summary: string }
 *
 * Behavior:
 * - Auto-scrolls to the bottom whenever a new step arrives
 * - Shows a small running indicator while analysis is active
 */
export default function AgentTrace({ steps, loading }) {
  const listRef = useRef(null)

  useEffect(() => {
    if (!listRef.current) return
    listRef.current.scrollTop = listRef.current.scrollHeight
  }, [steps])

  return (
    <section className="rounded-lg border border-slate-700/80 bg-slate-900/60 p-4 space-y-3 shadow-xl backdrop-blur">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Live Agent Trace</h2>
        {loading ? <span className="text-xs text-indigo-300 pulse-soft">Running...</span> : null}
      </div>

      <div
        ref={listRef}
        className="h-44 overflow-y-auto rounded-md border border-slate-700 bg-slate-950/60 p-3 text-sm"
      >
        {steps.length === 0 ? (
          <p className="text-slate-400">No agent steps yet.</p>
        ) : (
          <ul className="space-y-2">
            {steps.map((step, idx) => (
              <li key={`${step.tool}-${idx}`} className="text-slate-300">
                <span className="font-semibold text-indigo-300">{step.tool}</span>: {step.summary}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
