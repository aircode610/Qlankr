import { useEffect, useRef } from 'react';
import { Loader2, Zap, CheckCircle, Code2, Layers, Map } from '@/lib/lucide-icons';
import type { AnalysisStage, WorkflowId } from '../services/types';

interface AgentStep {
  tool: string;
  summary: string;
  stage: AnalysisStage | null;
}

interface AgentTraceDrawerProps {
  steps: AgentStep[];
  analyzing: boolean;
  activeWorkflow: WorkflowId | null;
  currentStage: AnalysisStage | null;
}

const WORKFLOW_META: Record<WorkflowId, { label: string; Icon: React.ElementType; color: string; bg: string }> = {
  unit_tests:        { label: 'Unit Tests',         Icon: Code2,   color: 'text-violet-400', bg: 'bg-violet-500/10 border-violet-500/30' },
  integration_tests: { label: 'Integration Tests',  Icon: Layers,  color: 'text-cyan-400',   bg: 'bg-cyan-500/10 border-cyan-500/30'     },
  e2e_planning:      { label: 'E2E Planning',        Icon: Map,     color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/30' },
};

const STAGE_LABELS: Record<AnalysisStage, string> = {
  gathering: 'Gathering context',
  unit_testing: 'Writing unit tests',
  integration_testing: 'Integration analysis',
  e2e_planning: 'E2E planning',
  submitting: 'Submitting',
};

export const AgentTraceDrawer = ({ steps, analyzing, activeWorkflow, currentStage }: AgentTraceDrawerProps) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [steps.length]);

  const meta = activeWorkflow ? WORKFLOW_META[activeWorkflow] : null;

  return (
    <div className="flex h-full flex-col bg-surface">
      {/* Workflow header */}
      {meta && (
        <div className="shrink-0 border-b border-border-subtle px-3 py-2.5">
          <div className={`flex items-center gap-2.5 rounded-lg border px-3 py-2 ${meta.bg}`}>
            <div className={`rounded p-1 ${meta.bg}`}>
              <meta.Icon className={`h-3.5 w-3.5 ${meta.color}`} />
            </div>
            <div className="min-w-0 flex-1">
              <p className={`text-xs font-medium ${meta.color}`}>{meta.label}</p>
              {currentStage && (
                <p className="text-[10px] text-text-muted">{STAGE_LABELS[currentStage]}</p>
              )}
            </div>
            {analyzing && <Loader2 className={`h-3.5 w-3.5 shrink-0 animate-spin ${meta.color}`} />}
            {!analyzing && steps.length > 0 && <CheckCircle className="h-3.5 w-3.5 shrink-0 text-emerald-400" />}
          </div>
        </div>
      )}

      {/* Step log */}
      <div className="scrollbar-thin flex-1 overflow-y-auto p-2">
        {steps.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
            <Zap className="h-6 w-6 text-text-muted opacity-40" />
            <p className="text-xs text-text-muted">
              {activeWorkflow ? 'Starting workflow…' : 'Select a workflow to run'}
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {steps.map((step, i) => (
              <div key={i} className="rounded border border-border-subtle bg-elevated/60 px-2.5 py-2">
                <div className="flex items-start gap-2">
                  <CheckCircle className="mt-0.5 h-3 w-3 shrink-0 text-emerald-500" />
                  <div className="min-w-0 flex-1">
                    <span className="block font-mono text-[11px] font-medium text-accent">{step.tool}</span>
                    <span className="mt-0.5 block text-[11px] leading-relaxed text-text-muted">{step.summary}</span>
                  </div>
                  <span className="shrink-0 text-[9px] text-text-muted">{i + 1}</span>
                </div>
              </div>
            ))}
            {analyzing && (
              <div className="flex items-center gap-2 rounded border border-accent/20 bg-accent/5 px-2.5 py-2">
                <Loader2 className="h-3 w-3 animate-spin text-accent" />
                <span className="text-xs text-accent">
                  {currentStage ? STAGE_LABELS[currentStage] : 'Processing'}…
                </span>
              </div>
            )}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {steps.length > 0 && (
        <div className="shrink-0 border-t border-border-subtle px-3 py-1.5 text-[10px] text-text-muted">
          {steps.length} tool call{steps.length !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
};
