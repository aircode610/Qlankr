# Dev B: External Tool Integrations — MCP Servers + Sniffer

**Branch:** `devb/tool-integrations`
**Depends on:** Dev C's models (rebase once merged)
**Files owned:**
- `backend/agent/tools.py` — extend with new MCP server configs + tool sets
- `backend/agent/sniffer.py` — NEW: HAR/pcap parser tools
- `backend/agent/tool_health.py` — NEW: Health check logic per integration
- `.env.example` — update with new environment variables

**Shared files (coordinate with):**
- `backend/agent/bug_prompts.py` — co-owned with Dev A (you write tool-specific prompt content; Dev A defines stage structure)
- `backend/models.py` — owned by Dev C, you import from it

---

## Overview

Add five new tool integrations that the bug reproduction pipeline (and optionally the impact analysis pipeline) can use. Each integration follows the existing MCP pattern: configure in `_server_config()`, make available via `get_mcp_client()`, filter per stage via `filter_tools()`.

**Key principle:** Every integration is optional. If credentials aren't in the environment, the integration is silently skipped. The agent adapts based on `available_tools` in state.

---

## Integration 1: Jira/YouTrack MCP

**Purpose:** Search existing issues for duplicates/related bugs, read ticket details and comment threads, create/update issues from bug reports.

**MCP Server:** Use `@modelcontextprotocol/server-atlassian` (community MCP) or build a custom stdio server if the community one doesn't cover all needs.

**Server config:**
```python
if os.environ.get("JIRA_URL") and os.environ.get("JIRA_API_TOKEN"):
    config["jira"] = {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-atlassian"],
        "env": {
            **utf8_env,
            "JIRA_URL": os.environ["JIRA_URL"],
            "JIRA_EMAIL": os.environ.get("JIRA_EMAIL", ""),
            "JIRA_API_TOKEN": os.environ["JIRA_API_TOKEN"],
        },
    }
```

**Tools to expose (wrap if community server names differ):**

| Tool name | Parameters | Returns |
|-----------|-----------|---------|
| `jira_search` | `jql: str` | List of issue summaries (key, summary, status, priority) |
| `jira_get_issue` | `key: str` | Full issue: description, comments, attachments, status history |
| `jira_get_comments` | `key: str` | Comment thread for an issue |
| `jira_create_issue` | `project: str, summary: str, description: str, type: str, priority: str` | Created issue key + URL |
| `jira_update_issue` | `key: str, fields: dict` | Updated issue key |
| `jira_link_issues` | `inward: str, outward: str, type: str` | Link confirmation |

**Normalization:** Community MCP servers may expose tools under different names (e.g., `search_issues` instead of `jira_search`). Build a name-mapping layer:
```python
JIRA_TOOL_ALIASES = {
    "search_issues": "jira_search",
    "get_issue": "jira_get_issue",
    ...
}
```

Apply aliases in `_normalize_tool_names()` called after `client.get_tools()`.

**Env vars:** `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY` (default project for issue creation)

---

## Integration 2: Notion/Confluence MCP

**Purpose:** Search documentation and runbooks for context relevant to bugs and components.

**MCP Server:** Two options:
- Notion: `@modelcontextprotocol/server-notion` (community)
- Confluence: `@modelcontextprotocol/server-atlassian` (same as Jira, different config) or custom

**Server config:**
```python
if os.environ.get("NOTION_API_KEY"):
    config["notion"] = {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-notion"],
        "env": {
            **utf8_env,
            "NOTION_API_KEY": os.environ["NOTION_API_KEY"],
        },
    }

if os.environ.get("CONFLUENCE_URL") and os.environ.get("CONFLUENCE_TOKEN"):
    config["confluence"] = {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-confluence"],
        "env": {
            **utf8_env,
            "CONFLUENCE_URL": os.environ["CONFLUENCE_URL"],
            "CONFLUENCE_TOKEN": os.environ["CONFLUENCE_TOKEN"],
        },
    }
```

**Tools to expose:**

