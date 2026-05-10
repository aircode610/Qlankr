# MCP Integration E2E Test Plan

Manual test plan for verifying each MCP server integration works end-to-end.

## Prerequisites

Start the backend server:
```bash
cd backend && .venv/bin/python -m uvicorn main:app --reload --port 8000
```

Or via Docker:
```bash
docker compose up --build
```

---

## Test 1: GitHub MCP Server

**Setup:** Ensure `GITHUB_TOKEN` is set in `.env`.

**Steps:**
1. Verify tools are visible:
   ```bash
   curl http://localhost:8000/debug/mcp/tools | jq '.tools[] | select(.name | test("pull_request|file_contents|search_code"))'
   ```
   Expected: `get_pull_request`, `get_pull_request_files`, `get_file_contents`, `search_code` etc.

2. Fetch a known PR:
   ```bash
   curl -X POST http://localhost:8000/debug/mcp/call \
     -H "Content-Type: application/json" \
     -d '{"tool": "get_pull_request", "args": {"owner": "aircode610", "repo": "Qlankr", "pull_number": 86}}'
   ```
   Expected: PR #86 metadata (title, body, author).

3. Search code:
   ```bash
   curl -X POST http://localhost:8000/debug/mcp/call \
     -H "Content-Type: application/json" \
     -d '{"tool": "search_code", "args": {"query": "get_mcp_client repo:aircode610/Qlankr"}}'
   ```
   Expected: Code search results showing files containing `get_mcp_client`.

---

## Test 2: Jira MCP Server

**Setup:**
1. Set in `.env`:
   - `JIRA_URL=https://your-domain.atlassian.net`
   - `JIRA_EMAIL=your-email@example.com`
   - `JIRA_API_TOKEN=<token from https://id.atlassian.com/manage-profile/security/api-tokens>`
2. Create a test issue in any Jira project. Note the issue key (e.g. `QA-123`).

**Steps:**
1. Health check:
   ```bash
   curl http://localhost:8000/settings/integrations | jq '.[] | select(.name == "jira")'
   ```
   Expected: `"configured": true, "healthy": true`

2. Search issues:
   ```bash
   curl -X POST http://localhost:8000/debug/mcp/call \
     -H "Content-Type: application/json" \
     -d '{"tool": "search_issues", "args": {"query": "test"}}'
   ```
   Expected: List of matching Jira issues.

3. Get specific issue:
   ```bash
   curl -X POST http://localhost:8000/debug/mcp/call \
     -H "Content-Type: application/json" \
     -d '{"tool": "get_issue", "args": {"issue_key": "QA-123"}}'
   ```
   Expected: Full issue details (summary, description, status, assignee).

4. Create an issue (optional):
   ```bash
   curl -X POST http://localhost:8000/debug/mcp/call \
     -H "Content-Type: application/json" \
     -d '{"tool": "create_issue", "args": {"project_key": "QA", "summary": "MCP E2E test issue", "description": "Created by MCP integration test", "issue_type": "Bug"}}'
   ```
   Expected: New issue created, response includes issue key.

---

## Test 3: Notion MCP Server

