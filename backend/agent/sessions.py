from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass
class Session:
    session_id: str
    pr_url: str
    created_at: datetime
    current_stage: str = "gathering"
    thread_id: str = ""  # LangGraph thread ID for checkpoint resume
    intermediate_result: dict = field(default_factory=dict)

    def to_status_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "current_stage": self.current_stage,
            "created_at": self.created_at.isoformat(),
            "intermediate_result": self.intermediate_result,
        }


# In-memory store (no persistence for now)
_sessions: dict[str, Session] = {}


def create_session(pr_url: str) -> Session:
    sid = uuid.uuid4().hex[:12]
    session = Session(
        session_id=sid,
        pr_url=pr_url,
        created_at=datetime.now(timezone.utc),
    )
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
