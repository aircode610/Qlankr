# Person 4 — MCP Integrations + Sniffer + Health Checks + BugInputPanel + BugReportView + Nav

**Branch:** `p4/tool-integrations-ui`
**Depends on:** Person 3's models branch (rebase first)
**Coordinate with:** Person 1 (tool filtering — P1 adds triage/mechanics/reproduction sets; P4 adds research/report sets to the same `_STAGE_TOOLS`), Person 2 (research stage calls P4's `get_available_integrations()`)

**Files owned:**
- `backend/mcp_servers/grafana_server.py` — NEW: custom MCP server
- `backend/mcp_servers/kibana_server.py` — NEW: custom MCP server
- `backend/mcp_servers/postman_server.py` — NEW: custom MCP server
- `backend/mcp_servers/__init__.py` — NEW
- `backend/agent/sniffer.py` — NEW: HAR/pcap parser tools
- `backend/agent/tool_health.py` — NEW: health check per integration
- `backend/agent/tools.py` — extend: Notion/Confluence/Grafana/Kibana/Postman MCP configs + `get_available_integrations()` + `BUG_RESEARCH_TOOLS` + `BUG_REPORT_TOOLS`
- `.env.example` — update with all new env vars
- `frontend/src/components/BugInputPanel.tsx` — NEW
- `frontend/src/components/BugReportView.tsx` — NEW
- `frontend/src/App.tsx` — update: tab navigation + `useBugReproState` hook

---

## Overview

Person 4 adds the external integrations that power the research stage, builds the sniffer and health check utilities, and owns the main frontend entry/exit points for the bug reproduction flow (input form, report view, navigation). The research/report stage components (BugCheckpointDialog, ResearchPanel) are Person 2's responsibility.

---

## Custom MCP Servers

Custom MCP servers are standalone Python processes launched via `stdio` by `MultiServerMCPClient`. Use the `mcp` SDK pattern:

```python
# Template for any custom server
from mcp.server import Server
from mcp.server.stdio import stdio_server
import httpx

app = Server("server-name")

@app.tool()
async def tool_name(param: str) -> str:
    """Tool description."""
    async with httpx.AsyncClient() as client:
        ...

async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

## Integration 1: Grafana Custom MCP Server (`backend/mcp_servers/grafana_server.py`)

**Tools:**

| Tool | Parameters | Returns |
|------|-----------|---------|
| `grafana_query_logs` | `datasource: str, query: str, from_ts: str, to_ts: str` | Log entries (timestamp, message, level, labels) |
| `grafana_query_metrics` | `datasource: str, query: str, from_ts: str, to_ts: str` | Metric data points |
| `grafana_get_annotations` | `dashboard_id: str, from_ts: str, to_ts: str` | Deployment markers and incident annotations |

**Config in `tools.py`:**
```python
if os.environ.get("GRAFANA_URL") and os.environ.get("GRAFANA_API_KEY"):
    config["grafana"] = {
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "mcp_servers.grafana_server"],
        "env": {**utf8_env, "GRAFANA_URL": os.environ["GRAFANA_URL"], "GRAFANA_API_KEY": os.environ["GRAFANA_API_KEY"]},
    }
```

**Env vars:** `GRAFANA_URL`, `GRAFANA_API_KEY`

---

## Integration 2: Kibana Custom MCP Server (`backend/mcp_servers/kibana_server.py`)

**Tools:**

| Tool | Parameters | Returns |
|------|-----------|---------|
| `kibana_search` | `index: str, query: str, from_ts: str, to_ts: str` | Elasticsearch results |
| `kibana_get_log_entry` | `index: str, id: str` | Single log entry |

**Config in `tools.py`:**
```python
if os.environ.get("KIBANA_URL") and os.environ.get("KIBANA_TOKEN"):
    config["kibana"] = {
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "mcp_servers.kibana_server"],
        "env": {**utf8_env, "KIBANA_URL": os.environ["KIBANA_URL"], "KIBANA_TOKEN": os.environ["KIBANA_TOKEN"]},
    }