| Tool name | Parameters | Returns |
|-----------|-----------|---------|
| `notion_search` | `query: str` | List of page titles + IDs + snippet |
| `notion_get_page` | `page_id: str` | Page content as markdown |
| `notion_get_database` | `database_id: str, filter: dict` | Query results from a Notion database |
| `confluence_search` | `cql: str` | List of page titles + IDs + snippet |
| `confluence_get_page` | `page_id: str` | Page content as markdown |

**Env vars:** `NOTION_API_KEY`, `NOTION_WORKSPACE_ID`, `CONFLUENCE_URL`, `CONFLUENCE_TOKEN`, `CONFLUENCE_SPACE_KEY`

---

## Integration 3: Grafana/Kibana MCP

**Purpose:** Query logs and metrics to correlate with bug reports — find error traces, performance spikes, and anomalies near the reported bug time.

**MCP Server:** No widely adopted community MCP server for Grafana/Kibana exists yet. Build a **custom stdio MCP server** in Python using the `mcp` SDK.

**Implementation:** `backend/mcp_servers/grafana_server.py`

```python
# Standalone MCP server — launched via stdio by the MultiServerMCPClient
from mcp.server import Server
from mcp.server.stdio import stdio_server
import httpx

app = Server("grafana")

@app.tool()
async def grafana_query_logs(datasource: str, query: str, from_ts: str, to_ts: str) -> str:
    """Query logs from Grafana (Loki/Elasticsearch datasource)."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAFANA_URL}/api/ds/query",
            headers={"Authorization": f"Bearer {GRAFANA_API_KEY}"},
            json={...}
        )
        return format_log_results(resp.json())
```

**Server config:**
```python
if os.environ.get("GRAFANA_URL") and os.environ.get("GRAFANA_API_KEY"):
    config["grafana"] = {
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "mcp_servers.grafana_server"],
        "env": {
            **utf8_env,
            "GRAFANA_URL": os.environ["GRAFANA_URL"],
            "GRAFANA_API_KEY": os.environ["GRAFANA_API_KEY"],
        },
    }
```

For Kibana, add a second server or extend the Grafana server:
```python
if os.environ.get("KIBANA_URL") and os.environ.get("KIBANA_TOKEN"):
    config["kibana"] = {
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "mcp_servers.kibana_server"],
        "env": {
            **utf8_env,
            "KIBANA_URL": os.environ["KIBANA_URL"],
            "KIBANA_TOKEN": os.environ["KIBANA_TOKEN"],
        },
    }
```

**Tools to expose:**

| Tool name | Parameters | Returns |
|-----------|-----------|---------|
| `grafana_query_logs` | `datasource: str, query: str, from_ts: str, to_ts: str` | Log entries (timestamp, message, level, labels) |
| `grafana_query_metrics` | `datasource: str, query: str, from_ts: str, to_ts: str` | Metric data points |
| `grafana_get_annotations` | `dashboard_id: str, from_ts: str, to_ts: str` | Annotations (deployment markers, incidents) |
| `kibana_search` | `index: str, query: str, from_ts: str, to_ts: str` | Elasticsearch results |
| `kibana_get_log_entry` | `index: str, id: str` | Single log entry details |

**Env vars:** `GRAFANA_URL`, `GRAFANA_API_KEY`, `KIBANA_URL`, `KIBANA_TOKEN`

**Files to create:**
- `backend/mcp_servers/__init__.py`
- `backend/mcp_servers/grafana_server.py`
- `backend/mcp_servers/kibana_server.py`

---

## Integration 4: Postman MCP

**Purpose:** Read API collections to understand API contracts and request/response shapes relevant to a bug. Optionally execute requests to test current behavior.

**MCP Server:** Community server or custom. Use the Postman API v10.

**Server config:**
```python
if os.environ.get("POSTMAN_API_KEY"):
    config["postman"] = {
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "mcp_servers.postman_server"],
        "env": {
            **utf8_env,
            "POSTMAN_API_KEY": os.environ["POSTMAN_API_KEY"],
            "POSTMAN_WORKSPACE_ID": os.environ.get("POSTMAN_WORKSPACE_ID", ""),
        },
    }
```

