/**
 * Qlankr API layer — TypeScript rewrite.
 *
 * Endpoints:
 * - POST /index    (SSE: index_step, index_done, error)
 * - POST /analyze  (SSE: agent_step, stage_change, checkpoint, result, error)
 * - POST /analyze/{session_id}/continue (SSE: same as analyze)
 * - GET  /graph/{owner}/{repo}
 * - POST /bug-report, /bug-report/.../continue, /bug-report/.../export, /settings/integrations
 */

import type {
  BugContinueRequest,
  BugReportRequest,
  BugCheckpointEvent,
  BugReportResultEvent,
  BugStageChangeEvent,
  IntegrationStatus,
  ResearchProgressEvent,
} from './types';
import { supabase } from "./supabase";

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new Error("Not authenticated");
  return { Authorization: `Bearer ${token}` };
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function buildUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

function safeJsonParse(value: string): unknown {
  try { return JSON.parse(value); }
  catch { return value; }
}

export interface SSEEvent {
  event: string;
  data: unknown;
}

function parseSseBlock(block: string): SSEEvent {
  const lines = block.split('\n');
  let event = 'message';
  const dataLines: string[] = [];

  for (const line of lines) {
    if (!line) continue;
    if (line.startsWith('event:')) { event = line.slice(6).trim(); continue; }
    if (line.startsWith('data:')) { dataLines.push(line.slice(5).trim()); }
  }

  return { event, data: safeJsonParse(dataLines.join('\n')) };
}

async function readErrorText(response: Response): Promise<string> {
  try {
    const text = await response.text();
    return text || `HTTP ${response.status}`;
  } catch { return `HTTP ${response.status}`; }
}

async function streamSsePost(
  path: string,
  payload: Record<string, unknown>,
  opts: { signal?: AbortSignal; onEvent?: (evt: SSEEvent) => void } = {},
): Promise<void> {
  const response = await fetch(buildUrl(path), {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(payload),
    signal: opts.signal,
  });

  if (!response.ok) throw new Error(await readErrorText(response));
  if (!response.body) throw new Error('Streaming is not available in this browser.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() || '';
    for (const block of blocks) {
      const trimmed = block.trim();
      if (!trimmed) continue;
      opts.onEvent?.(parseSseBlock(trimmed));
    }
  }
  if (buffer.trim()) opts.onEvent?.(parseSseBlock(buffer.trim()));
}

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

// ── Backend graph format (Sprint 1) ──────────────────────────────
interface BackendGraphNode {
  id: string;
  label: string;   // display name, e.g. "src/index.ts"
  type: 'file' | 'cluster';
  cluster: string;
}

interface BackendGraphEdge {
  source: string;
  target: string;
  type: string;    // "CALLS" | "IMPORTS"
}

interface BackendGraphData {
  nodes: BackendGraphNode[];
  edges: BackendGraphEdge[];
  clusters: Array<{ id: string; label: string; size: number }>;
}

// ── qlankr-shared types (subset we need here) ────────────────────
import type { GraphNode, GraphRelationship, NodeLabel } from 'qlankr-shared';

export interface NormalisedGraph {
  nodes: GraphNode[];
  relationships: GraphRelationship[];
}

/**
 * Converts the backend's simplified GraphData into the qlankr-shared
 * GraphNode / GraphRelationship format that the graph-adapter expects.
 */
function normaliseBackendGraph(raw: BackendGraphData): NormalisedGraph {
  const nodes: GraphNode[] = raw.nodes.map((n) => {
    const label: NodeLabel = n.type === 'cluster' ? 'Community' : 'File';
    return {
      id: n.id,
      label,
      properties: {
        name: n.label,
        filePath: n.id,
        communities: n.cluster ? [n.cluster] : [],
      },
    };
  });

  const relationships: GraphRelationship[] = raw.edges.map((e, i) => ({
    id: `edge_${i}_${e.source}_${e.target}`,
    sourceId: e.source,
    targetId: e.target,
    type: (e.type as GraphRelationship['type']) ?? 'CALLS',
    confidence: 1,
    reason: '',
  }));

  // Synthesise MEMBER_OF edges from the cluster field so graph-adapter
  // can colour file nodes by cluster membership.
  raw.nodes.forEach((n) => {
    if (n.type !== 'cluster' && n.cluster) {
      relationships.push({
        id: `member_of_${n.id}`,
        sourceId: n.id,
        targetId: n.cluster,
        type: 'MEMBER_OF' as GraphRelationship['type'],
        confidence: 1,
        reason: '',
      });
    }
  });

  return { nodes, relationships };
}

