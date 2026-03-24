import { GitBranch, Loader2, CheckCircle2, Terminal } from "lucide-react"

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
    <section className="rounded-xl border border-border-default bg-surface overflow-hidden animate-slide-up">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-border-subtle flex items-center gap-2.5">
        <div className="flex items-center justify-center w-5 h-5 rounded-full bg-accent/20 text-accent text-xs font-bold flex-shrink-0">
          1
        </div>
        <h2 className="text-sm font-semibold text-text-primary">Connect Repository</h2>
        {indexedRepo && (
          <CheckCircle2 size={14} className="ml-auto text-emerald-400 flex-shrink-0" />
        )}
      </div>

      <div className="p-5 space-y-4">
        {/* Input */}
        <form className="flex gap-2" onSubmit={handleSubmit}>
          <div className="flex-1 relative">
            <GitBranch
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none"
            />
            <input
              type="url"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
              className="w-full rounded-lg border border-border-default bg-deep pl-8 pr-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/30 transition-all"
              required
            />
          </div>
          <button
            type="submit"
            disabled={isDisabled}
            className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-40 hover:bg-accent-dim transition-all shadow-glow"
          >
            {indexing ? (
              <>
                <Loader2 size={13} className="animate-spin" />
                Indexing
              </>
            ) : (
              "Connect"
            )}
          </button>
        </form>

        {/* Progress */}
        <div className="rounded-lg border border-border-subtle bg-deep overflow-hidden">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-border-subtle">
            <Terminal size={12} className="text-text-muted" />
            <span className="text-[11px] text-text-muted font-mono uppercase tracking-wider">Index log</span>
            {indexing && <Loader2 size={10} className="ml-auto animate-spin text-accent" />}
          </div>
          <div className="p-3 max-h-36 overflow-y-auto scrollbar-thin">
            {indexMessages.length === 0 ? (
              <p className="text-xs text-text-muted font-mono">Waiting for events…</p>
            ) : (
              <ul className="space-y-1">
                {indexMessages.map((msg, idx) => (
                  <li key={`${msg.stage}-${idx}`} className="text-xs font-mono">
                    <span className="text-accent/80">[{msg.stage}]</span>{" "}
                    <span className="text-text-secondary">{msg.summary}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Success badge */}
        {indexedRepo && (
          <div className="flex items-center gap-3 rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-4 py-2.5 text-xs animate-fade-in">
            <CheckCircle2 size={14} className="text-emerald-400 flex-shrink-0" />
            <span className="text-emerald-300">
              <span className="font-semibold">{indexedRepo.repo}</span> indexed —{" "}
              {indexedRepo.files} files · {indexedRepo.clusters} clusters · {indexedRepo.symbols} symbols
            </span>
          </div>
        )}
      </div>
    </section>
  )
}
