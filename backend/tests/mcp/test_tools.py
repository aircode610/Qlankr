"""Tests for backend/agent/tools.py ? filter_tools() and stage tool subsets."""

import pytest
from unittest.mock import MagicMock, patch

from agent.tools import (
    E2E_TOOLS,
    GATHER_TOOLS,
    INTEGRATION_TOOLS,
    UNIT_TOOLS,
    filter_tools,
    get_mcp_client,
    make_process_tools,
)

# Known GitNexus tool names per the DEV-B spec (excludes GitHub tools and
# process resource wrappers which are created by make_process_tools).
_GITNEXUS_TOOLS = {
    "query", "context", "impact", "detect_changes", "rename", "cypher",
    "list_repos", "group_list", "group_sync", "group_contracts",
    "group_query", "group_status",
}


def make_tool(name: str):
    t = MagicMock()
    t.name = name
    return t


def make_tool_list(*names: str):
    return [make_tool(n) for n in names]


# ── filter_tools per stage ────────────────────────────────────────────────────

def test_filter_tools_gather():
    all_tools = make_tool_list("get_pull_request", "cypher", "context", "impact", "submit_analysis")
    result = filter_tools(all_tools, "gather")
    names = {t.name for t in result}
    assert "get_pull_request" in names
    assert "cypher" in names
    assert "context" not in names    # not in GATHER_TOOLS
    assert "impact" not in names     # not in GATHER_TOOLS
    assert "submit_analysis" not in names


def test_filter_tools_unit():
    all_tools = make_tool_list("context", "cypher", "get_file_contents", "impact", "query")
    result = filter_tools(all_tools, "unit")
    names = {t.name for t in result}
    assert names == {"context", "cypher", "get_file_contents"}


def test_filter_tools_integration():
    all_tools = make_tool_list("impact", "context", "query", "cypher", "get_pull_request")
    result = filter_tools(all_tools, "integration")
    names = {t.name for t in result}
    assert names == {"impact", "context", "query", "cypher"}


def test_filter_tools_e2e():
    all_tools = make_tool_list(
        "impact", "query", "cypher", "list_processes", "get_process",
        "context", "get_pull_request",
    )
    result = filter_tools(all_tools, "e2e")
    names = {t.name for t in result}
    assert names == {"impact", "query", "cypher", "list_processes", "get_process"}


def test_filter_tools_returns_empty_when_no_match():
    all_tools = make_tool_list("submit_analysis", "unknown_tool")
    result = filter_tools(all_tools, "unit")
    assert result == []


def test_filter_tools_preserves_order():
    names = ["cypher", "context", "get_file_contents"]
    all_tools = make_tool_list(*names)
    result = filter_tools(all_tools, "unit")
    assert [t.name for t in result] == names


# ── No disallowed tools leak into any stage ───────────────────────────────────

@pytest.mark.parametrize("stage_tools", [GATHER_TOOLS, UNIT_TOOLS, INTEGRATION_TOOLS, E2E_TOOLS])
def test_submit_analysis_not_in_any_stage(stage_tools):
    assert "submit_analysis" not in stage_tools


# ── Unknown stage raises KeyError ─────────────────────────────────────────────

def test_unknown_stage_raises():
    with pytest.raises(KeyError):
        filter_tools([], "bad_stage")


# ── Stage sets are non-empty ──────────────────────────────────────────────────

@pytest.mark.parametrize("stage,tool_set", [
    ("gather", GATHER_TOOLS),
    ("unit", UNIT_TOOLS),
    ("integration", INTEGRATION_TOOLS),
    ("e2e", E2E_TOOLS),
])
def test_stage_sets_non_empty(stage, tool_set):
    assert len(tool_set) > 0


# ── E2E stage includes process tools ─────────────────────────────────────────

def test_e2e_includes_process_tools():
    assert "list_processes" in E2E_TOOLS
    assert "get_process" in E2E_TOOLS


# ── get_mcp_client() server config ───────────────────────────────────────────

def test_get_mcp_client_configures_both_servers():
    with patch("agent.tools.MultiServerMCPClient") as mock_cls, \
         patch("agent.tools.shutil.which", return_value="/usr/local/bin/gitnexus"):
        mock_cls.return_value = MagicMock()
        get_mcp_client()
        config = mock_cls.call_args[0][0]
        assert "github" in config, "GitHub server missing from MCP client config"
        assert "gitnexus" in config, "GitNexus server missing from MCP client config"


def test_get_mcp_client_github_server_config():
    with patch("agent.tools.MultiServerMCPClient") as mock_cls:
        mock_cls.return_value = MagicMock()
        get_mcp_client()
        config = mock_cls.call_args[0][0]["github"]
        assert config["transport"] == "stdio"
        assert config["command"] == "npx"
        assert "@modelcontextprotocol/server-github" in config["args"]


def test_get_mcp_client_gitnexus_server_config():
    with patch("agent.tools.MultiServerMCPClient") as mock_cls, \
         patch("agent.tools.shutil.which", return_value="/usr/local/bin/gitnexus"):
        mock_cls.return_value = MagicMock()
        get_mcp_client()
        config = mock_cls.call_args[0][0]["gitnexus"]
        assert config["transport"] == "stdio"
        assert config["command"] == "gitnexus"
        assert "mcp" in config["args"]


def test_get_mcp_client_skips_gitnexus_when_not_installed():
    with patch("agent.tools.MultiServerMCPClient") as mock_cls, \
         patch("agent.tools.shutil.which", return_value=None):
        mock_cls.return_value = MagicMock()
        get_mcp_client()
        config = mock_cls.call_args[0][0]
        assert "github" in config
        assert "gitnexus" not in config


# ── make_process_tools() ──────────────────────────────────────────────────────

def test_make_process_tools_returns_two_tools():
    tools = make_process_tools("minetest")
    assert len(tools) == 2


def test_make_process_tools_names():
    tools = make_process_tools("minetest")
    names = {t.name for t in tools}
    assert names == {"list_processes", "get_process"}


def test_make_process_tools_have_descriptions():
    tools = make_process_tools("minetest")
    for tool in tools:
        assert tool.description and len(tool.description.strip()) > 0


def test_make_process_tools_are_callable():
    """Tools must be StructuredTool instances with a coroutine."""
    tools = make_process_tools("minetest")
    for tool in tools:
        assert callable(tool.func) or tool.coroutine is not None


# ── GitNexus tool coverage ────────────────────────────────────────────────────
# Verifies that the stage subsets collectively reference all known GitNexus
# tools. Full "16 tools returned by client.get_tools()" requires a live
# gitnexus MCP server and is covered by manual / integration testing.

def test_all_gitnexus_tools_referenced_across_stages():
    all_stage_tools = GATHER_TOOLS | UNIT_TOOLS | INTEGRATION_TOOLS | E2E_TOOLS
    missing = _GITNEXUS_TOOLS - all_stage_tools
    # Tools that are available but intentionally unused in any stage
    # (future multi-repo support, rarely used rename)
    intentionally_unused = {"rename", "group_list", "group_sync", "group_contracts", "group_query", "group_status"}
    missing -= intentionally_unused
    assert not missing, f"GitNexus tools not referenced in any stage subset: {missing}"