/** Fetch and normalise the knowledge graph for a repo */
export async function getGraph(owner: string, repo: string): Promise<NormalisedGraph> {
  const response = await fetch(buildUrl(`/graph/${owner}/${repo}`), { headers: { ...(await authHeaders()) } });
  if (!response.ok) throw new Error(await readErrorText(response));
  const raw = (await response.json()) as BackendGraphData;
  return normaliseBackendGraph(raw);
}

export interface IndexedRepoInfo {
  repo: string;      // "owner/repo"
  files: number;
  clusters: number;
  symbols: number;
}

/** List all repos already indexed on the backend */
export async function getIndexedRepos(): Promise<IndexedRepoInfo[]> {
  const response = await fetch(buildUrl('/repos'), { headers: { ...(await authHeaders()) } });
  if (!response.ok) throw new Error(await readErrorText(response));
  const j = (await response.json()) as { repos: IndexedRepoInfo[] };
  return j.repos;
}

/** Fetch file content from the indexed repo */
export async function getFileContent(owner: string, repo: string, path: string): Promise<{ path: string; content: string; language: string }> {
  const response = await fetch(buildUrl(`/file-content/${owner}/${repo}?path=${encodeURIComponent(path)}`), { headers: { ...(await authHeaders()) } });
  if (!response.ok) throw new Error(await readErrorText(response));
  return (await response.json()) as { path: string; content: string; language: string };
}

/** Index a repo — SSE stream */
export interface IndexCallbacks {
  signal?: AbortSignal;
  onEvent?: (evt: SSEEvent) => void;
  onIndexStep?: (data: { stage: string; summary: string }) => void;
  onIndexDone?: (data: { repo: string; files: number; clusters: number; symbols: number }) => void;
  onError?: (message: string) => void;
}

export async function indexRepo(
  repoUrl: string,
  opts: IndexCallbacks & { projectId?: string } = {},
): Promise<unknown> {
  let finalPayload: unknown = null;
  const body: Record<string, unknown> = { repo_url: repoUrl };
  if (opts.projectId) body.project_id = opts.projectId;
  try {
    await streamSsePost('/index', body, {
      signal: opts.signal,
      onEvent: (evt) => {
        opts.onEvent?.(evt);
        if (evt.event === 'index_step') opts.onIndexStep?.(evt.data as { stage: string; summary: string });
        else if (evt.event === 'index_done') { finalPayload = evt.data; opts.onIndexDone?.(evt.data as { repo: string; files: number; clusters: number; symbols: number }); }
        else if (evt.event === 'error') {
          const d = evt.data as { message?: string };
          opts.onError?.(d?.message || 'Indexing failed.');
        }
      },
    });
    return finalPayload;
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') throw error;
    opts.onError?.((error as Error).message || 'Indexing failed.');
    throw error;
  }
}

/** Analyze a PR — SSE stream */
export interface AnalyzeCallbacks {
  signal?: AbortSignal;
  onEvent?: (evt: SSEEvent) => void;
  onAgentStep?: (data: { tool: string; summary: string }) => void;
  onStageChange?: (data: { stage: string; summary: string }) => void;
  onCheckpoint?: (data: unknown) => void;
  onResult?: (data: unknown) => void;
  onError?: (message: string) => void;
}

