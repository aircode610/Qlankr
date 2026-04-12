import { useRef, useCallback, useState, useEffect, Component, ReactNode } from 'react';
import { AppStateProvider, useAppState } from './hooks/useAppState';
import { GraphCanvas, GraphCanvasHandle } from './components/GraphCanvas';
import { FileTreePanel } from './components/FileTreePanel';
import { StatusBar } from './components/StatusBar';
import { Navbar, AppView } from './components/Navbar';
import { IndexingPage } from './components/IndexingPage';
import { PrAnalysisPanel } from './components/PrAnalysisPanel';
import { AgentTraceDrawer } from './components/AgentTraceDrawer';
import { TestPipelineResults } from './components/TestPipelineResults';
import { CheckpointDialog } from './components/CheckpointDialog';
import { createKnowledgeGraph } from './core/graph/graph';
import { indexRepo, analyzePR, continueAnalysis, getGraph } from './services/api';
import type { AnalysisStage, CheckpointData, AnalyzeResult, WorkflowId } from './services/types';

const WORKFLOW_LABELS: Record<WorkflowId, string> = {
  unit_tests: 'Unit Tests',
  integration_tests: 'Integration Tests',
  e2e_planning: 'E2E Planning',
};

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

  // Transition to workspace ~900ms after indexing completes
  useEffect(() => {
    if (indexed) {
      const t = setTimeout(() => setShowWorkspace(true), 900);
      return () => clearTimeout(t);
    }
  }, [indexed]);

  // Switch to Analyze view automatically when a workflow starts
  const { analyzing, agentSteps, currentStage, checkpoint, result, error, activeWorkflow } = analysisState;
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
  const handleAnalyze = useCallback(async (prUrl: string, context: string | null, workflow: WorkflowId) => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setAnalysisState((prev) => ({
      ...prev,
      prUrl,
      context,
      activeWorkflow: workflow,
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
      await analyzePR(prUrl, context, null, workflow, {
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
        activeWorkflowLabel={activeWorkflow ? WORKFLOW_LABELS[activeWorkflow] : null}
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

      {/* ── Analyze view ── */}
      {view === 'analyze' && (
        <main className="flex min-h-0 flex-1 overflow-hidden">
          {/* Left column — workflow picker */}
          <div className="flex w-96 shrink-0 flex-col gap-4 overflow-y-auto border-r border-border-subtle bg-surface p-6">
            <PrAnalysisPanel
              onAnalyze={handleAnalyze}
              analyzing={analyzing}
              activeWorkflow={activeWorkflow}
              disabled={false}
            />
            {error && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2.5 text-xs text-red-400">
                {error}
              </div>
            )}
          </div>

          {/* Right column — trace / results */}
          <div className="min-w-0 flex-1 overflow-hidden">
            {result ? (
              <TestPipelineResults result={result} onHighlightFiles={handleHighlightFiles} />
            ) : (
              <AgentTraceDrawer
                steps={agentSteps}
                analyzing={analyzing}
                activeWorkflow={activeWorkflow}
                currentStage={currentStage}
              />
            )}
          </div>
        </main>
      )}

      <StatusBar />

      {checkpoint && (
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
