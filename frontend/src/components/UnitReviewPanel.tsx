import { useState } from 'react';
import { CheckCircle, RefreshCw, Send, ChevronDown, ChevronRight, Code } from '@/lib/lucide-icons';
import type { CheckpointData } from '../services/types';

interface UnitReviewPanelProps {
  checkpoint: CheckpointData;
  onApprove: () => void;
  onRefine: (feedback: string) => void;
}

const PRIORITY_STYLES: Record<string, string> = {
  high: 'border-orange-500/40 bg-orange-500/10 text-orange-400',
  medium: 'border-yellow-500/40 bg-yellow-500/10 text-yellow-400',
  low: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400',
};

export const UnitReviewPanel = ({ checkpoint, onApprove, onRefine }: UnitReviewPanelProps) => {
  const [feedback, setFeedback] = useState('');
  const [expandedComponents, setExpandedComponents] = useState<Set<number>>(new Set([0]));

  const intermediate = checkpoint.payload?.intermediate_result as {
    pr_metadata?: { title?: string };
    affected_components?: Array<{
      component: string;
      files_changed: string[];
      unit_tests: Array<{
        target: string;
        priority: string;
        mocks_needed?: string[];
        test_cases: Array<{ name: string; scenario: string; expected: string }>;
      }>;
    }>;
  } | undefined;

  const components = intermediate?.affected_components ?? [];
  const prTitle = intermediate?.pr_metadata?.title ?? '';

  const toggleComponent = (i: number) => {
    setExpandedComponents((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  const totalTests = components.reduce(
    (sum, c) => sum + c.unit_tests.reduce((s, u) => s + u.test_cases.length, 0),
    0,
  );

  return (
    <div className="flex h-full flex-col bg-surface">
      {/* Header */}
      <div className="border-b border-border-subtle bg-elevated/50 px-5 py-3">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-amber-400" />
          <span className="text-sm font-medium text-text-primary">Unit Tests — Review</span>
        </div>
        {prTitle && <p className="mt-1 text-[11px] text-text-muted">{prTitle}</p>}
        <p className="mt-1 text-[11px] text-text-muted">
          {components.length} component{components.length !== 1 ? 's' : ''} · {totalTests} test case{totalTests !== 1 ? 's' : ''}
        </p>
      </div>

      {/* Unit test results */}
      <div className="scrollbar-thin flex-1 overflow-y-auto p-4">
        {components.length === 0 ? (
          <p className="py-8 text-center text-xs text-text-muted">No unit tests generated</p>
        ) : (
          <div className="flex flex-col gap-3">
            {components.map((comp, ci) => (
              <div key={ci} className="rounded-lg border border-border-default bg-elevated">
                <button
                  onClick={() => toggleComponent(ci)}
                  className="flex w-full items-center gap-2 px-4 py-3 text-left"
                >
                  {expandedComponents.has(ci) ? (
                    <ChevronDown className="h-3.5 w-3.5 text-text-muted" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5 text-text-muted" />
                  )}
                  <span className="flex-1 text-xs font-medium text-text-primary">{comp.component}</span>
                  <span className="text-[10px] text-text-muted">
                    {comp.unit_tests.length} spec{comp.unit_tests.length !== 1 ? 's' : ''}
                  </span>
                </button>

                {expandedComponents.has(ci) && (
                  <div className="border-t border-border-subtle px-4 pb-3 pt-2">
                    {comp.files_changed.length > 0 && (
                      <div className="mb-2 flex flex-wrap gap-1">
                        {comp.files_changed.map((f, i) => (
                          <span key={i} className="font-mono text-[10px] text-text-muted">{f}</span>
                        ))}
                      </div>
                    )}

                    <div className="flex flex-col gap-2">
                      {comp.unit_tests.map((spec, si) => {
                        const pStyle = PRIORITY_STYLES[spec.priority?.toLowerCase()] || PRIORITY_STYLES.medium;
                        return (
                          <div key={si} className="rounded border border-border-subtle bg-deep">
                            <div className="flex items-center gap-2 px-3 py-2">
                              <Code className="h-3 w-3 text-accent" />
                              <span className="flex-1 font-mono text-[11px] text-text-primary">{spec.target}</span>
                              <span className={`rounded border px-1.5 py-0.5 text-[9px] font-medium ${pStyle}`}>
                                {spec.priority}
                              </span>
                            </div>
                            <div className="border-t border-border-subtle px-3 pb-2 pt-1.5">
                              {spec.mocks_needed && spec.mocks_needed.length > 0 && (
                                <div className="mb-1.5 flex flex-wrap gap-1">
                                  {spec.mocks_needed.map((m, i) => (
                                    <span key={i} className="rounded bg-border-subtle px-1.5 py-0.5 font-mono text-[9px] text-text-muted">
                                      mock: {m}
                                    </span>
                                  ))}
                                </div>
                              )}
                              {spec.test_cases.map((tc, ti) => (
                                <div key={ti} className="mb-1 rounded bg-elevated/50 px-2 py-1.5">
                                  <p className="font-mono text-[10px] font-medium text-text-primary">{tc.name}</p>
                                  <p className="text-[10px] text-text-muted">{tc.scenario}</p>
                                  <p className="text-[10px] text-emerald-400">→ {tc.expected}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Action bar — sticky bottom */}
      <div className="border-t border-border-subtle bg-elevated/50 px-4 py-3">
        {/* Feedback input */}
        <div className="mb-3 flex gap-2">
          <input
            type="text"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && feedback.trim()) onRefine(feedback.trim());
            }}
            placeholder="Feedback to refine tests…"
            className="flex-1 rounded-lg border border-border-subtle bg-deep px-3 py-2 text-xs text-text-primary placeholder:text-text-muted focus:border-accent/40 focus:outline-none"
          />
          <button
            onClick={() => feedback.trim() && onRefine(feedback.trim())}
            disabled={!feedback.trim()}
            className="flex items-center gap-1.5 rounded-lg border border-border-subtle bg-elevated px-3 py-2 text-xs text-text-secondary transition-colors hover:bg-hover hover:text-text-primary disabled:opacity-40"
          >
            <RefreshCw className="h-3 w-3" />
            Refine
          </button>
        </div>

        {/* Approve button */}
        <button
          onClick={onApprove}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-500/20 px-4 py-2.5 text-sm font-medium text-emerald-400 transition-colors hover:bg-emerald-500/30"
        >
          <CheckCircle className="h-4 w-4" />
          Approve & Choose Next Stage
        </button>
      </div>
    </div>
  );
};
