/**
 * RepoInput is Step 1 in the UI flow.
 *
 * What it does:
 * - Collects a GitHub repository URL from the user
 * - Calls `onConnect` (provided by App) to start indexing
 * - Displays streaming index progress messages as they arrive
 * - Shows final index summary when backend emits `index_done`
 *
 * What comes before:
 * - App initializes page state and passes handlers/values here.
 *
 * What comes after:
 * - Once indexed, App can fetch graph data and enable meaningful PR analysis.
 */
export default function RepoInput({
  repoUrl,
  setRepoUrl,
  indexing,
  indexMessages,
  onConnect,
  indexedRepo,
}) {
  function handleSubmit(event) {
    event.preventDefault()
    onConnect()
  }

  const isDisabled = indexing || !repoUrl.trim()

  return (
    <section className="rounded-lg border border-slate-700/80 bg-slate-900/60 p-4 space-y-3 shadow-xl backdrop-blur">
      <h2 className="text-lg font-semibold">Step 1: Connect Repository</h2>

      <form className="flex gap-2" onSubmit={handleSubmit}>
        <input
          type="url"
          value={repoUrl}
          onChange={(event) => setRepoUrl(event.target.value)}
          placeholder="https://github.com/owner/repo"
          className="flex-1 rounded-md border border-slate-600 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500"
          required
        />
        <button
          type="submit"
          disabled={isDisabled}
          className="rounded-md bg-cyan-500/90 text-slate-950 font-medium px-4 py-2 text-sm disabled:opacity-50 transition hover:bg-cyan-400"
        >
          {indexing ? "Indexing..." : "Connect"}
        </button>
      </form>

      <div className="rounded-md bg-slate-950/60 border border-slate-700 p-3 text-sm">
        <p className="font-medium mb-2">Index progress</p>
        {indexMessages.length === 0 ? (
          <p className="text-slate-400">No progress events yet.</p>
        ) : (
          <ul className="space-y-1">
            {indexMessages.map((msg, idx) => (
              <li key={`${msg.stage}-${idx}`} className="text-slate-300">
                <span className="font-semibold text-cyan-300">[{msg.stage}]</span> {msg.summary}
              </li>
            ))}
          </ul>
        )}
      </div>

      {indexedRepo ? (
        <div className="rounded-md border border-emerald-400/40 bg-emerald-500/10 p-3 text-sm text-emerald-200">
          Indexed {indexedRepo.repo} - files: {indexedRepo.files}, clusters:{" "}
          {indexedRepo.clusters}, symbols: {indexedRepo.symbols}
        </div>
      ) : null}
    </section>
  )
}
