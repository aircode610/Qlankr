"""
Entrypoint for LangGraph Studio.

Exports compiled graph instances that langgraph dev can discover
via the langgraph.json "graphs" config.

LangGraph Studio provides its own checkpointer, so we compile
WITHOUT MemorySaver here (unlike the runtime build_*_graph functions).
"""

from langgraph.graph import END, StateGraph

from agent.agent import (
    AnalysisState,
    _checkpoint_router,
    _choice_router,
    checkpoint_node,
    choice_node,
    e2e_checkpoint_node,
    e2e_planning_node,
    gather_node,
    integration_tests_node,
    submit_node,
    unit_tests_node,
)
from agent.bug_agent import (
    _checkpoint_mechanics_node,
    _checkpoint_research_node,
    _mechanics_node,
    _mechanics_router,
    _report_node,
    _reproduction_node,
    _research_node,
    _research_router,
    _triage_node,
)
from agent.agent import BugReproductionState


def _build_impact_for_studio():
    graph = StateGraph(AnalysisState)
    graph.add_node("gather", gather_node)
    graph.add_node("unit_tests", unit_tests_node)
    graph.add_node("checkpoint_unit", checkpoint_node)
    graph.add_node("choice", choice_node)
    graph.add_node("integration_tests", integration_tests_node)
    graph.add_node("e2e_checkpoint", e2e_checkpoint_node)
    graph.add_node("e2e_planning", e2e_planning_node)
    graph.add_node("submit", submit_node)

    graph.set_entry_point("gather")
    graph.add_edge("gather", "unit_tests")
    graph.add_edge("unit_tests", "checkpoint_unit")
    graph.add_conditional_edges(
        "checkpoint_unit",
        _checkpoint_router,
        {"unit_tests": "unit_tests", "choice": "choice"},
    )
    graph.add_conditional_edges(
        "choice",
        _choice_router,
        {"integration_tests": "integration_tests", "e2e_checkpoint": "e2e_checkpoint"},
    )
    graph.add_edge("e2e_checkpoint", "e2e_planning")
    graph.add_edge("integration_tests", "submit")
    graph.add_edge("e2e_planning", "submit")
    graph.add_edge("submit", END)

    return graph.compile()  # no checkpointer — Studio provides one


def _build_bug_for_studio():
    graph = StateGraph(BugReproductionState)
    graph.add_node("triage", _triage_node)
    graph.add_node("mechanics_analysis", _mechanics_node)
    graph.add_node("checkpoint_mechanics", _checkpoint_mechanics_node)
    graph.add_node("reproduction_planning", _reproduction_node)
    graph.add_node("research", _research_node)
    graph.add_node("checkpoint_research", _checkpoint_research_node)
    graph.add_node("report_generation", _report_node)

    graph.set_entry_point("triage")
    graph.add_edge("triage", "mechanics_analysis")
    graph.add_edge("mechanics_analysis", "checkpoint_mechanics")
    graph.add_conditional_edges(
        "checkpoint_mechanics",
        _mechanics_router,
        {"mechanics_analysis": "mechanics_analysis", "reproduction_planning": "reproduction_planning"},
    )
    graph.add_edge("reproduction_planning", "research")
    graph.add_edge("research", "checkpoint_research")
    graph.add_conditional_edges(
        "checkpoint_research",
        _research_router,
        {"research": "research", "report_generation": "report_generation"},
    )
    graph.add_edge("report_generation", END)

    return graph.compile()  # no checkpointer — Studio provides one


impact_analysis_graph = _build_impact_for_studio()
bug_reproduction_graph = _build_bug_for_studio()
