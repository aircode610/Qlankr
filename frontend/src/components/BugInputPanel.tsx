import { useCallback, useEffect, useState } from 'react';
import {
  Bug, Play, Loader2, ChevronDown, ChevronUp, X, AlertTriangle,
} from '@/lib/lucide-icons';
import { getIntegrations } from '../services/api';
import type { BugReportRequest, BugSeverity, IntegrationStatus } from '../services/types';

interface BugInputPanelProps {
  onSubmit: (req: BugReportRequest, enabledIntegrations: string[]) => void;
  analyzing: boolean;
}

const SEVERITIES: { value: BugSeverity; label: string; dot: string }[] = [
  { value: 'critical', label: 'Critical', dot: 'bg-red-400' },
  { value: 'major',    label: 'Major',    dot: 'bg-amber-400' },
  { value: 'minor',    label: 'Minor',    dot: 'bg-yellow-400' },
  { value: 'trivial',  label: 'Trivial',  dot: 'bg-emerald-400' },
];

const JIRA_PATTERN = /^[A-Z]+-\d+$/;
const INTEGRATION_ORDER = ['jira', 'notion', 'confluence', 'grafana', 'kibana', 'postman'] as const;

function chipStyle(s: IntegrationStatus | undefined, enabled: boolean): string {
  if (!s || !s.configured)
    return 'border-border-subtle bg-elevated/30 text-text-muted opacity-40 cursor-not-allowed';
  if (!enabled)
    return 'border-border-subtle bg-elevated text-text-muted cursor-pointer hover:border-accent/40 hover:text-text-secondary';
  if (s.healthy)
    return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400 cursor-pointer';
  return 'border-amber-500/40 bg-amber-500/10 text-amber-400 cursor-pointer';
}

function dotColor(s: IntegrationStatus | undefined, enabled: boolean): string {
  if (!s || !s.configured) return 'bg-slate-600/50';
  if (!enabled) return 'bg-text-muted/40';
  if (s.healthy) return 'bg-emerald-400';
  return 'bg-amber-400';
}

