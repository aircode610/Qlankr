from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from indexer import get_graph_data, index_repo
from agent.sessions import get_session
from models import (
    AnalyzeRequest,
    ContinueRequest,
    ErrorEvent,
    IndexRequest,
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


@app.post("/run-tests")
async def run_tests(_req: RunTestsRequest):
    raise HTTPException(
        status_code=501,
        detail="Test execution runner is not enabled until Phase 4.",
    )
