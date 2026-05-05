"""
Kibana / Elasticsearch custom MCP server — exposes log search and document lookup.

Launched via stdio by MultiServerMCPClient when KIBANA_URL + KIBANA_TOKEN are set.
Queries the Elasticsearch API behind Kibana.
"""

from __future__ import annotations

import json
import os

import httpx
from mcp.server.fastmcp import FastMCP

app = FastMCP("kibana")

KIBANA_URL = os.environ.get("KIBANA_URL", "").rstrip("/")
KIBANA_TOKEN = os.environ.get("KIBANA_TOKEN", "")


def _es_base() -> str:
    """Derive the Elasticsearch base URL from KIBANA_URL."""
    url = KIBANA_URL
    for suffix in ("/kibana", "/app"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break
    return url


def _headers() -> dict[str, str]:
    h: dict[str, str] = {"Content-Type": "application/json"}
    if KIBANA_TOKEN:
        h["Authorization"] = f"Bearer {KIBANA_TOKEN}"
    return h


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=_es_base(), headers=_headers(), timeout=15.0)


@app.tool()
async def kibana_search(
    index: str,
    query: str,
    from_ts: str = "",
    to_ts: str = "",
) -> str:
    """Search Elasticsearch index for log entries matching a query.

    Args:
        index: Elasticsearch index or index pattern (e.g. "logs-*").
        query: Search string (used in a match query against the message field).
        from_ts: Optional start timestamp (ISO-8601).
        to_ts: Optional end timestamp (ISO-8601).

    Returns:
        JSON list of hit documents (max 50).
    """
    must: list[dict] = [{"match": {"message": query}}]
    if from_ts or to_ts:
        ts_range: dict = {}
        if from_ts:
            ts_range["gte"] = from_ts
        if to_ts:
            ts_range["lte"] = to_ts
        must.append({"range": {"@timestamp": ts_range}})

    body = {
        "size": 50,
        "query": {"bool": {"must": must}},
        "sort": [{"@timestamp": {"order": "desc"}}],
    }

    async with _client() as c:
        r = await c.post(f"/{index}/_search", json=body)
        if r.status_code >= 400:
            return json.dumps({"error": f"ES returned HTTP {r.status_code}", "body": r.text[:500]})
        data = r.json()

    hits = data.get("hits", {}).get("hits", [])
    results = []
    for h in hits[:50]:
        src = h.get("_source", {})
        results.append({
            "id": h.get("_id"),
            "index": h.get("_index"),
            "timestamp": src.get("@timestamp", ""),
            "level": src.get("level", src.get("log", {}).get("level", "")),
            "message": src.get("message", ""),
            "source": src.get("service", {}).get("name", src.get("host", {}).get("name", "")),
            "labels": {k: v for k, v in src.items() if k not in ("message", "@timestamp", "level")},
        })
    return json.dumps(results)


@app.tool()
async def kibana_get_log_entry(
    index: str,
    id: str,
) -> str:
    """Retrieve a single log entry by ID from Elasticsearch.

    Args:
        index: Elasticsearch index name.
        id: Document ID.

    Returns:
        JSON document source.
    """
    async with _client() as c:
        r = await c.get(f"/{index}/_doc/{id}")
        if r.status_code >= 400:
            return json.dumps({"error": f"ES returned HTTP {r.status_code}", "body": r.text[:500]})
        data = r.json()
    return json.dumps(data.get("_source", {}))


if __name__ == "__main__":
    app.run()
