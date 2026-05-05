import { useRef, useCallback, useState, useEffect, Component, ReactNode } from 'react';
import { AppStateProvider, useAppState } from './hooks/useAppState';
import { GraphCanvas, GraphCanvasHandle } from './components/GraphCanvas';
import { FileTreePanel } from './components/FileTreePanel';
import { FileContentPanel } from './components/FileContentPanel';
import { StatusBar } from './components/StatusBar';
import { Navbar, AppView } from './components/Navbar';
import { IndexingPage } from './components/IndexingPage';
import { SettingsPanel } from './components/SettingsPanel';
import { AnalyzeInputPanel } from './components/AnalyzeInputPanel';
import { AnalyzeTraceDrawer, AnalyzeStageInfo } from './components/AnalyzeTraceDrawer';
import { TestPipelineResults } from './components/TestPipelineResults';
import { UnitReviewPanel } from './components/UnitReviewPanel';
import { ChoiceDialog } from './components/ChoiceDialog';
import { CheckpointDialog } from './components/CheckpointDialog';
import { BugInputPanel } from './components/BugInputPanel';
import { BugTraceDrawer, BugStageInfo, BugStage } from './components/BugTraceDrawer';
import { BugReportView } from './components/BugReportView';
import { BugCheckpointDialog } from './components/BugCheckpointDialog';
import { ResearchPanel } from './components/ResearchPanel';
import { createKnowledgeGraph } from './core/graph/graph';
import { indexRepo, analyzePR, continueAnalysis, getGraph, startBugReport, continueBugReport } from './services/api';
import type { AnalysisStage, CheckpointData, AnalyzeResult, BugReport, BugCheckpointEvent } from './services/types';

