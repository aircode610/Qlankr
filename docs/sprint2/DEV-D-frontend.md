# Dev D: Frontend — GitNexus UI Integration + Qlankr Panels

**Branch:** `devd/gitnexus-ui`
**Depends on:** Dev C's models (for SSE event types), Dev A + B's backend (for API contracts)
**Merges:** Last (after backend is stable)
**Files owned:**
- `frontend/` — entire frontend directory (replacing current React app)

---

## Overview

Replace the current custom React + Vite + Tailwind frontend with the GitNexus web explorer as the UI shell, then add Qlankr-specific panels for PR analysis, the 3-stage testing pipeline results, agent trace, and human-in-the-loop checkpoints.

---

## Part 1: GitNexus Web Explorer Integration

### Option A: Fork the GitNexus web source (preferred)

1. Clone/fork the GitNexus web app source from the gitnexus repo
2. It's a client-side app using Tree-sitter WASM + LadybugDB WASM for in-browser code analysis
3. Keep the graph explorer and its interactions (drag, zoom, hover, cluster filtering)
4. Keep the AI chat panel shell (we'll rewire it to our backend)
5. Add Qlankr branding (logo, colors, title)

### Option B: Rebuild with GitNexus visual style (fallback)

If licensing prevents forking, rebuild our current frontend to match the GitNexus visual style:
1. Keep our Sigma.js graph explorer
2. Add a chat-style panel for agent interaction
3. Match the GitNexus dark theme and layout

### What to preserve from current frontend

These patterns from the current app should carry over regardless of which option:

| Pattern | Current implementation | Keep/adapt |
|---------|----------------------|------------|
| SSE streaming | `api.js` with typed event generators | Adapt to new event types |
| Repo indexing flow | `RepoInput.jsx` → `POST /index` → progress events | Keep, wire to new UI |
| Graph visualization | `KnowledgeGraph.jsx` (Sigma.js + Graphology) | Keep if Option B; replace if Option A |
| PR input | `PRInput.jsx` → `POST /analyze` | Keep, add `context` field |
| Agent trace | `AgentTrace.jsx` → `agent_step` events | Keep, add `stage_change` events |

---

## Part 2: New Components

### 2.1 SSE Client (`api.js` rewrite)

Update the SSE client to handle new event types:

```javascript
// Event types the frontend must handle:
const EVENT_TYPES = {
  // Indexing (unchanged)
  'index_step': 'index_step',
  'index_done': 'index_done',

  // Analysis (updated)
  'agent_step': 'agent_step',       // tool call trace
  'stage_change': 'stage_change',   // stage transition
  'checkpoint': 'checkpoint',       // human-in-the-loop pause
  'result': 'result',               // final analysis result
  'error': 'error',                 // error

  // Test execution (Phase 4)
  'test_result': 'test_result',     // individual test pass/fail
  'test_run_done': 'test_run_done', // test run summary
};

/**
 * Start analysis. Returns an async generator of SSE events.
 * @param {string} prUrl
 * @param {string|null} context - optional bug report / scenario
 * @param {string|null} sessionId - set when resuming after checkpoint
 */
export async function* analyzePR(prUrl, context = null, sessionId = null) {
  const body = { pr_url: prUrl };
  if (context) body.context = context;
  if (sessionId) body.session_id = sessionId;

  const response = await fetch(`${API_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  // ... SSE parsing (same pattern as current api.js)
}

/**
 * Continue analysis after checkpoint.
 * @param {string} sessionId
 * @param {string} action - "approve" | "add_context" | "skip" | "rerun"
 * @param {string|null} additionalContext
 */
export async function* continueAnalysis(sessionId, action, additionalContext = null) {
  const body = { action };
  if (additionalContext) body.additional_context = additionalContext;

  const response = await fetch(`${API_URL}/analyze/${sessionId}/continue`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  // ... SSE parsing
}
```

### 2.2 `PrAnalysisPanel` — PR Input + Context

Replaces the current `PRInput.jsx`. Additions:

- **Context textarea:** Optional field for bug report or user scenario
  ```
  "Users report that crafting crashes when inventory is full.
   Steps: open inventory → select recipe → click craft → crash"
  ```
- **Session awareness:** Shows session_id after analysis starts
- **Stage indicator:** Shows which stage the agent is currently in

```jsx
function PrAnalysisPanel({ onAnalyze, currentStage, sessionId }) {
  const [prUrl, setPrUrl] = useState('');
  const [context, setContext] = useState('');

  return (
    <div className="panel">
      <h2>PR Analysis</h2>
      <input placeholder="GitHub PR URL" value={prUrl} onChange={...} />
      <textarea
        placeholder="Optional: describe a bug report or scenario to focus E2E testing..."
        value={context}
        onChange={...}
      />
      <button onClick={() => onAnalyze(prUrl, context)}>Analyze</button>

      {sessionId && (
        <div className="session-info">
          Session: {sessionId}
          {currentStage && <span className="stage-badge">{currentStage}</span>}
        </div>
      )}
    </div>
  );
}
```

### 2.3 `AgentTraceDrawer` — Live Agent Trace with Stages

Updates the current `AgentTrace.jsx`:

- **Stage sections:** Group tool calls under their stage heading
- **Stage badges:** Visual indicator (gathering / unit_testing / integration_testing / e2e_planning / submitting)
- **Progress bar:** Shows approximate progress through stages

```jsx
function AgentTraceDrawer({ steps, currentStage }) {
  // Group steps by stage
  const stageGroups = groupByStage(steps);

  const stages = ['gathering', 'unit_testing', 'integration_testing', 'e2e_planning', 'submitting'];
  const currentIndex = stages.indexOf(currentStage);

  return (
    <div className="trace-drawer">
      {/* Progress bar */}
      <div className="stage-progress">
        {stages.map((stage, i) => (
          <div
            key={stage}
            className={`stage-dot ${i < currentIndex ? 'completed' : ''} ${i === currentIndex ? 'active' : ''}`}
          >
            {stageLabel(stage)}
          </div>
        ))}
      </div>

      {/* Tool calls grouped by stage */}
      {stages.map(stage => (
        stageGroups[stage]?.length > 0 && (
          <div key={stage} className="stage-group">
            <h3>{stageLabel(stage)}</h3>
            {stageGroups[stage].map((step, i) => (
              <div key={i} className="tool-call">
                <span className="tool-name">{step.tool}</span>
                <span className="tool-summary">{step.summary}</span>
              </div>
            ))}
          </div>
        )
      ))}
    </div>
  );
}
```

### 2.4 `TestPipelineResults` — 3-Stage Results View

Replaces `ImpactSummary` + `ComponentCard`. This is the main results display.

**Layout:**

```
┌─────────────────────────────────────────────┐
│ PR: "Fix inventory overflow" (#42)          │
│ Summary: ...                                │
├─────────────────────────────────────────────┤
│ ▼ Stage 1: Unit Tests (8 specs, 23 cases)   │
│   ┌─ PlayerInventory.addItem ──────────────┐│
│   │ Priority: HIGH                         ││
│   │ Mocks: DatabaseConnection, EventBus    ││
│   │ ✓ adds item to empty inventory         ││
│   │ ✓ rejects when inventory full          ││
│   │ ✓ handles null item gracefully         ││
│   └────────────────────────────────────────┘│
│   ┌─ CraftingSystem.craft ─────────────────┐│
│   │ ...                                    ││
│   └────────────────────────────────────────┘│
├─────────────────────────────────────────────┤
│ ▼ Stage 2: Integration Tests (3 points)     │
│   ┌─ Inventory <> Crafting ────────────────┐│
│   │ Risk: HIGH                             ││
│   │ Modules: inventory, crafting           ││
│   │ Setup: player with 5 wood, 3 iron     ││
│   │ ✓ crafting consumes correct items      ││
│   │ ✓ fails gracefully when item removed   ││
│   └────────────────────────────────────────┘│
├─────────────────────────────────────────────┤
│ ▼ Stage 3: E2E Test Plans (2 scenarios)     │
│   ┌─ item_crafting_flow ───────────────────┐│
│   │ Priority: CRITICAL | ~5 min            ││
│   │ Preconditions: player has materials    ││
│   │ 1. Open inventory → see items          ││
│   │ 2. Select recipe → materials shown     ││
│   │ 3. Click craft → item created          ││
│   │ 4. Check inventory → materials gone    ││
│   │ ⚠ Step 3 affected by PR: addItem...   ││
│   └────────────────────────────────────────┘│
├─────────────────────────────────────────────┤
│ [Export Markdown] [Run Tests (Phase 4)]     │
└─────────────────────────────────────────────┘
```

**Component structure:**

```jsx
function TestPipelineResults({ result }) {
  // result is the full AnalyzeResponse
  const { affected_components, e2e_test_plans } = result;

  // Aggregate unit test stats
  const unitStats = aggregateUnitStats(affected_components);
  const integrationStats = aggregateIntegrationStats(affected_components);

  return (
    <div className="results">
      <PrHeader result={result} />

      <StageSection
        title="Stage 1: Unit Tests"
        stats={`${unitStats.specs} specs, ${unitStats.cases} cases`}
        defaultOpen={true}
      >
        {affected_components.map(comp => (
          comp.unit_tests.map(spec => (
            <UnitTestCard key={spec.target} spec={spec} />
          ))
        ))}
      </StageSection>

      <StageSection
        title="Stage 2: Integration Tests"
        stats={`${integrationStats.points} integration points`}
      >
        {affected_components.flatMap(comp =>
          comp.integration_tests.map(spec => (
            <IntegrationTestCard key={spec.integration_point} spec={spec} />
          ))
        )}
      </StageSection>

      <StageSection
        title="Stage 3: E2E Test Plans"
        stats={`${e2e_test_plans.length} scenarios`}
      >
        {e2e_test_plans.map(plan => (
          <E2ETestPlanCard key={plan.process} plan={plan} />
        ))}
      </StageSection>

      <ResultActions result={result} />
    </div>
  );
}
```

**Sub-components:**
- `UnitTestCard` — shows target, priority badge, mocks, test case list
- `IntegrationTestCard` — shows integration point, risk badge, modules, setup, test cases
- `E2ETestPlanCard` — shows process, priority, preconditions, numbered steps with affected-by-PR warnings
- `StageSection` — collapsible section with title, stats badge, children
- `PrHeader` — PR title, URL, summary
- `ResultActions` — export button, run tests button (Phase 4)

### 2.5 `CheckpointDialog` — Human-in-the-Loop

Modal dialog that appears when a `checkpoint` SSE event is received.

```jsx
function CheckpointDialog({ checkpoint, onContinue }) {
  // checkpoint = { session_id, stage_completed, intermediate_result, prompt }
  const [action, setAction] = useState('approve');
  const [additionalContext, setAdditionalContext] = useState('');

  return (
    <div className="modal-overlay">
      <div className="modal">
        <h2>Stage Complete: {stageLabel(checkpoint.stage_completed)}</h2>
        <p>{checkpoint.prompt}</p>

        {/* Show intermediate results preview */}
        <div className="intermediate-preview">
          <IntermediateResultPreview data={checkpoint.intermediate_result} />
        </div>

        {/* Action selector */}
        <div className="actions">
          <button
            className={action === 'approve' ? 'selected' : ''}
            onClick={() => setAction('approve')}
          >
            Approve & Continue
          </button>
          <button
            className={action === 'add_context' ? 'selected' : ''}
            onClick={() => setAction('add_context')}
          >
            Add Context
          </button>
          <button
            className={action === 'skip' ? 'selected' : ''}
            onClick={() => setAction('skip')}
          >
            Skip Next Stage
          </button>
          <button
            className={action === 'rerun' ? 'selected' : ''}
            onClick={() => setAction('rerun')}
          >
            Re-run This Stage
          </button>
        </div>

        {action === 'add_context' && (
          <textarea
            placeholder="Add context for the next stage..."
            value={additionalContext}
            onChange={e => setAdditionalContext(e.target.value)}
          />
        )}

        <button
          className="primary"
          onClick={() => onContinue(
            checkpoint.session_id,
            action,
            action === 'add_context' ? additionalContext : null
          )}
        >
          Continue
        </button>
      </div>
    </div>
  );
}
```

### 2.6 `TestExecutionPanel` (Phase 4)

Shows results from `POST /run-tests`:

```jsx
function TestExecutionPanel({ sessionId }) {
  const [results, setResults] = useState([]);
  const [summary, setSummary] = useState(null);
  const [running, setRunning] = useState(false);

  async function runTests() {
    setRunning(true);
    for await (const event of executeTests(sessionId)) {
      if (event.type === 'test_result') {
        setResults(prev => [...prev, event.result]);
      } else if (event.type === 'test_run_done') {
        setSummary(event);
        setRunning(false);
      }
    }
  }

  return (
    <div className="test-execution">
      <button onClick={runTests} disabled={running}>
        {running ? 'Running...' : 'Run Generated Tests'}
      </button>

      {results.map((r, i) => (
        <div key={i} className={`test-result ${r.status}`}>
          <span className="status-icon">{statusIcon(r.status)}</span>
          <span className="test-name">{r.test_name}</span>
          <span className="duration">{r.duration_ms}ms</span>
          {r.output && <pre className="output">{r.output}</pre>}
        </div>
      ))}

      {summary && (
        <div className="summary">
          {summary.passed}/{summary.total} passed |
          {summary.failed} failed |
          {summary.errors} errors |
          {summary.duration_ms}ms total
        </div>
      )}
    </div>
  );
}
```

### 2.7 Graph Highlighting

When analysis results arrive, highlight affected nodes in the graph explorer:

- **Changed files:** Red border/glow
- **Affected files (by blast radius):** Orange border
- **Affected clusters:** Brighter cluster color
- **Process paths:** Animated edges showing execution flow

Implementation depends on Option A vs B:
- **Option A (GitNexus explorer):** Use the explorer's API to highlight nodes by ID
- **Option B (Sigma.js):** Update node attributes in Graphology, Sigma re-renders automatically

---

## Part 3: App State Management

### State shape

```javascript
const [appState, setAppState] = useState({
  // Repo indexing
  repoUrl: null,
  indexing: false,
  indexed: false,
  graphData: null,

  // Analysis
  prUrl: null,
  context: null,          // user-provided bug report / scenario
  sessionId: null,
  currentStage: null,     // "gathering" | "unit_testing" | ...
  agentSteps: [],         // { tool, summary, stage }
  checkpoint: null,       // current checkpoint event (if paused)
  result: null,           // final AnalyzeResponse

  // Test execution (Phase 4)
  testResults: [],
  testSummary: null,
  testRunning: false,
});
```

### Event handling

```javascript
async function handleAnalyze(prUrl, context) {
  setAppState(s => ({ ...s, prUrl, context, currentStage: 'gathering', agentSteps: [], result: null }));

  for await (const event of analyzePR(prUrl, context)) {
    switch (event.type) {
      case 'stage_change':
        setAppState(s => ({ ...s, currentStage: event.stage }));
        break;
      case 'agent_step':
        setAppState(s => ({
          ...s,
          agentSteps: [...s.agentSteps, { ...event, stage: s.currentStage }],
        }));
        break;
      case 'checkpoint':
        setAppState(s => ({ ...s, checkpoint: event, sessionId: event.session_id }));
        return; // stop consuming — wait for user action
      case 'result':
        setAppState(s => ({ ...s, result: event, currentStage: null }));
        break;
      case 'error':
        setAppState(s => ({ ...s, error: event.message, currentStage: null }));
        break;
    }
  }
}

async function handleContinue(sessionId, action, additionalContext) {
  setAppState(s => ({ ...s, checkpoint: null }));

  for await (const event of continueAnalysis(sessionId, action, additionalContext)) {
    // Same switch as above
  }
}
```

---

## Part 4: Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  Qlankr                                          [Settings]      │
├──────────────┬───────────────────────────────────┬───────────────┤
│              │                                   │               │
│  Left Panel  │     Graph Explorer (center)       │  Right Panel  │
│              │                                   │               │
│  - Repo      │     [GitNexus graph viz]          │  - Agent      │
│    Input     │                                   │    Trace      │
│              │     Nodes highlighted on           │    Drawer     │
│  - PR        │     analysis results              │               │
│    Analysis  │                                   │  - Stage      │
│    Panel     │                                   │    Progress   │
│              │                                   │               │
│  - Context   │                                   │               │
│    Input     │                                   │               │
│              │                                   │               │
├──────────────┴───────────────────────────────────┴───────────────┤
│                                                                  │
│  Bottom Panel: TestPipelineResults (expandable, shows on result) │
│                                                                  │
│  [Stage 1: Unit Tests] [Stage 2: Integration] [Stage 3: E2E]    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

CheckpointDialog: modal overlay when checkpoint event received
```

---

## Acceptance Criteria

- [ ] App builds and runs with GitNexus graph explorer (or equivalent Sigma.js viz)
- [ ] Repo indexing works through the new UI (URL input → progress → graph)
- [ ] PR analysis works with optional context field
- [ ] Agent trace shows tool calls grouped by stage with progress bar
- [ ] `stage_change` events update the stage indicator in real time
- [ ] `checkpoint` events trigger the CheckpointDialog modal
- [ ] User can approve, add context, skip, or rerun from the dialog
- [ ] After continue, SSE stream resumes and trace updates
- [ ] Final results display in the 3-stage TestPipelineResults view
- [ ] Unit test specs show target, priority, mocks, test cases
- [ ] Integration test specs show modules, risk, setup, test cases
- [ ] E2E test plans show numbered steps with affected-by-PR warnings
- [ ] Markdown export works for all 3 stages
- [ ] Graph highlights affected nodes/edges after analysis
- [ ] Responsive layout works on 1280px+ screens
- [ ] (Phase 4) Run Tests button triggers container execution and streams results

---

## Testing

Update `frontend/src/test/`:

**New test files:**
- `components/PrAnalysisPanel.test.jsx` — context field, session display
- `components/TestPipelineResults.test.jsx` — renders all 3 stages, handles empty states
- `components/CheckpointDialog.test.jsx` — all 4 actions, context input
- `components/AgentTraceDrawer.test.jsx` — stage grouping, progress bar
- `components/TestExecutionPanel.test.jsx` — (Phase 4)
- `api.test.js` — updated for new event types, continueAnalysis()

**Mock data:**
Update `mock/mockApi.js` and `mock/mockGraphData.js` to include:
- 3-stage result payloads
- Checkpoint events
- Stage change events
- Test execution events (Phase 4)
