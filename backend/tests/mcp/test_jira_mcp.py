"""Tests for Jira MCP integration in backend/agent/tools.py"""

import os
import pytest
from unittest.mock import MagicMock, patch, AsyncMock, call
from langchain_core.messages import AIMessage, ToolMessage

from agent.tools import (
    JIRA_TOOL_ALIASES,
    BUG_TRIAGE_TOOLS,
    BUG_RESEARCH_TOOLS,
    BUG_REPORT_TOOLS,
    _normalize_tool_names,
    _server_config,
    safe_tools,
    make_messages_modifier,
    fix_dangling_tool_calls,
)


# ── Jira Tool Aliases ────────────────────────────────────────────────────────

def test_jira_tool_aliases_complete():
    """Verify all expected Jira tool aliases are defined."""
    expected_aliases = {
        "search_issues": "jira_search",
        "get_issue": "jira_get_issue",
        "create_issue": "jira_create_issue",
        "update_issue": "jira_update_issue",
        "get_comments": "jira_get_comments",
    }
    assert JIRA_TOOL_ALIASES == expected_aliases


def test_jira_tool_aliases_map_to_canonical_names():
    """Verify alias values use jira_* canonical prefix."""
    for old_name, canonical in JIRA_TOOL_ALIASES.items():
        assert canonical.startswith("jira_"), f"{old_name} maps to {canonical} without jira_ prefix"


# ── Tool Name Normalization ──────────────────────────────────────────────────

def make_mock_tool(name: str, has_model_copy: bool = False):
    """Create a mock tool with name and optional model_copy method."""
    tool = MagicMock()
    tool.name = name
    if has_model_copy:
        tool.model_copy = MagicMock(return_value=MagicMock(name=name))
    return tool


def test_normalize_tool_names_maps_aliases():
    """_normalize_tool_names should map aliased names to canonical jira_* names."""
    tools = [
        make_mock_tool("search_issues"),
        make_mock_tool("get_issue"),
        make_mock_tool("create_issue"),
        make_mock_tool("update_issue"),
        make_mock_tool("get_comments"),
    ]

    result = _normalize_tool_names(tools)
    names = [t.name for t in result]

    assert "jira_search" in names
    assert "jira_get_issue" in names
    assert "jira_create_issue" in names
    assert "jira_update_issue" in names
    assert "jira_get_comments" in names
    assert "search_issues" not in names
    assert "get_issue" not in names


def test_normalize_tool_names_preserves_non_aliased_tools():
    """Non-aliased tool names should pass through unchanged."""
    tools = [
        make_mock_tool("cypher"),
        make_mock_tool("search_issues"),
        make_mock_tool("context"),
    ]

    result = _normalize_tool_names(tools)
    names = [t.name for t in result]

    assert "cypher" in names
    assert "context" in names
    assert "jira_search" in names
    assert "search_issues" not in names


def test_normalize_tool_names_uses_model_copy():
    """Should use model_copy if available to create new instance."""
    tool = make_mock_tool("search_issues", has_model_copy=True)
    tool.model_copy.return_value = MagicMock(name="jira_search")

    result = _normalize_tool_names([tool])

    assert result[0].name == "jira_search"
    tool.model_copy.assert_called_once()


def test_normalize_tool_names_fallback_direct_assignment():
    """Should fallback to direct assignment if model_copy fails."""
    tool = MagicMock()
    tool.name = "search_issues"
    tool.model_copy = MagicMock(side_effect=Exception("copy failed"))

    result = _normalize_tool_names([tool])

    # Should still be renamed despite model_copy failure
    assert result[0].name == "jira_search"


def test_normalize_tool_names_preserves_tool_order():
    """Tool order should be preserved after normalization."""
    tools = [
        make_mock_tool("cypher"),
        make_mock_tool("search_issues"),
        make_mock_tool("get_issue"),
        make_mock_tool("impact"),
    ]

    result = _normalize_tool_names(tools)
    names = [t.name for t in result]

    # Check relative order of tools
    cypher_idx = names.index("cypher")
    jira_search_idx = names.index("jira_search")
    impact_idx = names.index("impact")
    assert cypher_idx < jira_search_idx < impact_idx


# ── Jira Server Configuration ────────────────────────────────────────────────