**Tools to expose:**

| Tool name | Parameters | Returns |
|-----------|-----------|---------|
| `postman_list_collections` | — | List of collection names + IDs |
| `postman_get_collection` | `collection_id: str` | Full collection with request names + endpoints |
| `postman_get_request` | `collection_id: str, request_id: str` | Single request: method, URL, headers, body |
| `postman_run_request` | `collection_id: str, request_id: str, variables: dict` | Execute request, return status + response body |

**Safety:** `postman_run_request` is a write-like operation (it actually sends HTTP requests). Mark it as `requires_confirmation: true` in the tool metadata so the agent's safe_tools wrapper can flag it.

**Env vars:** `POSTMAN_API_KEY`, `POSTMAN_WORKSPACE_ID`

**Files to create:**
- `backend/mcp_servers/postman_server.py`

---

## Integration 5: Network Sniffer Parser

**Purpose:** Parse captured network traffic (HAR files primarily; pcap as stretch goal) to find HTTP errors, timeouts, and malformed responses.

**Implementation:** NOT an MCP server — local Python tools registered directly as StructuredTools (same pattern as `make_process_tools`). HAR files are JSON; pcap uses `pyshark` if available.

**File:** `backend/agent/sniffer.py`

```python
def make_sniffer_tools() -> list[StructuredTool]:
    async def sniffer_parse_har(file_path: str) -> str:
        """Parse a HAR file and return a summary of requests, responses, and errors."""
        ...

    async def sniffer_find_errors(file_path: str) -> str:
        """Extract HTTP errors (4xx/5xx), timeouts, and failed requests from a HAR file."""
        ...

    async def sniffer_parse_pcap(file_path: str, filter: str = "") -> str:
        """Parse a pcap file with optional BPF filter. Returns packet summary."""
        ...

    return [
        StructuredTool.from_function(coroutine=sniffer_parse_har, ...),
        StructuredTool.from_function(coroutine=sniffer_find_errors, ...),
        StructuredTool.from_function(coroutine=sniffer_parse_pcap, ...),
    ]
```

**Dependencies:** Add `pyshark` (optional) to `requirements.txt`. HAR parsing uses only stdlib `json`.

---

## Tool Filtering Updates

Extend `_STAGE_TOOLS` for bug reproduction stages:

```python
BUG_TRIAGE_TOOLS: set[str] = {
    "get_commits", "search_code", "cypher",
    "jira_search", "jira_get_issue",
}

BUG_MECHANICS_TOOLS: set[str] = {
    "get_file_contents", "impact", "context", "cypher",
}

BUG_REPRODUCTION_TOOLS: set[str] = {
    "get_file_contents", "impact", "context", "cypher",
    "list_processes", "get_process",
    "postman_get_collection", "postman_get_request",
}

BUG_RESEARCH_TOOLS: set[str] = {
    "cypher",
    "jira_search", "jira_get_issue", "jira_get_comments",
    "notion_search", "notion_get_page",
    "confluence_search", "confluence_get_page",
    "grafana_query_logs", "kibana_search",
    "sniffer_parse_har", "sniffer_find_errors",
}

BUG_REPORT_TOOLS: set[str] = {
    "jira_create_issue", "jira_update_issue",
}
```

Add these to `_STAGE_TOOLS` dict.

---

## Tool Availability Helper

```python
async def get_available_integrations() -> list[str]:
    """Return names of integrations that are configured and reachable."""
    available = []
    config = _server_config()
    for name in ["jira", "notion", "confluence", "grafana", "kibana", "postman"]:
        if name in config:
            available.append(name)
    # Sniffer is always available (local tools)
    available.append("sniffer")
    return available
```

Dev A's bug agent calls this at startup and stores it in `BugReproductionState.available_tools`.

---

## Health Check Logic (`backend/agent/tool_health.py`)

