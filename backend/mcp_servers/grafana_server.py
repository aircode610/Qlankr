"""
Grafana custom MCP server — exposes log/metric queries and annotation lookups.

Launched via stdio by MultiServerMCPClient when GRAFANA_URL + GRAFANA_API_KEY are set.
"""

from __future__ import annotations

import json
import os

import httpx
from mcp.server.fastmcp import FastMCP

app = FastMCP("grafana")

GRAFANA_URL = os.environ.get("GRAFANA_URL", "").rstrip("/")
GRAFANA_API_KEY = os.environ.get("GRAFANA_API_KEY", "")

_HEADERS = {
    "Authorization": f"Bearer {GRAFANA_API_KEY}",
    "Content-Type": "application/json",
}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=GRAFANA_URL, headers=_HEADERS, timeout=15.0)


@app.tool()
async def grafana_query_logs(
    datasource: str,
    query: str,
    from_ts: str,
    to_ts: str,
) -> str:
    """Query Grafana Loki datasource for log entries.

    Args:
        datasource: Loki datasource UID (or name).
        query: LogQL query string, e.g. '{app="myservice"} |= "error"'.
        from_ts: Start timestamp (ISO-8601 or epoch ms).
        to_ts: End timestamp (ISO-8601 or epoch ms).

    Returns:
        JSON list of {timestamp, level, message, source, labels}.
    """
    body = {
        "queries": [
            {
                "refId": "A",
                "datasource": {"uid": datasource},
                "expr": query,
                "queryType": "range",
            }
        ],
        "from": from_ts,
        "to": to_ts,
    }
    async with _client() as c:
        r = await c.post("/api/ds/query", json=body)
        if r.status_code >= 400:
            return json.dumps({"error": f"Grafana returned HTTP {r.status_code}", "body": r.text[:500]})
        data = r.json()

    entries: list[dict] = []
    for frame in data.get("results", {}).get("A", {}).get("frames", []):
        values = frame.get("data", {}).get("values", [])
        if len(values) >= 2:
            timestamps, messages = values[0], values[1]
            labels = frame.get("schema", {}).get("fields", [{}])[-1].get("labels", {})
            for ts, msg in zip(timestamps, messages):
                entries.append({
                    "timestamp": str(ts),
                    "level": labels.get("level", ""),
                    "message": str(msg),
                    "source": labels.get("app", labels.get("job", datasource)),
                    "labels": labels,
                })
    return json.dumps(entries[:200])


@app.tool()
async def grafana_query_metrics(
    datasource: str,
    query: str,
    from_ts: str,
    to_ts: str,
) -> str:
    """Query Grafana Prometheus datasource for metric data points.

    Args:
        datasource: Prometheus datasource UID.
        query: PromQL query string.
        from_ts: Start timestamp (ISO-8601 or epoch ms).
        to_ts: End timestamp (ISO-8601 or epoch ms).

    Returns:
        JSON list of {metric, values: [[timestamp, value], ...]}.
    """
    body = {
        "queries": [
            {
                "refId": "A",
                "datasource": {"uid": datasource},
                "expr": query,
                "queryType": "range",
                "intervalMs": 15000,
                "maxDataPoints": 500,
            }
        ],
        "from": from_ts,
        "to": to_ts,
    }
    async with _client() as c:
        r = await c.post("/api/ds/query", json=body)
        if r.status_code >= 400:
            return json.dumps({"error": f"Grafana returned HTTP {r.status_code}", "body": r.text[:500]})
        data = r.json()

    series: list[dict] = []
    for frame in data.get("results", {}).get("A", {}).get("frames", []):
        schema_fields = frame.get("schema", {}).get("fields", [])
        metric_labels = schema_fields[-1].get("labels", {}) if schema_fields else {}
        values = frame.get("data", {}).get("values", [])
        if len(values) >= 2:
            series.append({
                "metric": metric_labels,
                "values": list(zip(values[0], values[1]))[:500],
            })
    return json.dumps(series)


@app.tool()
async def grafana_get_annotations(
    dashboard_id: str,
    from_ts: str,
    to_ts: str,
) -> str:
    """Get deployment markers and incident annotations from Grafana.

    Args:
        dashboard_id: Dashboard ID or UID.
        from_ts: Start timestamp (epoch ms).
        to_ts: End timestamp (epoch ms).

    Returns:
        JSON list of {id, time, timeEnd, text, tags}.
    """
    params = {"dashboardId": dashboard_id, "from": from_ts, "to": to_ts, "limit": 100}
    async with _client() as c:
        r = await c.get("/api/annotations", params=params)
        if r.status_code >= 400:
            return json.dumps({"error": f"HTTP {r.status_code}", "body": r.text[:500]})
        annotations = r.json()

    return json.dumps([
        {
            "id": a.get("id"),
            "time": a.get("time"),
            "timeEnd": a.get("timeEnd"),
            "text": a.get("text", ""),
            "tags": a.get("tags", []),
        }
        for a in (annotations if isinstance(annotations, list) else [])
    ])


if __name__ == "__main__":
    app.run()