def test_server_config_includes_github():
    """GitHub server should always be configured."""
    config = _server_config()
    assert "github" in config
    assert config["github"]["command"] == "npx"
    assert "@modelcontextprotocol/server-github" in config["github"]["args"]


def test_server_config_jira_when_credentials_present():
    """Jira server should be configured when JIRA_URL and JIRA_API_TOKEN are set."""
    with patch.dict(os.environ, {
        "JIRA_URL": "https://example.atlassian.net",
        "JIRA_EMAIL": "user@example.com",
        "JIRA_API_TOKEN": "secret_token",
    }):
        config = _server_config()
        assert "jira" in config
        assert config["jira"]["command"] == "npx"
        assert "@modelcontextprotocol/server-atlassian" in config["jira"]["args"]


def test_server_config_jira_requires_url_and_token():
    """Jira server should be skipped if URL or API token is missing."""
    # Missing JIRA_API_TOKEN
    with patch.dict(os.environ, {"JIRA_URL": "https://example.atlassian.net"}, clear=False):
        # Make sure JIRA_API_TOKEN is not set
        with patch.dict(os.environ, {}, clear=True):
            config = _server_config()
            assert "jira" not in config


def test_server_config_jira_env_vars():
    """Jira server config should include credentials from environment."""
    jira_url = "https://example.atlassian.net"
    jira_email = "user@example.com"
    jira_token = "my_token_123"

    with patch.dict(os.environ, {
        "JIRA_URL": jira_url,
        "JIRA_EMAIL": jira_email,
        "JIRA_API_TOKEN": jira_token,
    }):
        config = _server_config()
        assert config["jira"]["env"]["JIRA_URL"] == jira_url
        assert config["jira"]["env"]["JIRA_EMAIL"] == jira_email
        assert config["jira"]["env"]["JIRA_API_TOKEN"] == jira_token


def test_server_config_jira_env_vars_defaults():
    """JIRA_EMAIL should default to empty string if not provided."""
    with patch.dict(os.environ, {
        "JIRA_URL": "https://example.atlassian.net",
        "JIRA_API_TOKEN": "token",
    }, clear=True):
        config = _server_config()
        assert config["jira"]["env"]["JIRA_EMAIL"] == ""


