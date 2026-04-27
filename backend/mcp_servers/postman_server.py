"""
Postman custom MCP server — exposes collection browsing and request execution.

Launched via stdio by MultiServerMCPClient when POSTMAN_API_KEY is set.
"""

from __future__ import annotations

import json
import os

import httpx
from mcp.server.fastmcp import FastMCP

app = FastMCP("postman")

API_KEY = os.environ.get("POSTMAN_API_KEY", "")
WORKSPACE_ID = os.environ.get("POSTMAN_WORKSPACE_ID", "")
BASE = "https://api.getpostman.com"

_HEADERS = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE, headers=_HEADERS, timeout=15.0)


@app.tool()
async def postman_list_collections() -> str:
    """List all Postman collections in the workspace.

    Returns:
        JSON list of {id, name, owner, updatedAt}.
    """
    params: dict[str, str] = {}
    if WORKSPACE_ID:
        params["workspace"] = WORKSPACE_ID
    async with _client() as c:
        r = await c.get("/collections", params=params or None)
        if r.status_code >= 400:
            return json.dumps({"error": f"HTTP {r.status_code}", "body": r.text[:500]})
        data = r.json()

    collections = data.get("collections", [])
    return json.dumps([
        {
            "id": col.get("id") or col.get("uid"),
            "name": col.get("name"),
            "owner": col.get("owner", ""),
            "updatedAt": col.get("updatedAt", ""),
        }
        for col in collections
    ])


@app.tool()
async def postman_get_collection(collection_id: str) -> str:
    """Get details of a Postman collection including all requests.

    Args:
        collection_id: The collection ID or UID.

    Returns:
        JSON with collection info and list of requests with endpoints and methods.
    """
    async with _client() as c:
        r = await c.get(f"/collections/{collection_id}")
        if r.status_code >= 400:
            return json.dumps({"error": f"HTTP {r.status_code}", "body": r.text[:500]})
        data = r.json()

    col = data.get("collection", {})
    info = col.get("info", {})

    def _extract_items(items: list, prefix: str = "") -> list[dict]:
        requests: list[dict] = []
        for item in items:
            name = item.get("name", "")
            full_name = f"{prefix}/{name}" if prefix else name
            if "item" in item:
                requests.extend(_extract_items(item["item"], full_name))
            elif "request" in item:
                req = item["request"]
                url = req.get("url", {})
                raw_url = url.get("raw", "") if isinstance(url, dict) else str(url)
                requests.append({
                    "id": item.get("id", name),
                    "name": full_name,
                    "method": req.get("method", "GET"),
                    "url": raw_url,
                })
        return requests

    requests = _extract_items(col.get("item", []))
    return json.dumps({
        "name": info.get("name", ""),
        "description": info.get("description", ""),
        "requests": requests,
    })


@app.tool()
async def postman_get_request(collection_id: str, request_id: str) -> str:
    """Get full details of a specific request in a Postman collection.

    Args:
        collection_id: The collection ID or UID.
        request_id: The request item ID or name.

    Returns:
        JSON with method, URL, headers, and body schema.
    """
    async with _client() as c:
        r = await c.get(f"/collections/{collection_id}")
        if r.status_code >= 400:
            return json.dumps({"error": f"HTTP {r.status_code}", "body": r.text[:500]})
        data = r.json()

    col = data.get("collection", {})

    def _find(items: list) -> dict | None:
        for item in items:
            if "item" in item:
                found = _find(item["item"])
                if found:
                    return found
            elif item.get("id") == request_id or item.get("name") == request_id:
                return item
        return None

    item = _find(col.get("item", []))
    if not item:
        return json.dumps({"error": f"Request '{request_id}' not found in collection"})

    req = item.get("request", {})
    url = req.get("url", {})
    raw_url = url.get("raw", "") if isinstance(url, dict) else str(url)
    headers = [{"key": h.get("key"), "value": h.get("value")} for h in req.get("header", [])]
    body = req.get("body", {})

    return json.dumps({
        "name": item.get("name"),
        "method": req.get("method", "GET"),
        "url": raw_url,
        "headers": headers,
        "body_mode": body.get("mode", ""),
        "body_raw": body.get("raw", ""),
    })


@app.tool()
async def postman_run_request(
    collection_id: str,
    request_id: str,
    variables: str = "{}",
) -> str:
    """Execute a Postman request and return the response. USE WITH CAUTION.

    Args:
        collection_id: The collection ID or UID.
        request_id: The request item ID or name.
        variables: JSON string of variable overrides, e.g. '{"base_url": "http://localhost:3000"}'.

    Returns:
        JSON with status code and response body (truncated).
    """
    detail_raw = await postman_get_request(collection_id, request_id)
    detail = json.loads(detail_raw)
    if "error" in detail:
        return detail_raw

    try:
        vars_dict = json.loads(variables) if isinstance(variables, str) else variables
    except json.JSONDecodeError:
        vars_dict = {}

    url = detail.get("url", "")
    for k, v in vars_dict.items():
        url = url.replace(f"{{{{{k}}}}}", str(v))

    method = detail.get("method", "GET")
    headers = {h["key"]: h["value"] for h in detail.get("headers", []) if h.get("key")}
    body_raw = detail.get("body_raw", "")
    for k, v in vars_dict.items():
        body_raw = body_raw.replace(f"{{{{{k}}}}}", str(v))

    async with httpx.AsyncClient(timeout=30.0) as c:
        try:
            r = await c.request(
                method=method,
                url=url,
                headers=headers,
                content=body_raw if body_raw else None,
            )
            return json.dumps({
                "status": r.status_code,
                "headers": dict(r.headers),
                "body": r.text[:2000],
            })
        except Exception as e:
            return json.dumps({"error": str(e)})


if __name__ == "__main__":
    app.run()
