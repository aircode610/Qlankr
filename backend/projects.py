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


def create_project(
    user_id: UUID,
    *,
    name: str | None = None,
    repo_url: str | None = None,
) -> dict:
    """Create a project. Either `name` (user label, repo attached later) or
    `repo_url` (immediate indexing-ready project). At least one is required.
    """
    if not name and not repo_url:
        raise ValueError("create_project requires `name` or `repo_url`")

    scoped = user_scoped(user_id)
    payload: dict = {"index_status": "pending"}
    if name is not None:
        payload["name"] = name
    if repo_url is not None:
        owner, repo = parse_repo_url(repo_url)
        # Idempotent on (user_id, repo_url) only when a URL was given.
        existing = scoped.table("projects").select("*").eq("repo_url", repo_url).execute().data or []
        if existing:
            return existing[0]
        payload["repo_url"] = repo_url
        payload["owner"] = owner
        payload["repo_name"] = repo
        payload.setdefault("name", f"{owner}/{repo}")

    res = scoped.table("projects").insert(payload).execute()
    return (res.data or [])[0]


def attach_repo(user_id: UUID, project_id: str, repo_url: str) -> dict:
    """Attach a GitHub URL to an existing named project. Sets owner/repo_name/repo_url
    and resets the index status to 'pending' so the next indexing run kicks off."""
    owner, repo = parse_repo_url(repo_url)
    scoped = user_scoped(user_id)
    scoped.table("projects").update({
        "repo_url": repo_url,
        "owner": owner,
        "repo_name": repo,
        "index_status": "pending",
        "index_error": None,
    }).eq("id", project_id).execute()
    project = get_project(user_id, project_id)
    if not project:
        raise KeyError(project_id)
    return project


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
