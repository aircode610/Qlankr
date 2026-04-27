import { useRef, useCallback, useState, useEffect, Component, ReactNode } from 'react';
import { AppStateProvider, useAppState } from './hooks/useAppState';
import { GraphCanvas, GraphCanvasHandle } from './components/GraphCanvas';
import { FileTreePanel } from './components/FileTreePanel';
import { StatusBar } from './components/StatusBar';
import { Navbar, AppView } from './components/Navbar';
import { IndexingPage } from './components/IndexingPage';
import { PrAnalysisPanel } from './components/PrAnalysisPanel';
import { SettingsPanel } from './components/SettingsPanel';
import { AgentTraceDrawer } from './components/AgentTraceDrawer';
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
  } = useAppState();

  const graphCanvasRef = useRef<GraphCanvasHandle>(null);
  const abortRef = useRef<AbortController | null>(null);

  const [showWorkspace, setShowWorkspace] = useState(false);
  const [view, setView] = useState<AppView>('graph');
  const [indexError, setIndexError] = useState<string | null>(null);

  // Bug reproduction state
  const [bugState, setBugState] = useState<BugReproState>(INITIAL_BUG_STATE);
  const bugAbortRef = useRef<AbortController | null>(null);

  // Transition to workspace ~900ms after indexing completes
  useEffect(() => {
    if (indexed) {
      const t = setTimeout(() => setShowWorkspace(true), 900);
      return () => clearTimeout(t);
    }
  }, [indexed]);

  // Switch to Analyze view automatically when a workflow starts
  const { analyzing, agentSteps, currentStage, checkpoint, result, error } = analysisState;
  useEffect(() => {
    if (analyzing) setView('analyze');
  }, [analyzing]);

  /* ── Repo indexing ──────────────────────────────────────────── */
  const handleIndex = useCallback(async (url: string) => {
    setRepoUrl(url);
    setIndexing(true);
    setIndexMessages([]);
    setIndexError(null);
    setProgress({ phase: 'extracting', percent: 0, message: 'Indexing repository…' });

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
        // Tick off the previous running stage when a new one starts
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
          // If we already have a report, show it — let post-processing failures (e.g. Jira push) fail silently
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
            // Tick off previous running stage
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
        activeWorkflowLabel={analyzing ? 'Analyzing…' : null}
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
                <p className="text-sm text-text-muted">Loading knowledge graph…</p>
              </div>
            )}
          </div>
        </main>
      )}

      {/* ── Bug reproduction view ── */}
      {view === 'bug' && (
        <main className="flex min-h-0 flex-1 overflow-hidden">

          {/* ── IDLE: full-width centered form ── */}
          {bugState.mode === 'idle' && (
            <div className="min-w-0 flex-1 overflow-hidden">
              <BugInputPanel
                onSubmit={handleBugSubmit}
                analyzing={false}
              />
            </div>
          )}

          {/* ── ACTIVE (running / checkpoint / done / error): sidebar + main ── */}
          {bugState.mode !== 'idle' && (
            <>
              {/* Left sidebar — stage trace */}
              <div className="flex w-64 shrink-0 flex-col border-r border-border-subtle bg-surface">
                <BugTraceDrawer
                  stages={bugState.stages}
                  analyzing={bugState.mode === 'running'}
                  currentStage={bugState.currentStage}
                />
              </div>

              {/* Right main area */}
              <div className="min-w-0 flex-1 overflow-hidden">

                {/* Done — show full bug report */}
                {bugState.mode === 'done' && bugState.report && (
                  <BugReportView report={bugState.report} sessionId={bugState.sessionId!} />
                )}

                {/* Checkpoint — inline review panel, NOT a modal */}
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

                {/* Running — current stage indicator */}
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
                            : 'Starting…'}
                        </p>
                        <p className="mt-0.5 text-xs text-text-muted">
                          {bugState.stages.reduce((n, s) => n + s.toolCalls.length, 0)} tool calls so far
                        </p>
                      </div>
                    </div>
                    {/* Show last tool call */}
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

                {/* Error */}
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

      {/* ── Analyze view ── */}
      {view === 'settings' && (
        <main className="min-h-0 flex-1 overflow-hidden">
          <SettingsPanel />
        </main>
      )}

      {view === 'analyze' && (
        <main className="flex min-h-0 flex-1 overflow-hidden">
          {/* Left column — PR input + agent trace (narrow) */}
          <div className="flex w-72 shrink-0 flex-col border-r border-border-subtle bg-surface">
            {/* PR input area */}
            <div className="border-b border-border-subtle p-3">
              <PrAnalysisPanel
                onAnalyze={handleAnalyze}
                analyzing={analyzing}
                disabled={false}
              />
              {error && (
                <div className="mt-2 rounded border border-red-500/30 bg-red-500/10 px-2 py-1.5 text-[11px] text-red-400">
                  {error}
                </div>
              )}
            </div>

            {/* Agent trace (fills remaining space) */}
            <div className="min-h-0 flex-1 overflow-hidden">
              <AgentTraceDrawer
                steps={agentSteps}
                analyzing={analyzing}
                activeWorkflow={null}
                currentStage={currentStage}
              />
            </div>
          </div>

          {/* Right column — results / unit review / waiting state */}
          <div className="min-w-0 flex-1 overflow-hidden">
            {result ? (
              <TestPipelineResults result={result} onHighlightFiles={handleHighlightFiles} />
            ) : checkpoint && checkpoint.interrupt_type === 'checkpoint' ? (
              <UnitReviewPanel
                checkpoint={checkpoint}
                onApprove={() => handleCheckpointContinue('approve')}
                onRefine={(fb) => handleCheckpointContinue('rerun', fb)}
              />
            ) : analyzing || agentSteps.length > 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-3 bg-void/50">
                {analyzing && (
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-2 animate-pulse rounded-full bg-accent" />
                    <span className="text-sm text-text-muted">
                      {currentStage ? `Running ${currentStage.replace(/_/g, ' ')}…` : 'Starting analysis…'}
                    </span>
                  </div>
                )}
                {!analyzing && !result && !checkpoint && agentSteps.length > 0 && (
                  <p className="text-xs text-text-muted">Waiting…</p>
                )}
              </div>
            ) : (
              <div className="flex h-full flex-col items-center justify-center gap-2 bg-void/50">
                <p className="text-sm text-text-muted">Enter a PR URL and click Analyze</p>
                <p className="text-[11px] text-text-muted/60">Results will appear here as each stage completes</p>
              </div>
            )}
          </div>
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
