import { useState } from 'react';
import {
  CheckCircle, AlertTriangle, Copy, Download, FileText,
  ExternalLink, ChevronDown, ChevronRight, Loader2,
} from '@/lib/lucide-icons';
import { exportBugReport } from '../services/api';
import type { BugReport, BugSeverity, Confidence3, ResearchFindings } from '../services/types';

// ── Severity + confidence styling ────────────────────────────────────────────

const SEVERITY_STYLES: Record<BugSeverity, string> = {
  critical: 'border-red-500/40 bg-red-500/10 text-red-400',
  major:    'border-amber-500/40 bg-amber-500/10 text-amber-400',
  minor:    'border-yellow-500/40 bg-yellow-500/10 text-yellow-400',
  trivial:  'border-emerald-500/40 bg-emerald-500/10 text-emerald-400',
};

const CONFIDENCE_STYLES: Record<Confidence3, string> = {
  high:   'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
  medium: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
  low:    'border-red-500/30 bg-red-500/10 text-red-400',
};

// ── Download helper ───────────────────────────────────────────────────────────

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(url); }, 100);
}

// ── Copy helper ───────────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <button
      onClick={copy}
      className="ml-auto shrink-0 rounded p-1 text-text-muted transition-colors hover:text-text-secondary"
      title="Copy to clipboard"
    >
      {copied ? <CheckCircle className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({
  title,
  children,
  copyText,
  defaultOpen = true,
}: {
  title: string;
  children: React.ReactNode;
  copyText?: string;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-lg border border-border-subtle bg-elevated">
      <button
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <ChevronDown className="h-3.5 w-3.5 shrink-0 text-text-muted" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0 text-text-muted" />}
        <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary">{title}</span>
        {copyText && open && <CopyButton text={copyText} />}
      </button>
      {open && (
        <div className="border-t border-border-subtle px-4 pb-4 pt-3">
          {children}
        </div>
      )}
    </div>
  );
}

// ── Evidence tabs (inline, no ResearchPanel dependency) ──────────────────────

const LEVEL_COLORS: Record<string, string> = {
  error:   'border-red-500/30 bg-red-500/10 text-red-400',
  warn:    'border-amber-500/30 bg-amber-500/10 text-amber-400',
  warning: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
  info:    'border-blue-500/30 bg-blue-500/10 text-blue-400',
  debug:   'border-border-subtle bg-elevated text-text-muted',
};

type EvidenceTab = 'logs' | 'docs' | 'issues';

function EvidenceSection({ evidence }: { evidence: ResearchFindings }) {
  const [tab, setTab] = useState<EvidenceTab>('logs');

  const tabs: { id: EvidenceTab; label: string; count: number }[] = [
    { id: 'logs',   label: 'Logs',   count: evidence.log_entries?.length ?? 0 },
    { id: 'docs',   label: 'Docs',   count: evidence.doc_references?.length ?? 0 },
    { id: 'issues', label: 'Issues', count: evidence.related_issues?.length ?? 0 },
  ];

  return (
    <div className="flex flex-col">
      {/* Tab bar */}
      <div className="flex gap-0 border-b border-border-subtle">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 border-b-2 px-3 pb-2 text-xs transition-colors ${
              tab === t.id
                ? 'border-accent text-text-primary'
                : 'border-transparent text-text-muted hover:text-text-secondary'
            }`}
          >
            {t.label}
            {t.count > 0 && (
              <span className={`rounded px-1 py-0.5 text-[9px] font-medium ${
                tab === t.id ? 'bg-accent/20 text-accent' : 'bg-elevated text-text-muted'
              }`}>
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="scrollbar-thin mt-3 flex max-h-60 flex-col gap-1.5 overflow-y-auto">
        {tab === 'logs' && (
          evidence.log_entries?.length > 0 ? evidence.log_entries.map((e, i) => (
            <div key={i} className="rounded border border-border-subtle bg-elevated/60 px-3 py-2">
              <div className="mb-1 flex items-center gap-2">
                {e.level && (
                  <span className={`rounded border px-1.5 py-0.5 font-mono text-[9px] font-medium uppercase ${LEVEL_COLORS[(e.level ?? '').toLowerCase()] ?? LEVEL_COLORS.debug}`}>
                    {e.level}
                  </span>
                )}
                {e.source && <span className="text-[10px] text-text-muted">{e.source}</span>}
                {e.timestamp && <span className="ml-auto font-mono text-[10px] text-text-muted">{e.timestamp}</span>}
              </div>
              <p className="font-mono text-[11px] leading-relaxed text-text-primary">{e.message}</p>
            </div>
          )) : <p className="py-4 text-center text-xs text-text-muted">No log entries</p>
        )}
        {tab === 'docs' && (
          evidence.doc_references?.length > 0 ? evidence.doc_references.map((d, i) => (
            <div key={i} className="rounded border border-border-subtle bg-elevated/60 px-3 py-2.5">
              <div className="mb-1 flex items-start justify-between gap-2">
                <span className="text-xs font-medium text-text-primary">{d.title}</span>
                {d.url && (
                  <a href={d.url} target="_blank" rel="noopener noreferrer" className="shrink-0 font-mono text-[10px] text-accent hover:underline">
                    link ↗
                  </a>
                )}
              </div>
              {d.snippet && <p className="line-clamp-3 text-[11px] leading-relaxed text-text-muted">{d.snippet}</p>}
            </div>
          )) : <p className="py-4 text-center text-xs text-text-muted">No documentation references</p>
        )}
        {tab === 'issues' && (
          evidence.related_issues?.length > 0 ? evidence.related_issues.map((iss, i) => (
            <div key={i} className="rounded border border-border-subtle bg-elevated/60 px-3 py-2.5">
              <div className="flex items-start gap-2">
                <span className="shrink-0 font-mono text-[10px] text-accent">{iss.key}</span>
                <span className="flex-1 text-xs font-medium text-text-primary">{iss.summary}</span>
                <span className="shrink-0 rounded border border-border-subtle bg-deep px-1.5 py-0.5 text-[10px] text-text-muted">
                  {iss.status}
                </span>
              </div>
              {iss.url && (
                <a href={iss.url} target="_blank" rel="noopener noreferrer"
                  className="mt-1 block font-mono text-[10px] text-accent hover:underline">
                  {iss.url}
                </a>
              )}
            </div>
          )) : <p className="py-4 text-center text-xs text-text-muted">No related issues</p>
        )}
      </div>
    </div>
  );
}

// ── Props ────────────────────────────────────────────────────────────────────

interface BugReportViewProps {
  report: BugReport;
  sessionId: string;
}

// ── Main component ────────────────────────────────────────────────────────────

export const BugReportView = ({ report, sessionId }: BugReportViewProps) => {
  const [exporting, setExporting] = useState<'markdown' | 'pdf' | 'jira' | null>(null);
  const [jiraUrl, setJiraUrl] = useState<string | null>(report.jira_url ?? null);

  const handleExport = async (format: 'markdown' | 'pdf') => {
    setExporting(format);
    try {
      const blob = await exportBugReport(sessionId, format);
      const ext = format === 'pdf' ? 'pdf' : 'md';
      const title = report.title.replace(/[^a-z0-9]+/gi, '-').toLowerCase();
      downloadBlob(blob, `bug-report-${title}.${ext}`);
    } catch (e) {
      console.error('Export failed:', e);
    } finally {
      setExporting(null);
    }
  };

  const stepsText = report.reproduction_steps
    .map((s, i) => `${i + 1}. ${s.action}\n   Expected: ${s.expected}`)
    .join('\n');

  return (
    <div className="flex h-full flex-col overflow-hidden bg-void">
      {/* Scrollable content */}
      <div className="scrollbar-thin flex-1 overflow-y-auto p-4">
        <div className="mx-auto flex max-w-3xl flex-col gap-3">

          {/* Header card */}
          <div className="rounded-xl border border-border-default bg-surface p-4">
            <div className="mb-2 flex flex-wrap items-start gap-2">
              <h1 className="flex-1 text-sm font-semibold leading-snug text-text-primary">
                {report.title}
              </h1>
              <span className={`shrink-0 rounded border px-2 py-0.5 text-[11px] font-medium capitalize ${SEVERITY_STYLES[report.severity] ?? SEVERITY_STYLES.minor}`}>
                {report.severity}
              </span>
              <span className={`shrink-0 rounded border px-2 py-0.5 text-[11px] font-medium capitalize ${CONFIDENCE_STYLES[report.confidence] ?? CONFIDENCE_STYLES.low}`}>
                {report.confidence} confidence
              </span>
            </div>
            <div className="flex flex-wrap gap-3 text-[11px] text-text-muted">
              {report.category && (
                <span className="rounded border border-border-subtle bg-elevated px-2 py-0.5 font-mono text-accent">
                  {report.category}
                </span>
              )}
              {report.environment && (
                <span>{report.environment}</span>
              )}
              {jiraUrl && (
                <a href={jiraUrl} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-1 text-accent hover:underline">
                  <ExternalLink className="h-3 w-3" /> Jira issue ↗
                </a>
              )}
            </div>
          </div>

          {/* Reproduction steps */}
          <Section title="Reproduction Steps" copyText={stepsText}>
            <ol className="flex flex-col gap-3">
              {report.reproduction_steps.map((step, i) => (
                <li key={i} className="flex gap-3">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-accent/30 bg-accent/10 text-[10px] font-bold text-accent">
                    {i + 1}
                  </span>
                  <div className="flex-1 pt-0.5">
                    <p className="text-xs text-text-primary">{step.action}</p>
                    {step.expected && (
                      <p className="mt-1 text-[11px] text-emerald-400">
                        Expected: {step.expected}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </Section>

          {/* Expected vs Actual */}
          <Section
            title="Expected vs Actual"
            copyText={`Expected:\n${report.expected_behavior}\n\nActual:\n${report.actual_behavior}`}
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="rounded border border-emerald-500/30 bg-emerald-500/5 p-3">
                <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-400">Expected</p>
                <p className="text-xs leading-relaxed text-text-secondary">{report.expected_behavior}</p>
              </div>
              <div className="rounded border border-red-500/30 bg-red-500/5 p-3">
                <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-red-400">Actual</p>
                <p className="text-xs leading-relaxed text-text-secondary">{report.actual_behavior}</p>
              </div>
            </div>
          </Section>

          {/* Root cause analysis */}
          <Section title="Root Cause Analysis" copyText={report.root_cause_analysis}>
            <p className="whitespace-pre-wrap text-xs leading-relaxed text-text-secondary">
              {report.root_cause_analysis}
            </p>
          </Section>

          {/* Evidence */}
          {report.evidence && (
            <Section title="Evidence">
              <EvidenceSection evidence={report.evidence} />
            </Section>
          )}

          {/* Affected components */}
          {report.affected_components?.length > 0 && (
            <Section title="Affected Components" defaultOpen={false}>
              <div className="flex flex-col gap-2">
                {report.affected_components.map((c, i) => (
                  <div key={i} className="rounded border border-border-subtle bg-elevated/60 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <span className="flex-1 text-xs font-medium text-text-primary">{c.component}</span>
                      <span className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${CONFIDENCE_STYLES[c.confidence] ?? CONFIDENCE_STYLES.low}`}>
                        {c.confidence}
                      </span>
                    </div>
                    {c.impact_summary && (
                      <p className="mt-1 text-[11px] text-text-muted">{c.impact_summary}</p>
                    )}
                    {c.files_changed?.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {c.files_changed.map((f) => (
                          <span key={f} className="rounded border border-border-subtle bg-deep px-1.5 py-0.5 font-mono text-[10px] text-text-muted">
                            {f}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Recommendations */}
          {report.recommendations?.length > 0 && (
            <Section
              title="Recommendations"
              copyText={report.recommendations.map((r, i) => `${i + 1}. ${r}`).join('\n')}
              defaultOpen={false}
            >
              <ul className="flex flex-col gap-2">
                {report.recommendations.map((r, i) => (
                  <li key={i} className="flex gap-2 text-xs">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
                    <span className="leading-relaxed text-text-secondary">{r}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {/* Bottom padding */}
          <div className="h-4" />
        </div>
      </div>

      {/* Action bar */}
      <div className="shrink-0 border-t border-border-subtle bg-surface px-4 py-3">
        <div className="mx-auto flex max-w-3xl flex-wrap gap-2">
          <button
            onClick={() => handleExport('markdown')}
            disabled={!!exporting}
            className="flex items-center gap-1.5 rounded-lg border border-border-subtle bg-elevated px-3 py-1.5 text-xs text-text-secondary transition-colors hover:bg-hover hover:text-text-primary disabled:opacity-50"
          >
            {exporting === 'markdown' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileText className="h-3.5 w-3.5" />}
            Export Markdown
          </button>

          <button
            onClick={() => handleExport('pdf')}
            disabled={!!exporting}
            className="flex items-center gap-1.5 rounded-lg border border-border-subtle bg-elevated px-3 py-1.5 text-xs text-text-secondary transition-colors hover:bg-hover hover:text-text-primary disabled:opacity-50"
          >
            {exporting === 'pdf' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
            Export PDF
          </button>

          {!jiraUrl && (
            <button
              onClick={async () => {
                setExporting('jira');
                try {
                  const resp = await fetch(
                    `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/bug-report/${encodeURIComponent(sessionId)}/export`,
                    {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ format: 'markdown', push_to_jira: true }),
                    },
                  );
                  if (resp.ok) {
                    const data = await resp.json().catch(() => null);
                    if (data?.jira_url) setJiraUrl(data.jira_url);
                  }
                } catch { /* ignore */ } finally { setExporting(null); }
              }}
              disabled={!!exporting}
              className="flex items-center gap-1.5 rounded-lg bg-accent/20 px-3 py-1.5 text-xs font-medium text-accent transition-colors hover:bg-accent/30 disabled:opacity-50"
            >
              {exporting === 'jira' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ExternalLink className="h-3.5 w-3.5" />}
              Push to Jira
            </button>
          )}

          {jiraUrl && (
            <a
              href={jiraUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-400 hover:bg-emerald-500/20"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              View in Jira ↗
            </a>
          )}
        </div>
      </div>
    </div>
  );
};
