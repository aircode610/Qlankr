import { useState } from 'react';
import { CheckCircle, AlertTriangle, MessageSquare, RefreshCw } from '@/lib/lucide-icons';
import type { CheckpointData } from '../services/types';

// ── Data shapes ───────────────────────────────────────────────────────────────

interface LogEntry {
  timestamp?: string;
  level?: string;
  message: string;
  source?: string;
}

interface DocReference {
  title: string;
  url?: string;
  excerpt?: string;
}

interface RelatedIssue {
  id?: string;
  title: string;
  url?: string;
  status?: string;
  relevance?: string;
}

interface NetworkTrace {
  url?: string;
  method?: string;
  status_code?: number;
  error?: string;
}

interface ResearchFindings {
  log_entries: LogEntry[];
  doc_references: DocReference[];
  related_issues: RelatedIssue[];
  network_traces: NetworkTrace[];
  sources_queried: string[];
  sources_with_results: string[];
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface ResearchPanelProps {
  checkpoint: CheckpointData;
  onApprove: () => void;
  onAddContext: (context: string) => void;
}

// ── Tab types ─────────────────────────────────────────────────────────────────

type Tab = 'logs' | 'docs' | 'issues' | 'network';

const LEVEL_COLORS: Record<string, string> = {
  error:   'text-red-400 bg-red-500/10 border-red-500/30',
  warn:    'text-amber-400 bg-amber-500/10 border-amber-500/30',
  warning: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
  info:    'text-blue-400 bg-blue-500/10 border-blue-500/30',
  debug:   'text-text-muted bg-elevated border-border-subtle',
};

function levelStyle(level?: string) {
  return LEVEL_COLORS[(level ?? '').toLowerCase()] ?? LEVEL_COLORS.debug;
}

// ── Tab panels ────────────────────────────────────────────────────────────────

function LogsTab({ entries }: { entries: LogEntry[] }) {
  if (entries.length === 0) {
    return <EmptyState message="No log entries found" />;
  }
  return (
    <div className="flex flex-col gap-1.5">
      {entries.map((entry, i) => (
        <div key={i} className="rounded border border-border-subtle bg-elevated px-3 py-2">
          <div className="mb-1 flex items-center gap-2">
            {entry.level && (
              <span className={`rounded border px-1.5 py-0.5 font-mono text-[9px] font-medium uppercase ${levelStyle(entry.level)}`}>
                {entry.level}
              </span>
            )}
            {entry.source && (
              <span className="text-[10px] text-text-muted">{entry.source}</span>
            )}
            {entry.timestamp && (
              <span className="ml-auto font-mono text-[10px] text-text-muted">{entry.timestamp}</span>
            )}
          </div>
          <p className="font-mono text-[11px] leading-relaxed text-text-primary">{entry.message}</p>
        </div>
      ))}
    </div>
  );
}

function DocsTab({ refs }: { refs: DocReference[] }) {
  if (refs.length === 0) {
    return <EmptyState message="No documentation references found" />;
  }
  return (
    <div className="flex flex-col gap-2">
      {refs.map((doc, i) => (
        <div key={i} className="rounded border border-border-subtle bg-elevated px-3 py-2.5">
          <div className="mb-1 flex items-start justify-between gap-2">
            <span className="text-xs font-medium text-text-primary">{doc.title}</span>
            {doc.url && (
              <a
                href={doc.url}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 font-mono text-[10px] text-accent hover:underline"
              >
                link ↗
              </a>
            )}
          </div>
          {doc.excerpt && (
            <p className="text-[11px] leading-relaxed text-text-muted line-clamp-3">{doc.excerpt}</p>
          )}
        </div>
      ))}
    </div>
  );
}

function IssuesTab({ issues }: { issues: RelatedIssue[] }) {
  if (issues.length === 0) {
    return <EmptyState message="No related issues found" />;
  }
  return (
    <div className="flex flex-col gap-2">
      {issues.map((issue, i) => (
        <div key={i} className="rounded border border-border-subtle bg-elevated px-3 py-2.5">
          <div className="mb-1 flex items-start gap-2">
            {issue.id && (
              <span className="shrink-0 font-mono text-[10px] text-accent">{issue.id}</span>
            )}
            <span className="flex-1 text-xs font-medium text-text-primary">{issue.title}</span>
            {issue.status && (
              <span className="shrink-0 rounded border border-border-subtle bg-deep px-1.5 py-0.5 text-[10px] text-text-muted">
                {issue.status}
              </span>
            )}
          </div>
          {issue.relevance && (
            <p className="text-[11px] leading-relaxed text-text-muted">{issue.relevance}</p>
          )}
          {issue.url && (
            <a
              href={issue.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 block font-mono text-[10px] text-accent hover:underline"
            >
              {issue.url}
            </a>
          )}
        </div>
      ))}
    </div>
  );
}

function NetworkTab({ traces }: { traces: NetworkTrace[] }) {
  if (traces.length === 0) {
    return <EmptyState message="No network traces captured" />;
  }
  return (
    <div className="flex flex-col gap-1.5">
      {traces.map((trace, i) => {
        const isError = trace.status_code ? trace.status_code >= 400 : !!trace.error;
        return (
          <div
            key={i}
            className={`rounded border px-3 py-2 ${
              isError
                ? 'border-red-500/30 bg-red-500/5'
                : 'border-border-subtle bg-elevated'
            }`}
          >
            <div className="flex items-center gap-2">
              {trace.method && (
                <span className="font-mono text-[10px] font-bold text-accent">{trace.method}</span>
              )}
              {trace.status_code !== undefined && (
                <span className={`font-mono text-[10px] font-medium ${isError ? 'text-red-400' : 'text-emerald-400'}`}>
                  {trace.status_code}
                </span>
              )}
              {trace.url && (
                <span className="flex-1 truncate font-mono text-[11px] text-text-muted">{trace.url}</span>
              )}
            </div>
            {trace.error && (
              <p className="mt-1 font-mono text-[10px] text-red-400">{trace.error}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 rounded border border-border-subtle bg-elevated/30 px-3 py-6">
      <p className="w-full text-center text-xs text-text-muted">{message}</p>
    </div>
  );
}

// ── Sources bar ───────────────────────────────────────────────────────────────

function SourcesBar({ queried, withResults }: { queried: string[]; withResults: string[] }) {
  if (queried.length === 0) return null;
  const hitSet = new Set(withResults);
  return (
    <div className="flex flex-wrap gap-1.5 px-5 py-2.5 border-b border-border-subtle">
      {queried.map((s) => {
        const hit = hitSet.has(s);
        return (
          <span
            key={s}
            className={`flex items-center gap-1 rounded border px-2 py-0.5 text-[11px] ${
              hit
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                : 'border-border-subtle bg-elevated text-text-muted'
            }`}
          >
            {hit ? <CheckCircle className="h-2.5 w-2.5" /> : <span className="h-2.5 w-2.5 text-center leading-none">—</span>}
            {s}
          </span>
        );
      })}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export const ResearchPanel = ({ checkpoint, onApprove, onAddContext }: ResearchPanelProps) => {
  const [activeTab, setActiveTab] = useState<Tab>('logs');
  const [context, setContext] = useState('');
  const [showContext, setShowContext] = useState(false);

  const findings = (checkpoint.payload?.intermediate_result ?? {}) as Partial<ResearchFindings>;
  const logEntries   = findings.log_entries    ?? [];
  const docRefs      = findings.doc_references  ?? [];
  const issues       = findings.related_issues  ?? [];
  const netTraces    = findings.network_traces   ?? [];
  const queried      = findings.sources_queried  ?? [];
  const withResults  = findings.sources_with_results ?? [];

  const totalEvidence = logEntries.length + docRefs.length + issues.length + netTraces.length;

  const tabs: { id: Tab; label: string; count: number }[] = [
    { id: 'logs',    label: 'Logs',    count: logEntries.length },
    { id: 'docs',    label: 'Docs',    count: docRefs.length    },
    { id: 'issues',  label: 'Issues',  count: issues.length     },
    { id: 'network', label: 'Network', count: netTraces.length  },
  ];

  return (
    <div className="flex h-full flex-col bg-surface">
      {/* Header */}
      <div className="shrink-0 border-b border-border-subtle bg-elevated/50 px-5 py-3">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 animate-pulse rounded-full bg-amber-400" />
          <span className="text-sm font-medium text-text-primary">Research Review</span>
        </div>
        <p className="mt-1 text-[11px] text-text-muted">
          {queried.length} source{queried.length !== 1 ? 's' : ''} queried
          {totalEvidence > 0 ? ` · ${totalEvidence} evidence item${totalEvidence !== 1 ? 's' : ''}` : ''}
        </p>
      </div>

      {/* Sources bar */}
      <SourcesBar queried={queried} withResults={withResults} />

      {/* No-evidence warning */}
      {totalEvidence === 0 && (
        <div className="mx-4 mt-3 flex items-center gap-2 rounded border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-400">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          No external evidence found — report will rely on code analysis only.
        </div>
      )}

      {/* Tabs */}
      <div className="shrink-0 flex gap-0 border-b border-border-subtle px-4 pt-3">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 border-b-2 px-3 pb-2 text-xs transition-colors ${
              activeTab === tab.id
                ? 'border-accent text-text-primary'
                : 'border-transparent text-text-muted hover:text-text-secondary'
            }`}
          >
            {tab.label}
            {tab.count > 0 && (
              <span className={`rounded px-1 py-0.5 text-[9px] font-medium ${
                activeTab === tab.id ? 'bg-accent/20 text-accent' : 'bg-elevated text-text-muted'
              }`}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="scrollbar-thin flex-1 overflow-y-auto p-4">
        {activeTab === 'logs'    && <LogsTab    entries={logEntries} />}
        {activeTab === 'docs'    && <DocsTab    refs={docRefs}       />}
        {activeTab === 'issues'  && <IssuesTab  issues={issues}      />}
        {activeTab === 'network' && <NetworkTab traces={netTraces}   />}
      </div>

      {/* Action bar */}
      <div className="shrink-0 border-t border-border-subtle bg-elevated/50 px-4 py-3">
        {showContext && (
          <div className="mb-3">
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="Add context, logs, or additional details for the research stage…"
              rows={3}
              autoFocus
              className="w-full rounded border border-border-subtle bg-deep px-3 py-2 text-xs text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
            />
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <button
            onClick={onApprove}
            className="flex items-center gap-2 rounded-lg bg-emerald-500/20 px-4 py-2 text-sm font-medium text-emerald-400 transition-colors hover:bg-emerald-500/30"
          >
            <CheckCircle className="h-4 w-4" />
            Approve &amp; Continue
          </button>

          {showContext ? (
            <>
              <button
                onClick={() => { if (context.trim()) onAddContext(context.trim()); }}
                disabled={!context.trim()}
                className="flex items-center gap-2 rounded-lg bg-accent/20 px-4 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/30 disabled:opacity-40"
              >
                <MessageSquare className="h-4 w-4" />
                Submit Context
              </button>
              <button
                onClick={() => { setShowContext(false); setContext(''); }}
                className="flex items-center gap-2 rounded-lg border border-border-subtle bg-elevated px-4 py-2 text-sm text-text-secondary transition-colors hover:bg-hover hover:text-text-primary"
              >
                <RefreshCw className="h-4 w-4" />
                Cancel
              </button>
            </>
          ) : (
            <button
              onClick={() => setShowContext(true)}
              className="flex items-center gap-2 rounded-lg bg-accent/20 px-4 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/30"
            >
              <MessageSquare className="h-4 w-4" />
              Add Context
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
