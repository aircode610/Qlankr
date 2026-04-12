import { useRef, useCallback, Component, ReactNode } from 'react';
import { AppStateProvider, useAppState } from './hooks/useAppState';
import { GraphCanvas, GraphCanvasHandle } from './components/GraphCanvas';
import { FileTreePanel } from './components/FileTreePanel';
import { StatusBar } from './components/StatusBar';
import { RepoInput } from './components/RepoInput';
import { PrAnalysisPanel } from './components/PrAnalysisPanel';
import { AgentTraceDrawer } from './components/AgentTraceDrawer';
import { TestPipelineResults } from './components/TestPipelineResults';
import { CheckpointDialog } from './components/CheckpointDialog';
import { createKnowledgeGraph } from './core/graph/graph';
import { indexRepo, analyzePR, continueAnalysis, getGraph } from './services/api';
import type { AnalysisStage, CheckpointData, AnalyzeResult } from './services/types';

// ── Error boundary — prevents entire UI going black on render errors ──
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
          <pre className="max-w-lg overflow-auto rounded bg-elevated p-3 text-left text-[11px] text-text-muted">{this.state.error}</pre>
          <button onClick={() => this.setState({ error: null })} className="rounded bg-accent px-4 py-2 text-sm text-white hover:bg-accent-dim">
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

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
    selectedNode,
  } = useAppState();

  const graphCanvasRef = useRef<GraphCanvasHandle>(null);
  const abortRef = useRef<AbortController | null>(null);

  /* ── Repo indexing ─────────────────────────────────────────── */
  const handleIndex = useCallback(async (url: string) => {
    setRepoUrl(url);
    setIndexing(true);
    setIndexMessages([]);
    setProgress({ phase: 'extracting', percent: 0, message: 'Indexing repository…' });

    try {
      await indexRepo(url, {
        onIndexStep: (data) => {
          setIndexMessages((prev) => [...prev, { stage: data.stage, summary: data.summary }]);
        },
        onIndexDone: async (data) => {
          setIndexed(true);
          setProgress({ phase: 'complete', percent: 100, message: `Indexed ${data.files} files` });

          // Fetch and load the knowledge graph
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
          setProgress({ phase: 'error', percent: 0, message: msg });
          setTimeout(() => setProgress(null), 3000);
        },
      });
    } catch {
      // error handled by onError callback
    } finally {
      setIndexing(false);
    }
  }, [setRepoUrl, setIndexing, setIndexMessages, setProgress, setIndexed, setGraph]);

  /* ── PR analysis ───────────────────────────────────────────── */
  const handleAnalyze = useCallback(async (prUrl: string, context: string | null) => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setAnalysisState((prev) => ({
      ...prev,
      prUrl,
      context,
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
      await analyzePR(prUrl, context, null, {
        signal: abortRef.current.signal,
        onAgentStep: (data) => {
          setAnalysisState((prev) => ({
            ...prev,
            agentSteps: [...prev.agentSteps, { tool: data.tool, summary: data.summary, stage: prev.currentStage }],
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
          const result = data as AnalyzeResult;
          const allFiles = result.affected_components.flatMap((c) => c.files_changed);
          setAnalysisState((prev) => ({
            ...prev,
            analyzing: false,
            result,
            currentStage: null,
          }));
          // Highlight affected files in graph
          if (graph && allFiles.length > 0) {
            const fileIds = new Set(
              graph.nodes.filter((n) => allFiles.some((f) => n.properties.filePath.endsWith(f))).map((n) => n.id)
            );
            setAffectedFileIds(fileIds);
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
            agentSteps: [...prev.agentSteps, { tool: data.tool, summary: data.summary, stage: prev.currentStage }],
          }));
        },
        onStageChange: (data) => {
          setAnalysisState((prev) => ({ ...prev, currentStage: data.stage as AnalysisStage }));
        },
        onCheckpoint: (data) => {
          setAnalysisState((prev) => ({ ...prev, analyzing: false, checkpoint: data as CheckpointData }));
        },
        onResult: (data) => {
          const result = data as AnalyzeResult;
          const allFiles = result.affected_components.flatMap((c) => c.files_changed);
          setAnalysisState((prev) => ({ ...prev, analyzing: false, result, currentStage: null }));
          if (graph && allFiles.length > 0) {
            const fileIds = new Set(
              graph.nodes.filter((n) => allFiles.some((f) => n.properties.filePath.endsWith(f))).map((n) => n.id)
            );
            setAffectedFileIds(fileIds);
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

  const { analyzing, agentSteps, currentStage, sessionId, checkpoint, result, error } = analysisState;

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-void">
      {/* ── Main layout ── */}
      <main className="flex min-h-0 flex-1">

        {/* Left panel — file tree */}
        <FileTreePanel onFocusNode={handleFocusNode} />

        {/* Centre — graph canvas */}
        <div className="relative min-w-0 flex-1">
          {graph ? (
            <GraphCanvas ref={graphCanvasRef} />
          ) : (
            /* No-graph placeholder */
            <div className="flex h-full flex-col items-center justify-center gap-4 bg-void">
              <div className="animate-breathe rounded-full border-2 border-accent/30 p-6">
                <div className="h-16 w-16 rounded-full bg-gradient-to-br from-accent/30 to-accent/5" />
              </div>
              <p className="text-sm text-text-muted">Index a repository to load the knowledge graph</p>
            </div>
          )}
        </div>

        {/* Right panel — controls + trace + results */}
        <div className="flex w-80 flex-col border-l border-border-subtle bg-surface">

          {/* Input area */}
          <div className="flex flex-col gap-4 border-b border-border-subtle p-4">
            <RepoInput
              onIndex={handleIndex}
              indexing={indexing}
              indexed={indexed}
              indexMessages={indexMessages}
            />
            <PrAnalysisPanel
              onAnalyze={handleAnalyze}
              analyzing={analyzing}
              currentStage={currentStage}
              sessionId={sessionId}
              disabled={!indexed}
            />
            {error && (
              <div className="rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
                {error}
              </div>
            )}
          </div>

          {/* Agent trace / results */}
          <div className="min-h-0 flex-1 overflow-hidden">
            {result ? (
              <TestPipelineResults result={result} onHighlightFiles={handleHighlightFiles} />
            ) : (
              <AgentTraceDrawer steps={agentSteps} analyzing={analyzing} currentStage={currentStage} />
            )}
          </div>
        </div>
      </main>

      <StatusBar />

      {/* Checkpoint modal */}
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
      <AppContent />
    </AppStateProvider>
  );
}

export default App;
