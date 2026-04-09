from typing import Literal

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    pr_url: str


class TestSuggestions(BaseModel):
    skip: list[str] = Field(default_factory=list)
    run: list[str] = Field(default_factory=list)
    deeper: list[str] = Field(default_factory=list)


class AffectedComponent(BaseModel):
    component: str
    files_changed: list[str] = Field(default_factory=list)
    impact_summary: str
    risks: list[str] = Field(default_factory=list)
    test_suggestions: TestSuggestions = Field(default_factory=TestSuggestions)
    confidence: Literal["high", "medium", "low"]


class AnalyzeResponse(BaseModel):
    pr_title: str
    pr_url: str
    pr_summary: str
    affected_components: list[AffectedComponent]
    agent_steps: int


# SSE event payloads

class AgentStepEvent(BaseModel):
    type: Literal["agent_step"] = "agent_step"
    tool: str
    summary: str


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


# Index SSE event models

class IndexStepEvent(BaseModel):
    type: Literal["index_step"] = "index_step"
    stage: str  # "clone" | "analyze" | "structure" | "parsing" | "resolution" | "clustering" | "processes" | "search"
    summary: str


class IndexDoneEvent(BaseModel):
    type: Literal["index_done"] = "index_done"
    repo: str  # "owner/repo"
    files: int
    clusters: int
    symbols: int


# Graph / viz models

class GraphNode(BaseModel):
    id: str
    label: str
    type: Literal["file", "cluster"]
    cluster: str


class GraphEdge(BaseModel):
    source: str
    target: str
    type: Literal["CALLS", "IMPORTS"]


class GraphCluster(BaseModel):
    id: str
    label: str
    size: int


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    clusters: list[GraphCluster]


class ResultEvent(AnalyzeResponse):
    type: Literal["result"] = "result"


# Request models

class IndexRequest(BaseModel):
    repo_url: str  # GitHub repo URL, e.g. https://github.com/owner/repo
