import { createContext, useContext, useMemo, ReactNode } from 'react';
import { GraphStateProvider, useGraphState } from './app-state/graph';
import type { PipelineProgress } from 'qlankr-shared';
import type { AnalysisState } from '../services/types';
import type { ProjectDetail } from '../services/api';
import { useState } from 'react';

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

  // Current project (replaces repoUrl)
  currentProject: ProjectDetail | null;
  setCurrentProject: (p: ProjectDetail | null) => void;

  // Backward-compat shim for LegacyApp.tsx. repoUrl is derived from
  // currentProject; setRepoUrl is a no-op because the project is now
  // selected via routing (/projects/:id), not by mutating state.
  repoUrl: string | null;
  setRepoUrl: (url: string | null) => void;

  // Repo indexing
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

  // Current project
  const [currentProject, setCurrentProject] = useState<ProjectDetail | null>(null);

  // Repo indexing
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
      currentProject, setCurrentProject,
      repoUrl: currentProject?.repo_url ?? null,
      setRepoUrl: () => { /* no-op: project is selected via routing now */ },
      indexing, setIndexing,
      indexed, setIndexed,
      indexMessages, setIndexMessages,
      progress, setProgress,
      analysisState, setAnalysisState,
      affectedFileIds, setAffectedFileIds,
    }),
    [graphState, currentProject, indexing, indexed, indexMessages, progress, analysisState, affectedFileIds],
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
