import { GitPullRequest, Loader2 } from "lucide-react"

function isValidPrUrl(value) {
  try {
    const url = new URL(value)
    return /\/pull\/\d+/.test(url.pathname)
  } catch {
    return false
  }
}

export default function PRInput({ prUrl, setPrUrl, disabled, onSubmit }) {
  const hasValue = Boolean(prUrl.trim())
  const isValid = isValidPrUrl(prUrl)
  const canSubmit = hasValue && isValid && !disabled

  function handleSubmit(event) {
    event.preventDefault()
    if (!canSubmit) return
    onSubmit()
  }

  return (
    <section className="rounded-xl border border-border-default bg-surface overflow-hidden animate-slide-up">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-border-subtle flex items-center gap-2.5">
        <div className="flex items-center justify-center w-5 h-5 rounded-full bg-accent/20 text-accent text-xs font-bold flex-shrink-0">
          2
        </div>
        <h2 className="text-sm font-semibold text-text-primary">Analyze Pull Request</h2>
      </div>

      <div className="p-5 space-y-3">
        <form className="flex gap-2" onSubmit={handleSubmit}>
          <div className="flex-1 relative">
            <GitPullRequest
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none"
            />
            <input
              type="url"
              value={prUrl}
              onChange={(e) => setPrUrl(e.target.value)}
              placeholder="https://github.com/owner/repo/pull/42"
              className="w-full rounded-lg border border-border-default bg-deep pl-8 pr-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/30 transition-all"
              required
            />
          </div>
          <button
            type="submit"
            disabled={!canSubmit}
            className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-40 hover:bg-accent-dim transition-all shadow-glow"
          >
            {disabled ? (
              <>
                <Loader2 size={13} className="animate-spin" />
                Analyzing
              </>
            ) : (
              "Analyze"
            )}
          </button>
        </form>

        {hasValue && !isValid && (
          <p className="text-xs text-amber-400 flex items-center gap-1.5 animate-fade-in">
            <span className="opacity-70">⚠</span>
            Enter a valid GitHub PR URL — e.g. github.com/owner/repo/pull/123
          </p>
        )}
      </div>
    </section>
  )
}