export async function analyzePR(
  prUrl: string,
  context: string | null = null,
  sessionId: string | null = null,
  workflowType: string | null = null,
  opts: AnalyzeCallbacks & { projectId?: string } = {},
): Promise<unknown> {
  const body: Record<string, unknown> = { pr_url: prUrl };
  if (context) body.context = context;
  if (sessionId) body.session_id = sessionId;
  if (opts.projectId) body.project_id = opts.projectId;

  let finalPayload: unknown = null;
  try {
    await streamSsePost('/analyze', body, {
      signal: opts.signal,
      onEvent: (evt) => {
        opts.onEvent?.(evt);
        if (evt.event === 'agent_step') opts.onAgentStep?.(evt.data as { tool: string; summary: string });
        else if (evt.event === 'stage_change') opts.onStageChange?.(evt.data as { stage: string; summary: string });
        else if (evt.event === 'checkpoint') opts.onCheckpoint?.(evt.data);
        else if (evt.event === 'result') { finalPayload = evt.data; opts.onResult?.(evt.data); }
        else if (evt.event === 'error') {
          const d = evt.data as { message?: string };
          opts.onError?.(d?.message || 'Analysis failed.');
        }
      },
    });
    return finalPayload;
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') throw error;
    opts.onError?.((error as Error).message || 'Analysis failed.');
    throw error;
  }
}

/** Continue analysis after checkpoint */
export async function continueAnalysis(
  sessionId: string,
  action: 'approve' | 'add_context' | 'skip' | 'rerun',
  additionalContext: string | null = null,
  opts: AnalyzeCallbacks = {},
): Promise<unknown> {
  const body: Record<string, unknown> = { action };
  if (additionalContext) body.additional_context = additionalContext;

  let finalPayload: unknown = null;
  try {
    await streamSsePost(`/analyze/${sessionId}/continue`, body, {
      signal: opts.signal,
      onEvent: (evt) => {
        opts.onEvent?.(evt);
        if (evt.event === 'agent_step') opts.onAgentStep?.(evt.data as { tool: string; summary: string });
        else if (evt.event === 'stage_change') opts.onStageChange?.(evt.data as { stage: string; summary: string });
        else if (evt.event === 'checkpoint') opts.onCheckpoint?.(evt.data);
        else if (evt.event === 'result') { finalPayload = evt.data; opts.onResult?.(evt.data); }
        else if (evt.event === 'error') {
          const d = evt.data as { message?: string };
          opts.onError?.(d?.message || 'Analysis failed.');
        }
      },
    });
    return finalPayload;
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') throw error;
    opts.onError?.((error as Error).message || 'Continue failed.');
    throw error;
  }
}

// ── Sprint 3: bug report + settings ─────────────────────────────

export interface BugReproCallbacks {
  signal?: AbortSignal;
  onEvent?: (evt: SSEEvent) => void;
  onBugStageChange?: (d: { stage: string; summary: string }) => void;
  onBugCheckpoint?: (d: {
    session_id: string;
    stage_completed: string;
    interrupt_type: string;
    payload: Record<string, unknown>;
  }) => void;
  onResearchProgress?: (d: { source: string; finding_count: number; summary: string }) => void;
  onBugResult?: (d: { session_id: string; report: unknown; agent_steps: number }) => void;
  onError?: (message: string) => void;
}

export async function startBugReport(
  req: BugReportRequest,
  callbacks: BugReproCallbacks = {},
): Promise<void> {
  try {
    await streamSsePost(
      '/bug-report',
      { ...req } as Record<string, unknown>,
      {
        signal: callbacks.signal,
        onEvent: (evt) => {
          callbacks.onEvent?.(evt);
          if (evt.event === 'bug_stage_change') {
            const d = evt.data as BugStageChangeEvent;
            callbacks.onBugStageChange?.({ stage: d.stage, summary: d.summary });
          } else if (evt.event === 'bug_checkpoint') {
            const d = evt.data as BugCheckpointEvent;
            callbacks.onBugCheckpoint?.({
              session_id: d.session_id,
              stage_completed: d.stage_completed,
              interrupt_type: d.interrupt_type,
              payload: d.payload,
            });
          } else if (evt.event === 'research_progress') {
            const d = evt.data as ResearchProgressEvent;
            callbacks.onResearchProgress?.({
              source: d.source,
              finding_count: d.finding_count,
              summary: d.summary,
            });
          } else if (evt.event === 'bug_result') {
            const d = evt.data as BugReportResultEvent;
            callbacks.onBugResult?.({ session_id: d.session_id, report: d.report, agent_steps: d.agent_steps });
          } else if (evt.event === 'error') {
            const m = (evt.data as { message?: string })?.message || 'Bug run failed';
            callbacks.onError?.(m);
          }
        },
      },
    );
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') throw error;
    callbacks.onError?.((error as Error).message || 'Bug run failed');
    throw error;
  }
}