```python
async def check_integration_health(name: str) -> dict:
    """Test if an integration is reachable and authenticated.
    Returns {"name": str, "status": "ok"|"error", "message": str}
    """
    ...
```

Each integration has a lightweight health check:
- **Jira:** `GET /rest/api/2/myself` — returns 200 if authenticated
- **Notion:** `GET /v1/users/me` — returns 200 if token valid
- **Confluence:** `GET /wiki/rest/api/user/current` — returns 200 if authenticated
- **Grafana:** `GET /api/health` — returns 200 if reachable
- **Kibana:** `GET /api/status` — returns 200 if reachable
- **Postman:** `GET /me` — returns 200 if API key valid

Dev C calls these from the `/settings/integrations` endpoint.

---

## Environment Variables (update .env.example)

```bash
# ── Existing ──
ANTHROPIC_API_KEY=
GITHUB_TOKEN=

# ── Sprint 3: External Integrations ──
# Jira / YouTrack
JIRA_URL=                    # e.g. https://your-domain.atlassian.net
JIRA_EMAIL=                  # Jira account email
JIRA_API_TOKEN=              # API token from id.atlassian.com
JIRA_PROJECT_KEY=            # Default project for issue creation (e.g. QA)

# Notion
NOTION_API_KEY=              # Integration token from notion.so/my-integrations
NOTION_WORKSPACE_ID=         # (optional) default workspace

# Confluence
CONFLUENCE_URL=              # e.g. https://your-domain.atlassian.net/wiki
CONFLUENCE_TOKEN=            # API token (same as Jira if Atlassian Cloud)
CONFLUENCE_SPACE_KEY=        # Default space key for search

# Grafana
GRAFANA_URL=                 # e.g. https://grafana.your-domain.com
GRAFANA_API_KEY=             # Service account token with Viewer role

# Kibana
KIBANA_URL=                  # e.g. https://kibana.your-domain.com
KIBANA_TOKEN=                # API key or basic auth token

# Postman
POSTMAN_API_KEY=             # API key from go.postman.co/settings/me/api-keys
POSTMAN_WORKSPACE_ID=        # (optional) default workspace ID
```

---

## Testing

### Unit Tests (`backend/tests/mcp/test_tool_integrations.py`)

- Each integration's server config is generated only when env vars are present
- `filter_tools()` returns correct subsets for all bug reproduction stages
- `get_available_integrations()` reflects configured tools
- `safe_tools()` wraps new MCP tools correctly
- Tool name normalization/aliasing works

### Integration Tests (require real credentials — run manually or in CI with secrets)

- Jira: search returns results, get_issue returns expected fields
- Notion: search returns results, get_page returns markdown content
- Grafana: query_logs returns entries (mock Loki datasource)
- Postman: list_collections returns at least one collection

### Health Check Tests (`backend/tests/mcp/test_tool_health.py`)

- Health check returns "ok" for configured, reachable integrations
- Health check returns "error" with message for misconfigured integrations
- Health check does not crash for unconfigured integrations

---

## Acceptance Criteria

- [ ] Jira MCP integration: search, get_issue, create_issue work end-to-end
- [ ] Notion MCP integration: search, get_page work end-to-end
- [ ] Confluence MCP integration: search, get_page work end-to-end
- [ ] Grafana MCP server: query_logs returns structured results
- [ ] Kibana MCP server: search returns structured results
- [ ] Postman MCP server: list_collections, get_request work end-to-end
- [ ] Sniffer tools: parse HAR files, extract errors correctly
- [ ] Each integration is optional — missing env vars skip it silently
- [ ] `get_available_integrations()` accurately reports configured tools
- [ ] Health checks work for all integrations
- [ ] `filter_tools()` covers all 5 bug reproduction stages
- [ ] Tool name aliases normalize community MCP server names
- [ ] `safe_tools()` wraps all new tools (errors → ToolMessages)
- [ ] `.env.example` updated with all new variables
- [ ] All new MCP tools appear in `/debug/mcp/tools` when configured
