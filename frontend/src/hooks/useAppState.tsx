import { createContext, useContext, useMemo, ReactNode } from 'react';
import { GraphStateProvider, useGraphState } from './app-state/graph';
import type { PipelineProgress } from 'qlankr-shared';
import type { AnalysisStage, AnalysisState, CheckpointData, AnalyzeResult, TestRunSummary, TestResult } from '../services/types';
import { useState, useCallback } from 'react';

/** App state context — combines graph state + Qlankr analysis state */
interface AppStateContextValue {
  // Graph state (delegated)
  graph: ReturnType<typeof useGraphState>['graph'];
  setGraph: ReturnType<typeof useGraphState>['setGraph'];
  selectedNode: ReturnType<typeof useGraphState>['selectedNode'];
  setSelectedNode: ReturnType<typeof useGraphState>['setSelectedNode'];
  visibleLabels: ReturnType<typeof useGraphState>['visibleLabels'];
  toggleLabelVisibility: ReturnType<typeof useGraphState>['toggleLabelVisibility'];
  visibleEdgeTypes: ReturnType<typeof useGraphState>['visibleEdgeTypes'];
  toggleEdgeVisibility: ReturnType<typeof useGraphState>['toggleEdgeVisibility'];
  depthFilter: ReturnType<typeof useGraphState>['depthFilter'];
  setDepthFilter: ReturnType<typeof useGraphState>['setDepthFilter'];
  highlightedNodeIds: ReturnType<typeof useGraphState>['highlightedNodeIds'];
  setHighlightedNodeIds: ReturnType<typeof useGraphState>['setHighlightedNodeIds'];

  // Repo indexing
  repoUrl: string | null;
  setRepoUrl: (url: string | null) => void;
  indexing: boolean;
  setIndexing: (v: boolean) => void;
  indexed: boolean;
  setIndexed: (v: boolean) => void;
  indexMessages: Array<{ stage: string; summary: string }>;
  setIndexMessages: React.Dispatch<React.SetStateAction<Array<{ stage: string; summary: string }>>>;
  progress: PipelineProgress | null;
  setProgress: (p: PipelineProgress | null) => void;

  // Analysis
  analysisState: AnalysisState;
  setAnalysisState: React.Dispatch<React.SetStateAction<AnalysisState>>;

  // Affected nodes highlight (for graph viz)
  affectedFileIds: Set<string>;
  setAffectedFileIds: (ids: Set<string>) => void;
}

const AppStateContext = createContext<AppStateContextValue | null>(null);

const AppStateProviderInner = ({ children }: { children: ReactNode }) => {
  const graphState = useGraphState();

  // Repo indexing
  const [repoUrl, setRepoUrl] = useState<string | null>(null);
  const [indexing, setIndexing] = useState(false);
  const [indexed, setIndexed] = useState(false);
  const [indexMessages, setIndexMessages] = useState<Array<{ stage: string; summary: string }>>([]);
  const [progress, setProgress] = useState<PipelineProgress | null>(null);

  // Analysis state
  const [analysisState, setAnalysisState] = useState<AnalysisState>({
    prUrl: null,
    context: null,
    sessionId: null,
    activeWorkflow: null,
    currentStage: null,
    agentSteps: [],
    checkpoint: null,
    result: null,
    error: null,
    analyzing: false,
    testResults: [],
    testSummary: null,
    testRunning: false,
  });

  // Affected file IDs for graph highlighting
  const [affectedFileIds, setAffectedFileIds] = useState<Set<string>>(new Set());

  const value = useMemo<AppStateContextValue>(
    () => ({
      ...graphState,
      repoUrl, setRepoUrl,
      indexing, setIndexing,
      indexed, setIndexed,
      indexMessages, setIndexMessages,
      progress, setProgress,
      analysisState, setAnalysisState,
      affectedFileIds, setAffectedFileIds,
    }),
    [graphState, repoUrl, indexing, indexed, indexMessages, progress, analysisState, affectedFileIds],
  );

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
};

export const AppStateProvider = ({ children }: { children: ReactNode }) => {
  return (
    <GraphStateProvider>
      <AppStateProviderInner>{children}</AppStateProviderInner>
    </GraphStateProvider>
  );
};

export const useAppState = (): AppStateContextValue => {
  const ctx = useContext(AppStateContext);
  if (!ctx) throw new Error('useAppState must be used within an AppStateProvider');
  return ctx;
};
