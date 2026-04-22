# Dev D: Frontend — Bug Input, Reproduction Trace, Report View, Settings

**Branch:** `devd/bug-repro-ui`
**Depends on:** Dev C's models (SSE events), Dev A's agent (event stream), Dev B's integrations (settings API)
**Files owned:**
- `frontend/src/components/BugInputPanel.tsx` — NEW: Bug description form
- `frontend/src/components/BugTraceDrawer.tsx` — NEW: Live stage progress for bug reproduction
- `frontend/src/components/ResearchPanel.tsx` — NEW: Research findings display
- `frontend/src/components/BugReportView.tsx` — NEW: Developer-ready report display + export
- `frontend/src/components/BugCheckpointDialog.tsx` — NEW: Checkpoint dialogs for bug flow
- `frontend/src/components/SettingsPanel.tsx` — NEW: Integration configuration UI
- `frontend/src/App.tsx` — update: add navigation between Impact Analysis and Bug Reproduction modes
- `frontend/src/services/api.ts` — extend: new API client functions for bug endpoints
- `frontend/src/services/types.ts` — extend: TypeScript types matching Dev C's models

**Shared files (coordinate with):**
- `shared/src/pipeline.ts` — may need new types for bug reproduction stages

---

## Overview

Build the frontend for the bug reproduction pipeline and integration settings. The UI is a parallel workflow to the existing Impact Analysis — users switch between the two modes via a top-level navigation.

**Five new views:**
1. **Bug input form** — where the user describes the bug
2. **Bug trace drawer** — live progress through triage → mechanics → reproduction → research → report
3. **Checkpoint dialogs** — review mechanics analysis + approve/refine; review research + approve/add context
4. **Report view** — the final developer-ready bug report with export buttons
5. **Settings panel** — configure external tool integrations (Jira, Notion, Grafana, etc.)

---

## Navigation Update

Update `App.tsx` to support two modes:

```tsx
type AppMode = "impact-analysis" | "bug-reproduction";

// Top-level tab navigation
<nav>
  <button onClick={() => setMode("impact-analysis")} active={mode === "impact-analysis"}>
    Impact Analysis
  </button>
  <button onClick={() => setMode("bug-reproduction")} active={mode === "bug-reproduction"}>
    Bug Reproduction
  </button>
  <button onClick={() => setShowSettings(true)}>
    Settings
  </button>
</nav>
```

When `mode === "impact-analysis"`, render the existing Sprint 2 UI (PrAnalysisPanel, AgentTraceDrawer, TestPipelineResults, etc.).
When `mode === "bug-reproduction"`, render the new bug reproduction UI (BugInputPanel, BugTraceDrawer, ResearchPanel, BugReportView).

The knowledge graph canvas is shared — it renders in both modes.

---

## Component 1: BugInputPanel

**File:** `frontend/src/components/BugInputPanel.tsx`

**Purpose:** Form for the QA tester to describe a bug and start the reproduction pipeline.

**Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Bug description | textarea | Yes | Free-text description of the bug |
| Environment | text input | No | "iOS 17.4, iPhone 15, build 4.2.1" |
| Severity | dropdown | No | critical / major / minor / trivial |
| Repository | text input | No | GitHub repo URL (for code tracing) |
| Jira ticket | text input | No | Linked Jira issue key (e.g., "QA-123") |
| Attachments | file input / URL list | No | Screenshots, videos, HAR files |

**Behavior:**
- "Analyze Bug" button sends POST /bug-report with form data
- Button disabled until description is non-empty
- On submit: switches view to BugTraceDrawer
- Validates Jira ticket format if provided (e.g., `^[A-Z]+-\d+$`)
- Shows which integrations are available (green dot = configured)

