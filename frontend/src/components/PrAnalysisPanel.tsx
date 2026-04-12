import { useState } from 'react';
import {
  GitPullRequest, Code2, Layers, Map,
  Loader2, CheckCircle, MessageSquare, ChevronDown, ChevronUp,
} from '@/lib/lucide-icons';
import type { WorkflowId } from '../services/types';

interface WorkflowDef {
  id: WorkflowId;
  title: string;
  description: string;
  Icon: React.ElementType;
  // full literal class strings so Tailwind scans them
  cardActive: string;
  iconBox: string;
  iconColor: string;
  runBtn: string;
  bar: string;
}

const WORKFLOWS: WorkflowDef[] = [
  {
    id: 'unit_tests',
    title: 'Unit Tests',
    description: 'Generate test specs for changed components and functions',
    Icon: Code2,
    cardActive: 'border-violet-500/40 bg-violet-500/5',
    iconBox: 'bg-violet-500/15',
    iconColor: 'text-violet-400',
    runBtn: 'border-violet-500/40 bg-violet-500/10 text-violet-400 hover:bg-violet-500/20',
    bar: 'bg-violet-500',
  },
  {
    id: 'integration_tests',
    title: 'Integration Tests',
    description: 'Map cross-module integration points and test scenarios',
    Icon: Layers,
    cardActive: 'border-cyan-500/40 bg-cyan-500/5',
    iconBox: 'bg-cyan-500/15',
    iconColor: 'text-cyan-400',
    runBtn: 'border-cyan-500/40 bg-cyan-500/10 text-cyan-400 hover:bg-cyan-500/20',
    bar: 'bg-cyan-500',
  },
  {
    id: 'e2e_planning',
    title: 'E2E Planning',
    description: 'Trace user journeys and plan end-to-end test scenarios',
    Icon: Map,
    cardActive: 'border-emerald-500/40 bg-emerald-500/5',
    iconBox: 'bg-emerald-500/15',
    iconColor: 'text-emerald-400',
    runBtn: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20',
    bar: 'bg-emerald-500',
  },
];

interface PrAnalysisPanelProps {
  onAnalyze: (prUrl: string, context: string | null, workflow: WorkflowId) => void;
  analyzing: boolean;
  activeWorkflow: WorkflowId | null;
  disabled: boolean;
}

export const PrAnalysisPanel = ({ onAnalyze, analyzing, activeWorkflow, disabled }: PrAnalysisPanelProps) => {
  const [prUrl, setPrUrl] = useState('');
  const [context, setContext] = useState('');
  const [showContext, setShowContext] = useState(false);

  const isValidPr = /\/pull\/\d+/.test(prUrl);
  const canRun = isValidPr && !disabled && !analyzing;

  return (
    <div className="flex flex-col gap-3">
      {/* PR URL input */}
      <div className={`flex items-center gap-2.5 rounded-xl border bg-elevated/50 px-3 py-2.5 transition-all ${
        isValidPr ? 'border-accent/40 shadow-[0_0_0_2px_rgba(124,58,237,0.08)]' : 'border-border-subtle focus-within:border-accent/30'
      }`}>
        <GitPullRequest className="h-3.5 w-3.5 shrink-0 text-text-muted" />
        <input
          type="text"
          placeholder="GitHub PR URL"
          value={prUrl}
          onChange={(e) => setPrUrl(e.target.value)}
          disabled={analyzing}
          className="flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-muted focus:outline-none disabled:opacity-50"
        />
        {isValidPr && <CheckCircle className="h-3 w-3 shrink-0 text-emerald-400" />}
      </div>

      {/* Optional context */}
      <button
        onClick={() => setShowContext(!showContext)}
        className="flex items-center gap-1.5 text-[11px] text-text-muted transition-colors hover:text-text-secondary"
      >
        <MessageSquare className="h-3 w-3" />
        {showContext ? 'Hide context' : 'Add bug report / context'}
        {showContext ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>

      {showContext && (
        <textarea
          placeholder="Describe a bug or scenario to focus the analysis..."
          value={context}
          onChange={(e) => setContext(e.target.value)}
          disabled={analyzing}
          rows={2}
          className="resize-none rounded-lg border border-border-subtle bg-elevated/50 px-3 py-2 text-xs text-text-primary placeholder:text-text-muted focus:border-accent/40 focus:outline-none disabled:opacity-50"
        />
      )}

      {/* Workflow cards */}
      <div className="flex flex-col gap-2">
        <p className="text-[10px] font-medium tracking-wide text-text-muted uppercase">Choose a workflow</p>
        {WORKFLOWS.map((wf) => {
          const isRunning = analyzing && activeWorkflow === wf.id;
          const isDone = !analyzing && activeWorkflow === wf.id;

          return (
            <div
              key={wf.id}
              className={`group rounded-xl border transition-all duration-200 ${
                isRunning
                  ? wf.cardActive
                  : isDone
                    ? `${wf.cardActive} opacity-60`
                    : 'border-border-subtle bg-elevated/20 hover:border-border-default hover:bg-elevated/50'
              }`}
            >
              <div className="flex items-center gap-3 px-3 py-2.5">
                {/* Icon */}
                <div className={`shrink-0 rounded-lg p-1.5 transition-colors ${
                  isRunning || isDone ? wf.iconBox : 'bg-border-subtle group-hover:bg-elevated'
                }`}>
                  <wf.Icon className={`h-4 w-4 transition-colors ${
                    isRunning || isDone ? wf.iconColor : 'text-text-muted group-hover:text-text-secondary'
                  }`} />
                </div>

                {/* Text */}
                <div className="min-w-0 flex-1">
                  <p className={`text-xs font-medium transition-colors ${
                    isRunning || isDone ? 'text-text-primary' : 'text-text-secondary group-hover:text-text-primary'
                  }`}>
                    {wf.title}
                  </p>
                  <p className="truncate text-[10px] leading-relaxed text-text-muted">{wf.description}</p>
                </div>

                {/* Action button */}
                {isRunning ? (
                  <div className={`shrink-0 rounded-lg border px-2.5 py-1 text-xs ${wf.runBtn}`}>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  </div>
                ) : isDone ? (
                  <CheckCircle className={`h-4 w-4 shrink-0 ${wf.iconColor}`} />
                ) : (
                  <button
                    onClick={() => onAnalyze(prUrl, context || null, wf.id)}
                    disabled={!canRun}
                    className={`shrink-0 rounded-lg border px-2.5 py-1 text-xs font-medium transition-all ${wf.runBtn} opacity-0 group-hover:opacity-100 disabled:pointer-events-none disabled:opacity-0`}
                  >
                    Run
                  </button>
                )}
              </div>

              {/* Running progress bar */}
              {isRunning && (
                <div className="mx-3 mb-2.5 h-0.5 overflow-hidden rounded-full bg-border-subtle">
                  <div className={`h-full w-1/3 animate-[slide_1.5s_ease-in-out_infinite] rounded-full ${wf.bar}`} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
