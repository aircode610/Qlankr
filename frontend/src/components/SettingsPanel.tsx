import { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Send } from '@/lib/lucide-icons';
import { getIntegrations, updateIntegration } from '../services/api';
import type { IntegrationStatus } from '../services/types';

const INTEGRATION_ORDER = [
  'jira',
  'notion',
  'confluence',
  'grafana',
  'kibana',
  'postman',
] as const;

const FIELD_PRESETS: Record<string, { label: string; key: string; secret?: boolean }[]> = {
  jira: [
    { label: 'Jira URL', key: 'JIRA_URL' },
    { label: 'Email', key: 'JIRA_EMAIL' },
    { label: 'API token', key: 'JIRA_API_TOKEN', secret: true },
    { label: 'Project', key: 'JIRA_PROJECT_KEY' },
  ],
  notion: [{ label: 'API key', key: 'NOTION_API_KEY', secret: true }, { label: 'Workspace', key: 'NOTION_WORKSPACE_ID' }],
  confluence: [
    { label: 'Confluence URL', key: 'CONFLUENCE_URL' },
    { label: 'Token', key: 'CONFLUENCE_TOKEN', secret: true },
    { label: 'Space', key: 'CONFLUENCE_SPACE_KEY' },
  ],
  grafana: [
    { label: 'Grafana URL', key: 'GRAFANA_URL' },
    { label: 'API key', key: 'GRAFANA_API_KEY', secret: true },
  ],
  kibana: [
    { label: 'Kibana URL', key: 'KIBANA_URL' },
    { label: 'Token', key: 'KIBANA_TOKEN', secret: true },
  ],
  postman: [
    { label: 'API key', key: 'POSTMAN_API_KEY', secret: true },
    { label: 'Workspace', key: 'POSTMAN_WORKSPACE_ID' },
  ],
};

function statusColor(s: IntegrationStatus) {
  if (!s.configured) return 'bg-slate-500/40';
  if (s.healthy) return 'bg-emerald-500/80';
  return 'bg-amber-500/80';
}

function statusLabel(s: IntegrationStatus) {
  if (!s.configured) return 'Not configured';
  if (s.healthy) return 'Connected';
  return 'Unhealthy';
}

type Row = (typeof INTEGRATION_ORDER)[number];

export const SettingsPanel = () => {
  const [list, setList] = useState<IntegrationStatus[] | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState<Record<string, Record<string, string>>>({});

  const fieldsBy = useMemo(() => FIELD_PRESETS, []);

  const load = useCallback(async () => {
    setLoadErr(null);
    try {
      const rows = await getIntegrations();
      setList(rows);
    } catch (e) {
      setLoadErr((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onField = (name: string, key: string, v: string) => {
    setDirty((d) => ({
      ...d,
      [name]: { ...(d[name] || {}), [key]: v },
    }));
  };

  const testOne = async (name: string) => {
    const creds = dirty[name];
    if (!creds || Object.keys(creds).length === 0) {
      setLoadErr('Add at least one credential to test this integration.');
      return;
    }
    setSaving(true);
    setLoadErr(null);
    try {
      await updateIntegration(name, creds);
      await load();
    } catch (e) {
      setLoadErr((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const saveAll = async () => {
    const names = Object.keys(dirty);
    if (names.length === 0) {
      return;
    }
    setSaving(true);
    setLoadErr(null);
    try {
      for (const n of names) {
        if (Object.keys(dirty[n]).length) {
          await updateIntegration(n, dirty[n]);
        }
      }
      setDirty({});
      await load();
    } catch (e) {
      setLoadErr((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  if (!list) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center bg-void">
        <div className="flex items-center gap-2 text-text-muted">
          {loadErr ? <span className="text-amber-400">{loadErr}</span> : <><Loader2 className="h-4 w-4 animate-spin" />Loading integrations…</>}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-auto bg-void p-6">
      <div className="mx-auto w-full max-w-3xl">
        <h1 className="mb-1 text-lg font-semibold text-text-primary">Integrations</h1>
        <p className="mb-6 text-sm text-text-muted">
          Credentials are stored in this browser session and applied on the server process for health checks. Use Test connection per tool or Save all for a batch.
        </p>
        {loadErr && <div className="mb-4 rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">{loadErr}</div>}

        <div className="mb-4 flex justify-end">
          <button
            type="button"
            disabled={saving || Object.keys(dirty).length === 0}
            onClick={() => void saveAll()}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-dim disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save all'}
          </button>
        </div>

        <div className="flex flex-col gap-4">
          {INTEGRATION_ORDER.map((id) => {
            const s = list.find((x) => x.name === id) || { name: id, configured: false, healthy: false, message: '' };
            return (
              <div
                key={id}
                className="rounded-xl border border-border-subtle bg-elevated p-4 shadow-glow/30"
              >
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 rounded-full ${statusColor(s)}`} title={s.message} />
                    <span className="text-sm font-medium capitalize text-text-primary">{id}</span>
                  </div>
                  <span className="text-xs text-text-muted">
                    {statusLabel(s)} {s.message ? `— ${s.message}` : ''}
                  </span>
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {(fieldsBy as Record<string, { label: string; key: string; secret?: boolean }[]>) [id].map(
                    (f) => (
                      <label key={f.key} className="text-xs text-text-secondary">
                        <span className="mb-0.5 block text-[10px] uppercase tracking-wider text-text-muted">{f.label}</span>
                        <input
                          className="w-full rounded border border-border-subtle bg-surface px-2 py-1.5 text-sm text-text-primary"
                          type={f.secret ? 'password' : 'text'}
                          autoComplete="off"
                          placeholder="•••"
                          onChange={(e) => onField(id, f.key, e.target.value)}
                        />
                      </label>
                    )
                  )}
                </div>
                <div className="mt-3 flex justify-end">
                  <button
                    type="button"
                    onClick={() => void testOne(id as Row)}
                    className="flex items-center gap-1.5 rounded border border-border-subtle bg-surface px-3 py-1.5 text-xs text-text-primary hover:bg-hover"
                    disabled={saving}
                  >
                    <Send className="h-3.5 w-3.5" />
                    Test connection
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
