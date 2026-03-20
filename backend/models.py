from typing import Literal
from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    pr_url: str


class TestSuggestions(BaseModel):
    skip: list[str]
    run: list[str]
    deeper: list[str]


class AffectedComponent(BaseModel):
    component: str
    files_changed: list[str]
    impact_summary: str
    risks: list[str]
    test_suggestions: TestSuggestions
    confidence: Literal["high", "medium", "low"]


class AnalyzeResponse(BaseModel):
    pr_title: str
    pr_url: str
    pr_summary: str
    affected_components: list[AffectedComponent]
    agent_steps: int


# SSE event payloads

class AgentStepEvent(BaseModel):
    tool: str
    summary: str


class ErrorEvent(BaseModel):
    message: str
