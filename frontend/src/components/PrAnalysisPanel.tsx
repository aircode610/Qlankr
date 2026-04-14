import { useState } from 'react';
import { GitPullRequest, Play, Loader2, CheckCircle, MessageSquare, ChevronDown, ChevronUp } from '@/lib/lucide-icons';

interface PrAnalysisPanelProps {
  onAnalyze: (prUrl: string, context: string | null) => void;
  analyzing: boolean;
  disabled: boolean;
}

export const PrAnalysisPanel = ({ onAnalyze, analyzing, disabled }: PrAnalysisPanelProps) => {
  const [prUrl, setPrUrl] = useState('');
  const [context, setContext] = useState('');
  const [showContext, setShowContext] = useState(false);

  const isValidPr = /\/pull\/\d+/.test(prUrl);
  const canRun = isValidPr && !disabled && !analyzing;

  return (
    <div className="flex flex-col gap-2">
      {/* PR URL input */}
      <div className={`flex items-center gap-2 rounded-lg border bg-elevated/50 px-3 py-2 transition-all ${
        isValidPr ? 'border-accent/40' : 'border-border-subtle focus-within:border-accent/30'
      }`}>
        <GitPullRequest className="h-3.5 w-3.5 shrink-0 text-text-muted" />
        <input
          type="text"
          placeholder="GitHub PR URL"
          value={prUrl}
          onChange={(e) => setPrUrl(e.target.value)}
          disabled={analyzing}
          className="flex-1 bg-transparent text-xs text-text-primary placeholder:text-text-muted focus:outline-none disabled:opacity-50"
        />
        {isValidPr && <CheckCircle className="h-3 w-3 shrink-0 text-emerald-400" />}
      </div>

      {/* Context toggle */}
      <button
        onClick={() => setShowContext(!showContext)}
        className="flex items-center gap-1 self-start text-[10px] text-text-muted transition-colors hover:text-text-secondary"
      >
        <MessageSquare className="h-2.5 w-2.5" />
        {showContext ? 'Hide context' : 'Add context'}
        {showContext ? <ChevronUp className="h-2.5 w-2.5" /> : <ChevronDown className="h-2.5 w-2.5" />}
      </button>

      {showContext && (
        <textarea
          placeholder="Bug report, scenario, or context..."
          value={context}
          onChange={(e) => setContext(e.target.value)}
          disabled={analyzing}
          rows={2}
          className="resize-none rounded-lg border border-border-subtle bg-elevated/50 px-3 py-2 text-[11px] text-text-primary placeholder:text-text-muted focus:border-accent/40 focus:outline-none disabled:opacity-50"
        />
      )}

      {/* Analyze button */}
      <button
        onClick={() => onAnalyze(prUrl, context || null)}
        disabled={!canRun}
        className="flex items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2 text-xs font-medium text-white transition-all hover:bg-accent-dim disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {analyzing ? (
          <>
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Analyzing…
          </>
        ) : (
          <>
            <Play className="h-3.5 w-3.5" />
            Analyze PR
          </>
        )}
      </button>
    </div>
  );
};
