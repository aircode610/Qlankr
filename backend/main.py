from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from indexer import get_graph_data, index_repo
from models import AnalyzeRequest, ErrorEvent, IndexRequest

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# SSE helpers

def sse_event(data: BaseModel) -> str:
    return f"data: {data.model_dump_json()}\n\n"


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


@app.post("/analyze")
async def analyze(request: AnalyzeRequest):
    # Wired to run_agent() in task A5 once Person B delivers agent/agent.py
    async def generate():
        try:
            from agent.agent import run_agent  # noqa: PLC0415
            async for event in run_agent(request.pr_url):
                yield sse_event(event)
        except ImportError:
            yield sse_event(ErrorEvent(message="Agent not yet implemented"))

    return StreamingResponse(generate(), media_type="text/event-stream")
