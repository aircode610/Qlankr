import { useState } from 'react';
import { GitPullRequest, Loader2, MessageSquare } from '@/lib/lucide-icons';
import type { AnalysisStage } from '../services/types';

const STAGE_LABELS: Record<AnalysisStage, string> = {
  gathering: 'Gathering Context',
  unit_testing: 'Unit Tests',
  integration_testing: 'Integration Tests',
  e2e_planning: 'E2E Planning',
  submitting: 'Submitting',
};

interface PrAnalysisPanelProps {
  onAnalyze: (prUrl: string, context: string | null) => void;
  analyzing: boolean;
  currentStage: AnalysisStage | null;
  sessionId: string | null;
  disabled: boolean;
}

export const PrAnalysisPanel = ({ onAnalyze, analyzing, currentStage, sessionId, disabled }: PrAnalysisPanelProps) => {
  const [prUrl, setPrUrl] = useState('');
  const [context, setContext] = useState('');
  const [showContext, setShowContext] = useState(false);

  const isValidPr = /\/pull\/\d+/.test(prUrl);

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-xs font-medium tracking-wide text-text-secondary uppercase">PR Analysis</h3>

      <div className="flex gap-2">
        <div className="relative flex-1">
          <GitPullRequest className="absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
          <input
            type="text"
            placeholder="GitHub PR URL"
            value={prUrl}
            onChange={(e) => setPrUrl(e.target.value)}
            disabled={analyzing}
            className="w-full rounded border border-border-subtle bg-elevated py-2 pr-3 pl-8 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none disabled:opacity-50"
          />
        </div>
        <button
          onClick={() => onAnalyze(prUrl, context || null)}
          disabled={analyzing || !isValidPr || disabled}
          className="rounded bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-dim disabled:opacity-50"
        >
          {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Analyze'}
        </button>
      </div>

      <button
        onClick={() => setShowContext(!showContext)}
        className="flex items-center gap-1.5 text-[11px] text-text-muted transition-colors hover:text-text-secondary"
      >
        <MessageSquare className="h-3 w-3" />
        {showContext ? 'Hide context' : 'Add bug report / scenario context'}
      </button>

      {showContext && (
        <textarea
          placeholder="Optional: describe a bug report or scenario to focus E2E testing..."
          value={context}
          onChange={(e) => setContext(e.target.value)}
          disabled={analyzing}
          rows={3}
          className="rounded border border-border-subtle bg-elevated px-3 py-2 text-xs text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none disabled:opacity-50"
        />
      )}

      {sessionId && (
        <div className="flex items-center gap-2 text-[11px]">
          <span className="text-text-muted">Session: {sessionId.slice(0, 8)}</span>
          {currentStage && (
            <span className="rounded-full border border-accent/30 bg-accent/10 px-2 py-0.5 text-accent">
              {STAGE_LABELS[currentStage] || currentStage}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
