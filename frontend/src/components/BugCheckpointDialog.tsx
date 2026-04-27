import { useState } from 'react';
import { X, CheckCircle, MessageSquare, RefreshCw, AlertTriangle } from '@/lib/lucide-icons';
import type { CheckpointData } from '../services/types';

// ── Typed shapes for intermediate_result ─────────────────────────────────────

interface MechanicsResult {
  affected_components: string[];
  root_cause_hypotheses: Array<{
    hypothesis: string;
    confidence: string;
    evidence: string;
  }>;
  code_paths: Array<{
    path: string;
    description: string;
    confidence: string;
  }>;
}

interface ResearchResult {
  sources_queried: string[];
  sources_with_results: string[];
  related_issues_count: number;
  log_entries_count: number;
  doc_references_count: number;
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface BugCheckpointDialogProps {
  checkpoint: CheckpointData;
  /** Mechanics: action is 'approve' | 'refine' (+ feedback).
   *  Research:  action is 'approve' | 'add_context' (+ context). */
  onContinue: (response: Record<string, string>) => void;
  onDismiss: () => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const CONFIDENCE_COLORS: Record<string, string> = {
  high:   'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  medium: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  low:    'bg-red-500/15 text-red-400 border-red-500/30',
};

function ConfidenceBadge({ value }: { value: string }) {
  const cls = CONFIDENCE_COLORS[value.toLowerCase()] ?? CONFIDENCE_COLORS.low;
  return (
    <span className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${cls}`}>
      {value}
    </span>
  );
}

// ── Post-mechanics body ───────────────────────────────────────────────────────

function MechanicsBody({ result }: { result: MechanicsResult }) {
  return (
    <div className="space-y-4">
      {/* Affected components */}
      {result.affected_components.length > 0 && (
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-text-muted">
            Affected components
          </p>
          <div className="flex flex-wrap gap-1.5">
            {result.affected_components.map((c) => (
              <span
                key={c}
                className="rounded border border-accent/30 bg-accent/10 px-2 py-0.5 font-mono text-[11px] text-accent"
              >
                {c}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Root cause hypotheses */}
      {result.root_cause_hypotheses.length > 0 && (
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-text-muted">
            Root cause hypotheses
          </p>
          <div className="space-y-2">
            {result.root_cause_hypotheses.map((h, i) => (
              <div
                key={i}
                className="rounded border border-border-subtle bg-deep px-3 py-2.5"
              >
                <div className="mb-1.5 flex items-start justify-between gap-2">
                  <span className="text-xs leading-relaxed text-text-primary">{h.hypothesis}</span>
                  <ConfidenceBadge value={h.confidence} />
                </div>
                {h.evidence && (
                  <p className="text-[11px] leading-relaxed text-text-muted line-clamp-2">
                    {h.evidence}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Post-research body ────────────────────────────────────────────────────────

function ResearchBody({ result }: { result: ResearchResult }) {
  const allSources = result.sources_queried;
  const withResults = new Set(result.sources_with_results);
  const evidenceItems = [
    { label: 'Log entries',      count: result.log_entries_count },
    { label: 'Doc references',   count: result.doc_references_count },
    { label: 'Related issues',   count: result.related_issues_count },
  ];
  const totalEvidence =
    result.log_entries_count + result.doc_references_count + result.related_issues_count;

  return (
    <div className="space-y-4">
      {/* Sources */}
      <div>
        <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-text-muted">
          Sources queried
        </p>
        {allSources.length === 0 ? (
          <p className="text-xs text-text-muted">No external sources were queried.</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {allSources.map((s) => {
              const hit = withResults.has(s);
              return (
                <span
                  key={s}
                  className={`flex items-center gap-1 rounded border px-2 py-0.5 text-[11px] ${
                    hit
                      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                      : 'border-border-subtle bg-elevated text-text-muted'
                  }`}
                >
                  {hit ? (
                    <CheckCircle className="h-2.5 w-2.5" />
                  ) : (
                    <span className="h-2.5 w-2.5 text-center leading-none">—</span>
                  )}
                  {s}
                </span>
              );
            })}
          </div>
        )}
      </div>

      {/* Evidence counts */}
      <div>
        <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-text-muted">
          Evidence collected
        </p>
        {totalEvidence === 0 ? (
          <div className="flex items-center gap-2 rounded border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-400">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            No external evidence found — report will rely on code analysis only.
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-2">
            {evidenceItems.map(({ label, count }) => (
              <div
                key={label}
                className="rounded border border-border-subtle bg-deep px-3 py-2 text-center"
              >
                <p className="text-lg font-semibold text-text-primary">{count}</p>
                <p className="text-[10px] text-text-muted">{label}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export const BugCheckpointDialog = ({ checkpoint, onContinue, onDismiss }: BugCheckpointDialogProps) => {
  const [inputText, setInputText] = useState('');
  const [showInput, setShowInput] = useState(false);

  const checkpointType = checkpoint.payload?.type as string | undefined;
  const isMechanics = checkpointType === 'checkpoint_mechanics';
  const result = checkpoint.payload?.intermediate_result as MechanicsResult | ResearchResult | undefined;

  const secondaryLabel = isMechanics ? 'Refine' : 'Add Context';
  const secondaryPlaceholder = isMechanics
    ? 'Describe what to investigate further or correct…'
    : 'Add context, logs, or additional details for the research stage…';

  function handleSecondary() {
    if (!showInput) {
      setShowInput(true);
      return;
    }
    if (isMechanics) {
      onContinue({ action: 'refine', feedback: inputText });
    } else {
      onContinue({ action: 'add_context', context: inputText });
    }
  }

  return (
    <div className="flex h-full flex-col bg-surface">

      {/* Header */}
      <div className="shrink-0 flex items-center justify-between border-b border-border-subtle bg-elevated/50 px-5 py-4">
        <div className="flex items-center gap-2.5">
          <div className="h-2 w-2 animate-pulse rounded-full bg-amber-400" />
          <span className="text-sm font-medium text-text-primary">
            {isMechanics ? 'Mechanics Review' : 'Research Review'}
          </span>
          <span className="rounded border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-400">
            Awaiting approval
          </span>
        </div>
        <button
          onClick={onDismiss}
          title="Dismiss checkpoint (pipeline stays paused)"
          className="rounded p-1 text-text-muted transition-colors hover:bg-hover hover:text-text-primary"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Body */}
      <div className="scrollbar-thin flex-1 overflow-y-auto px-5 py-5">
        {result && isMechanics && (
          <MechanicsBody result={result as MechanicsResult} />
        )}
        {result && !isMechanics && (
          <ResearchBody result={result as ResearchResult} />
        )}

        {/* Refine / Add Context textarea */}
        {showInput && (
          <div className="mt-5">
            <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              {isMechanics ? 'Refinement feedback' : 'Additional context'}
            </label>
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder={secondaryPlaceholder}
              rows={4}
              className="w-full rounded-lg border border-border-subtle bg-deep px-3 py-2.5 text-xs leading-relaxed text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
              autoFocus
            />
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="shrink-0 flex flex-wrap gap-2 border-t border-border-subtle bg-elevated/50 px-5 py-4">
        <button
          onClick={() => onContinue({ action: 'approve' })}
          className="flex items-center gap-2 rounded-lg bg-emerald-500/20 px-4 py-2 text-sm font-medium text-emerald-400 transition-colors hover:bg-emerald-500/30"
        >
          <CheckCircle className="h-4 w-4" />
          Approve &amp; Continue
        </button>

        <button
          onClick={handleSecondary}
          className="flex items-center gap-2 rounded-lg bg-accent/20 px-4 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/30"
        >
          <MessageSquare className="h-4 w-4" />
          {showInput ? `Submit ${secondaryLabel}` : secondaryLabel}
        </button>

        {showInput && (
          <button
            onClick={() => { setShowInput(false); setInputText(''); }}
            className="flex items-center gap-2 rounded-lg border border-border-subtle bg-elevated px-4 py-2 text-sm text-text-secondary transition-colors hover:bg-hover hover:text-text-primary"
          >
            <RefreshCw className="h-4 w-4" />
            Cancel
          </button>
        )}
      </div>
    </div>
  );
};
