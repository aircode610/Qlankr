import pytest
from pydantic import ValidationError

from models import (
    AffectedComponent,
    AnalyzeRequest,
    AnalyzeResponse,
    ErrorEvent,
    GraphEdge,
    GraphNode,
    IndexRequest,
    ResultEvent,
    TestSuggestions,
)


def test_index_request_requires_repo_url():
    with pytest.raises(ValidationError):
        IndexRequest()


def test_analyze_request_requires_pr_url():
    with pytest.raises(ValidationError):
        AnalyzeRequest()


def test_graph_node_type_literal_rejects_unknown():
    with pytest.raises(ValidationError):
        GraphNode(id="x", label="x", type="unknown", cluster="c")


def test_graph_node_type_literal_accepts_file():
    node = GraphNode(id="x", label="x", type="file", cluster="c")
    assert node.type == "file"


def test_graph_node_type_literal_accepts_cluster():
    node = GraphNode(id="x", label="x", type="cluster", cluster="c")
    assert node.type == "cluster"


def test_graph_edge_type_literal_rejects_contains():
    # CONTAINS is used in the frontend mock but is NOT valid on the backend
    with pytest.raises(ValidationError):
        GraphEdge(source="a", target="b", type="CONTAINS")


def test_graph_edge_type_literal_accepts_calls():
    edge = GraphEdge(source="a", target="b", type="CALLS")
    assert edge.type == "CALLS"


def test_graph_edge_type_literal_accepts_imports():
    edge = GraphEdge(source="a", target="b", type="IMPORTS")
    assert edge.type == "IMPORTS"


def test_affected_component_confidence_literal_rejects_invalid():
    with pytest.raises(ValidationError):
        AffectedComponent(
            component="X",
            files_changed=[],
            impact_summary="x",
            risks=[],
            test_suggestions=TestSuggestions(skip=[], run=[], deeper=[]),
            confidence="very high",
        )


def test_affected_component_confidence_literal_accepts_valid():
    for val in ("high", "medium", "low"):
        comp = AffectedComponent(
            component="X",
            files_changed=[],
            impact_summary="x",
            risks=[],
            test_suggestions=TestSuggestions(skip=[], run=[], deeper=[]),
            confidence=val,
        )
        assert comp.confidence == val


def test_error_event_type_default():
    e = ErrorEvent(message="oops")
    assert e.type == "error"


def test_result_event_inherits_analyze_response():
    r = ResultEvent(
        pr_title="t",
        pr_url="u",
        pr_summary="s",
        affected_components=[],
        agent_steps=3,
    )
    assert r.type == "result"
    assert r.pr_title == "t"
    assert r.agent_steps == 3
