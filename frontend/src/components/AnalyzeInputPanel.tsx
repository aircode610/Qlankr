import { useState } from 'react';
import {
  GitPullRequest, Play, Loader2, CheckCircle, ChevronDown, ChevronUp, MessageSquare,
} from '@/lib/lucide-icons';

interface AnalyzeInputPanelProps {
  onAnalyze: (prUrl: string, context: string | null) => void;
  analyzing: boolean;
}

export const AnalyzeInputPanel = ({ onAnalyze, analyzing }: AnalyzeInputPanelProps) => {
  const [prUrl, setPrUrl] = useState('');
  const [context, setContext] = useState('');
  const [showContext, setShowContext] = useState(false);

  const isValidPr = /\/pull\/\d+/.test(prUrl);
  const canRun = isValidPr && !analyzing;

  const handleSubmit = () => {
    if (!canRun) return;
    onAnalyze(prUrl, context.trim() || null);
  };

  return (
    <div className="flex h-full items-start justify-center overflow-y-auto bg-void py-10">
      <div className="w-full max-w-xl px-6">

        {/* Header */}
        <div className="mb-7 text-center">
          <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl border border-accent/25 bg-accent/10">
            <GitPullRequest className="h-5 w-5 text-accent" />
          </div>
          <h2 className="text-sm font-semibold text-text-primary">Analyze a Pull Request</h2>
          <p className="mt-1 text-xs text-text-muted">
            Enter a PR URL and the agent will identify affected components, risks, and generate test coverage.
          </p>
        </div>

        {/* PR URL input */}
        <div className="mb-4 rounded-xl border border-border-default bg-elevated p-4 focus-within:border-accent/40 transition-colors">
          <label className="mb-2 block text-[10px] font-semibold uppercase tracking-wider text-text-muted">
            Pull Request URL <span className="text-red-400">*</span>
          </label>
          <div className="flex items-center gap-2">
            <GitPullRequest className="h-4 w-4 shrink-0 text-text-muted" />
            <input
              type="text"
              placeholder="https://github.com/owner/repo/pull/123"
              value={prUrl}
              onChange={(e) => setPrUrl(e.target.value)}
              disabled={analyzing}
              className="flex-1 bg-transparent text-xs text-text-primary placeholder:text-text-muted/60 focus:outline-none disabled:opacity-50"
            />
            {isValidPr && <CheckCircle className="h-4 w-4 shrink-0 text-emerald-400" />}
          </div>
        </div>

        {/* Context toggle */}
        <button
          onClick={() => setShowContext(!showContext)}
          className="mb-3 flex items-center gap-1.5 text-[11px] text-text-muted transition-colors hover:text-text-secondary"
        >
          <MessageSquare className="h-3 w-3" />
          {showContext ? 'Hide context' : 'Add context (bug report, scenario, etc.)'}
          {showContext ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </button>

        {showContext && (
          <div className="mb-4 rounded-xl border border-border-default bg-elevated p-4 focus-within:border-accent/40 transition-colors">
            <label className="mb-2 block text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              Context
            </label>
            <textarea
              placeholder="Describe a bug, scenario, or context to focus the analysis..."
              value={context}
              onChange={(e) => setContext(e.target.value)}
              disabled={analyzing}
              rows={4}
              className="w-full resize-none bg-transparent text-xs leading-relaxed text-text-primary placeholder:text-text-muted/60 focus:outline-none disabled:opacity-50"
            />
          </div>
        )}

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={!canRun}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent py-2.5 text-sm font-medium text-white shadow-[0_0_16px_rgba(124,58,237,0.25)] transition-all hover:bg-accent-dim disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
        >
          {analyzing ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Analyzing...
            </>
          ) : (
            <>
              <Play className="h-4 w-4" />
              Analyze PR
            </>
          )}
        </button>
      </div>
    </div>
  );
};
