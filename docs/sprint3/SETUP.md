# Sprint 3 — Integrations Setup Guide

This guide covers every environment variable needed for the Sprint 3 bug reproduction pipeline, how each integration is used, and what a QA engineer needs to get started.

---

## Quick Start

Copy `.env.example` to `.env` and fill in the credentials for the integrations your team uses. **All integrations are optional** — the pipeline runs without any of them, falling back to code-graph-only analysis.

```bash
cp .env.example .env
# Edit .env with your credentials
docker compose up
```

---

## Required Variables (always needed)

| Variable | Where to get it | Purpose |
|----------|----------------|---------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Powers all AI stages |
| `GITHUB_TOKEN` | GitHub → Settings → Developer settings → Personal access tokens | Read PR diffs, search code |
| `VITE_API_URL` | Set to `http://localhost:8000` for local dev | Frontend → backend URL |

---

## Optional Integrations

Each integration below is **silently skipped** if its credentials are absent. The bug agent will note which sources were unavailable in its research findings.

### Jira

Used for: searching related issues, fetching ticket history, posting the final bug report.

| Variable | Example | Notes |
|----------|---------|-------|
| `JIRA_URL` | `https://studio.atlassian.net` | Cloud domain (no trailing slash) |
| `JIRA_EMAIL` | `qa@studio.com` | Atlassian account email |
| `JIRA_API_TOKEN` | `ATATT3xFf...` | From [id.atlassian.com](https://id.atlassian.com/manage-profile/security/api-tokens) |
| `JIRA_PROJECT_KEY` | `QA` | Default project for new issues |

**Health check endpoint:** `GET {JIRA_URL}/rest/api/2/myself`

---

### Notion

Used for: searching game design docs, patch notes, internal wikis.

| Variable | Example | Notes |
|----------|---------|-------|
| `NOTION_API_KEY` | `ntn_abc123...` | From [notion.so/my-integrations](https://www.notion.so/my-integrations) |
| `NOTION_WORKSPACE_ID` | `abc12345-...` | Optional — narrows search scope |

**Setup:** Create an integration at notion.so/my-integrations and share the pages/databases you want the agent to read.

**Health check endpoint:** `GET https://api.notion.com/v1/users/me`

---

### Confluence

Used for: runbooks, architecture docs, incident postmortems.

| Variable | Example | Notes |
|----------|---------|-------|
| `CONFLUENCE_URL` | `https://studio.atlassian.net/wiki` | Note the `/wiki` suffix |
| `CONFLUENCE_TOKEN` | Same as `JIRA_API_TOKEN` | Atlassian API tokens work for both |
| `CONFLUENCE_SPACE_KEY` | `ENG` | Optional — default search space |

**Health check endpoint:** `GET {CONFLUENCE_URL}/wiki/rest/api/user/current`

---

### Grafana

Used for: querying Loki logs and Prometheus metrics around the time of the bug.

| Variable | Example | Notes |
|----------|---------|-------|
| `GRAFANA_URL` | `https://grafana.studio.com` | No trailing slash |
| `GRAFANA_API_KEY` | `glsa_abc123...` | Service account token — needs at least Viewer role |

**Creating a service account token:**
1. Grafana → Administration → Service accounts → Create service account
2. Set Role: Viewer
3. Add token → copy the value

**Health check endpoint:** `GET {GRAFANA_URL}/api/health`

---

### Kibana / Elasticsearch

Used for: searching structured application logs in Elasticsearch.

| Variable | Example | Notes |
|----------|---------|-------|
| `KIBANA_URL` | `https://kibana.studio.com` | Kibana or ES base URL |
| `KIBANA_TOKEN` | `eyJ...` | Elasticsearch Bearer token or API key |

The custom MCP server queries Elasticsearch directly using the `KIBANA_URL` as the base and `KIBANA_TOKEN` as a Bearer token.

**Health check endpoint:** `GET {KIBANA_URL}/api/status`

---

### Postman

Used for: inspecting API contracts, understanding request/response schemas for affected endpoints.

| Variable | Example | Notes |
|----------|---------|-------|
| `POSTMAN_API_KEY` | `PMAK-abc123...` | From [go.postman.co/settings/me/api-keys](https://go.postman.co/settings/me/api-keys) |
| `POSTMAN_WORKSPACE_ID` | `abc12345-...` | Optional — narrows to a workspace |

**Health check endpoint:** `GET https://api.getpostman.com/me`

---

## Integration Selector (UI)

In the Bug Reproduction tab, each integration shows as a chip in the "Tools for this run" row:

- **Filled green dot** — configured and healthy, enabled for this run
- **Filled amber dot** — configured but health check failed, still enabled
- **Grey dot** — not configured (click Settings to add credentials)
- **Sniffer** — always available (no credentials needed, parses HAR/pcap files)

Clicking a chip **toggles** that integration for the current run. This lets QA engineers selectively disable slow integrations (e.g. skip Grafana if it's unrelated to a UI bug) or focus the agent on specific sources.

---

## Verifying Integration Health

```bash
curl http://localhost:8000/settings/integrations
```

Returns:
```json
{
  "integrations": [
    { "name": "jira", "configured": true, "healthy": true, "message": "OK (200)" },
    { "name": "grafana", "configured": false, "healthy": false, "message": "GRAFANA_URL/API_KEY not set" },
    ...
  ]
}
```

---

## Verifying MCP Tool Registration

After setting credentials, restart the backend and run:

```bash
curl http://localhost:8000/debug/mcp/tools | python3 -m json.tool | grep '"name"'
```

You should see tools like `grafana_query_logs`, `kibana_search`, `postman_list_collections`, etc. if the env vars are set correctly.

---

## Sniffer (HAR/pcap)

The sniffer runs locally — no credentials needed.

- **HAR files:** Export from browser DevTools (Network tab → Export as HAR). Any `.har` file works.
- **pcap files:** Captured with Wireshark or `tcpdump`. Requires `pyshark` to be installed (`pip install pyshark`).

In the bug form, add file paths or URLs in the Attachments field. The agent will call `sniffer_parse_har` and `sniffer_find_errors` automatically when the research stage runs.

---

## Environment Variables Summary

```bash
# Core (required)
ANTHROPIC_API_KEY=
GITHUB_TOKEN=
VITE_API_URL=http://localhost:8000

# Observability (optional)
LANGSMITH_API_KEY=
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=qlankr

# Jira
JIRA_URL=
JIRA_EMAIL=
JIRA_API_TOKEN=
JIRA_PROJECT_KEY=

# Notion
NOTION_API_KEY=
NOTION_WORKSPACE_ID=

# Confluence
CONFLUENCE_URL=
CONFLUENCE_TOKEN=
CONFLUENCE_SPACE_KEY=

# Grafana
GRAFANA_URL=
GRAFANA_API_KEY=

# Kibana / Elasticsearch
KIBANA_URL=
KIBANA_TOKEN=

# Postman
POSTMAN_API_KEY=
POSTMAN_WORKSPACE_ID=
```
