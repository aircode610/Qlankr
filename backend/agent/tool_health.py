"""
Lightweight health checks for external integrations. Used by GET /settings/integrations.
Credential overrides (from POST /settings/integrations) are session-scoped in-memory.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

# name -> cred dict merged for checks (P4 may extend env-based checks)
_credential_session_overrides: dict[str, dict[str, Any]] = {}


def set_credential_overrides(overrides: dict[str, dict[str, Any]]) -> None:
    _credential_session_overrides.clear()
    for k, v in overrides.items():
        _credential_session_overrides[k] = dict(v)


def merge_session_credentials(name: str, creds: dict[str, Any]) -> None:
    cur = _credential_session_overrides.get(name, {})
    _credential_session_overrides[name] = {**cur, **creds}
    merge_credential_env(name)


def merge_credential_env(name: str) -> None:
    """After a single integration update, copy known keys into os.environ for the process.

    Staged deployments may instead write to a secret store; this is sufficient for local dev
    and health pings that read os.environ.
    """
    c = _credential_session_overrides.get(name)
    if not c:
        return
    env_map: dict[str, list[str]] = {
        "jira": ["JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT_KEY"],
        "notion": ["NOTION_API_KEY", "NOTION_WORKSPACE_ID"],
        "confluence": ["CONFLUENCE_URL", "CONFLUENCE_TOKEN", "CONFLUENCE_SPACE_KEY"],
        "grafana": ["GRAFANA_URL", "GRAFANA_API_KEY"],
        "kibana": ["KIBANA_URL", "KIBANA_TOKEN"],
        "postman": ["POSTMAN_API_KEY", "POSTMAN_WORKSPACE_ID"],
    }
    for var in env_map.get(name, []):
        if var in c and c[var]:
            os.environ[var] = str(c[var])


def _jira_configured() -> bool:
    return bool(
        (os.environ.get("JIRA_URL") and os.environ.get("JIRA_API_TOKEN"))
        or (
            "jira" in _credential_session_overrides
            and _credential_session_overrides["jira"].get("JIRA_API_TOKEN")
            and _credential_session_overrides["jira"].get("JIRA_URL")
        )
    )


def _notion_configured() -> bool:
    return bool(
        os.environ.get("NOTION_API_KEY")
        or _credential_session_overrides.get("notion", {}).get("NOTION_API_KEY")
    )


def _confluence_configured() -> bool:
    return bool(
        (os.environ.get("CONFLUENCE_URL") and os.environ.get("CONFLUENCE_TOKEN"))
        or (
            _credential_session_overrides.get("confluence", {}).get("CONFLUENCE_URL")
            and _credential_session_overrides.get("confluence", {}).get("CONFLUENCE_TOKEN")
        )
    )


def _grafana_configured() -> bool:
    return bool(
        (os.environ.get("GRAFANA_URL") and os.environ.get("GRAFANA_API_KEY"))
        or (
            _credential_session_overrides.get("grafana", {}).get("GRAFANA_URL")
            and _credential_session_overrides.get("grafana", {}).get("GRAFANA_API_KEY")
        )
    )


def _kibana_configured() -> bool:
    return bool(
        (os.environ.get("KIBANA_URL") and os.environ.get("KIBANA_TOKEN"))
        or (
            _credential_session_overrides.get("kibana", {}).get("KIBANA_URL")
            and _credential_session_overrides.get("kibana", {}).get("KIBANA_TOKEN")
        )
    )


def _postman_configured() -> bool:
    return bool(
        os.environ.get("POSTMAN_API_KEY")
        or _credential_session_overrides.get("postman", {}).get("POSTMAN_API_KEY")
    )


async def _ping(url: str, **kwargs: Any) -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url, **kwargs)
        if r.status_code < 400:
            return True, f"OK ({r.status_code})"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)


def _jira_url() -> str:
    c = _credential_session_overrides.get("jira", {})
    return str(c.get("JIRA_URL") or os.environ.get("JIRA_URL", "")).rstrip("/")


def _confluence_url() -> str:
    c = _credential_session_overrides.get("confluence", {})
    return str(c.get("CONFLUENCE_URL") or os.environ.get("CONFLUENCE_URL", "")).rstrip("/")


def _grafana_url() -> str:
    c = _credential_session_overrides.get("grafana", {})
    return str(c.get("GRAFANA_URL") or os.environ.get("GRAFANA_URL", "")).rstrip("/")


def _kibana_url() -> str:
    c = _credential_session_overrides.get("kibana", {})
    return str(c.get("KIBANA_URL") or os.environ.get("KIBANA_URL", "")).rstrip("/")


async def check_integration_health(name: str) -> dict:
    """
    Return {"name": str, "configured": bool, "healthy": bool, "message": str}
    as plain dicts for FastAPI; callers may wrap in IntegrationStatus.
    """
    if name == "jira":
        if not _jira_configured():
            return {
                "name": "jira",
                "configured": False,
                "healthy": False,
                "message": "JIRA_URL and JIRA_API_TOKEN not set",
            }
        import base64

        u = _jira_url() + "/rest/api/2/myself"
        token = (
            _credential_session_overrides.get("jira", {}).get("JIRA_API_TOKEN")
            or os.environ.get("JIRA_API_TOKEN", "")
        )
        email = (
            _credential_session_overrides.get("jira", {}).get("JIRA_EMAIL")
            or os.environ.get("JIRA_EMAIL", "")
        )
        if not email or "@" not in str(email):
            return {
                "name": "jira",
                "configured": True,
                "healthy": False,
                "message": "JIRA_EMAIL (Atlassian account) required for /myself check",
            }
        b64 = base64.b64encode(f"{email}:{token}".encode()).decode("ascii")
        h = {"Authorization": f"Basic {b64}"}
        ok, msg = await _ping(u, headers=h)
        return {"name": "jira", "configured": True, "healthy": ok, "message": msg}

    if name == "notion":
        if not _notion_configured():
            return {
                "name": "notion",
                "configured": False,
                "healthy": False,
                "message": "NOTION_API_KEY not set",
            }
        key = (
            _credential_session_overrides.get("notion", {}).get("NOTION_API_KEY")
            or os.environ.get("NOTION_API_KEY", "")
        )
        ok, m = await _ping(
            "https://api.notion.com/v1/users/me",
            headers={
                "Authorization": f"Bearer {key}",
                "Notion-Version": "2022-06-28",
            },
        )
        return {"name": "notion", "configured": True, "healthy": ok, "message": m}

    if name == "confluence":
        if not _confluence_configured():
            return {
                "name": "confluence",
                "configured": False,
                "healthy": False,
                "message": "CONFLUENCE_URL/TOKEN not set",
            }
        u = _confluence_url() + "/wiki/rest/api/user/current"
        tok = (
            _credential_session_overrides.get("confluence", {}).get("CONFLUENCE_TOKEN")
            or os.environ.get("CONFLUENCE_TOKEN", "")
        )
        ok, m = await _ping(u, headers={"Authorization": f"Bearer {tok}"})
        return {"name": "confluence", "configured": True, "healthy": ok, "message": m}

    if name == "grafana":
        if not _grafana_configured():
            return {
                "name": "grafana",
                "configured": False,
                "healthy": False,
                "message": "GRAFANA_URL/API_KEY not set",
            }
        u = _grafana_url() + "/api/health"
        gkey = (
            _credential_session_overrides.get("grafana", {}).get("GRAFANA_API_KEY")
            or os.environ.get("GRAFANA_API_KEY", "")
        )
        ok, msg = await _ping(u, headers={"Authorization": f"Bearer {gkey}"})
        return {"name": "grafana", "configured": True, "healthy": ok, "message": msg}

    if name == "kibana":
        if not _kibana_configured():
            return {
                "name": "kibana",
                "configured": False,
                "healthy": False,
                "message": "KIBANA_URL/TOKEN not set",
            }
        u = _kibana_url() + "/api/status"
        ktok = (
            _credential_session_overrides.get("kibana", {}).get("KIBANA_TOKEN")
            or os.environ.get("KIBANA_TOKEN", "")
        )
        headers: dict[str, str] = {}
        if ktok:
            headers["Authorization"] = f"Bearer {ktok}"
        ok, msg = await _ping(u, headers=headers or None)
        return {"name": "kibana", "configured": True, "healthy": ok, "message": msg}

    if name == "postman":
        if not _postman_configured():
            return {
                "name": "postman",
                "configured": False,
                "healthy": False,
                "message": "POSTMAN_API_KEY not set",
            }
        key = (
            _credential_session_overrides.get("postman", {}).get("POSTMAN_API_KEY")
            or os.environ.get("POSTMAN_API_KEY", "")
        )
        ok, m = await _ping(
            "https://api.getpostman.com/me", headers={"X-Api-Key": key}
        )
        return {"name": "postman", "configured": True, "healthy": ok, "message": m}

    return {
        "name": name,
        "configured": False,
        "healthy": False,
        "message": f"Unknown integration: {name}",
    }


async def check_all_integrations() -> list[dict]:
    """Run health check for all known integrations (Jira, Notion, Confluence, Grafana, Kibana, Postman)."""
    names = ["jira", "notion", "confluence", "grafana", "kibana", "postman"]
    return [await check_integration_health(n) for n in names]
