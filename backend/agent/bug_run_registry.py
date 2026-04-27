"""In-process registry for active bug report runs. Split out so test fixtures can clear without loading the LLM."""

from __future__ import annotations

_bug_runs: dict[str, bool] = {}


def mark_bug_run_started(session_id: str) -> None:
    _bug_runs[session_id] = True


def is_active_bug_run(session_id: str) -> bool:
    return session_id in _bug_runs


def clear_bug_runs() -> None:
    _bug_runs.clear()
