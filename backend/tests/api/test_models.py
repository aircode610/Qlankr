import pytest
from pydantic import ValidationError

from models import (
    AffectedComponent,
    AnalyzeRequest,
    AnalyzeResponse,
    ContinueRequest,
    E2ETestPlan,
    E2ETestStep,
    ErrorEvent,
    GraphEdge,
    GraphNode,
    IndexRequest,
    IntegrationTestCase,
    IntegrationTestSpec,
    ResultEvent,
    UnitTestCase,
    UnitTestSpec,
)


def test_index_request_requires_repo_url():
    with pytest.raises(ValidationError):
        IndexRequest()


def test_analyze_request_requires_pr_url():
    with pytest.raises(ValidationError):
        AnalyzeRequest()


def test_analyze_request_optional_context_and_session():
    r = AnalyzeRequest(
        pr_url="https://github.com/o/r/pull/1",
        context="crash on login",
        session_id="abc123",
    )
    assert r.context == "crash on login"
    assert r.session_id == "abc123"


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
            confidence="very high",
        )


def test_affected_component_confidence_literal_accepts_valid():
    for val in ("high", "medium", "low"):
        comp = AffectedComponent(
            component="X",
            files_changed=[],
            impact_summary="x",
            risks=[],
            confidence=val,
        )
        assert comp.confidence == val


def test_affected_component_backward_compat_empty_test_lists():
    c = AffectedComponent(
        component="Auth",
        impact_summary="login touched",
        confidence="high",
    )
    assert c.unit_tests == []
    assert c.integration_tests == []


def test_unit_test_spec_defaults():
    spec = UnitTestSpec(
        target="Foo.bar",
        test_cases=[
            UnitTestCase(name="n", scenario="s", expected="e"),
        ],
        priority="high",
    )
    assert spec.mocks_needed == []
    assert spec.generated_code is None


def test_integration_test_spec_risk_level_literal():
    with pytest.raises(ValidationError):
        IntegrationTestSpec(
            integration_point="a <> b",
            modules_involved=["a"],
            test_cases=[],
            data_setup="d",
            risk_level="tiny",
        )


def test_integration_test_spec_valid_risk():
    spec = IntegrationTestSpec(
        integration_point="a <> b",
        modules_involved=["a", "b"],
        test_cases=[
            IntegrationTestCase(name="n", scenario="s", expected="e"),
        ],
        data_setup="seed db",
        risk_level="HIGH",
    )
    assert spec.risk_level == "HIGH"


def test_e2e_test_plan_step_list_ordering_preserved():
    plan = E2ETestPlan(
        process="p1",
        scenario="s",
        steps=[
            E2ETestStep(step=2, action="b", expected="y"),
            E2ETestStep(step=1, action="a", expected="x"),
        ],
        preconditions="none",
        priority="LOW",
        estimated_duration="1 min",
    )
    assert [s.step for s in plan.steps] == [2, 1]


def test_continue_request_action_literal():
    with pytest.raises(ValidationError):
        ContinueRequest.model_validate({"action": "nope"})


def test_continue_request_valid_actions():
    for a in ("approve", "add_context", "skip", "rerun"):
        r = ContinueRequest(action=a)
        assert r.action == a


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
    assert r.e2e_test_plans == []


def test_analyze_response_serialization_roundtrip():
    body = AnalyzeResponse(
        pr_title="t",
        pr_url="u",
        pr_summary="s",
        affected_components=[
            AffectedComponent(
                component="c",
                impact_summary="i",
                confidence="low",
                unit_tests=[
                    UnitTestSpec(
                        target="T.m",
                        test_cases=[
                            UnitTestCase(name="n", scenario="sc", expected="ex"),
                        ],
                        priority="medium",
                    )
                ],
            )
        ],
        agent_steps=1,
    ).model_dump_json()
    parsed = AnalyzeResponse.model_validate_json(body)
    assert len(parsed.affected_components[0].unit_tests) == 1