export const BugInputPanel = ({ onSubmit, analyzing }: BugInputPanelProps) => {
  const [description, setDescription]       = useState('');
  const [environment, setEnvironment]       = useState('');
  const [severity, setSeverity]             = useState<BugSeverity | ''>('');
  const [repoUrl, setRepoUrl]               = useState('');
  const [jiraTicket, setJiraTicket]         = useState('');
  const [jiraError, setJiraError]           = useState(false);
  const [attachmentInput, setAttachmentInput] = useState('');
  const [attachments, setAttachments]       = useState<string[]>([]);
  const [showOptional, setShowOptional]     = useState(false);

  const [integrations, setIntegrations]               = useState<IntegrationStatus[] | null>(null);
  const [enabledIntegrations, setEnabledIntegrations] = useState<Set<string>>(new Set());

  useEffect(() => {
    getIntegrations()
      .then((list) => {
        setIntegrations(list);
        setEnabledIntegrations(new Set(list.filter((i) => i.configured && i.healthy).map((i) => i.name)));
      })
      .catch(() => setIntegrations([]));
  }, []);

  const toggleIntegration = useCallback((name: string) => {
    const s = integrations?.find((i) => i.name === name);
    if (!s?.configured) return;
    setEnabledIntegrations((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  }, [integrations]);

  const handleJiraChange = (val: string) => {
    setJiraTicket(val);
    setJiraError(val.length > 0 && !JIRA_PATTERN.test(val));
  };

  const addAttachment = () => {
    const t = attachmentInput.trim();
    if (t && !attachments.includes(t)) {
      setAttachments((p) => [...p, t]);
      setAttachmentInput('');
    }
  };

  const canSubmit = description.trim().length > 0 && !jiraError && !analyzing;

  const handleSubmit = () => {
    if (!canSubmit) return;
    const req: BugReportRequest = { description: description.trim() };
    if (environment.trim()) req.environment = environment.trim();
    if (severity)           req.severity    = severity;
    if (repoUrl.trim())     req.repo_url    = repoUrl.trim();
    if (jiraTicket.trim())  req.jira_ticket = jiraTicket.trim();
    if (attachments.length) req.attachments = attachments;
    onSubmit(req, Array.from(enabledIntegrations));
  };

  const integrationMap = new Map(integrations?.map((i) => [i.name, i]) ?? []);

  return (
    <div className="flex h-full items-start justify-center overflow-y-auto bg-void py-10">
      <div className="w-full max-w-xl px-6">

        {/* Header */}
        <div className="mb-7 text-center">
          <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl border border-red-500/25 bg-red-500/10">
            <Bug className="h-5 w-5 text-red-400" />
          </div>
          <h2 className="text-sm font-semibold text-text-primary">Report a Bug</h2>
          <p className="mt-1 text-xs text-text-muted">
            Describe the issue and the agent will research, reproduce, and document it.
          </p>
        </div>

        {/* Description — the main field, always visible and spacious */}
        <div className="mb-4 rounded-xl border border-border-default bg-elevated p-4 focus-within:border-accent/40 transition-colors">
          <label className="mb-2 block text-[10px] font-semibold uppercase tracking-wider text-text-muted">
            Bug Description <span className="text-red-400">*</span>
          </label>
          <textarea
            placeholder={
              "Describe what happened, when, and how to reproduce it.\n\nExample:\n" +
              "• Players can't save after the 2.4 patch on iOS\n" +
              "• The save button shows a spinner then silently fails\n" +
              "• Reproducible 100% on iOS 17.4, works fine on Android"
            }
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={analyzing}
            rows={8}
            className="w-full resize-none bg-transparent text-xs leading-relaxed text-text-primary placeholder:text-text-muted/60 focus:outline-none disabled:opacity-50"
          />
        </div>

        {/* Quick fields row: environment + severity */}
        <div className="mb-3 grid grid-cols-2 gap-2.5">
          <input
            type="text"
            placeholder="Environment (e.g. iOS 17.4)"
            value={environment}
            onChange={(e) => setEnvironment(e.target.value)}
            disabled={analyzing}
            className="rounded-lg border border-border-subtle bg-elevated/50 px-3 py-2 text-xs text-text-primary placeholder:text-text-muted focus:border-accent/40 focus:outline-none disabled:opacity-50"
          />
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value as BugSeverity | '')}
            disabled={analyzing}
            className="rounded-lg border border-border-subtle bg-elevated/50 px-3 py-2 text-xs text-text-primary focus:border-accent/40 focus:outline-none disabled:opacity-50"
          >
            <option value="">Severity (optional)</option>
            {SEVERITIES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>

        {/* Optional fields toggle */}
        <button
          onClick={() => setShowOptional(!showOptional)}
          className="mb-3 flex items-center gap-1.5 text-[11px] text-text-muted transition-colors hover:text-text-secondary"
        >
          {showOptional
            ? <ChevronUp className="h-3 w-3" />
            : <ChevronDown className="h-3 w-3" />}
          {showOptional ? 'Fewer options' : 'More options (repo, Jira, attachments)'}
        </button>

        {showOptional && (
          <div className="mb-3 flex flex-col gap-2.5">
            {/* Repository URL */}
            <input
              type="text"
              placeholder="Repository URL (e.g. https://github.com/org/repo)"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              disabled={analyzing}
              className="rounded-lg border border-border-subtle bg-elevated/50 px-3 py-2 text-xs text-text-primary placeholder:text-text-muted focus:border-accent/40 focus:outline-none disabled:opacity-50"
            />

            {/* Jira ticket */}
            <div>
              <input
                type="text"
                placeholder="Related Jira ticket (e.g. QA-456)"
                value={jiraTicket}
                onChange={(e) => handleJiraChange(e.target.value)}
                disabled={analyzing}
                className={`w-full rounded-lg border bg-elevated/50 px-3 py-2 text-xs text-text-primary placeholder:text-text-muted focus:outline-none disabled:opacity-50 ${
                  jiraError
                    ? 'border-red-500/50 focus:border-red-500/70'
                    : 'border-border-subtle focus:border-accent/40'
                }`}
              />
              {jiraError && (
                <p className="mt-1 flex items-center gap-1 text-[10px] text-red-400">
                  <AlertTriangle className="h-2.5 w-2.5" />
                  Format: PROJECT-123
                </p>
              )}
            </div>

            {/* Attachments */}
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="HAR file path or URL"
                value={attachmentInput}
                onChange={(e) => setAttachmentInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addAttachment()}
                disabled={analyzing}
                className="flex-1 rounded-lg border border-border-subtle bg-elevated/50 px-3 py-2 text-xs text-text-primary placeholder:text-text-muted focus:border-accent/40 focus:outline-none disabled:opacity-50"
              />
              <button
                onClick={addAttachment}
                disabled={!attachmentInput.trim() || analyzing}
                className="shrink-0 rounded-lg border border-border-subtle bg-elevated px-3 py-2 text-xs text-text-muted hover:text-text-primary disabled:opacity-40"
              >
                Add
              </button>
            </div>
            {attachments.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {attachments.map((a) => (
                  <span key={a} className="flex items-center gap-1 rounded-md border border-border-subtle bg-elevated px-2 py-1 text-[10px] text-text-muted">
                    <span className="max-w-[200px] truncate">{a}</span>
                    <button
                      onClick={() => setAttachments((p) => p.filter((x) => x !== a))}
                      className="shrink-0 hover:text-red-400"
                    >
                      <X className="h-2.5 w-2.5" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Integration selector */}
        {integrations !== null && (
          <div className="mb-4 rounded-xl border border-border-subtle bg-elevated/40 p-3.5">
            <p className="mb-2.5 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              Tools for this run
            </p>
            <div className="flex flex-wrap gap-1.5">
              {INTEGRATION_ORDER.map((name) => {
                const s = integrationMap.get(name);
                const enabled = enabledIntegrations.has(name);
                return (
                  <button
                    key={name}
                    onClick={() => toggleIntegration(name)}
                    disabled={!s?.configured || analyzing}
                    title={
                      !s?.configured
                        ? `${name} not configured — add credentials in Settings`
                        : enabled ? `Disable ${name} for this run` : `Enable ${name}`
                    }
                    className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] font-medium capitalize transition-all ${chipStyle(s, enabled)}`}
                  >
                    <span className={`h-1.5 w-1.5 rounded-full ${dotColor(s, enabled)}`} />
                    {name}
                  </button>
                );
              })}
              {/* Sniffer — always on */}
              <span className="flex items-center gap-1.5 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                sniffer
              </span>
            </div>
          </div>
        )}

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent py-2.5 text-sm font-medium text-white shadow-[0_0_16px_rgba(124,58,237,0.25)] transition-all hover:bg-accent-dim disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
        >
          {analyzing ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Analyzing…
            </>
          ) : (
            <>
              <Play className="h-4 w-4" />
              Analyze Bug
            </>
          )}
        </button>
      </div>
    </div>
  );
};