export async function continueBugReport(
  sessionId: string,
  req: BugContinueRequest,
  callbacks: BugReproCallbacks = {},
): Promise<void> {
  const body: Record<string, unknown> = { action: req.action };
  if (req.feedback) body.feedback = req.feedback;
  if (req.additional_context) body.additional_context = req.additional_context;
  try {
    await streamSsePost(
      `/bug-report/${encodeURIComponent(sessionId)}/continue`,
      body,
      {
        signal: callbacks.signal,
        onEvent: (evt) => {
          callbacks.onEvent?.(evt);
          if (evt.event === 'bug_stage_change') {
            const d = evt.data as BugStageChangeEvent;
            callbacks.onBugStageChange?.({ stage: d.stage, summary: d.summary });
          } else if (evt.event === 'bug_checkpoint') {
            const d = evt.data as BugCheckpointEvent;
            callbacks.onBugCheckpoint?.({
              session_id: d.session_id,
              stage_completed: d.stage_completed,
              interrupt_type: d.interrupt_type,
              payload: d.payload,
            });
          } else if (evt.event === 'research_progress') {
            const d = evt.data as ResearchProgressEvent;
            callbacks.onResearchProgress?.({
              source: d.source,
              finding_count: d.finding_count,
              summary: d.summary,
            });
          } else if (evt.event === 'bug_result') {
            const d = evt.data as BugReportResultEvent;
            callbacks.onBugResult?.({ session_id: d.session_id, report: d.report, agent_steps: d.agent_steps });
          } else if (evt.event === 'error') {
            const m = (evt.data as { message?: string })?.message || 'Continue failed';
            callbacks.onError?.(m);
          }
        },
      },
    );
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') throw error;
    callbacks.onError?.((error as Error).message || 'Continue failed');
    throw error;
  }
}

export async function exportBugReport(
  sessionId: string,
  format: 'markdown' | 'pdf',
): Promise<Blob> {
  const response = await fetch(
    buildUrl(
      `/bug-report/${encodeURIComponent(sessionId)}/export`,
    ),
    {
      method: 'POST',
      headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
      body: JSON.stringify({ format, push_to_jira: false }),
    },
  );
  if (!response.ok) {
    try {
      throw new Error((await response.text()) || `HTTP ${response.status}`);
    } catch {
      throw new Error(`HTTP ${response.status}`);
    }
  }
  return response.blob();
}

export async function getIntegrations(): Promise<IntegrationStatus[]> {
  const response = await fetch(buildUrl('/settings/integrations'), { headers: { ...(await authHeaders()) } });
  if (!response.ok) {
    try {
      throw new Error((await response.text()) || `HTTP ${response.status}`);
    } catch {
      throw new Error(`HTTP ${response.status}`);
    }
  }
  const j = (await response.json()) as { integrations: IntegrationStatus[] };
  return j.integrations;
}

export async function updateIntegration(
  name: string,
  credentials: Record<string, string>,
): Promise<IntegrationStatus[]> {
  const response = await fetch(buildUrl('/settings/integrations'), {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, credentials }),
  });
  if (!response.ok) {
    try {
      throw new Error((await response.text()) || `HTTP ${response.status}`);
    } catch {
      throw new Error(`HTTP ${response.status}`);
    }
  }
  const j = (await response.json()) as { integrations: IntegrationStatus[] };
  return j.integrations;
}

// ── Task 21: Projects CRUD ───────────────────────────────────────

export type Project = {
  id: string;
  user_id: string;
  name: string | null;          // user-given label, set when repo is not attached yet
  repo_url: string | null;
  owner: string | null;
  repo_name: string | null;
  index_status: "pending" | "indexing" | "ready" | "failed" | "stale";
  index_error?: string | null;
  graph_stats?: { node_count?: number; edge_count?: number } | null;
  last_indexed_at?: string | null;
  created_at: string;
};

