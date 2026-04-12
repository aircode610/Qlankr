"""Tests for backend/agent/prompts.py — stage prompt constants."""

import pytest

from agent.prompts import (
    BASE_PROMPT,
    BUDGET_WARNING_MESSAGE,
    E2E_PROMPT,
    GATHER_PROMPT,
    INTEGRATION_PROMPT,
    SYSTEM_PROMPT,
    UNIT_PROMPT,
)
from agent.tools import E2E_TOOLS, GATHER_TOOLS, INTEGRATION_TOOLS, UNIT_TOOLS


# ── All constants exported and non-empty ─────────────────────────────────────

@pytest.mark.parametrize("prompt,name", [
    (BASE_PROMPT, "BASE_PROMPT"),
    (GATHER_PROMPT, "GATHER_PROMPT"),
    (UNIT_PROMPT, "UNIT_PROMPT"),
    (INTEGRATION_PROMPT, "INTEGRATION_PROMPT"),
    (E2E_PROMPT, "E2E_PROMPT"),
])
def test_prompt_is_non_empty_string(prompt, name):
    assert isinstance(prompt, str), f"{name} is not a string"
    assert len(prompt.strip()) > 0, f"{name} is empty"


# ── Backward-compat alias ─────────────────────────────────────────────────────

def test_system_prompt_alias_equals_base_prompt():
    assert SYSTEM_PROMPT is BASE_PROMPT or SYSTEM_PROMPT == BASE_PROMPT


# ── Each stage prompt mentions only its allowed tools ────────────────────────
# We check the negative: tools exclusive to OTHER stages should not appear
# in a given stage's prompt.

def _tools_exclusive_to(own_set: set[str], *other_sets: set[str]) -> set[str]:
    """Return tool names that appear ONLY in own_set, not in any other set."""
    union_of_others = set().union(*other_sets)
    return own_set - union_of_others


def test_gather_prompt_excludes_unit_only_tools():
    # "context" is in UNIT but not in GATHER
    unit_exclusive = _tools_exclusive_to(UNIT_TOOLS, GATHER_TOOLS, INTEGRATION_TOOLS, E2E_TOOLS)
    for tool in unit_exclusive:
        assert tool not in GATHER_PROMPT, (
            f"Tool '{tool}' is exclusive to UNIT_TOOLS but found in GATHER_PROMPT"
        )


def test_unit_prompt_excludes_gather_only_tools():
    gather_exclusive = _tools_exclusive_to(GATHER_TOOLS, UNIT_TOOLS, INTEGRATION_TOOLS, E2E_TOOLS)
    for tool in gather_exclusive:
        assert tool not in UNIT_PROMPT, (
            f"Tool '{tool}' is exclusive to GATHER_TOOLS but found in UNIT_PROMPT"
        )


def test_unit_prompt_excludes_integration_only_tools():
    integration_exclusive = _tools_exclusive_to(INTEGRATION_TOOLS, GATHER_TOOLS, UNIT_TOOLS, E2E_TOOLS)
    for tool in integration_exclusive:
        assert tool not in UNIT_PROMPT, (
            f"Tool '{tool}' is exclusive to INTEGRATION_TOOLS but found in UNIT_PROMPT"
        )


# ── Budget numbers appear in each stage prompt ────────────────────────────────

@pytest.mark.parametrize("prompt,budget,name", [
    (GATHER_PROMPT, "10", "GATHER_PROMPT"),
    (UNIT_PROMPT, "15", "UNIT_PROMPT"),
    (INTEGRATION_PROMPT, "15", "INTEGRATION_PROMPT"),
    (E2E_PROMPT, "20", "E2E_PROMPT"),
])
def test_budget_mentioned_in_stage_prompt(prompt, budget, name):
    assert budget in prompt, f"Budget '{budget}' not found in {name}"


# ── Process tools appear in E2E prompt but not in unit/gather ────────────────

def test_e2e_prompt_mentions_process_tools():
    assert "list_processes" in E2E_PROMPT
    assert "get_process" in E2E_PROMPT


def test_gather_prompt_does_not_mention_list_processes():
    assert "list_processes" not in GATHER_PROMPT


def test_unit_prompt_does_not_mention_process_tools():
    assert "list_processes" not in UNIT_PROMPT
    assert "get_process" not in UNIT_PROMPT


# ── BUDGET_WARNING_MESSAGE has required placeholders ─────────────────────────

def test_budget_warning_has_tool_calls_used_placeholder():
    assert "{tool_calls_used}" in BUDGET_WARNING_MESSAGE


def test_budget_warning_has_budget_placeholder():
    assert "{budget}" in BUDGET_WARNING_MESSAGE
