"""Startup hooks that run once when the FastAPI app boots."""
import logging


def reconcile_orphaned_runs() -> None:
    """Mark any pr_analyses / bug_reports rows still in status='running' as cancelled.

    A row in 'running' state at startup means the previous backend died mid-run.
    Without this, history views would show perpetually-running phantoms.
    """
    try:
        from db import get_client  # noqa: PLC0415

        client = get_client()
        payload = {"status": "cancelled", "failure_reason": "backend restarted"}
        client.table("pr_analyses").update(payload).eq("status", "running").execute()
        client.table("bug_reports").update(payload).eq("status", "running").execute()
    except Exception as e:
        logging.warning("startup reconciliation failed (non-fatal): %s", e)
