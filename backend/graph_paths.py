import os
from pathlib import Path
from uuid import UUID


def graphs_root() -> Path:
    override = os.environ.get("QLANKR_GRAPHS_ROOT")
    if override:
        return Path(override)
    return Path(os.environ["HOME"]) / ".qlankr" / "graphs"


def graph_dir(user_id: UUID, owner: str, repo: str, ensure: bool = False) -> Path:
    path = graphs_root() / str(user_id) / f"{owner}_{repo}"
    if ensure:
        path.mkdir(parents=True, exist_ok=True)
    return path


def clones_root() -> Path:
    override = os.environ.get("QLANKR_CLONES_ROOT")
    if override:
        return Path(override)
    return Path(os.environ["HOME"]) / ".qlankr" / "clones"


def clone_dir(user_id: UUID, owner: str, repo: str, ensure_parent: bool = False) -> Path:
    path = clones_root() / str(user_id) / f"{owner}_{repo}"
    if ensure_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def user_present_repos(user_id: UUID) -> list[tuple[str, str]]:
    user_root = graphs_root() / str(user_id)
    if not user_root.is_dir():
        return []
    out = []
    for entry in user_root.iterdir():
        if not entry.is_dir():
            continue
        if "_" not in entry.name:
            continue
        owner, repo = entry.name.split("_", 1)
        out.append((owner, repo))
    return out