**Mockup:**
```
┌──────────────────────────────────────────────┐
│  Describe the Bug                             │
│  ┌──────────────────────────────────────────┐ │
│  │ Players lose items when teleporting      │ │
│  │ between zones. Inventory shows empty     │ │
│  │ after zone transition completes...       │ │
│  └──────────────────────────────────────────┘ │
│                                               │
│  Environment: [iOS 17.4, build 4.2.1       ] │
│  Severity:    [major ▼]                       │
│  Repository:  [github.com/studio/game      ] │
│  Jira Ticket: [QA-456                      ] │
│  Attachments: [+ Add file or URL]             │
│                                               │
│  Available: ●GitHub ●Jira ●Notion ○Grafana   │
│                                               │
│  [   Analyze Bug   ]                          │
└──────────────────────────────────────────────┘
```

---

## Component 2: BugTraceDrawer

**File:** `frontend/src/components/BugTraceDrawer.tsx`

**Purpose:** Show live progress through the bug reproduction pipeline stages.

**Design:** Follows the same pattern as `AgentTraceDrawer` from Sprint 2 but adapted for the bug reproduction stages.

**Stages to display:**
1. Triage — classifying the bug
2. Mechanics Analysis — tracing code paths
3. Reproduction Planning — generating steps
4. Research — querying external sources
5. Report Generation — assembling the report

**Stage indicators:**
- `pending` — gray circle, not started
- `running` — animated spinner
- `checkpoint` — yellow pause icon (waiting for user)
- `completed` — green checkmark
- `error` — red X

**SSE event mapping:**
- `bug_stage_change` → update stage indicator + show summary text
- `agent_step` → show tool call under current stage (expandable)
- `research_progress` → show source-by-source progress under Research stage
- `bug_checkpoint` → switch to checkpoint dialog
- `bug_result` → switch to BugReportView

**Research stage special rendering:**
```
Research
  ├── ●Jira: 3 related issues found
  ├── ●Notion: 2 docs matched
  ├── ○Grafana: not configured
  └── ◐Kibana: searching...
```

Each source shows its status: configured + result count, not configured, or in progress.

---

## Component 3: BugCheckpointDialog

**File:** `frontend/src/components/BugCheckpointDialog.tsx`

**Purpose:** Show checkpoint data and collect user response at two points in the pipeline.

### Checkpoint: Post-Mechanics Analysis

Shows:
- List of identified components with confidence indicators
- Root cause hypotheses (numbered, ranked)
- Code paths (collapsible)

Actions:
- "Approve" → POST /bug-report/{session_id}/continue `{action: "approve"}`
- "Refine" → shows textarea for feedback → POST /continue `{action: "refine", feedback: "..."}`

### Checkpoint: Post-Research

Shows:
- Evidence summary (text paragraph)
- Counts: N log entries, N docs, N related issues
- Expandable sections for each evidence type

Actions:
- "Approve" → POST /bug-report/{session_id}/continue `{action: "approve"}`
- "Add Context" → shows textarea → POST /continue `{action: "add_context", additional_context: "..."}`

**Implementation:** Reuse the `CheckpointDialog` pattern from Sprint 2 with different content rendering based on `interrupt_type`.

---

## Component 4: BugReportView

**File:** `frontend/src/components/BugReportView.tsx`

