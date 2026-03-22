/**
 * PRInput is Step 2 in the UI flow.
 *
 * What it does:
 * - Collects a PR URL
 * - Performs lightweight front-end validation before submit
 * - Disables submit while analysis is running
 *
 * Connected to:
 * - App's `handleAnalyzePr`, which calls `analyzePR()` from api.js
 * - AgentTrace/ImpactSummary, which render results of that stream
 */
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
    <section className="rounded-lg border border-slate-700/80 bg-slate-900/60 p-4 space-y-3 shadow-xl backdrop-blur">
      <h2 className="text-lg font-semibold">Step 2: Analyze Pull Request</h2>

      <form className="flex gap-2" onSubmit={handleSubmit}>
        <input
          type="url"
          value={prUrl}
          onChange={(event) => setPrUrl(event.target.value)}
          placeholder="https://github.com/owner/repo/pull/42"
          className="flex-1 rounded-md border border-slate-600 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500"
          required
        />
        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded-md bg-indigo-500 text-white px-4 py-2 text-sm disabled:opacity-50 transition hover:bg-indigo-400"
        >
          {disabled ? "Analyzing..." : "Analyze"}
        </button>
      </form>

      {hasValue && !isValid ? (
        <p className="text-sm text-amber-300">
          Enter a valid GitHub PR URL ending in /pull/123.
        </p>
      ) : null}
    </section>
  )
}
