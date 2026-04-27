/** Workflow the user chose to run */
export type WorkflowId = 'unit_tests' | 'integration_tests' | 'e2e_planning';

/** Analysis pipeline stages — matches StateGraph node names from backend */
export type AnalysisStage =
  | 'gather'
  | 'unit_tests'
  | 'checkpoint_unit'
  | 'choice'
  | 'integration_tests'
  | 'e2e_checkpoint'
  | 'e2e_planning'
  | 'submit';

/** Checkpoint data from SSE — matches backend CheckpointEvent */
export interface CheckpointData {
  session_id: string;
  stage_completed: string;
  interrupt_type: string;  // "checkpoint" | "choice" | "e2e_context" | "question"
  payload: {
    type?: string;
    prompt?: string;
    options?: string[];
    intermediate_result?: unknown;
    [key: string]: unknown;
  };
}

/** Test case structures */
export interface UnitTestCase {
  name: string;
  scenario: string;
  expected: string;
}

export interface UnitTestSpec {
  target: string;
  priority: 'high' | 'medium' | 'low';
  mocks_needed: string[];
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
  modules_involved: string[];
  risk_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  data_setup: string;
  test_cases: IntegrationTestCase[];
  generated_code?: string;
}

export interface E2ETestStep {
  step: number;
  action: string;
  expected: string;
}

export interface E2ETestPlan {
  process: string;
  scenario: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  estimated_duration: string;
  preconditions: string;
  steps: E2ETestStep[];
  affected_by_pr: string[];
}

export interface AffectedComponent {
  component: string;
  files_changed: string[];
  impact_summary: string;
  impact_detail?: string;
  risks: string[];
  confidence: 'high' | 'medium' | 'low';
  unit_tests?: UnitTestSpec[];
  integration_tests?: IntegrationTestSpec[];
}

export interface AnalyzeResult {
  pr_title: string;
  pr_url: string;
  pr_summary: string;
  pr_summary_detail?: string;
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
  | 'test_run_done'
  | 'bug_stage_change'
  | 'bug_checkpoint'
  | 'research_progress'
  | 'bug_result'
  | 'export_ready';

// ── Sprint 3 bug + integrations (mirrors Pydantic models) ──────────────────

export type BugSeverity = 'critical' | 'major' | 'minor' | 'trivial';
export type Confidence3 = 'high' | 'medium' | 'low';

export interface BugReportRequest {
  description: string;
  environment?: string;
  severity?: BugSeverity;
  repo_url?: string;
  jira_ticket?: string;
  attachments?: string[];
  session_id?: string;
}

export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  source: string;
  labels: Record<string, unknown>;
}

export interface DocReference {
  title: string;
  url: string;
  source: string;
  snippet: string;
}

export interface RelatedIssue {
  key: string;
  summary: string;
  status: string;
  url: string;
}

export interface ResearchFindings {
  log_entries: LogEntry[];
  doc_references: DocReference[];
  related_issues: RelatedIssue[];
  db_state: Record<string, unknown>[];
  admin_notes: string[];
  evidence_summary: string;
}

export interface BugReport {
  title: string;
  severity: BugSeverity;
  category: string;
  environment: string;
  reproduction_steps: E2ETestStep[];
  expected_behavior: string;
  actual_behavior: string;
  root_cause_analysis: string;
  root_cause_detail?: string;
  affected_components: AffectedComponent[];
  evidence: ResearchFindings;
  recommendations: string[];
  recommendation_details?: string[];
  confidence: Confidence3;
  jira_url?: string;
}

export interface BugContinueRequest {
  action: 'approve' | 'refine' | 'add_context';
  feedback?: string;
  additional_context?: string;
}

export interface BugStageChangeEvent {
  type: 'bug_stage_change';
  stage: string;
  summary: string;
}

export interface BugCheckpointEvent {
  type: 'bug_checkpoint';
  session_id: string;
  stage_completed: string;
  interrupt_type: string;
  payload: Record<string, unknown>;
}

export interface ResearchProgressEvent {
  type: 'research_progress';
  source: string;
  finding_count: number;
  summary: string;
}

export interface BugReportResultEvent {
  type: 'bug_result';
  session_id: string;
  report: BugReport;
  agent_steps: number;
}

export interface IntegrationStatus {
  name: string;
  configured: boolean;
  healthy: boolean;
  message: string;
}
