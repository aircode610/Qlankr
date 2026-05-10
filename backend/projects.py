import re
from uuid import UUID

from db import user_scoped


_GITHUB_RE = re.compile(r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$")


def parse_repo_url(repo_url: str) -> tuple[str, str]:
    m = _GITHUB_RE.match(repo_url.strip())
    if not m:
        raise ValueError(f"Not a GitHub repo URL: {repo_url}")
    return m.group("owner"), m.group("repo")


def list_projects(user_id: UUID) -> list[dict]:
    scoped = user_scoped(user_id)
    res = scoped.table("projects").select("*").order("created_at", desc=True).execute()
    return res.data or []


def get_project(user_id: UUID, project_id: str) -> dict | None:
    scoped = user_scoped(user_id)
    res = scoped.table("projects").select("*").eq("id", project_id).execute()
    rows = res.data or []
    return rows[0] if rows else None


def create_project(user_id: UUID, repo_url: str) -> dict:
    owner, repo = parse_repo_url(repo_url)
    scoped = user_scoped(user_id)
    existing = scoped.table("projects").select("*").eq("repo_url", repo_url).execute().data or []
    if existing:
        return existing[0]
    res = scoped.table("projects").insert({
        "repo_url": repo_url,
        "owner": owner,
        "repo_name": repo,
        "index_status": "pending",
    }).execute()
    return (res.data or [])[0]


def delete_project(user_id: UUID, project_id: str) -> None:
    scoped = user_scoped(user_id)
    scoped.table("projects").delete().eq("id", project_id).execute()


def update_status(user_id: UUID, project_id: str, *, status: str, error: str | None = None, stats: dict | None = None, last_indexed_at: str | None = None) -> None:
    payload = {"index_status": status}
    if error is not None:
        payload["index_error"] = error
    if stats is not None:
        payload["graph_stats"] = stats
    if last_indexed_at is not None:
        payload["last_indexed_at"] = last_indexed_at
    scoped = user_scoped(user_id)
    scoped.table("projects").update(payload).eq("id", project_id).execute()
