import { useEffect, useRef } from 'react';
import { Loader2, Zap, CheckCircle } from '@/lib/lucide-icons';
import type { AnalysisStage } from '../services/types';

interface AgentStep {
  tool: string;
  summary: string;
  stage: AnalysisStage | null;
}

interface AgentTraceDrawerProps {
  steps: AgentStep[];
  analyzing: boolean;
  currentStage: AnalysisStage | null;
}

const STAGES: AnalysisStage[] = ['gathering', 'unit_testing', 'integration_testing', 'e2e_planning', 'submitting'];

const STAGE_LABELS: Record<AnalysisStage, string> = {
  gathering: 'Gather Context',
  unit_testing: 'Unit Tests',
  integration_testing: 'Integration',
  e2e_planning: 'E2E Planning',
  submitting: 'Submit',
};

const stageIndex = (stage: AnalysisStage | null): number =>
  stage ? STAGES.indexOf(stage) : -1;

export const AgentTraceDrawer = ({ steps, analyzing, currentStage }: AgentTraceDrawerProps) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [steps.length]);

  const currentIdx = stageIndex(currentStage);

  return (
    <div className="flex h-full flex-col bg-surface">
      {/* Stage progress bar */}
      <div className="border-b border-border-subtle px-3 py-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-medium text-text-secondary">Pipeline Stages</span>
          {analyzing && <Loader2 className="h-3 w-3 animate-spin text-accent" />}
        </div>
        <div className="flex gap-1">
          {STAGES.map((stage, i) => {
            const done = i < currentIdx;
            const active = i === currentIdx;
            return (
              <div key={stage} className="flex flex-1 flex-col items-center gap-1">
                <div
                  className={`h-1.5 w-full rounded-full transition-all duration-500 ${
                    done ? 'bg-emerald-500' : active ? 'bg-accent animate-pulse' : 'bg-border-subtle'
                  }`}
                />
                <span className={`text-[9px] text-center ${active ? 'text-accent' : done ? 'text-emerald-500' : 'text-text-muted'}`}>
                  {STAGE_LABELS[stage]}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Step log */}
      <div className="scrollbar-thin flex-1 overflow-y-auto p-2">
        {steps.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
            <Zap className="h-6 w-6 text-text-muted opacity-40" />
            <p className="text-xs text-text-muted">Agent steps will appear here</p>
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {steps.map((step, i) => (
              <div key={i} className="animate-fade-in rounded border border-border-subtle bg-elevated/60 px-2.5 py-2">
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
        <div className="border-t border-border-subtle px-3 py-1.5 text-[10px] text-text-muted">
          {steps.length} tool call{steps.length !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
};
