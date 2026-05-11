from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from enum import Enum

from models import BugReport


class SessionType(str, Enum):
    IMPACT_ANALYSIS = "impact_analysis"
    BUG_REPRODUCTION = "bug_reproduction"


@dataclass
class Session:
    session_id: str
    session_type: SessionType
    pr_url: str | None
    bug_description: str | None
    created_at: datetime
    current_stage: str = "gathering"
    thread_id: str = ""
    intermediate_result: dict = field(default_factory=dict)
    bug_report: BugReport | None = None

    def to_status_dict(self) -> dict:
        out: dict = {
            "session_id": self.session_id,
            "session_type": self.session_type.value,
            "current_stage": self.current_stage,
            "created_at": self.created_at.isoformat(),
            "intermediate_result": self.intermediate_result,
            "pr_url": self.pr_url,
        }
        if self.bug_description is not None:
            out["bug_description"] = self.bug_description
        if self.bug_report is not None:
            out["bug_report"] = (
                self.bug_report.model_dump()
                if isinstance(self.bug_report, BugReport)
                else self.bug_report
            )
        return out

    def get_bug_report(self):
        return self.bug_report


# In-memory store (no persistence for now)
_sessions: dict[str, Session] = {}


def create_session(
    pr_url: str | None = None,
    *,
    session_type: SessionType = SessionType.IMPACT_ANALYSIS,
    bug_description: str | None = None,
) -> Session:
    """Create a new session. Default session type is impact (PR) analysis; use BUG_REPRODUCTION for bug flow."""
    sid = uuid.uuid4().hex[:12]
    session = Session(
        session_id=sid,
        session_type=session_type,
        pr_url=pr_url,
        bug_description=bug_description,
        created_at=datetime.now(timezone.utc),
    )
    if session_type == SessionType.BUG_REPRODUCTION:
        if session.current_stage == "gathering":
            session.current_stage = "bug_triage"
    _sessions[sid] = session
    return session


def get_session(session_id: str) -> Session | None:
    return _sessions.get(session_id)


def update_session(session_id: str, **kwargs) -> None:
    session = _sessions.get(session_id)
    if session:
        for k, v in kwargs.items():
            setattr(session, k, v)


def clear_sessions() -> None:
    """Reset store (used by tests)."""
    _sessions.clear()


# ── Supabase persistence hooks ───────────────────────────────────────────
# Per-stage outputs are not yet wired into the LangGraph nodes (follow-up).
# These helpers persist run start + final result so history views work.

def persist_pr_analysis_start(
    user_id, session_id: str, project_id: str, pr_url: str,
    pr_number: int | None = None, pr_title: str | None = None,
) -> None:
    import logging
    try:
        from db import user_scoped  # noqa: PLC0415
        scoped = user_scoped(user_id)
        scoped.table("pr_analyses").insert({
            "id": session_id,
            "project_id": project_id,
            "pr_url": pr_url,
            "pr_number": pr_number,
            "pr_title": pr_title,
            "status": "running",
        }).execute()
    except Exception as e:
        logging.error("persist_pr_analysis_start failed for %s: %s", session_id, e)


def persist_pr_analysis_finalize(
    user_id, session_id: str, *,
    status: str, final_result: dict | None = None,
    failure_reason: str | None = None,
) -> None:
    import logging
    from datetime import datetime, timezone  # noqa: PLC0415
    try:
        from db import user_scoped  # noqa: PLC0415
        payload: dict = {
            "status": status,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        if final_result is not None:
            payload["final_result"] = final_result
        if failure_reason is not None:
            payload["failure_reason"] = failure_reason
        scoped = user_scoped(user_id)
        scoped.table("pr_analyses").update(payload).eq("id", session_id).execute()
    except Exception as e:
        logging.error("persist_pr_analysis_finalize failed for %s: %s", session_id, e)
