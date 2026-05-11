from dataclasses import dataclass
from typing import Any
from uuid import UUID

from db import user_scoped


@dataclass(frozen=True)
class UserCredentials:
    anthropic_api_key: str | None = None
    github_token: str | None = None
    jira: dict | None = None
    notion: dict | None = None
    confluence: dict | None = None
    grafana: dict | None = None
    kibana: dict | None = None
    postman: dict | None = None


_COLUMN_MAP = {
    "anthropic_api_key": "anthropic_api_key",
    "github_token": "github_token",
    "jira": "jira_creds",
    "notion": "notion_creds",
    "confluence": "confluence_creds",
    "grafana": "grafana_creds",
    "kibana": "kibana_creds",
    "postman": "postman_creds",
}


def load_credentials(user_id: UUID) -> UserCredentials:
    scoped = user_scoped(user_id)
    res = scoped.table("user_credentials").select("*").execute()
    rows = res.data or []
    if not rows:
        return UserCredentials()
    row = rows[0]
    return UserCredentials(
        anthropic_api_key=row.get("anthropic_api_key"),
        github_token=row.get("github_token"),
        jira=row.get("jira_creds"),
        notion=row.get("notion_creds"),
        confluence=row.get("confluence_creds"),
        grafana=row.get("grafana_creds"),
        kibana=row.get("kibana_creds"),
        postman=row.get("postman_creds"),
    )


def save_credentials(user_id: UUID, **updates: Any) -> None:
    payload = {_COLUMN_MAP[k]: v for k, v in updates.items() if k in _COLUMN_MAP}
    if not payload:
        return
    scoped = user_scoped(user_id)
    existing = scoped.table("user_credentials").select("user_id").execute().data or []
    if existing:
        scoped.table("user_credentials").update(payload).execute()
    else:
        scoped.table("user_credentials").insert(payload).execute()