```

**Env vars:** `KIBANA_URL`, `KIBANA_TOKEN`

---

## Integration 3: Notion MCP (community server)

**Tools:** `notion_search`, `notion_get_page`, `notion_get_database`

**Config in `tools.py`:**
```python
if os.environ.get("NOTION_API_KEY"):
    config["notion"] = {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-notion"],
        "env": {**utf8_env, "NOTION_API_KEY": os.environ["NOTION_API_KEY"]},
    }
```

**Env vars:** `NOTION_API_KEY`, `NOTION_WORKSPACE_ID` (optional)

---

## Integration 4: Confluence MCP (community server)

**Tools:** `confluence_search`, `confluence_get_page`

**Config in `tools.py`:**
```python
if os.environ.get("CONFLUENCE_URL") and os.environ.get("CONFLUENCE_TOKEN"):
    config["confluence"] = {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-confluence"],
        "env": {**utf8_env, "CONFLUENCE_URL": os.environ["CONFLUENCE_URL"], "CONFLUENCE_TOKEN": os.environ["CONFLUENCE_TOKEN"]},
    }
```

**Env vars:** `CONFLUENCE_URL`, `CONFLUENCE_TOKEN`, `CONFLUENCE_SPACE_KEY` (optional)

---

## Integration 5: Postman Custom MCP Server (`backend/mcp_servers/postman_server.py`)

**Tools:**

| Tool | Parameters | Returns |
|------|-----------|---------|
| `postman_list_collections` | — | List of collection names + IDs |
| `postman_get_collection` | `collection_id: str` | Requests with endpoints + methods |
| `postman_get_request` | `collection_id: str, request_id: str` | Method, URL, headers, body schema |
| `postman_run_request` | `collection_id: str, request_id: str, variables: dict` | Response status + body (mark `requires_confirmation: true`) |

**Config in `tools.py`:**
```python
if os.environ.get("POSTMAN_API_KEY"):
    config["postman"] = {
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "mcp_servers.postman_server"],
        "env": {**utf8_env, "POSTMAN_API_KEY": os.environ["POSTMAN_API_KEY"], "POSTMAN_WORKSPACE_ID": os.environ.get("POSTMAN_WORKSPACE_ID", "")},
    }
```

**Env vars:** `POSTMAN_API_KEY`, `POSTMAN_WORKSPACE_ID` (optional)

---

## Sniffer Tools (`backend/agent/sniffer.py`)

Local `StructuredTool` instances — NOT an MCP server. Follow the `make_process_tools` pattern from `agent/tools.py:144`.

```python
def make_sniffer_tools() -> list[StructuredTool]:
    async def sniffer_parse_har(file_path: str) -> str:
        """Parse a HAR file, return a summary of all requests/responses."""
        # stdlib json only — no extra dependencies

    async def sniffer_find_errors(file_path: str) -> str:
        """Extract 4xx/5xx, timeouts, and failed requests from a HAR file."""

    async def sniffer_parse_pcap(file_path: str, filter: str = "") -> str:
        """Parse a pcap file with optional BPF filter. Requires pyshark (optional)."""
        # Gracefully return error string if pyshark not installed

    return [
        StructuredTool.from_function(coroutine=sniffer_parse_har, name="sniffer_parse_har", description="..."),
        StructuredTool.from_function(coroutine=sniffer_find_errors, name="sniffer_find_errors", description="..."),
        StructuredTool.from_function(coroutine=sniffer_parse_pcap, name="sniffer_parse_pcap", description="..."),
    ]
```

Add `pyshark` as an optional dependency in `requirements.txt` (comment: `# optional, for pcap parsing`). HAR parsing uses only stdlib.

---

## Tool Health Checks (`backend/agent/tool_health.py`)

Called by Person 3's `/settings/integrations` endpoint.

```python
async def check_integration_health(name: str) -> dict:
    """Returns {"name": str, "configured": bool, "healthy": bool, "message": str}"""

async def check_all_integrations() -> list[dict]:
    """Run health check for all known integrations."""
    names = ["jira", "notion", "confluence", "grafana", "kibana", "postman"]
    return [await check_integration_health(n) for n in names]
```

Lightweight HTTP ping per service (returns immediately if not configured):

