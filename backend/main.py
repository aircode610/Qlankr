import shutil
from typing import Any, AsyncIterator
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from auth import get_current_user
from export import export_markdown, export_pdf
from graph_paths import graph_dir
from indexer import get_clone_path, get_graph_data, index_repo, list_indexed_repos
from projects import (
    create_project,
    delete_project,
    get_project,
    list_projects,
)
from agent.sessions import SessionType, get_session
from agent.tool_health import check_all_integrations, merge_session_credentials
from models import (
    AnalyzeRequest,
    BugContinueRequest,
    BugReportRequest,
    ContinueRequest,
    ErrorEvent,
    ExportRequest,
    IndexRequest,
    IntegrationConfigRequest,
    IntegrationSettingsResponse,
    RunTestsRequest,
)

from contextlib import asynccontextmanager  # noqa: E402

from startup import reconcile_orphaned_runs  # noqa: E402


@asynccontextmanager
async def _lifespan(_app):
    reconcile_orphaned_runs()
    yield


app = FastAPI(lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# SSE helpers

def sse_event(data: BaseModel) -> str:
    event_type = getattr(data, "type", "message")
    return f"event: {event_type}\ndata: {data.model_dump_json()}\n\n"


async def stream_response(generator: AsyncIterator[BaseModel]) -> AsyncIterator[str]:
    async for event in generator:
        yield sse_event(event)


# Endpoints

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/index")
async def index(request: IndexRequest, user_id: UUID = Depends(get_current_user)):
    print(f"[INDEX] user={user_id} project_id={request.project_id!r} repo_url={request.repo_url!r}", flush=True)
    if request.project_id:
        from projects import attach_repo  # noqa: PLC0415
        try:
            attached = attach_repo(user_id, request.project_id, request.repo_url)
            print(f"[INDEX] attach_repo returned: id={attached['id']} owner={attached.get('owner')} repo_name={attached.get('repo_name')} repo_url={attached.get('repo_url')}", flush=True)
        except (ValueError, KeyError) as e:
            print(f"[INDEX] attach_repo FAILED: {e}", flush=True)
            raise HTTPException(status_code=400, detail=str(e))
    else:
        print("[INDEX] WARNING called without project_id", flush=True)
    return StreamingResponse(
        stream_response(index_repo(user_id, request.repo_url)),
        media_type="text/event-stream",
    )


@app.get("/repos")
async def get_repos(user_id: UUID = Depends(get_current_user)):
    """List all repos that have been indexed (persists across page reloads)."""
    return {"repos": list_indexed_repos(user_id)}


@app.get("/graph/{owner}/{repo}")
async def graph(owner: str, repo: str, user_id: UUID = Depends(get_current_user)):
    return await get_graph_data(user_id, owner, repo)


# ── Projects CRUD ─────────────────────────────────────────────────────────────

class CreateProjectBody(BaseModel):
    name: str | None = None
    repo_url: str | None = None


class AttachRepoBody(BaseModel):
    repo_url: str


@app.get("/projects")
async def get_projects(user_id: UUID = Depends(get_current_user)):
    return list_projects(user_id)


@app.post("/projects", status_code=201)
async def post_project(body: CreateProjectBody, user_id: UUID = Depends(get_current_user)):
    try:
        return create_project(user_id, name=body.name, repo_url=body.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/projects/{project_id}/attach")
async def post_attach_repo(project_id: str, body: AttachRepoBody, user_id: UUID = Depends(get_current_user)):
    from projects import attach_repo  # noqa: PLC0415

    try:
        return attach_repo(user_id, project_id, body.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError:
        raise HTTPException(status_code=404, detail="project not found")


@app.get("/projects/{project_id}")
async def get_project_detail(project_id: str, user_id: UUID = Depends(get_current_user)):
    project = get_project(user_id, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="not found")
    local_graph_present = (
        bool(project.get("owner")) and bool(project.get("repo_name"))
        and graph_dir(user_id, project["owner"], project["repo_name"]).is_dir()
    )
    return {**project, "local_graph_present": local_graph_present}


@app.delete("/projects/{project_id}", status_code=204)
async def delete_project_endpoint(project_id: str, user_id: UUID = Depends(get_current_user)):
    project = get_project(user_id, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="not found")
    delete_project(user_id, project_id)
    if project.get("owner") and project.get("repo_name"):
        path = graph_dir(user_id, project["owner"], project["repo_name"])
        if path.is_dir():
            shutil.rmtree(path)
    return None


# ── Debug endpoints (dev only) ────────────────────────────────────────────────

class _DebugCallRequest(BaseModel):
    tool: str
    args: dict[str, Any] = {}


def _unwrap(raw) -> Any:
    """Return a JSON-serialisable version of whatever an MCP tool returns."""
    if hasattr(raw, "content"):
        raw = raw.content
    if isinstance(raw, list):
        blocks = []
        for block in raw:
            if isinstance(block, dict) and block.get("type") == "text":
                import json as _json
                text = block.get("text", "")
                try:
                    blocks.append(_json.loads(text))
                except Exception:
                    blocks.append(text)
            else:
                blocks.append(block)
        return blocks[0] if len(blocks) == 1 else blocks
    return raw


@app.get("/debug/mcp/tools")
async def debug_mcp_tools(user_id: UUID = Depends(get_current_user)):
    """List all MCP tools the backend can see."""
    from agent.tools import get_mcp_client
    client = get_mcp_client()
    tools = await client.get_tools()
    return {
        "count": len(tools),
        "tools": [
            {"name": t.name, "description": getattr(t, "description", "")[:120]}
            for t in sorted(tools, key=lambda x: x.name)
        ],
    }


@app.get("/debug/mcp/repos")
async def debug_mcp_repos(user_id: UUID = Depends(get_current_user)):
    """Call list_repos and return the raw parsed response."""
    from agent.tools import get_mcp_client
    client = get_mcp_client()
    tools = await client.get_tools()
    tool_map = {t.name: t for t in tools}
    if "list_repos" not in tool_map:
        raise HTTPException(status_code=404, detail="list_repos tool not found")
    raw = await tool_map["list_repos"].ainvoke({})
    return {"raw": _unwrap(raw)}


@app.post("/debug/mcp/call")
async def debug_mcp_call(req: _DebugCallRequest, user_id: UUID = Depends(get_current_user)):
    """Call any MCP tool with arbitrary args and return the raw response."""
    from agent.tools import get_mcp_client
    client = get_mcp_client()
    tools = await client.get_tools()
    tool_map = {t.name: t for t in tools}
    if req.tool not in tool_map:
        raise HTTPException(
            status_code=404,
            detail=f"tool {req.tool!r} not found ? available: {sorted(tool_map)}",
        )
    raw = await tool_map[req.tool].ainvoke(req.args)
    return {"tool": req.tool, "args": req.args, "result": _unwrap(raw)}


@app.get("/file-content/{owner}/{repo}")
async def file_content(owner: str, repo: str, path: str, user_id: UUID = Depends(get_current_user)):
    """Return the text content of a file from the cloned repo."""
    import os

    clone = get_clone_path(user_id, owner, repo)
    if not clone:
        raise HTTPException(status_code=404, detail="Repo not indexed")

    # Prevent path traversal
    safe = os.path.normpath(path).lstrip("/")
    if safe.startswith(".."):
        raise HTTPException(status_code=400, detail="Invalid path")

    full = os.path.join(clone, safe)
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Infer language from extension
    ext = os.path.splitext(safe)[1].lstrip(".")
    return {"path": safe, "content": content, "language": ext}


@app.post("/analyze")
async def analyze(req: AnalyzeRequest, user_id: UUID = Depends(get_current_user)):
    from uuid import uuid4 as _uuid4  # noqa: PLC0415
    from agent.sessions import persist_pr_analysis_start, persist_pr_analysis_finalize  # noqa: PLC0415

    # Generate the session_id up front so we can use it for history persistence.
    # If the client passed one (e.g. resuming after a checkpoint), reuse it.
    session_id = req.session_id or str(_uuid4())

    # Persist run start if we have a project to attach it to.
    if req.project_id:
        pr_number: int | None = None
        # Try to extract PR number from common URL patterns.
        try:
            from urllib.parse import urlparse  # noqa: PLC0415
            parts = urlparse(req.pr_url).path.rstrip("/").split("/")
            if "pull" in parts:
                idx = parts.index("pull")
                pr_number = int(parts[idx + 1])
        except (ValueError, IndexError):
            pr_number = None
        persist_pr_analysis_start(
            user_id, session_id, req.project_id, req.pr_url,
            pr_number=pr_number, pr_title=None,
        )

    async def generate():
        from agent.agent import run_agent  # noqa: PLC0415
        final_result: dict | None = None
        error_message: str | None = None
        try:
            async for event in run_agent(
                req.pr_url,
                context=req.context,
                session_id=session_id,
            ):
                # Capture terminal payloads so we can persist them on finalization.
                evt_type = getattr(event, "type", None)
                if evt_type == "result":
                    final_result = event.model_dump() if hasattr(event, "model_dump") else None
                elif evt_type == "error":
                    error_message = getattr(event, "message", "agent emitted error event")
                yield sse_event(event)
        except Exception as e:  # noqa: BLE001
            error_message = error_message or str(e)
            raise
        finally:
            if req.project_id:
                if final_result is not None and not error_message:
                    persist_pr_analysis_finalize(
                        user_id, session_id, status="completed", final_result=final_result,
                    )
                elif error_message:
                    persist_pr_analysis_finalize(
                        user_id, session_id, status="failed", failure_reason=error_message,
                    )

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/analyze/{session_id}/continue")
async def continue_analysis(session_id: str, req: ContinueRequest, user_id: UUID = Depends(get_current_user)):
    from agent.agent import has_analysis_thread  # noqa: PLC0415
    if not has_analysis_thread(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    async def generate():
        from agent.agent import continue_agent  # noqa: PLC0415
        user_response = {"action": req.action}
        if req.additional_context:
            user_response["context"] = req.additional_context
            user_response["feedback"] = req.additional_context
            user_response["choice"] = req.additional_context  # for choice_node
        async for event in continue_agent(session_id, user_response):
            yield sse_event(event)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/analyze/{session_id}/status")
async def analyze_session_status(session_id: str, user_id: UUID = Depends(get_current_user)):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_status_dict()


# ── Sprint 3: bug reproduction + settings + export ───────────────────────────


@app.post("/bug-report")
async def create_bug_report(req: BugReportRequest, user_id: UUID = Depends(get_current_user)):
    from agent.bug_run_registry import persist_bug_run_start, persist_bug_run_finalize  # noqa: PLC0415

    async def generate():
        from agent.bug_agent import run_bug_report  # noqa: PLC0415

        # run_bug_report generates its own session_id internally; capture from the
        # first event that carries one so we can persist with the same id.
        captured_session_id: str | None = None
        persisted_start = False
        final_report: dict | None = None
        severity: str | None = None
        error_message: str | None = None

        try:
            async for event in run_bug_report(
                description=req.description,
                environment=req.environment,
                severity=req.severity,
                repo_url=req.repo_url,
                jira_ticket=req.jira_ticket,
                attachments=req.attachments,
            ):
                # Pluck session_id off any event that exposes it.
                if captured_session_id is None:
                    sid = getattr(event, "session_id", None)
                    if isinstance(sid, str) and sid:
                        captured_session_id = sid
                        if req.project_id and not persisted_start:
                            persist_bug_run_start(user_id, captured_session_id, req.project_id, req.description)
                            persisted_start = True

                evt_type = getattr(event, "type", None)
                if evt_type == "bug_result":
                    final_report = event.model_dump() if hasattr(event, "model_dump") else None
                    try:
                        report = final_report.get("report") if isinstance(final_report, dict) else None
                        if isinstance(report, dict):
                            severity = report.get("severity") or report.get("triage", {}).get("severity")
                    except Exception:  # noqa: BLE001
                        severity = None
                elif evt_type == "error":
                    error_message = getattr(event, "message", "agent emitted error event")

                yield sse_event(event)
        except Exception as e:  # noqa: BLE001
            error_message = error_message or str(e)
            raise
        finally:
            if req.project_id and captured_session_id:
                if final_report is not None and not error_message:
                    persist_bug_run_finalize(
                        user_id, captured_session_id, status="completed",
                        final_report=final_report, severity=severity,
                    )
                elif error_message:
                    persist_bug_run_finalize(
                        user_id, captured_session_id, status="failed", failure_reason=error_message,
                    )

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/bug-report/{session_id}/continue")
async def continue_bug_report_ep(session_id: str, req: BugContinueRequest, user_id: UUID = Depends(get_current_user)):
    async def generate():
        from agent.bug_agent import continue_bug_report  # noqa: PLC0415
        user_response: dict[str, Any] = {"action": req.action}
        if req.feedback:
            user_response["feedback"] = req.feedback
        if req.additional_context:
            user_response["additional_context"] = req.additional_context
            user_response["context"] = req.additional_context
        async for event in continue_bug_report(session_id, user_response):
            yield sse_event(event)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/bug-report/{session_id}/status")
async def bug_report_status(session_id: str, user_id: UUID = Depends(get_current_user)):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.session_type != SessionType.BUG_REPRODUCTION:
        raise HTTPException(status_code=400, detail="Not a bug reproduction session")
    return session.to_status_dict()


@app.post("/bug-report/{session_id}/export")
async def export_bug_report_ep(session_id: str, req: ExportRequest, user_id: UUID = Depends(get_current_user)):
    from models import BugReport  # noqa: PLC0415

    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.session_type != SessionType.BUG_REPRODUCTION:
        raise HTTPException(status_code=400, detail="Not a bug reproduction session")
    if session.bug_report is None:
        raise HTTPException(
            status_code=400, detail="Bug report not ready — complete the pipeline first."
        )
    br = (
        session.bug_report
        if isinstance(session.bug_report, BugReport)
        else BugReport.model_validate(session.bug_report)
    )
    if req.push_to_jira:
        # Jira create/update is implemented in the research/report stages; export stays local.
        pass
    if req.format == "markdown":
        content, filename = export_markdown(br)
        return Response(
            content=content.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    raw, filename = export_pdf(br)
    body = raw if isinstance(raw, (bytes, bytearray)) else bytes(raw)
    return Response(
        content=body,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/settings/integrations")
async def get_integrations(user_id: UUID = Depends(get_current_user)):
    from models import IntegrationStatus  # noqa: PLC0415

    raw = await check_all_integrations()
    return IntegrationSettingsResponse(
        integrations=[IntegrationStatus.model_validate(x) for x in raw]
    )


@app.post("/settings/integrations")
async def update_integration(req: IntegrationConfigRequest, user_id: UUID = Depends(get_current_user)):
    merge_session_credentials(req.name, dict(req.credentials or {}))
    from models import IntegrationStatus  # noqa: PLC0415

    raw = await check_all_integrations()
    return {
        "ok": True,
        "integrations": [IntegrationStatus.model_validate(x) for x in raw],
    }


@app.post("/run-tests")
async def run_tests(_req: RunTestsRequest, user_id: UUID = Depends(get_current_user)):
    raise HTTPException(
        status_code=501,
        detail="Test execution runner is not enabled until Phase 4.",
    )


class UpdateCredentialsBody(BaseModel):
    anthropic_api_key: str | None = None
    github_token: str | None = None
    jira: dict | None = None
    notion: dict | None = None
    confluence: dict | None = None
    grafana: dict | None = None
    kibana: dict | None = None
    postman: dict | None = None


@app.get("/settings/credentials")
async def get_credentials(user_id: UUID = Depends(get_current_user)):
    from credentials import load_credentials  # noqa: PLC0415

    creds = load_credentials(user_id)
    return {
        "has_anthropic_api_key": creds.anthropic_api_key is not None,
        "has_github_token": creds.github_token is not None,
        "integrations": {
            name: getattr(creds, name) is not None
            for name in ("jira", "notion", "confluence", "grafana", "kibana", "postman")
        },
    }


@app.post("/settings/credentials", status_code=204)
async def post_credentials(body: UpdateCredentialsBody, user_id: UUID = Depends(get_current_user)):
    from credentials import save_credentials  # noqa: PLC0415

    updates = body.model_dump(exclude_none=True)
    save_credentials(user_id, **updates)
    return None


@app.get("/projects/{project_id}/pr-analyses")
async def list_pr_analyses(project_id: str, user_id: UUID = Depends(get_current_user)):
    from db import user_scoped  # noqa: PLC0415

    scoped = user_scoped(user_id)
    res = scoped.table("pr_analyses").select("*").eq("project_id", project_id).order("created_at", desc=True).execute()
    return res.data or []


@app.get("/projects/{project_id}/bug-reports")
async def list_bug_reports(project_id: str, user_id: UUID = Depends(get_current_user)):
    from db import user_scoped  # noqa: PLC0415

    scoped = user_scoped(user_id)
    res = scoped.table("bug_reports").select("*").eq("project_id", project_id).order("created_at", desc=True).execute()
    return res.data or []


@app.get("/pr-analyses/{run_id}")
async def get_pr_analysis(run_id: str, user_id: UUID = Depends(get_current_user)):
    from db import user_scoped  # noqa: PLC0415

    scoped = user_scoped(user_id)
    rows = (scoped.table("pr_analyses").select("*").eq("id", run_id).execute().data) or []
    if not rows:
        raise HTTPException(status_code=404, detail="not found")
    return rows[0]


@app.get("/bug-reports/{run_id}")
async def get_bug_report(run_id: str, user_id: UUID = Depends(get_current_user)):
    from db import user_scoped  # noqa: PLC0415

    scoped = user_scoped(user_id)
    rows = (scoped.table("bug_reports").select("*").eq("id", run_id).execute().data) or []
    if not rows:
        raise HTTPException(status_code=404, detail="not found")
    return rows[0]
