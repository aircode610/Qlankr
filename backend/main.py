from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from export import export_markdown, export_pdf
from indexer import get_clone_path, get_graph_data, index_repo
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

app = FastAPI()

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
async def index(request: IndexRequest):
    return StreamingResponse(
        stream_response(index_repo(request.repo_url)),
        media_type="text/event-stream",
    )


@app.get("/graph/{owner}/{repo}")
async def graph(owner: str, repo: str):
    return await get_graph_data(owner, repo)


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
async def debug_mcp_tools():
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
async def debug_mcp_repos():
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
async def debug_mcp_call(req: _DebugCallRequest):
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
async def file_content(owner: str, repo: str, path: str):
    """Return the text content of a file from the cloned repo."""
    import os

    repo_key = f"{owner}/{repo}"
    clone = get_clone_path(repo_key)
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
async def analyze(req: AnalyzeRequest):
    async def generate():
        from agent.agent import run_agent  # noqa: PLC0415
        async for event in run_agent(
            req.pr_url,
            context=req.context,
            session_id=req.session_id,
        ):
            yield sse_event(event)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/analyze/{session_id}/continue")
async def continue_analysis(session_id: str, req: ContinueRequest):
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
async def analyze_session_status(session_id: str):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_status_dict()


# ── Sprint 3: bug reproduction + settings + export ───────────────────────────


@app.post("/bug-report")
async def create_bug_report(req: BugReportRequest):
    async def generate():
        from agent.bug_agent import run_bug_report  # noqa: PLC0415
        async for event in run_bug_report(
            description=req.description,
            environment=req.environment,
            severity=req.severity,
            repo_url=req.repo_url,
            jira_ticket=req.jira_ticket,
            attachments=req.attachments,
        ):
            yield sse_event(event)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/bug-report/{session_id}/continue")
async def continue_bug_report_ep(session_id: str, req: BugContinueRequest):
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
async def bug_report_status(session_id: str):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.session_type != SessionType.BUG_REPRODUCTION:
        raise HTTPException(status_code=400, detail="Not a bug reproduction session")
    return session.to_status_dict()


@app.post("/bug-report/{session_id}/export")
async def export_bug_report_ep(session_id: str, req: ExportRequest):
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
async def get_integrations():
    from models import IntegrationStatus  # noqa: PLC0415

    raw = await check_all_integrations()
    return IntegrationSettingsResponse(
        integrations=[IntegrationStatus.model_validate(x) for x in raw]
    )


@app.post("/settings/integrations")
async def update_integration(req: IntegrationConfigRequest):
    merge_session_credentials(req.name, dict(req.credentials or {}))
    from models import IntegrationStatus  # noqa: PLC0415

    raw = await check_all_integrations()
    return {
        "ok": True,
        "integrations": [IntegrationStatus.model_validate(x) for x in raw],
    }


@app.post("/run-tests")
async def run_tests(_req: RunTestsRequest):
    raise HTTPException(
        status_code=501,
        detail="Test execution runner is not enabled until Phase 4.",
    )