| Integration | Endpoint |
|-------------|----------|
| Jira | `GET {JIRA_URL}/rest/api/2/myself` |
| Notion | `GET https://api.notion.com/v1/users/me` |
| Confluence | `GET {CONFLUENCE_URL}/wiki/rest/api/user/current` |
| Grafana | `GET {GRAFANA_URL}/api/health` |
| Kibana | `GET {KIBANA_URL}/api/status` |
| Postman | `GET https://api.getpostman.com/me` |

---

## Tool Availability Helper (`backend/agent/tools.py`)

```python
async def get_available_integrations() -> list[str]:
    """Return names of configured integrations. Called by Person 2 at pipeline startup."""
    config = _server_config()
    available = [name for name in ["jira", "notion", "confluence", "grafana", "kibana", "postman"] if name in config]
    available.append("sniffer")   # always available (local tools, no credentials needed)
    return available
```

---

## Tool Set Additions (`backend/agent/tools.py`)

Person 4 owns `BUG_RESEARCH_TOOLS` and `BUG_REPORT_TOOLS`. Person 1 owns the first three sets. Commit these additions early so Person 2 can rebase:

```python
BUG_RESEARCH_TOOLS: set[str] = {
    "cypher",
    "jira_search", "jira_get_issue", "jira_get_comments",
    "notion_search", "notion_get_page",
    "confluence_search", "confluence_get_page",
    "grafana_query_logs", "kibana_search",
    "sniffer_parse_har", "sniffer_find_errors",
}

BUG_REPORT_TOOLS: set[str] = {
    "jira_create_issue",
    "jira_update_issue",
}
```

Register in `_STAGE_TOOLS`:
```python
"bug_research": BUG_RESEARCH_TOOLS,
"bug_report":   BUG_REPORT_TOOLS,
```

---

## `.env.example` Updates

Add below existing variables:

```bash
# ── Sprint 3: External Integrations ──────────────────────────────────────────

# Jira (config owned by Person 3)
JIRA_URL=                    # https://your-domain.atlassian.net
JIRA_EMAIL=
JIRA_API_TOKEN=
JIRA_PROJECT_KEY=            # default project for issue creation (e.g. QA)

# Notion
NOTION_API_KEY=              # integration token from notion.so/my-integrations
NOTION_WORKSPACE_ID=         # optional

# Confluence
CONFLUENCE_URL=              # https://your-domain.atlassian.net/wiki
CONFLUENCE_TOKEN=
CONFLUENCE_SPACE_KEY=        # optional

# Grafana
GRAFANA_URL=                 # https://grafana.your-domain.com
GRAFANA_API_KEY=             # service account token with Viewer role

# Kibana
KIBANA_URL=                  # https://kibana.your-domain.com
KIBANA_TOKEN=

# Postman
POSTMAN_API_KEY=             # from go.postman.co/settings/me/api-keys
POSTMAN_WORKSPACE_ID=        # optional
```

---

## Frontend: `BugInputPanel.tsx`

Bug description form. Submits to `POST /bug-report` and opens the SSE stream.

**Fields:**
| Field | Type | Required |
|-------|------|----------|
| Bug description | `textarea` | Yes |
| Environment | text | No |
| Severity | dropdown (`critical/major/minor/trivial`) | No |
| Repository URL | text | No |
| Jira ticket | text | No — validate `^[A-Z]+-\d+$` if provided |
| Attachments | URL list / file input | No |

**Behavior:**
- "Analyze Bug" button disabled until `description.length > 0`.
- On submit: call `startBugReport(req, callbacks)` from `api.ts`, switch parent to BugTraceDrawer view.
- Show integration availability dots (`●` configured, `○` not configured) — fetch from `GET /settings/integrations` on mount.

**Mockup:**
```
┌──────────────────────────────────────────────┐
│  Describe the Bug                             │
│  ┌──────────────────────────────────────────┐ │
│  │ Players lose items when teleporting...   │ │
│  └──────────────────────────────────────────┘ │
│  Environment: [iOS 17.4, build 4.2.1       ]  │
│  Severity:    [major ▼]                        │
│  Repository:  [github.com/studio/game      ]  │
│  Jira Ticket: [QA-456                      ]  │
│  Attachments: [+ Add file or URL]             │
│  Available: ●GitHub ●Jira ●Notion ○Grafana    │
│  [   Analyze Bug   ]                          │
└──────────────────────────────────────────────┘
```