// ── Error boundary ────────────────────────────────────────────────────────────
class ErrorBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state = { error: null };
  static getDerivedStateFromError(err: unknown) {
    return { error: err instanceof Error ? err.message : String(err) };
  }
  render() {
    if (this.state.error) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-3 bg-void p-8 text-center">
          <p className="text-sm font-medium text-red-400">Something went wrong</p>
          <pre className="max-w-lg overflow-auto rounded bg-elevated p-3 text-left text-[11px] text-text-muted">
            {this.state.error}
          </pre>
          <button
            onClick={() => this.setState({ error: null })}
            className="rounded bg-accent px-4 py-2 text-sm text-white hover:bg-accent-dim"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Bug reproduction state ────────────────────────────────────────────────────
interface BugReproState {
  mode: 'idle' | 'running' | 'checkpoint' | 'done' | 'error';
  sessionId: string | null;
  currentStage: BugStage | null;
  stages: BugStageInfo[];
  checkpointData: BugCheckpointEvent | null;
  report: BugReport | null;
  error: string | null;
}

const INITIAL_BUG_STATE: BugReproState = {
  mode: 'idle',
  sessionId: null,
  currentStage: null,
  stages: [],
  checkpointData: null,
  report: null,
  error: null,
};

// ── Analyze mode state ───────────────────────────────────────────────────────
type AnalyzeMode = 'idle' | 'running' | 'checkpoint' | 'done' | 'error';

// ── Main app content ──────────────────────────────────────────────────────────
const AppContent = () => {
  const {
    graph, setGraph,
    repoUrl, setRepoUrl,
    indexing, setIndexing,
    indexed, setIndexed,
    indexMessages, setIndexMessages,
    setProgress,
    analysisState, setAnalysisState,
    affectedFileIds, setAffectedFileIds,
    selectedNode, setSelectedNode,
  } = useAppState();

  const graphCanvasRef = useRef<GraphCanvasHandle>(null);
  const abortRef = useRef<AbortController | null>(null);

  const [showWorkspace, setShowWorkspace] = useState(false);
  const [view, setView] = useState<AppView>('graph');
  const [indexError, setIndexError] = useState<string | null>(null);

  // File content panel state for graph view
  const [fileViewOpen, setFileViewOpen] = useState(false);
  const [fileViewPath, setFileViewPath] = useState<string | null>(null);

  // Bug reproduction state
  const [bugState, setBugState] = useState<BugReproState>(INITIAL_BUG_STATE);
  const bugAbortRef = useRef<AbortController | null>(null);

  // Analyze stage tracking (mirrors BugTraceDrawer pattern)
  const [analyzeStages, setAnalyzeStages] = useState<AnalyzeStageInfo[]>([]);

  // Transition to workspace ~900ms after indexing completes
  useEffect(() => {
    if (indexed) {
      const t = setTimeout(() => setShowWorkspace(true), 900);
      return () => clearTimeout(t);
    }
  }, [indexed]);

  // Derive analyze mode from analysisState
  const { analyzing, agentSteps, currentStage, checkpoint, result, error } = analysisState;
  const analyzeMode: AnalyzeMode =
    result ? 'done' :
    checkpoint ? 'checkpoint' :
    error && !analyzing ? 'error' :
    analyzing ? 'running' :
    agentSteps.length > 0 ? 'running' :
    'idle';

  // Open file content panel when a file is selected in graph view
  useEffect(() => {
    if (selectedNode && selectedNode.label === 'File' && view === 'graph') {
      setFileViewPath(selectedNode.properties.filePath);
      setFileViewOpen(true);
    }
  }, [selectedNode, view]);

  // Update analyze stage tracking when currentStage changes
  useEffect(() => {
    if (!currentStage) return;
    setAnalyzeStages((prev) => {
      // Complete previous running stages
      const updated = prev.map((s) =>
        s.status === 'running' && s.stage !== currentStage
          ? { ...s, status: 'completed' as const }
          : s
      );
      const existing = updated.find((s) => s.stage === currentStage);
      if (existing) {
        return updated.map((s) => s.stage === currentStage ? { ...s, status: 'running' as const } : s);
      }
      return [...updated, { stage: currentStage, status: 'running' as const, toolCalls: [] }];
    });
  }, [currentStage]);

  // Track tool calls per stage for analyze
  useEffect(() => {
    if (agentSteps.length === 0) return;
    const lastStep = agentSteps[agentSteps.length - 1];
    if (!lastStep.stage) return;
    setAnalyzeStages((prev) =>
      prev.map((s) =>
        s.stage === lastStep.stage
          ? { ...s, toolCalls: [...s.toolCalls, { tool: lastStep.tool, summary: lastStep.summary }] }
          : s
      )
    );
  }, [agentSteps.length]);

  // Complete all stages when result arrives
  useEffect(() => {
    if (result) {
      setAnalyzeStages((prev) =>
        prev.map((s) => s.status === 'running' ? { ...s, status: 'completed' } : s)
      );
    }
  }, [result]);

  // Mark checkpoint stage
  useEffect(() => {
    if (checkpoint) {
      setAnalyzeStages((prev) =>
        prev.map((s) => s.status === 'running' ? { ...s, status: 'checkpoint' } : s)
      );
    }
  }, [checkpoint]);

  // Handle deep-link navigation from URL params (file cross-linking)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const focusFile = params.get('focusFile');
    const highlightFiles = params.get('highlightFiles');

    if (focusFile && graph) {
      setView('graph');
      const node = graph.nodes.find((n) => n.properties.filePath.endsWith(focusFile));
      if (node) {
        setSelectedNode(node);
        setFileViewPath(node.properties.filePath);
        setFileViewOpen(true);
        setTimeout(() => graphCanvasRef.current?.focusNode(node.id), 300);
      }
    }

    if (highlightFiles && graph) {
      const files = highlightFiles.split(',');
      const ids = new Set(
        graph.nodes.filter((n) => files.some((f) => n.properties.filePath.endsWith(f))).map((n) => n.id)
      );
      setAffectedFileIds(ids);
    }

    // Clean URL params after processing
    if (focusFile || highlightFiles) {
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [graph, setSelectedNode, setAffectedFileIds]);

  /* ── Repo indexing ──────────────────────────────────────────── */
  const handleIndex = useCallback(async (url: string) => {
    setRepoUrl(url);
    setIndexing(true);
    setIndexMessages([]);
    setIndexError(null);
    setProgress({ phase: 'extracting', percent: 0, message: 'Indexing repository...' });

    try {
      await indexRepo(url, {
        onIndexStep: (data) => {
          setIndexMessages((prev) => [...prev, { stage: data.stage, summary: data.summary }]);
        },
        onIndexDone: async (data) => {
          setIndexed(true);
          setProgress({ phase: 'complete', percent: 100, message: `Indexed ${data.files} files` });
          try {
            const [owner, repo] = data.repo.split('/');
            const { nodes, relationships } = await getGraph(owner, repo);
            const kg = createKnowledgeGraph();
            nodes.forEach((n) => kg.addNode(n));
            relationships.forEach((r) => kg.addRelationship(r));
            setGraph(kg);
          } catch (err) {
            console.warn('Failed to load graph:', err);
          }
          setTimeout(() => setProgress(null), 2000);
        },
        onError: (msg) => {
          setIndexError(msg);
          setProgress({ phase: 'error', percent: 0, message: msg });
          setTimeout(() => setProgress(null), 3000);
        },
      });
    } catch {
      // handled by onError
    } finally {
      setIndexing(false);
    }
  }, [setRepoUrl, setIndexing, setIndexMessages, setProgress, setIndexed, setGraph]);

  /* ── PR analysis ────────────────────────────────────────────── */
  const handleAnalyze = useCallback(async (prUrl: string, context: string | null) => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    // Reset analyze stages
    setAnalyzeStages([]);

    setAnalysisState((prev) => ({
      ...prev,
      prUrl,
      context,
      activeWorkflow: null,
      analyzing: true,
      agentSteps: [],
      checkpoint: null,
      result: null,
      error: null,
      currentStage: null,
      sessionId: null,
    }));
    setAffectedFileIds(new Set());

    try {
      await analyzePR(prUrl, context, null, null, {
        signal: abortRef.current.signal,
        onAgentStep: (data) => {
          setAnalysisState((prev) => ({
            ...prev,
            agentSteps: [
              ...prev.agentSteps,
              { tool: data.tool, summary: data.summary, stage: prev.currentStage },
            ],
          }));
        },
        onStageChange: (data) => {
          setAnalysisState((prev) => ({ ...prev, currentStage: data.stage as AnalysisStage }));
        },
        onCheckpoint: (data) => {
          setAnalysisState((prev) => ({
            ...prev,
            analyzing: false,
            checkpoint: data as CheckpointData,
            sessionId: (data as CheckpointData).session_id,
          }));
        },
        onResult: (data) => {
          const res = data as AnalyzeResult;
          const allFiles = res.affected_components.flatMap((c) => c.files_changed);
          setAnalysisState((prev) => ({ ...prev, analyzing: false, result: res, currentStage: null }));
          if (graph && allFiles.length > 0) {
            const ids = new Set(
              graph.nodes
                .filter((n) => allFiles.some((f) => n.properties.filePath.endsWith(f)))
                .map((n) => n.id)
            );
            setAffectedFileIds(ids);
          }
        },
        onError: (msg) => {
          setAnalysisState((prev) => ({ ...prev, analyzing: false, error: msg }));
        },
      });
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setAnalysisState((prev) => ({ ...prev, analyzing: false, error: err.message }));
      }
    }
  }, [setAnalysisState, setAffectedFileIds, graph]);

  /* ── Checkpoint continue ────────────────────────────────────── */
  const handleCheckpointContinue = useCallback(async (
    action: 'approve' | 'add_context' | 'skip' | 'rerun',
    context?: string,
  ) => {
    const { sessionId } = analysisState;
    if (!sessionId) return;

    setAnalysisState((prev) => ({ ...prev, checkpoint: null, analyzing: true }));
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    try {
      await continueAnalysis(sessionId, action, context ?? null, {
        signal: abortRef.current.signal,
        onAgentStep: (data) => {
          setAnalysisState((prev) => ({
            ...prev,
            agentSteps: [
              ...prev.agentSteps,
              { tool: data.tool, summary: data.summary, stage: prev.currentStage },
            ],
          }));
        },
        onStageChange: (data) => {
          setAnalysisState((prev) => ({ ...prev, currentStage: data.stage as AnalysisStage }));
        },
        onCheckpoint: (data) => {
          setAnalysisState((prev) => ({ ...prev, analyzing: false, checkpoint: data as CheckpointData }));
        },
        onResult: (data) => {
          const res = data as AnalyzeResult;
          const allFiles = res.affected_components.flatMap((c) => c.files_changed);
          setAnalysisState((prev) => ({ ...prev, analyzing: false, result: res, currentStage: null }));
          if (graph && allFiles.length > 0) {
            const ids = new Set(
              graph.nodes
                .filter((n) => allFiles.some((f) => n.properties.filePath.endsWith(f)))
                .map((n) => n.id)
            );
            setAffectedFileIds(ids);
          }
        },
        onError: (msg) => {
          setAnalysisState((prev) => ({ ...prev, analyzing: false, error: msg }));
        },
      });
    } catch {
      // handled by onError
    }
  }, [analysisState, setAnalysisState, setAffectedFileIds, graph]);

  /* ── Bug submission ─────────────────────────────────────────────── */
  const handleBugSubmit = useCallback(async (
    req: import('./services/types').BugReportRequest,
    _enabledIntegrations: string[],
  ) => {
    bugAbortRef.current?.abort();
    bugAbortRef.current = new AbortController();

    setBugState({ ...INITIAL_BUG_STATE, mode: 'running' });
    setView('bug');

    const updateStage = (stageName: string, status: BugStageInfo['status'], toolCall?: { tool: string; summary: string }) => {
      setBugState((prev) => {
        const completedStages = status === 'running' && prev.currentStage && prev.currentStage !== stageName
          ? prev.stages.map((s) => s.stage === prev.currentStage && s.status === 'running' ? { ...s, status: 'completed' as const } : s)
          : prev.stages;
        const existing = completedStages.find((s) => s.stage === stageName as BugStage);
        if (existing) {
          return {
            ...prev,
            currentStage: stageName as BugStage,
            stages: completedStages.map((s) =>
              s.stage === stageName
                ? { ...s, status, toolCalls: toolCall ? [...s.toolCalls, toolCall] : s.toolCalls }
                : s,
            ),
          };
        }
        return {
          ...prev,
          currentStage: stageName as BugStage,
          stages: [...completedStages, {
            stage: stageName as BugStage,
            status,
            toolCalls: toolCall ? [toolCall] : [],
          }],
        };
      });
    };

    try {
      await startBugReport(req, {
        signal: bugAbortRef.current.signal,
        onBugStageChange: (d) => updateStage(d.stage, 'running'),
        onEvent: (evt) => {
          if (evt.event === 'agent_step') {
            const d = evt.data as { tool: string; summary: string };
            setBugState((prev) => {
              if (!prev.currentStage) return prev;
              return {
                ...prev,
                stages: prev.stages.map((s) =>
                  s.stage === prev.currentStage
                    ? { ...s, toolCalls: [...s.toolCalls, { tool: d.tool, summary: d.summary }] }
                    : s,
                ),
              };
            });
          }
        },
        onBugCheckpoint: (d) => {
          setBugState((prev) => ({
            ...prev,
            mode: 'checkpoint',
            sessionId: d.session_id,
            checkpointData: d as BugCheckpointEvent,
            stages: prev.stages.map((s) =>
              s.stage === prev.currentStage ? { ...s, status: 'checkpoint' } : s,
            ),
          }));
        },
        onBugResult: (d) => {
          setBugState((prev) => ({
            ...prev,
            mode: 'done',
            sessionId: d.session_id,
            report: d.report as BugReport,
            currentStage: null,
            stages: prev.stages.map((s) => ({ ...s, status: s.status === 'running' ? 'completed' : s.status })),
          }));
        },
        onError: (msg) => {
          setBugState((prev) => prev.report
            ? { ...prev, mode: 'done', currentStage: null, stages: prev.stages.map((s) => ({ ...s, status: s.status === 'running' ? 'completed' : s.status })) }
            : { ...prev, mode: 'error', error: msg }
          );
        },
      });
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setBugState((prev) => prev.report
          ? { ...prev, mode: 'done', currentStage: null, stages: prev.stages.map((s) => ({ ...s, status: s.status === 'running' ? 'completed' : s.status })) }
          : { ...prev, mode: 'error', error: err.message }
        );
      }
    }
  }, []);

  /* ── Bug checkpoint continue ─────────────────────────────────────── */
  const handleBugCheckpointContinue = useCallback(async (
    action: 'approve' | 'refine' | 'add_context',
    feedback?: string,
  ) => {
    const { sessionId } = bugState;
    if (!sessionId) return;

    setBugState((prev) => ({ ...prev, mode: 'running', checkpointData: null }));
    bugAbortRef.current?.abort();
    bugAbortRef.current = new AbortController();

    try {
      await continueBugReport(sessionId, { action, feedback }, {
        signal: bugAbortRef.current.signal,
        onBugStageChange: (d) => {
          setBugState((prev) => {
            const completedStages = prev.currentStage && prev.currentStage !== d.stage
              ? prev.stages.map((s) => s.stage === prev.currentStage && s.status === 'running' ? { ...s, status: 'completed' as const } : s)
              : prev.stages;
            const existing = completedStages.find((s) => s.stage === d.stage as BugStage);
            if (existing) {
              return { ...prev, currentStage: d.stage as BugStage, stages: completedStages.map((s) => s.stage === d.stage ? { ...s, status: 'running' } : s) };
            }
            return { ...prev, currentStage: d.stage as BugStage, stages: [...completedStages, { stage: d.stage as BugStage, status: 'running', toolCalls: [] }] };
          });
        },
        onEvent: (evt) => {
          if (evt.event === 'agent_step') {
            const d = evt.data as { tool: string; summary: string };
            setBugState((prev) => {
              if (!prev.currentStage) return prev;
              return { ...prev, stages: prev.stages.map((s) => s.stage === prev.currentStage ? { ...s, toolCalls: [...s.toolCalls, { tool: d.tool, summary: d.summary }] } : s) };
            });
          }
        },
        onBugCheckpoint: (d) => {
          setBugState((prev) => ({ ...prev, mode: 'checkpoint', checkpointData: d as BugCheckpointEvent }));
        },
        onBugResult: (d) => {
          setBugState((prev) => ({ ...prev, mode: 'done', report: d.report as BugReport, currentStage: null, stages: prev.stages.map((s) => ({ ...s, status: s.status === 'running' ? 'completed' : s.status })) }));
        },
        onError: (msg) => {
          setBugState((prev) => prev.report
            ? { ...prev, mode: 'done', currentStage: null, stages: prev.stages.map((s) => ({ ...s, status: s.status === 'running' ? 'completed' : s.status })) }
            : { ...prev, mode: 'error', error: msg }
          );
        },
      });
    } catch { /* handled by onError */ }
  }, [bugState]);

  const handleFocusNode = useCallback((nodeId: string) => {
    graphCanvasRef.current?.focusNode(nodeId);
  }, []);

  const handleHighlightFiles = useCallback((filePaths: string[]) => {
    if (!graph) return;
    const ids = new Set(
      graph.nodes.filter((n) => filePaths.some((f) => n.properties.filePath.endsWith(f))).map((n) => n.id)
    );
    setAffectedFileIds(ids);
  }, [graph, setAffectedFileIds]);

  /** Open a file in graph view — used by cross-linking from analyze/bug reports */
  const handleFileNavigate = useCallback((filePath: string, allFiles?: string[]) => {
    // Open in new tab with URL params
    const params = new URLSearchParams();
    params.set('focusFile', filePath);
    if (allFiles && allFiles.length > 0) {
      params.set('highlightFiles', allFiles.join(','));
    }
    window.open(`${window.location.pathname}?${params.toString()}`, '_blank');
  }, []);

  // ── Landing / indexing screen ────────────────────────────────
  if (!showWorkspace) {
    return (
      <IndexingPage
        onIndex={handleIndex}
        indexing={indexing}
        indexed={indexed}
        indexMessages={indexMessages}
        error={indexError}
      />
    );
  }

  // Derive a short repo name for the navbar badge
  const repoName = repoUrl
    ? repoUrl.replace(/^https?:\/\/github\.com\//, '').replace(/\.git$/, '')
    : null;

  // ── Workspace ────────────────────────────────────────────────
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-void">
      <Navbar
        view={view}
        onViewChange={setView}
        repoName={repoName}
        analyzing={analyzing}
        activeWorkflowLabel={analyzing ? 'Analyzing...' : null}
        bugAnalyzing={bugState.mode === 'running'}
      />

      {/* ── Graph view ── */}
      {view === 'graph' && (
        <main className="flex min-h-0 flex-1">
          <FileTreePanel onFocusNode={handleFocusNode} />
          <div className="relative min-w-0 flex-1">
            {graph ? (
              <GraphCanvas ref={graphCanvasRef} />
            ) : (
              <div className="flex h-full flex-col items-center justify-center gap-4 bg-void">
                <div className="animate-breathe rounded-full border-2 border-accent/30 p-6">
                  <div className="h-16 w-16 rounded-full bg-gradient-to-br from-accent/30 to-accent/5" />
                </div>
                <p className="text-sm text-text-muted">Loading knowledge graph...</p>
              </div>
            )}
          </div>
          {/* File content panel — slides in when a file is selected */}
          {fileViewOpen && fileViewPath && (
            <FileContentPanel
              filePath={fileViewPath}
              repoName={repoName}
              onClose={() => setFileViewOpen(false)}
            />
          )}
        </main>
      )}

      {/* ── Bug reproduction view ── */}
      {view === 'bug' && (
        <main className="flex min-h-0 flex-1 overflow-hidden">
          {bugState.mode === 'idle' && (
            <div className="min-w-0 flex-1 overflow-hidden">
              <BugInputPanel onSubmit={handleBugSubmit} analyzing={false} />
            </div>
          )}

          {bugState.mode !== 'idle' && (
            <>
              <div className="flex w-64 shrink-0 flex-col border-r border-border-subtle bg-surface">
                <BugTraceDrawer
                  stages={bugState.stages}
                  analyzing={bugState.mode === 'running'}
                  currentStage={bugState.currentStage}
                />
              </div>

              <div className="min-w-0 flex-1 overflow-hidden">
                {bugState.mode === 'done' && bugState.report && (
                  <BugReportView
                    report={bugState.report}
                    sessionId={bugState.sessionId!}
                    onFileNavigate={handleFileNavigate}
                  />
                )}

                {bugState.mode === 'checkpoint' && bugState.checkpointData && (() => {
                  const cp = bugState.checkpointData as unknown as CheckpointData;
                  const stageCompleted = bugState.checkpointData.stage_completed;
                  return stageCompleted === 'research' ? (
                    <ResearchPanel
                      checkpoint={cp}
                      onApprove={() => handleBugCheckpointContinue('approve')}
                      onAddContext={(ctx) => handleBugCheckpointContinue('add_context', ctx)}
                    />
                  ) : (
                    <BugCheckpointDialog
                      checkpoint={cp}
                      onContinue={(resp) => {
                        const action = (resp.action ?? 'approve') as 'approve' | 'refine' | 'add_context';
                        handleBugCheckpointContinue(action, resp.feedback ?? resp.context);
                      }}
                      onDismiss={() => setBugState((prev) => ({ ...prev, checkpointData: null }))}
                    />
                  );
                })()}

                {bugState.mode === 'running' && (
                  <div className="flex h-full flex-col items-center justify-center gap-4 bg-void/50">
                    <div className="flex flex-col items-center gap-3">
                      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-red-500/20 bg-red-500/10">
                        <div className="h-3 w-3 animate-pulse rounded-full bg-red-400" />
                      </div>
                      <div className="text-center">
                        <p className="text-sm font-medium text-text-primary">
                          {bugState.currentStage
                            ? bugState.currentStage.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
                            : 'Starting...'}
                        </p>
                        <p className="mt-0.5 text-xs text-text-muted">
                          {bugState.stages.reduce((n, s) => n + s.toolCalls.length, 0)} tool calls so far
                        </p>
                      </div>
                    </div>
                    {(() => {
                      const lastStage = [...bugState.stages].reverse().find((s) => s.toolCalls.length > 0);
                      const lastCall = lastStage?.toolCalls.at(-1);
                      return lastCall ? (
                        <div className="rounded-lg border border-border-subtle bg-elevated/60 px-3 py-2 text-center">
                          <p className="font-mono text-[11px] text-accent">{lastCall.tool}</p>
                          {lastCall.summary && (
                            <p className="mt-0.5 text-[11px] text-text-muted">{lastCall.summary}</p>
                          )}
                        </div>
                      ) : null;
                    })()}
                  </div>
                )}

                {bugState.mode === 'error' && (
                  <div className="flex h-full flex-col items-center justify-center gap-3 bg-void/50">
                    <p className="text-sm font-medium text-red-400">Analysis failed</p>
                    {bugState.error && (
                      <p className="max-w-sm text-center text-xs text-text-muted">{bugState.error}</p>
                    )}
                    <button
                      onClick={() => setBugState(INITIAL_BUG_STATE)}
                      className="rounded-lg border border-border-subtle bg-elevated px-4 py-2 text-xs text-text-secondary hover:bg-hover hover:text-text-primary"
                    >
                      Start Over
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </main>
      )}

      {/* ── Settings view ── */}
      {view === 'settings' && (
        <main className="min-h-0 flex-1 overflow-hidden">
          <SettingsPanel />
        </main>
      )}

      {/* ── Analyze view (redesigned to match Bug tab) ── */}
      {view === 'analyze' && (
        <main className="flex min-h-0 flex-1 overflow-hidden">

          {/* IDLE: full-width centered form */}
          {analyzeMode === 'idle' && (
            <div className="min-w-0 flex-1 overflow-hidden">
              <AnalyzeInputPanel onAnalyze={handleAnalyze} analyzing={false} />
            </div>
          )}

          {/* ACTIVE (running / checkpoint / done / error): sidebar + main */}
          {analyzeMode !== 'idle' && (
            <>
              {/* Left sidebar — stage trace */}
              <div className="flex w-64 shrink-0 flex-col border-r border-border-subtle bg-surface">
                <AnalyzeTraceDrawer
                  stages={analyzeStages}
                  analyzing={analyzing}
                  currentStage={currentStage}
                />
              </div>

              {/* Right main area */}
              <div className="min-w-0 flex-1 overflow-hidden">

                {/* Done — show results */}
                {analyzeMode === 'done' && result && (
                  <TestPipelineResults
                    result={result}
                    onHighlightFiles={handleHighlightFiles}
                    onFileNavigate={handleFileNavigate}
                  />
                )}

                {/* Checkpoint — unit review */}
                {analyzeMode === 'checkpoint' && checkpoint && checkpoint.interrupt_type === 'checkpoint' && (
                  <UnitReviewPanel
                    checkpoint={checkpoint}
                    onApprove={() => handleCheckpointContinue('approve')}
                    onRefine={(fb) => handleCheckpointContinue('rerun', fb)}
                    onFileNavigate={handleFileNavigate}
                  />
                )}

                {/* Running — current stage indicator */}
                {analyzeMode === 'running' && (
                  <div className="flex h-full flex-col items-center justify-center gap-4 bg-void/50">
                    <div className="flex flex-col items-center gap-3">
                      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-accent/20 bg-accent/10">
                        <div className="h-3 w-3 animate-pulse rounded-full bg-accent" />
                      </div>
                      <div className="text-center">
                        <p className="text-sm font-medium text-text-primary">
                          {currentStage
                            ? currentStage.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
                            : 'Starting analysis...'}
                        </p>
                        <p className="mt-0.5 text-xs text-text-muted">
                          {agentSteps.length} tool calls so far
                        </p>
                      </div>
                    </div>
                    {agentSteps.length > 0 && (() => {
                      const lastStep = agentSteps[agentSteps.length - 1];
                      return (
                        <div className="rounded-lg border border-border-subtle bg-elevated/60 px-3 py-2 text-center">
                          <p className="font-mono text-[11px] text-accent">{lastStep.tool}</p>
                          {lastStep.summary && (
                            <p className="mt-0.5 text-[11px] text-text-muted">{lastStep.summary}</p>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                )}

                {/* Error */}
                {analyzeMode === 'error' && (
                  <div className="flex h-full flex-col items-center justify-center gap-3 bg-void/50">
                    <p className="text-sm font-medium text-red-400">Analysis failed</p>
                    {error && (
                      <p className="max-w-sm text-center text-xs text-text-muted">{error}</p>
                    )}
                    <button
                      onClick={() => {
                        setAnalysisState((prev) => ({ ...prev, error: null, agentSteps: [], currentStage: null }));
                        setAnalyzeStages([]);
                      }}
                      className="rounded-lg border border-border-subtle bg-elevated px-4 py-2 text-xs text-text-secondary hover:bg-hover hover:text-text-primary"
                    >
                      Start Over
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </main>
      )}

      <StatusBar />

      {/* Choice popup — integration vs e2e */}
      {checkpoint && checkpoint.interrupt_type === 'choice' && (
        <ChoiceDialog
          onChoice={(choice) => handleCheckpointContinue('approve', choice)}
        />
      )}

      {/* Generic checkpoint dialog for e2e_context or unknown types */}
      {checkpoint && checkpoint.interrupt_type !== 'checkpoint' && checkpoint.interrupt_type !== 'choice' && (
        <CheckpointDialog
          checkpoint={checkpoint}
          onContinue={handleCheckpointContinue}
          onDismiss={() => setAnalysisState((prev) => ({ ...prev, checkpoint: null }))}
        />
      )}
    </div>
  );
};

function App() {
  return (
    <AppStateProvider>
      <ErrorBoundary>
        <AppContent />
      </ErrorBoundary>
    </AppStateProvider>
  );
}

export default App;
