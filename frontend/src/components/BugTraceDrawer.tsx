import { useEffect, useRef, useState } from 'react';
import {
  Loader2, CheckCircle, XCircle, Circle, PauseCircle, ChevronDown, ChevronRight, Bug,
} from '@/lib/lucide-icons';

export type BugStage =
  | 'triage'
  | 'mechanics_analysis'
  | 'reproduction_planning'
  | 'research'
  | 'report_generation';

export type StageStatus = 'pending' | 'running' | 'checkpoint' | 'completed' | 'error';

export interface BugStageInfo {
  stage: BugStage;
  status: StageStatus;
  toolCalls: { tool: string; summary: string }[];
}

interface BugTraceDrawerProps {
  stages: BugStageInfo[];
  analyzing: boolean;
  currentStage: BugStage | null;
}

const STAGE_LABELS: Record<BugStage, string> = {
  triage:               'Triage',
  mechanics_analysis:   'Mechanics Analysis',
  reproduction_planning:'Reproduction Planning',
  research:             'Research',
  report_generation:    'Report Generation',
};

const STAGE_ORDER: BugStage[] = [
  'triage',
  'mechanics_analysis',
  'reproduction_planning',
  'research',
  'report_generation',
];

function StatusIcon({ status }: { status: StageStatus }) {
  switch (status) {
    case 'running':
      return <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />;
    case 'checkpoint':
      return <PauseCircle className="h-3.5 w-3.5 text-amber-400" />;
    case 'completed':
      return <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />;
    case 'error':
      return <XCircle className="h-3.5 w-3.5 text-red-400" />;
    default:
      return <Circle className="h-3.5 w-3.5 text-text-muted opacity-40" />;
  }
}

function StageRow({ info, isActive }: { info: BugStageInfo; isActive: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const rowRef = useRef<HTMLDivElement>(null);
  const canExpand = info.status === 'running' || info.status === 'completed' || info.status === 'checkpoint';

  useEffect(() => {
    if (isActive) {
      rowRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [isActive]);

  const rowBg =
    info.status === 'running'    ? 'border-accent/30 bg-accent/5' :
    info.status === 'completed'  ? 'border-emerald-500/20 bg-emerald-500/5' :
    info.status === 'checkpoint' ? 'border-amber-500/20 bg-amber-500/5' :
    info.status === 'error'      ? 'border-red-500/20 bg-red-500/5' :
                                   'border-border-subtle bg-elevated/30';

  return (
    <div ref={rowRef} className="flex flex-col gap-0">
      <button
        className={`flex w-full items-center gap-2.5 rounded border px-2.5 py-2 text-left transition-colors ${rowBg} ${canExpand ? 'cursor-pointer' : 'cursor-default'}`}
        onClick={() => canExpand && setExpanded(v => !v)}
        disabled={!canExpand}
      >
        <StatusIcon status={info.status} />
        <span className={`flex-1 text-xs font-medium ${info.status === 'pending' ? 'text-text-muted' : 'text-text-primary'}`}>
          {STAGE_LABELS[info.stage]}
        </span>
        {info.toolCalls.length > 0 && (
          <span className="text-[10px] text-text-muted">{info.toolCalls.length} call{info.toolCalls.length !== 1 ? 's' : ''}</span>
        )}
        {canExpand && (
          expanded
            ? <ChevronDown className="h-3 w-3 text-text-muted" />
            : <ChevronRight className="h-3 w-3 text-text-muted" />
        )}
      </button>

      {expanded && info.toolCalls.length > 0 && (
        <div className="ml-4 mt-1 flex flex-col gap-1 border-l border-border-subtle pl-3">
          {info.toolCalls.map((call, i) => (
            <div key={i} className="rounded border border-border-subtle bg-elevated/60 px-2.5 py-2">
              <div className="flex items-start gap-2">
                <CheckCircle className="mt-0.5 h-3 w-3 shrink-0 text-emerald-500" />
                <div className="min-w-0 flex-1">
                  <span className="block font-mono text-[11px] font-medium text-accent">{call.tool}</span>
                  {call.summary && (
                    <span className="mt-0.5 block text-[11px] leading-relaxed text-text-muted">{call.summary}</span>
                  )}
                </div>
                <span className="shrink-0 text-[9px] text-text-muted">{i + 1}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export const BugTraceDrawer = ({ stages, analyzing, currentStage }: BugTraceDrawerProps) => {
  const stageMap = new Map(stages.map(s => [s.stage, s]));
  const totalCalls = stages.reduce((sum, s) => sum + s.toolCalls.length, 0);

  const rows: BugStageInfo[] = STAGE_ORDER.map(stage =>
    stageMap.get(stage) ?? { stage, status: 'pending', toolCalls: [] }
  );

  return (
    <div className="flex h-full flex-col bg-surface">
      {/* Header */}
      <div className="shrink-0 border-b border-border-subtle px-3 py-2.5">
        <div className="flex items-center gap-2.5 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2">
          <div className="rounded bg-red-500/10 p-1">
            <Bug className="h-3.5 w-3.5 text-red-400" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-red-400">Bug Reproduction</p>
            {currentStage && (
              <p className="text-[10px] text-text-muted">{STAGE_LABELS[currentStage]}</p>
            )}
          </div>
          {analyzing && <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-red-400" />}
          {!analyzing && totalCalls > 0 && <CheckCircle className="h-3.5 w-3.5 shrink-0 text-emerald-400" />}
        </div>
      </div>

      {/* Stage list */}
      <div className="scrollbar-thin flex-1 overflow-y-auto p-2">
        <div className="flex flex-col gap-1.5">
          {rows.map(info => (
            <StageRow
              key={info.stage}
              info={info}
              isActive={info.stage === currentStage}
            />
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="shrink-0 border-t border-border-subtle px-3 py-1.5 text-[10px] text-text-muted">
        {totalCalls} total tool call{totalCalls !== 1 ? 's' : ''}
      </div>
    </div>
  );
};
