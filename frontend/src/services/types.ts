/** Workflow the user chose to run */
export type WorkflowId = 'unit_tests' | 'integration_tests' | 'e2e_planning';

/** Analysis pipeline stages */
export type AnalysisStage =
  | 'gathering'
  | 'unit_testing'
  | 'integration_testing'
  | 'e2e_planning'
  | 'submitting';

/** Checkpoint data from SSE */
export interface CheckpointData {
  session_id: string;
  stage_completed: AnalysisStage;
  intermediate_result: unknown;
  prompt: string;
}

/** Test case structures */
export interface UnitTestCase {
  name: string;
  scenario: string;
  expected: string;
}

export interface UnitTestSpec {
  target: string;
  priority: 'HIGH' | 'MEDIUM' | 'LOW' | 'CRITICAL';
  mocks: string[];
  test_cases: UnitTestCase[];
  generated_code?: string;
}

export interface IntegrationTestCase {
  name: string;
  scenario: string;
  expected: string;
}

export interface IntegrationTestSpec {
  integration_point: string;
  modules: string[];
  risk: 'HIGH' | 'MEDIUM' | 'LOW' | 'CRITICAL';
  data_setup: string;
  test_cases: IntegrationTestCase[];
}

export interface E2ETestStep {
  step_number: number;
  action: string;
  expected: string;
}

export interface E2ETestPlan {
  process: string;
  scenario: string;
  priority: 'HIGH' | 'MEDIUM' | 'LOW' | 'CRITICAL';
  estimated_duration: string;
  preconditions: string;
  steps: E2ETestStep[];
  affected_paths: string[];
}

/** Sprint 1 backend format — test_suggestions instead of structured specs */
export interface TestSuggestions {
  skip: string[];
  run: string[];
  deeper: string[];
}

export interface AffectedComponent {
  component: string;
  files_changed: string[];
  impact_summary: string;
  risks: string[];
  confidence: 'high' | 'medium' | 'low' | 'critical';
  /** Sprint 1 backend format */
  test_suggestions?: TestSuggestions;
  /** Sprint 2 backend format (future) */
  unit_tests?: UnitTestSpec[];
  integration_tests?: IntegrationTestSpec[];
}

export interface AnalyzeResult {
  pr_title: string;
  pr_url: string;
  pr_summary: string;
  affected_components: AffectedComponent[];
  /** Sprint 2 only */
  e2e_test_plans?: E2ETestPlan[];
  agent_steps: number;
}

export interface TestResult {
  test_name: string;
  status: 'passed' | 'failed' | 'error' | 'skipped';
  duration_ms: number;
  output?: string;
}

export interface TestRunSummary {
  total: number;
  passed: number;
  failed: number;
  errors: number;
  duration_ms: number;
}

/** Full analysis state shape */
export interface AnalysisState {
  prUrl: string | null;
  context: string | null;
  sessionId: string | null;
  activeWorkflow: WorkflowId | null;
  currentStage: AnalysisStage | null;
  agentSteps: Array<{ tool: string; summary: string; stage: AnalysisStage | null }>;
  checkpoint: CheckpointData | null;
  result: AnalyzeResult | null;
  error: string | null;
  analyzing: boolean;
  testResults: TestResult[];
  testSummary: TestRunSummary | null;
  testRunning: boolean;
}

/** SSE event types */
export type SSEEventType =
  | 'index_step'
  | 'index_done'
  | 'agent_step'
  | 'stage_change'
  | 'checkpoint'
  | 'result'
  | 'error'
  | 'test_result'
  | 'test_run_done';