def test_server_config_github_env_vars():
    """GitHub config should use GITHUB_TOKEN from environment."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_token_123"}):
        config = _server_config()
        assert config["github"]["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] == "ghp_token_123"


def test_server_config_github_token_defaults_to_empty():
    """GITHUB_TOKEN should default to empty string if not set."""
    with patch.dict(os.environ, {}, clear=True):
        config = _server_config()
        assert config["github"]["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] == ""


def test_server_config_includes_utf8_settings():
    """Server config should include UTF-8 encoding settings."""
    config = _server_config()
    for server_name in ["github"]:
        env = config[server_name]["env"]
        assert env.get("PYTHONUTF8") == "1"
        assert env.get("PYTHONIOENCODING") == "utf-8"
        assert env.get("LANG") == "en_US.UTF-8"
        assert env.get("LC_ALL") == "en_US.UTF-8"


def test_server_config_gitnexus_when_available():
    """GitNexus should be configured when binary is available."""
    with patch("agent.tools.shutil.which", return_value="/usr/local/bin/gitnexus"):
        config = _server_config()
        assert "gitnexus" in config


def test_server_config_no_gitnexus_when_unavailable():
    """GitNexus should not be configured when binary is not available."""
    with patch("agent.tools.shutil.which", return_value=None):
        config = _server_config()
        assert "gitnexus" not in config


# ── Jira Tool Sets ──────────────────────────────────────────────────────────

def test_bug_triage_tools_includes_jira_tools():
    """BUG_TRIAGE_TOOLS should include Jira tools."""
    assert "jira_search" in BUG_TRIAGE_TOOLS
    assert "jira_get_issue" in BUG_TRIAGE_TOOLS
    assert "jira_get_comments" in BUG_TRIAGE_TOOLS


def test_bug_research_tools_includes_jira_tools():
    """BUG_RESEARCH_TOOLS should include Jira search and fetch tools."""
    assert "jira_search" in BUG_RESEARCH_TOOLS
    assert "jira_get_issue" in BUG_RESEARCH_TOOLS
    assert "jira_get_comments" in BUG_RESEARCH_TOOLS


def test_bug_report_tools_includes_jira_create_update():
    """BUG_REPORT_TOOLS should include Jira create/update tools."""
    assert "jira_create_issue" in BUG_REPORT_TOOLS
    assert "jira_update_issue" in BUG_REPORT_TOOLS


def test_bug_report_tools_excludes_read_tools():
    """BUG_REPORT_TOOLS should not include read-only Jira tools."""
    assert "jira_search" not in BUG_REPORT_TOOLS
    assert "jira_get_issue" not in BUG_REPORT_TOOLS
    assert "jira_get_comments" not in BUG_REPORT_TOOLS


# ── Safe Tools ────────────────────────────────────────────────────────────────

def test_safe_tools_wraps_coroutine():
    """safe_tools should wrap tool coroutines."""
    original_coro = AsyncMock(return_value="result")
    tool = MagicMock()
    tool.coroutine = original_coro
    tool.copy = MagicMock(return_value=MagicMock())
    tool.response_format = None

    result = safe_tools([tool])
    assert len(result) == 1
    tool.copy.assert_called_once()


def test_safe_tools_catches_exceptions_plain():
    """safe_tools should catch exceptions and return error message."""
    import asyncio

    async def run_test():
        original_coro = AsyncMock(side_effect=ValueError("Tool failed"))
        tool = MagicMock()
        tool.coroutine = original_coro
        tool.response_format = None

        wrapped_tool = MagicMock()
        wrapped_tool.coroutine = None
        tool.copy = MagicMock(return_value=wrapped_tool)

        safe_tools([tool])

        # Extract the wrapped coroutine from the copy call
        call_kwargs = tool.copy.call_args[1]
        wrapped_coro = call_kwargs["coroutine"]

        result = await wrapped_coro()
        assert "Tool error:" in result
        assert "Tool failed" in result

    asyncio.run(run_test())


def test_safe_tools_catches_exceptions_artifact():
    """safe_tools should return (msg, None) tuple for artifact tools on error."""
    import asyncio

    async def run_test():
        original_coro = AsyncMock(side_effect=RuntimeError("MCP error"))
        tool = MagicMock()
        tool.coroutine = original_coro
        tool.response_format = "content_and_artifact"

        wrapped_tool = MagicMock()
        wrapped_tool.coroutine = None
        tool.copy = MagicMock(return_value=wrapped_tool)

        safe_tools([tool])

        call_kwargs = tool.copy.call_args[1]
        wrapped_coro = call_kwargs["coroutine"]

        result = await wrapped_coro()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert "Tool error:" in result[0]
        assert result[1] is None

    asyncio.run(run_test())


def test_safe_tools_passes_through_success():
    """safe_tools should pass through successful results."""
    import asyncio

    async def run_test():
        original_coro = AsyncMock(return_value="success_result")
        tool = MagicMock()
        tool.coroutine = original_coro
        tool.response_format = None

        wrapped_tool = MagicMock()
        wrapped_tool.coroutine = None
        tool.copy = MagicMock(return_value=wrapped_tool)

        safe_tools([tool])

        call_kwargs = tool.copy.call_args[1]
        wrapped_coro = call_kwargs["coroutine"]

        result = await wrapped_coro()
        assert result == "success_result"

    asyncio.run(run_test())


def test_safe_tools_skips_non_coroutines():
    """safe_tools should skip tools without coroutines."""
    tool = MagicMock()
    tool.coroutine = None

    result = safe_tools([tool])
    assert len(result) == 1
    assert result[0] == tool


# ── Messages Modifier ────────────────────────────────────────────────────────

def test_make_messages_modifier_creates_hook():
    """make_messages_modifier should return a callable hook."""
    hook = make_messages_modifier()
    assert callable(hook)


def test_messages_modifier_truncates_long_content():
    """Modifier should truncate ToolMessage content exceeding max_chars."""
    hook = make_messages_modifier(max_chars=20)
    msg = ToolMessage(
        content="This is a very long message that exceeds the limit",
        tool_call_id="call_1",
    )
    state = {"messages": [msg]}

    result = hook(state)

    assert "messages" in result
    assert len(result["messages"]) == 1
    assert len(result["messages"][0].content) <= 20 + 50  # 20 chars + truncation message
    assert "truncated" in result["messages"][0].content


def test_messages_modifier_passes_short_content():
    """Modifier should not truncate content under max_chars."""
    hook = make_messages_modifier(max_chars=100)
    msg = ToolMessage(content="short", tool_call_id="call_1")
    state = {"messages": [msg]}

    result = hook(state)

    assert result == {}  # No changes
    assert msg.content == "short"


def test_messages_modifier_preserves_non_tool_messages():
    """Modifier should leave non-ToolMessages unchanged."""
    hook = make_messages_modifier(max_chars=10)
    ai_msg = AIMessage(content="AI response")
    state = {"messages": [ai_msg]}

    result = hook(state)

    assert result == {}


def test_messages_modifier_handles_list_content():
    """Modifier should handle ToolMessage with list content (blocks)."""
    hook = make_messages_modifier(max_chars=20)
    msg = ToolMessage(
        content=[
            {"type": "text", "text": "This is a very long text block"},
        ],
        tool_call_id="call_1",
    )
    state = {"messages": [msg]}

    result = hook(state)

    assert "messages" in result
    content_blocks = result["messages"][0].content
    assert isinstance(content_blocks, list)
    assert "truncated" in content_blocks[0]["text"]


def test_messages_modifier_handles_mixed_blocks():
    """Modifier should handle mixed block types in list content."""
    hook = make_messages_modifier(max_chars=10)
    msg = ToolMessage(
        content=[
            {"type": "text", "text": "short"},
            {"type": "text", "text": "this is definitely longer than ten chars"},
            {"type": "other", "value": "ignored"},
        ],
        tool_call_id="call_1",
    )
    state = {"messages": [msg]}

    result = hook(state)

    assert "messages" in result
    blocks = result["messages"][0].content
    assert blocks[0]["text"] == "short"  # Unchanged
    assert "truncated" in blocks[1]["text"]  # Truncated


# ── Dangling Tool Calls ──────────────────────────────────────────────────────

def test_fix_dangling_tool_calls_adds_missing_responses():
    """Should add ToolMessages for unmatched tool_call_ids."""
    messages = [
        AIMessage(
            content="Calling tools",
            tool_calls=[
                {"id": "call_1", "function": {"name": "tool_a", "arguments": "{}"}},
                {"id": "call_2", "function": {"name": "tool_b", "arguments": "{}"}},
            ]
        ),
        ToolMessage(content="result_1", tool_call_id="call_1"),
    ]

    result = fix_dangling_tool_calls(messages)

    assert len(result) == 4  # AI msg, 2 original ToolMessages + 1 synthetic
    assert result[-1].tool_call_id == "call_2"
    assert "Interrupted" in result[-1].content


def test_fix_dangling_tool_calls_preserves_matched():
    """Should not add messages for matched tool_call_ids."""
    messages = [
        AIMessage(
            content="Calling tools",
            tool_calls=[
                {"id": "call_1", "function": {"name": "tool_a", "arguments": "{}"}},
            ]
        ),
        ToolMessage(content="result", tool_call_id="call_1"),
    ]

    result = fix_dangling_tool_calls(messages)

    assert len(result) == 2  # Unchanged


def test_fix_dangling_tool_calls_no_tool_calls():
    """Should handle AIMessages without tool_calls."""
    messages = [AIMessage(content="No tools called")]

    result = fix_dangling_tool_calls(messages)

    assert len(result) == 1
    assert result[0] == messages[0]


def test_fix_dangling_tool_calls_multiple_ais():
    """Should handle multiple AIMessages with tool calls."""
    messages = [
        AIMessage(
            content="First call",
            tool_calls=[{"id": "call_1", "function": {"name": "tool_a", "arguments": "{}"}}]
        ),
        ToolMessage(content="result_1", tool_call_id="call_1"),
        AIMessage(
            content="Second call",
            tool_calls=[
                {"id": "call_2", "function": {"name": "tool_b", "arguments": "{}"}},
                {"id": "call_3", "function": {"name": "tool_c", "arguments": "{}"}},
            ]
        ),
    ]

    result = fix_dangling_tool_calls(messages)

    # Should add 2 synthetic messages for call_2 and call_3
    tool_message_ids = {msg.tool_call_id for msg in result if isinstance(msg, ToolMessage)}
    assert "call_1" in tool_message_ids
    assert "call_2" in tool_message_ids
    assert "call_3" in tool_message_ids