**Purpose:** Display the final developer-ready bug report with export options.

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Bug Report: Players lose items on zone transition   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  Severity: [MAJOR]  Category: gameplay               │
│  Confidence: [HIGH]  Environment: iOS 17.4           │
│                                                      │
│  ┌─ Reproduction Steps ────────────────────────────┐ │
│  │ 1. Log in as Player with items in inventory     │ │
│  │ 2. Navigate to Zone A → Zone B transition       │ │
│  │ 3. Initiate zone transition                     │ │
│  │ 4. Check inventory after transition completes   │ │
│  │    Expected: Items preserved                    │ │
│  │    Actual: Inventory empty                      │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ Root Cause Analysis ───────────────────────────┐ │
│  │ The ZoneTransitionHandler.executeTransition()   │ │
│  │ calls InventoryManager.serialize() before the   │ │
│  │ zone unloads, but the deserialization on the    │ │
│  │ target zone occurs before the save completes... │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ Evidence ──────────────────────────────────────┐ │
│  │ Logs (3)  │  Docs (2)  │  Issues (1)           │ │
│  │ ──────────┴────────────┴─────────────────────── │ │
│  │ [2026-04-20 14:32] ERROR: Inventory save       │ │
│  │   timeout during zone transition...             │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ Affected Components ───────────────────────────┐ │
│  │ • ZoneTransitionHandler (HIGH confidence)       │ │
│  │ • InventoryManager (HIGH confidence)            │ │
│  │ • SaveSystem (MEDIUM confidence)                │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ Recommendations ──────────────────────────────┐  │
│  │ • Add await to serialize() call in transition   │ │
│  │ • Add inventory verification after zone load    │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  [Export Markdown]  [Export PDF]  [Push to Jira]     │
└─────────────────────────────────────────────────────┘
```

**Export buttons:**
- "Export Markdown" → POST /bug-report/{session_id}/export `{format: "markdown"}` → download .md file
- "Export PDF" → POST /bug-report/{session_id}/export `{format: "pdf"}` → download .pdf file
- "Push to Jira" → POST /bug-report/{session_id}/export `{format: "markdown", push_to_jira: true}` → shows created issue URL

**Copy to clipboard:** Each section has a copy icon (same pattern as Sprint 2 impact summary cards).

---

## Component 5: ResearchPanel

**File:** `frontend/src/components/ResearchPanel.tsx`

**Purpose:** Show research findings organized by source, with expandable detail.

**Tabs:**
- **Logs** — Grafana/Kibana log entries with timestamp, level, message
- **Docs** — Notion/Confluence page links with snippets
- **Issues** — Jira issues with status badges
- **Network** — Sniffer findings (if HAR files were provided)

Each tab shows count badge. Empty tabs show "Not configured" or "No findings" depending on whether the integration was available.

---

## Component 6: SettingsPanel

**File:** `frontend/src/components/SettingsPanel.tsx`

**Purpose:** Configure external tool integrations. Accessible from the top nav.

**Layout:**
```
┌──────────────────────────────────────────────┐
│  Integration Settings                         │
│                                               │
│  ┌─ Jira ─────────────────── ● Connected ──┐ │
│  │ URL:       [https://team.atlassian.net ] │ │
│  │ Email:     [qa@studio.com             ] │ │
│  │ API Token: [••••••••••••••            ] │ │
│  │ Project:   [QA                        ] │ │
│  │ [Test Connection]                        │ │
│  └──────────────────────────────────────────┘ │
│                                               │
│  ┌─ Notion ───────────────── ○ Not Configured │
│  │ API Key:   [                          ] │ │
│  │ [Test Connection]                        │ │
│  └──────────────────────────────────────────┘ │
│                                               │
│  ┌─ Grafana ──────────────── ● Connected ──┐ │
│  │ URL:       [https://grafana.studio.io ] │ │
│  │ API Key:   [••••••••••••••            ] │ │
│  │ [Test Connection]                        │ │
│  └──────────────────────────────────────────┘ │
│                                               │
│  ... (Kibana, Postman, Confluence)           │
│                                               │
│  [Save All]                                   │
└──────────────────────────────────────────────┘
```

**Behavior:**
- On page load: GET /settings/integrations to populate current status
- "Test Connection" per integration: calls POST /settings/integrations with that tool's config, then re-fetches status
- "Save All": saves all configs at once
- Status indicators: green = connected, yellow = configured but unhealthy, gray = not configured
- Sensitive fields (API tokens) masked with •••• after save

---

## API Client Updates (`frontend/src/services/api.ts`)

```typescript
// Bug reproduction
export async function startBugReport(req: BugReportRequest): Promise<EventSource> { ... }
export async function continueBugReport(sessionId: string, req: BugContinueRequest): Promise<EventSource> { ... }
export async function getBugReportStatus(sessionId: string): Promise<BugReportStatus> { ... }
export async function exportBugReport(sessionId: string, format: "markdown" | "pdf"): Promise<Blob> { ... }
export async function exportAndPushToJira(sessionId: string): Promise<{ jira_url: string }> { ... }

// Settings
export async function getIntegrations(): Promise<IntegrationStatus[]> { ... }
export async function updateIntegration(name: string, credentials: Record<string, string>): Promise<void> { ... }
```

---

## TypeScript Types (`frontend/src/services/types.ts`)

Add types matching Dev C's Pydantic models:

```typescript
// Bug reproduction types
interface BugReportRequest {
  description: string;
  environment?: string;
  severity?: "critical" | "major" | "minor" | "trivial";
  repo_url?: string;
  jira_ticket?: string;
  attachments?: string[];
  session_id?: string;
}

interface BugReport {
  title: string;
  severity: "critical" | "major" | "minor" | "trivial";
  category: string;
  environment: string;
  reproduction_steps: E2ETestStep[];
  expected_behavior: string;
  actual_behavior: string;
  root_cause_analysis: string;
  affected_components: AffectedComponent[];
  evidence: ResearchFindings;
  recommendations: string[];
  confidence: "high" | "medium" | "low";
  jira_url?: string;
}

interface ResearchFindings {
  log_entries: LogEntry[];
  doc_references: DocReference[];
  related_issues: RelatedIssue[];
  db_state: Record<string, unknown>[];
  admin_notes: string[];
  evidence_summary: string;
}

// SSE events
interface BugStageChangeEvent { type: "bug_stage_change"; stage: string; summary: string; }
interface BugCheckpointEvent { type: "bug_checkpoint"; session_id: string; stage_completed: string; payload: Record<string, unknown>; }
interface ResearchProgressEvent { type: "research_progress"; source: string; finding_count: number; summary: string; }
interface BugReportResultEvent { type: "bug_result"; session_id: string; report: BugReport; agent_steps: number; }

// Settings
interface IntegrationStatus {
  name: string;
  configured: boolean;
  healthy: boolean;
  message: string;
}
```

---

## State Management

Extend the existing `useAppState` hook or create a new `useBugReproState` hook:

```typescript
interface BugReproState {
  mode: "idle" | "running" | "checkpoint" | "done" | "error";
  sessionId: string | null;
  currentStage: string | null;
  stages: StageStatus[];              // {name, status, summary, toolCalls[]}
  checkpointData: BugCheckpointEvent | null;
  researchProgress: Record<string, { count: number; summary: string }>;
  report: BugReport | null;
  error: string | null;
}
```

The SSE event handler updates this state as events arrive, same pattern as Sprint 2.

---

## Testing

### Component Tests (`frontend/src/__tests__/bug-repro.test.tsx`)

- BugInputPanel: button disabled when description empty, enabled when filled
- BugInputPanel: Jira ticket validation shows error on invalid format
- BugTraceDrawer: stages render in correct order with correct indicators
- BugTraceDrawer: research progress shows per-source status
- BugCheckpointDialog: renders mechanics results, sends approve/refine
- BugCheckpointDialog: renders research summary, sends approve/add_context
- BugReportView: all report sections render correctly
- BugReportView: export buttons trigger correct API calls
- ResearchPanel: tabs show correct counts, empty state handled
- SettingsPanel: renders integration cards, test connection works
- Navigation: switching modes shows correct panels

### SSE Integration Tests

- Bug reproduction SSE stream processed correctly
- ResearchProgressEvent updates per-source indicators
- BugCheckpointEvent triggers dialog
- BugReportResultEvent displays report view

---

## Acceptance Criteria

- [ ] Bug input form accepts description and optional fields, submits to /bug-report
- [ ] BugTraceDrawer shows live stage progress through all 5 stages
- [ ] Research stage shows per-source progress (configured vs not configured)
- [ ] Mechanics checkpoint dialog shows components + hypotheses + approve/refine
- [ ] Research checkpoint dialog shows evidence summary + approve/add context
- [ ] BugReportView displays all report sections (repro steps, root cause, evidence, recommendations)
- [ ] Export Markdown downloads a .md file
- [ ] Export PDF downloads a .pdf file
- [ ] Push to Jira creates an issue and shows the URL
- [ ] Settings panel shows all 6 integrations with status indicators
- [ ] Test Connection works per integration
- [ ] Navigation switches between Impact Analysis and Bug Reproduction without losing state
- [ ] All existing Sprint 2 UI still works unchanged
- [ ] Copy to clipboard works on report sections