export type ProjectDetail = Project & { local_graph_present: boolean };

export async function listProjects(): Promise<Project[]> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/projects`, {
    headers: { ...(await authHeaders()) },
  });
  if (!r.ok) throw new Error(`listProjects ${r.status}`);
  return r.json();
}

export async function createProject(body: { name?: string; repo_url?: string }): Promise<Project> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/projects`, {
    method: "POST",
    headers: { ...(await authHeaders()), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`createProject ${r.status}`);
  return r.json();
}

export async function attachRepoToProject(projectId: string, repoUrl: string): Promise<Project> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/projects/${projectId}/attach`, {
    method: "POST",
    headers: { ...(await authHeaders()), "Content-Type": "application/json" },
    body: JSON.stringify({ repo_url: repoUrl }),
  });
  if (!r.ok) throw new Error(`attachRepoToProject ${r.status}`);
  return r.json();
}

export async function getProject(id: string): Promise<ProjectDetail> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/projects/${id}`, {
    headers: { ...(await authHeaders()) },
  });
  if (!r.ok) throw new Error(`getProject ${r.status}`);
  return r.json();
}

export async function deleteProject(id: string): Promise<void> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/projects/${id}`, {
    method: "DELETE",
    headers: { ...(await authHeaders()) },
  });
  if (!r.ok && r.status !== 204) throw new Error(`deleteProject ${r.status}`);
}

export type CredentialStatus = {
  has_anthropic_api_key: boolean;
  has_github_token: boolean;
  integrations: Record<"jira" | "notion" | "confluence" | "grafana" | "kibana" | "postman", boolean>;
};

export async function getCredentialStatus(): Promise<CredentialStatus> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/settings/credentials`, {
    headers: { ...(await authHeaders()) },
  });
  if (!r.ok) throw new Error(`getCredentialStatus ${r.status}`);
  return r.json();
}

export async function saveCredentials(body: Partial<{
  anthropic_api_key: string;
  github_token: string;
  jira: object;
  notion: object;
  confluence: object;
  grafana: object;
  kibana: object;
  postman: object;
}>): Promise<void> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/settings/credentials`, {
    method: "POST",
    headers: { ...(await authHeaders()), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok && r.status !== 204) throw new Error(`saveCredentials ${r.status}`);
}

export type PrAnalysisRow = {
  id: string;
  project_id: string;
  pr_url: string;
  pr_number: number | null;
  pr_title: string | null;
  status: "running" | "completed" | "failed" | "cancelled";
  created_at: string;
  completed_at: string | null;
};

export type BugReportRow = {
  id: string;
  project_id: string;
  bug_description: string;
  severity: string | null;
  status: "running" | "completed" | "failed" | "cancelled";
  created_at: string;
  completed_at: string | null;
};

export async function listPrAnalyses(projectId: string): Promise<PrAnalysisRow[]> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/projects/${projectId}/pr-analyses`, {
    headers: { ...(await authHeaders()) },
  });
  if (!r.ok) throw new Error(`listPrAnalyses ${r.status}`);
  return r.json();
}

export async function listBugReports(projectId: string): Promise<BugReportRow[]> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/projects/${projectId}/bug-reports`, {
    headers: { ...(await authHeaders()) },
  });
  if (!r.ok) throw new Error(`listBugReports ${r.status}`);
  return r.json();
}

export async function getPrAnalysis(id: string): Promise<PrAnalysisRow & Record<string, unknown>> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/pr-analyses/${id}`, {
    headers: { ...(await authHeaders()) },
  });
  if (!r.ok) throw new Error(`getPrAnalysis ${r.status}`);
  return r.json();
}

export async function getBugReport(id: string): Promise<BugReportRow & Record<string, unknown>> {
  const r = await fetch(`${import.meta.env.VITE_API_URL}/bug-reports/${id}`, {
    headers: { ...(await authHeaders()) },
  });
  if (!r.ok) throw new Error(`getBugReport ${r.status}`);
  return r.json();
}