**Setup:**
1. Set `NOTION_API_KEY` in `.env` (from https://www.notion.so/my-integrations)
2. Share at least one Notion page with the integration.

**Steps:**
1. Health check:
   ```bash
   curl http://localhost:8000/settings/integrations | jq '.[] | select(.name == "notion")'
   ```
   Expected: `"configured": true, "healthy": true`

2. Search pages:
   ```bash
   curl -X POST http://localhost:8000/debug/mcp/call \
     -H "Content-Type: application/json" \
     -d '{"tool": "search", "args": {"query": "your page title"}}'
   ```
   Expected: List of matching Notion pages.

---

## Test 4: Confluence MCP Server

**Setup:**
1. Set in `.env`:
   - `CONFLUENCE_URL=https://your-domain.atlassian.net/wiki`
   - `CONFLUENCE_TOKEN=<API token>`
   - `CONFLUENCE_SPACE_KEY=<optional space key>`

**Steps:**
1. Health check:
   ```bash
   curl http://localhost:8000/settings/integrations | jq '.[] | select(.name == "confluence")'
   ```
   Expected: `"configured": true, "healthy": true`

2. Search pages:
   ```bash
   curl -X POST http://localhost:8000/debug/mcp/call \
     -H "Content-Type: application/json" \
     -d '{"tool": "search_pages", "args": {"query": "test"}}'
   ```
   Expected: List of matching Confluence pages.

---

## Test 5: Grafana MCP Server

**Setup:**
1. Set in `.env`:
   - `GRAFANA_URL=https://grafana.your-domain.com`
   - `GRAFANA_API_KEY=<service account token with Viewer role>`
2. Note a Loki datasource UID from your Grafana instance.

**Steps:**
1. Health check:
   ```bash
   curl http://localhost:8000/settings/integrations | jq '.[] | select(.name == "grafana")'
   ```
   Expected: `"configured": true, "healthy": true`

2. Query logs:
   ```bash
   curl -X POST http://localhost:8000/debug/mcp/call \
     -H "Content-Type: application/json" \
     -d '{"tool": "grafana_query_logs", "args": {"datasource": "<loki-uid>", "query": "{app=\"myservice\"}", "from_ts": "now-1h", "to_ts": "now"}}'
   ```
   Expected: JSON list of log entries (may be empty if no matching logs).

---

## Test 6: Kibana / Elasticsearch MCP Server

**Setup:**
1. Set in `.env`:
   - `KIBANA_URL=https://kibana.your-domain.com`
   - `KIBANA_TOKEN=<Bearer token>`
2. Have at least one Elasticsearch index with data.

**Steps:**
1. Health check:
   ```bash
   curl http://localhost:8000/settings/integrations | jq '.[] | select(.name == "kibana")'
   ```
   Expected: `"configured": true, "healthy": true`

2. Search logs:
   ```bash
   curl -X POST http://localhost:8000/debug/mcp/call \
     -H "Content-Type: application/json" \
     -d '{"tool": "kibana_search", "args": {"index": "logs-*", "query": "error"}}'
   ```
   Expected: JSON list of matching log entries.

---

## Test 7: Postman MCP Server

**Setup:**
1. Set in `.env`:
   - `POSTMAN_API_KEY=<from https://go.postman.co/settings/me/api-keys>`
   - `POSTMAN_WORKSPACE_ID=<optional workspace ID>`
2. Have at least one collection in your Postman workspace.

**Steps:**
1. Health check:
   ```bash
   curl http://localhost:8000/settings/integrations | jq '.[] | select(.name == "postman")'
   ```
   Expected: `"configured": true, "healthy": true`

2. List collections:
   ```bash
   curl -X POST http://localhost:8000/debug/mcp/call \
     -H "Content-Type: application/json" \
     -d '{"tool": "postman_list_collections", "args": {}}'
   ```
   Expected: JSON list of Postman collections with id, name, owner.

---

## Test 8: GitNexus MCP Server

**Setup:** GitNexus must be installed (`npm install -g gitnexus` or available in Docker). A repo must be indexed first via `POST /index`.

**Steps:**
1. Verify GitNexus tools are listed:
   ```bash
   curl http://localhost:8000/debug/mcp/tools | jq '.tools[] | select(.name | test("cypher|impact|context|query|list_repos"))'
   ```
   Expected: `cypher`, `impact`, `context`, `query`, `list_repos` etc.

2. List indexed repos:
   ```bash
   curl http://localhost:8000/debug/mcp/repos
   ```
   Expected: List of repos with stats (files, nodes, edges, communities, processes).

3. Run a Cypher query:
   ```bash
   curl -X POST http://localhost:8000/debug/mcp/call \
     -H "Content-Type: application/json" \
     -d '{"tool": "cypher", "args": {"query": "MATCH (p:Process) RETURN p.id, p.label LIMIT 5", "repo": "Qlankr"}}'
   ```
   Expected: List of Process nodes from the knowledge graph.

---

## Verification Checklist

| # | Server | Health | Tool Discovery | Tool Execution | Notes |
|---|--------|--------|---------------|----------------|-------|
| 1 | GitHub | N/A | [ ] | [ ] | |
| 2 | Jira | [ ] | [ ] | [ ] | |
| 3 | Notion | [ ] | [ ] | [ ] | |
| 4 | Confluence | [ ] | [ ] | [ ] | |
| 5 | Grafana | [ ] | [ ] | [ ] | |
| 6 | Kibana | [ ] | [ ] | [ ] | |
| 7 | Postman | [ ] | [ ] | [ ] | |
| 8 | GitNexus | N/A | [ ] | [ ] | |
