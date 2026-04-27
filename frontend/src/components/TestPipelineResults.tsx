import { useState } from 'react';
import { ChevronDown, ChevronRight, CheckCircle, AlertTriangle, Layers, Code, Eye } from '@/lib/lucide-icons';
import type { AnalyzeResult, AffectedComponent, UnitTestSpec, IntegrationTestSpec, E2ETestPlan } from '../services/types';

const CONFIDENCE_STYLES: Record<string, string> = {
  critical: 'border-red-500/40 bg-red-500/10 text-red-400',
  high: 'border-orange-500/40 bg-orange-500/10 text-orange-400',
  medium: 'border-yellow-500/40 bg-yellow-500/10 text-yellow-400',
  low: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400',
};

/* ── Unit Test Card ── */
const UnitTestCard = ({ spec }: { spec: UnitTestSpec }) => {
  const [open, setOpen] = useState(false);
  const priorityStyle = CONFIDENCE_STYLES[spec.priority.toLowerCase()] || CONFIDENCE_STYLES.medium;

  return (
    <div className="rounded border border-border-subtle bg-deep">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 px-3 py-2 text-left">
        {open ? <ChevronDown className="h-3.5 w-3.5 text-text-muted" /> : <ChevronRight className="h-3.5 w-3.5 text-text-muted" />}
        <Code className="h-3.5 w-3.5 text-accent" />
        <span className="flex-1 font-mono text-xs text-text-primary">{spec.target}</span>
        <span className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${priorityStyle}`}>{spec.priority}</span>
        <span className="text-[10px] text-text-muted">{spec.test_cases.length} test{spec.test_cases.length !== 1 ? 's' : ''}</span>
      </button>
      {open && (
        <div className="border-t border-border-subtle px-3 pb-3 pt-2">
          {spec.mocks_needed.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-1">
              {spec.mocks_needed.map((m, i) => <span key={i} className="rounded bg-border-subtle px-1.5 py-0.5 font-mono text-[10px] text-text-muted">mock: {m}</span>)}
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            {spec.test_cases.map((tc, i) => (
              <div key={i} className="rounded bg-elevated/50 px-2.5 py-2">
                <p className="font-mono text-[11px] font-medium text-text-primary">{tc.name}</p>
                <p className="mt-0.5 text-[11px] text-text-muted">{tc.scenario}</p>
                <p className="mt-1 text-[11px] text-emerald-400">→ {tc.expected}</p>
              </div>
            ))}
          </div>
          {spec.generated_code && (
            <details className="mt-2">
              <summary className="cursor-pointer text-[11px] text-accent hover:underline">View generated code</summary>
              <pre className="scrollbar-thin mt-1 max-h-40 overflow-auto rounded bg-void p-2 font-mono text-[10px] text-text-secondary">{spec.generated_code}</pre>
            </details>
          )}
        </div>
      )}
    </div>
  );
};

/* ── Integration Test Card ── */
const IntegrationTestCard = ({ spec }: { spec: IntegrationTestSpec }) => {
  const [open, setOpen] = useState(false);
  const riskStyle = CONFIDENCE_STYLES[spec.risk_level.toLowerCase()] || CONFIDENCE_STYLES.medium;

  return (
    <div className="rounded border border-border-subtle bg-deep">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 px-3 py-2 text-left">
        {open ? <ChevronDown className="h-3.5 w-3.5 text-text-muted" /> : <ChevronRight className="h-3.5 w-3.5 text-text-muted" />}
        <Layers className="h-3.5 w-3.5 text-node-interface" />
        <span className="flex-1 font-mono text-xs text-text-primary">{spec.integration_point}</span>
        <span className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${riskStyle}`}>{spec.risk_level}</span>
      </button>
      {open && (
        <div className="border-t border-border-subtle px-3 pb-3 pt-2">
          <div className="mb-2 flex flex-wrap gap-1">
            {spec.modules_involved.map((m, i) => <span key={i} className="rounded bg-accent/10 px-1.5 py-0.5 font-mono text-[10px] text-accent">{m}</span>)}
          </div>
          {spec.data_setup && <p className="mb-2 text-[11px] text-text-muted">{spec.data_setup}</p>}
          <div className="flex flex-col gap-1.5">
            {spec.test_cases.map((tc, i) => (
              <div key={i} className="rounded bg-elevated/50 px-2.5 py-2">
                <p className="font-mono text-[11px] font-medium text-text-primary">{tc.name}</p>
                <p className="mt-0.5 text-[11px] text-text-muted">{tc.scenario}</p>
                <p className="mt-1 text-[11px] text-emerald-400">→ {tc.expected}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

/* ── E2E Plan Card ── */
const E2EPlanCard = ({ plan }: { plan: E2ETestPlan }) => {
  const [open, setOpen] = useState(false);
  const priorityStyle = CONFIDENCE_STYLES[plan.priority.toLowerCase()] || CONFIDENCE_STYLES.medium;

  return (
    <div className="rounded border border-border-subtle bg-deep">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 px-3 py-2 text-left">
        {open ? <ChevronDown className="h-3.5 w-3.5 text-text-muted" /> : <ChevronRight className="h-3.5 w-3.5 text-text-muted" />}
        <Eye className="h-3.5 w-3.5 text-node-function" />
        <span className="flex-1 text-xs text-text-primary">{plan.process}</span>
        <span className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${priorityStyle}`}>{plan.priority}</span>
        <span className="text-[10px] text-text-muted">{plan.estimated_duration}</span>
      </button>
      {open && (
        <div className="border-t border-border-subtle px-3 pb-3 pt-2">
          <p className="mb-2 text-[11px] italic text-text-secondary">{plan.scenario}</p>
          {plan.preconditions && <p className="mb-2 text-[11px] text-text-muted">Pre: {plan.preconditions}</p>}
          <ol className="flex flex-col gap-1.5">
            {plan.steps.map((step) => (
              <li key={step.step} className="flex gap-2 rounded bg-elevated/50 px-2.5 py-2">
                <span className="shrink-0 font-mono text-[10px] font-medium text-accent">{step.step}.</span>
                <div>
                  <p className="text-[11px] text-text-primary">{step.action}</p>
                  <p className="mt-0.5 text-[11px] text-emerald-400">→ {step.expected}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
};

/* ── Component Card ── */
const ComponentResultCard = ({ component }: { component: AffectedComponent }) => {
  const [open, setOpen] = useState(true);
  const [activeTab, setActiveTab] = useState<'unit' | 'integration'>('unit');
  const confStyle = CONFIDENCE_STYLES[component.confidence] || CONFIDENCE_STYLES.medium;

  return (
    <div className="rounded-lg border border-border-default bg-elevated">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-3 px-4 py-3 text-left">
        {open ? <ChevronDown className="h-4 w-4 text-text-muted" /> : <ChevronRight className="h-4 w-4 text-text-muted" />}
        <div className="flex-1">
          <span className="text-sm font-medium text-text-primary">{component.component}</span>
          <span className="ml-2 text-xs text-text-muted">{component.files_changed.length} file{component.files_changed.length !== 1 ? 's' : ''}</span>
        </div>
        <span className={`rounded border px-2 py-0.5 text-[10px] font-medium uppercase ${confStyle}`}>{component.confidence}</span>
      </button>

      {open && (
        <div className="border-t border-border-subtle px-4 pb-4 pt-3">
          <p className="mb-3 text-xs leading-relaxed text-text-secondary">{component.impact_summary}</p>

          {component.risks.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-1.5">
              {component.risks.map((r, i) => (
                <span key={i} className="flex items-center gap-1 rounded border border-orange-500/30 bg-orange-500/10 px-2 py-0.5 text-[10px] text-orange-400">
                  <AlertTriangle className="h-2.5 w-2.5" />{r}
                </span>
              ))}
            </div>
          )}

          {component.files_changed.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-1">
              {component.files_changed.map((f, i) => <span key={i} className="font-mono text-[10px] text-text-muted">{f}</span>)}
            </div>
          )}

          {/* Sprint 2: Unit / Integration tabs */}
          {((component.unit_tests?.length ?? 0) > 0 || (component.integration_tests?.length ?? 0) > 0) && (
            <>
              <div className="mb-2 flex gap-1 border-b border-border-subtle pb-2">
                <button onClick={() => setActiveTab('unit')} className={`rounded px-2 py-1 text-xs transition-colors ${activeTab === 'unit' ? 'bg-accent/20 text-accent' : 'text-text-muted hover:text-text-secondary'}`}>
                  Unit ({component.unit_tests?.length ?? 0})
                </button>
                <button onClick={() => setActiveTab('integration')} className={`rounded px-2 py-1 text-xs transition-colors ${activeTab === 'integration' ? 'bg-accent/20 text-accent' : 'text-text-muted hover:text-text-secondary'}`}>
                  Integration ({component.integration_tests?.length ?? 0})
                </button>
              </div>
              <div className="flex flex-col gap-2">
                {activeTab === 'unit' && component.unit_tests?.map((spec, i) => <UnitTestCard key={i} spec={spec} />)}
                {activeTab === 'integration' && component.integration_tests?.map((spec, i) => <IntegrationTestCard key={i} spec={spec} />)}
              </div>
            </>
          )}

        </div>
      )}
    </div>
  );
};

/* ── Main Results Panel ── */
interface TestPipelineResultsProps {
  result: AnalyzeResult;
  onHighlightFiles: (filePaths: string[]) => void;
}

export const TestPipelineResults = ({ result, onHighlightFiles }: TestPipelineResultsProps) => {
  const [activeSection, setActiveSection] = useState<'components' | 'e2e'>('components');

  const allFiles = result.affected_components.flatMap((c) => c.files_changed);

  return (
    <div className="flex h-full flex-col bg-surface">
      {/* PR Summary header */}
      <div className="border-b border-border-subtle bg-elevated/50 px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <a href={result.pr_url} target="_blank" rel="noopener noreferrer" className="block truncate text-sm font-medium text-accent hover:underline">{result.pr_title}</a>
            <p className="mt-1 text-[11px] leading-relaxed text-text-muted">{result.pr_summary}</p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1 text-[10px] text-text-muted">
            <span>{result.agent_steps} steps</span>
            <span>{result.affected_components.length} components</span>
          </div>
        </div>
        {allFiles.length > 0 && (
          <button
            onClick={() => onHighlightFiles(allFiles)}
            className="mt-2 flex items-center gap-1.5 rounded border border-accent/30 bg-accent/10 px-2.5 py-1 text-[11px] text-accent transition-colors hover:bg-accent/20"
          >
            <CheckCircle className="h-3 w-3" />
            Highlight {allFiles.length} affected files in graph
          </button>
        )}
      </div>

      {/* Section tabs */}
      <div className="flex border-b border-border-subtle px-4">
        <button
          onClick={() => setActiveSection('components')}
          className={`border-b-2 px-3 py-2 text-xs transition-colors ${activeSection === 'components' ? 'border-accent text-accent' : 'border-transparent text-text-muted hover:text-text-secondary'}`}
        >
          Components ({result.affected_components.length})
        </button>
        <button
          onClick={() => setActiveSection('e2e')}
          className={`border-b-2 px-3 py-2 text-xs transition-colors ${activeSection === 'e2e' ? 'border-accent text-accent' : 'border-transparent text-text-muted hover:text-text-secondary'}`}
        >
          E2E Plans ({result.e2e_test_plans?.length ?? 0})
        </button>
      </div>

      {/* Content */}
      <div className="scrollbar-thin flex-1 overflow-y-auto p-4">
        {activeSection === 'components' && (
          <div className="flex flex-col gap-3">
            {result.affected_components.map((comp, i) => (
              <ComponentResultCard
                key={i}
                component={comp}
              />
            ))}
          </div>
        )}
        {activeSection === 'e2e' && (
          <div className="flex flex-col gap-2">
            {(result.e2e_test_plans ?? []).length === 0 ? (
              <p className="py-4 text-center text-xs text-text-muted">No E2E plans generated</p>
            ) : (
              (result.e2e_test_plans ?? []).map((plan, i) => <E2EPlanCard key={i} plan={plan} />)
            )}
          </div>
        )}
      </div>
    </div>
  );
};
