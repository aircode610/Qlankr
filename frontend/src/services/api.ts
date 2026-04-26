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
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
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

  return { nodes, relationships };
}

/** Fetch and normalise the knowledge graph for a repo */
export async function getGraph(owner: string, repo: string): Promise<NormalisedGraph> {
  const response = await fetch(buildUrl(`/graph/${owner}/${repo}`));
  if (!response.ok) throw new Error(await readErrorText(response));
  const raw = (await response.json()) as BackendGraphData;
  return normaliseBackendGraph(raw);
}

/** Index a repo — SSE stream */
export interface IndexCallbacks {
  signal?: AbortSignal;
  onEvent?: (evt: SSEEvent) => void;
  onIndexStep?: (data: { stage: string; summary: string }) => void;
  onIndexDone?: (data: { repo: string; files: number; clusters: number; symbols: number }) => void;
  onError?: (message: string) => void;
}

export async function indexRepo(repoUrl: string, opts: IndexCallbacks = {}): Promise<unknown> {
  let finalPayload: unknown = null;
  try {
    await streamSsePost('/index', { repo_url: repoUrl }, {
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
  opts: AnalyzeCallbacks = {},
): Promise<unknown> {
  const body: Record<string, unknown> = { pr_url: prUrl };
  if (context) body.context = context;
  if (sessionId) body.session_id = sessionId;

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
      headers: { 'Content-Type': 'application/json' },
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
  const response = await fetch(buildUrl('/settings/integrations'));
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
    headers: { 'Content-Type': 'application/json' },
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