---

## Frontend: `BugReportView.tsx`

Displays the final `BugReport` from the `bug_result` SSE event.

**Sections (in order):**
1. Header: title, severity badge, category, confidence, environment
2. Reproduction Steps — numbered list of `{action, expected_result}` per step
3. Expected vs Actual Behavior
4. Root Cause Analysis — markdown text block
5. Evidence — tabbed: Logs / Docs / Issues (delegate to `ResearchPanel` or inline)
6. Affected Components — list with confidence badges
7. Recommendations — bulleted list

**Actions:**
- "Export Markdown" → `exportBugReport(sessionId, "markdown")` → download `.md`
- "Export PDF" → `exportBugReport(sessionId, "pdf")` → download `.pdf`
- "Push to Jira" → `POST /bug-report/{sessionId}/export` with `push_to_jira: true` → show Jira URL
- Copy icon per section (same clipboard pattern as Sprint 2 impact cards)

---

## Frontend: `App.tsx` — Navigation + `useBugReproState`

### Navigation update

Add a second mode alongside the existing `'graph'` / `'analyze'` views:

```tsx
type AppMode = "impact-analysis" | "bug-reproduction";
```

Top-level tab navigation:
- **Impact Analysis** — existing Sprint 2 layout (unchanged)
- **Bug Reproduction** — new layout: left column `BugInputPanel`/`BugTraceDrawer`, right column `BugReportView`
- **Settings** (gear icon) → renders `SettingsPanel` overlay

The graph canvas is shared and visible in both modes.

### `useBugReproState` hook

```typescript
interface BugReproState {
  mode: "idle" | "running" | "checkpoint" | "done" | "error";
  sessionId: string | null;
  currentStage: string | null;
  stages: { name: string; status: StageStatus; summary: string; toolCalls: {tool: string; summary: string}[] }[];
  checkpointData: BugCheckpointEvent | null;
  researchProgress: Record<string, { count: number; summary: string }>;
  report: BugReport | null;
  error: string | null;
}
```

SSE event handlers update this state:
- `bug_stage_change` → update `stages[n].status` + `currentStage`
- `agent_step` → push to `stages[n].toolCalls`
- `research_progress` → update `researchProgress[source]`
- `bug_checkpoint` → set `checkpointData`, set `mode = "checkpoint"`
- `bug_result` → set `report`, set `mode = "done"`

Pass `stages`, `checkpointData`, `researchProgress`, `report` as props to child components.

---

## Acceptance Criteria

- [ ] Grafana MCP server: `grafana_query_logs` returns structured log entries
- [ ] Kibana MCP server: `kibana_search` returns structured results
- [ ] Notion MCP: `notion_search` + `notion_get_page` work end-to-end
- [ ] Confluence MCP: `confluence_search` + `confluence_get_page` work end-to-end
- [ ] Postman MCP server: `postman_list_collections` + `postman_get_request` work
- [ ] Each integration silently skipped when env vars absent
- [ ] Sniffer: `sniffer_parse_har` parses a sample HAR and returns summary
- [ ] Sniffer: `sniffer_find_errors` extracts 4xx/5xx entries correctly
- [ ] `get_available_integrations()` returns only configured integration names
- [ ] Health checks return correct status for configured and unconfigured integrations
- [ ] `filter_tools(all_tools, "bug_research")` returns only `BUG_RESEARCH_TOOLS` intersection
- [ ] All new MCP tools appear in `/debug/mcp/tools` response when configured
- [ ] `.env.example` updated with all new variables and comments
- [ ] `BugInputPanel` disables submit until description is filled; validates Jira ticket format
- [ ] `BugInputPanel` shows integration availability dots from `/settings/integrations`
- [ ] `BugReportView` renders all report sections and export buttons
- [ ] Export buttons trigger correct downloads
- [ ] Navigation switches between Impact Analysis and Bug Reproduction without state loss
- [ ] Sprint 2 impact analysis UI fully unchanged
