"""In-process registry for active bug report runs. Split out so test fixtures can clear without loading the LLM."""

from __future__ import annotations

_bug_runs: dict[str, bool] = {}


def mark_bug_run_started(session_id: str) -> None:
    _bug_runs[session_id] = True


def is_active_bug_run(session_id: str) -> bool:
    return session_id in _bug_runs


def clear_bug_runs() -> None:
    _bug_runs.clear()


# ── Supabase persistence hooks ───────────────────────────────────────────
# Per-stage outputs are not yet wired into the LangGraph nodes (follow-up).

def persist_bug_run_start(
    user_id, session_id: str, project_id: str, bug_description: str,
) -> None:
    import logging
    try:
        from db import user_scoped  # noqa: PLC0415
        scoped = user_scoped(user_id)
        scoped.table("bug_reports").insert({
            "id": session_id,
            "project_id": project_id,
            "bug_description": bug_description,
            "status": "running",
        }).execute()
    except Exception as e:
        logging.error("persist_bug_run_start failed for %s: %s", session_id, e)


def persist_bug_run_finalize(
    user_id, session_id: str, *,
    status: str, final_report: dict | None = None,
    severity: str | None = None, failure_reason: str | None = None,
) -> None:
    import logging
    from datetime import datetime, timezone  # noqa: PLC0415
    try:
        from db import user_scoped  # noqa: PLC0415
        payload: dict = {
            "status": status,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        if final_report is not None:
            payload["final_report"] = final_report
        if severity is not None:
            payload["severity"] = severity
        if failure_reason is not None:
            payload["failure_reason"] = failure_reason
        scoped = user_scoped(user_id)
        scoped.table("bug_reports").update(payload).eq("id", session_id).execute()
    except Exception as e:
        logging.error("persist_bug_run_finalize failed for %s: %s", session_id, e)
