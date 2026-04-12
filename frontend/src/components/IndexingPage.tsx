import { useState, useEffect, useRef } from 'react';
import { Loader2, CheckCircle, AlertCircle, Zap } from '@/lib/lucide-icons';

interface IndexingPageProps {
  onIndex: (url: string) => void;
  indexing: boolean;
  indexed: boolean;
  indexMessages: Array<{ stage: string; summary: string }>;
  error: string | null;
}

export const IndexingPage = ({ onIndex, indexing, indexed, indexMessages, error }: IndexingPageProps) => {
  const [url, setUrl] = useState('');
  const logBottomRef = useRef<HTMLDivElement>(null);

  const isValidUrl = /github\.com\/[^/]+\/[^/]+/.test(url);

  useEffect(() => {
    logBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [indexMessages.length]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isValidUrl && !indexing) onIndex(url);
  };

  const showLog = indexing || indexed || indexMessages.length > 0;

  return (
    <div className="relative flex h-screen flex-col items-center justify-center overflow-hidden bg-void px-4">

      {/* Background decoration */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-1/2 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent/5 blur-3xl" />
        <div className="absolute left-1/4 top-1/4 h-64 w-64 rounded-full bg-violet-900/10 blur-2xl" />
        <div className="absolute bottom-1/4 right-1/4 h-48 w-48 rounded-full bg-indigo-900/10 blur-2xl" />
      </div>

      {/* Content */}
      <div className="relative z-10 flex w-full max-w-md flex-col gap-8">

        {/* Branding */}
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-accent to-violet-800 shadow-[0_0_32px_rgba(124,58,237,0.35)]">
            <Zap className="h-7 w-7 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-text-primary">Qlankr</h1>
            <p className="mt-1 text-sm text-text-muted">Knowledge graph for your codebase</p>
          </div>
        </div>

        {/* Input card */}
        <div className="rounded-2xl border border-border-subtle bg-elevated/60 p-6 shadow-xl backdrop-blur-sm">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="mb-2 block text-xs font-medium tracking-wide text-text-secondary uppercase">
                Repository
              </label>
              <div className={`flex items-center gap-3 rounded-xl border bg-void/60 px-4 py-3 transition-all ${
                isValidUrl
                  ? 'border-accent/50 shadow-[0_0_0_3px_rgba(124,58,237,0.08)]'
                  : 'border-border-subtle focus-within:border-accent/40 focus-within:shadow-[0_0_0_3px_rgba(124,58,237,0.06)]'
              }`}>
                <span className="font-mono text-sm text-text-muted">github.com/</span>
                <input
                  type="text"
                  placeholder="owner/repo"
                  value={url.replace(/^https?:\/\/github\.com\//, '')}
                  onChange={(e) => {
                    const raw = e.target.value;
                    setUrl(raw.startsWith('http') ? raw : `https://github.com/${raw}`);
                  }}
                  disabled={indexing || indexed}
                  autoFocus
                  className="flex-1 bg-transparent font-mono text-sm text-text-primary placeholder:text-text-muted focus:outline-none disabled:opacity-60"
                />
                {isValidUrl && !indexing && (
                  <CheckCircle className="h-4 w-4 shrink-0 text-emerald-400" />
                )}
              </div>
            </div>

            {!indexed && (
              <button
                type="submit"
                disabled={!isValidUrl || indexing}
                className="flex items-center justify-center gap-2 rounded-xl bg-accent py-3 text-sm font-medium text-white shadow-[0_0_20px_rgba(124,58,237,0.25)] transition-all hover:bg-accent-dim hover:shadow-[0_0_24px_rgba(124,58,237,0.35)] disabled:opacity-50 disabled:shadow-none"
              >
                {indexing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Indexing…
                  </>
                ) : (
                  'Index Repository'
                )}
              </button>
            )}
          </form>
        </div>

        {/* Trace log */}
        {showLog && (
          <div className="rounded-2xl border border-border-subtle bg-deep/80 backdrop-blur-sm">
            {/* Log header */}
            <div className="flex items-center gap-2 border-b border-border-subtle px-4 py-2.5">
              <div className="flex gap-1">
                <span className="h-2.5 w-2.5 rounded-full bg-red-500/60" />
                <span className="h-2.5 w-2.5 rounded-full bg-yellow-500/60" />
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500/60" />
              </div>
              <span className="flex-1 text-center font-mono text-[10px] text-text-muted">indexing log</span>
              {indexing && <Loader2 className="h-3 w-3 animate-spin text-accent" />}
              {indexed && <CheckCircle className="h-3 w-3 text-emerald-400" />}
            </div>

            {/* Messages */}
            <div className="scrollbar-thin max-h-52 overflow-y-auto px-4 py-3 font-mono text-[11px]">
              {indexMessages.length === 0 && indexing && (
                <p className="text-text-muted">Connecting to backend…</p>
              )}
              {indexMessages.map((msg, i) => (
                <div key={i} className="flex gap-3 py-0.5 leading-relaxed">
                  <span className="shrink-0 text-accent">[{msg.stage}]</span>
                  <span className="text-text-secondary">{msg.summary}</span>
                </div>
              ))}
              {indexed && (
                <div className="mt-2 flex items-center gap-2 text-emerald-400">
                  <CheckCircle className="h-3 w-3" />
                  <span>Indexing complete — loading workspace…</span>
                </div>
              )}
              {error && (
                <div className="mt-2 flex items-center gap-2 text-red-400">
                  <AlertCircle className="h-3 w-3" />
                  <span>{error}</span>
                </div>
              )}
              <div ref={logBottomRef} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
