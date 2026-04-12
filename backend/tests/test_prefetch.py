"""Tests for backend/agent/prefetch.py — prefetch_context()."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.prefetch import prefetch_context


def make_tool(name: str, return_value="[]"):
    t = MagicMock()
    t.name = name
    t.ainvoke = AsyncMock(return_value=return_value)
    return t


def make_client(tools=None, resource_value=None, resource_raises=False):
    """Build a mock MCP client context manager."""
    client = MagicMock()
    tools = tools or []
    client.get_tools = AsyncMock(return_value=tools)
    if resource_raises:
        client.read_resource = AsyncMock(side_effect=Exception("resource not supported"))
    else:
        client.read_resource = AsyncMock(return_value=resource_value or "[]")
    # Support async context manager
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# ── Returns empty for None repo_name ─────────────────────────────────────────

async def test_returns_empty_dict_for_none_repo_name():
    result = await prefetch_context("https://github.com/owner/repo/pull/1", None)
    assert result == {"processes": [], "stats": {}, "changed_symbols": []}


async def test_no_mcp_calls_when_repo_name_is_none():
    with patch("agent.prefetch.get_mcp_client") as mock_client_fn:
        await prefetch_context("https://github.com/owner/repo/pull/1", None)
    mock_client_fn.assert_not_called()


# ── Returns stats and processes for a known repo ──────────────────────────────

async def test_returns_stats_for_known_repo():
    list_repos_response = (
        '[{"name": "minetest", "path": "/tmp/minetest", '
        '"stats": {"files": 100, "nodes": 500, "edges": 200, "communities": 10, "processes": 5}}]'
    )
    list_repos_tool = make_tool("list_repos", return_value=list_repos_response)
    client = make_client(
        tools=[list_repos_tool],
        resource_raises=True,  # force cypher fallback path
    )

    # Cypher fallback returns no processes
    cypher_tool = make_tool("cypher", return_value="[]")
    client.get_tools = AsyncMock(return_value=[list_repos_tool, cypher_tool])

    with patch("agent.prefetch.get_mcp_client", return_value=client):
        result = await prefetch_context("https://github.com/owner/minetest/pull/1", "minetest")

    assert result["stats"]["files"] == 100
    assert result["stats"]["nodes"] == 500
    assert result["stats"]["processes"] == 5


async def test_returns_processes_via_resource_uri():
    list_repos_tool = make_tool("list_repos", return_value="[]")
    client = make_client(
        tools=[list_repos_tool],
        resource_value='[{"name": "item_crafting_flow", "description": "Crafting loop"}]',
    )

    with patch("agent.prefetch.get_mcp_client", return_value=client):
        result = await prefetch_context("https://github.com/owner/repo/pull/1", "repo")

    assert len(result["processes"]) == 1
    assert result["processes"][0]["name"] == "item_crafting_flow"


# ── Cypher fallback when resource read fails ──────────────────────────────────

async def test_cypher_fallback_when_resource_read_fails():
    cypher_response = '[{"name": "login_flow", "description": "User login"}]'
    list_repos_tool = make_tool("list_repos", return_value="[]")
    cypher_tool = make_tool("cypher", return_value=cypher_response)
    client = make_client(
        tools=[list_repos_tool, cypher_tool],
        resource_raises=True,
    )
    # get_tools is called twice (once for tools, once inside _fetch_processes fallback)
    client.get_tools = AsyncMock(return_value=[list_repos_tool, cypher_tool])

    with patch("agent.prefetch.get_mcp_client", return_value=client):
        result = await prefetch_context("https://github.com/owner/repo/pull/1", "repo")

    assert len(result["processes"]) == 1
    assert result["processes"][0]["name"] == "login_flow"


# ── Graceful on total failure ─────────────────────────────────────────────────

async def test_graceful_on_exception():
    """Any unhandled exception must return empty dicts, never raise."""
    client = make_client()
    client.get_tools = AsyncMock(side_effect=Exception("connection refused"))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with patch("agent.prefetch.get_mcp_client", return_value=client):
        result = await prefetch_context("https://github.com/owner/repo/pull/1", "repo")

    assert result == {"processes": [], "stats": {}, "changed_symbols": []}


async def test_graceful_when_mcp_client_raises_on_enter():
    """If the context manager itself fails, return empty dicts."""
    client = MagicMock()
    client.__aenter__ = AsyncMock(side_effect=Exception("server not found"))
    client.__aexit__ = AsyncMock(return_value=False)

    with patch("agent.prefetch.get_mcp_client", return_value=client):
        result = await prefetch_context("https://github.com/owner/repo/pull/1", "repo")

    assert result == {"processes": [], "stats": {}, "changed_symbols": []}


# ── changed_symbols is always empty list ─────────────────────────────────────

async def test_changed_symbols_always_empty():
    """changed_symbols is populated by the gather stage, not prefetch."""
    list_repos_tool = make_tool("list_repos", return_value="[]")
    client = make_client(tools=[list_repos_tool], resource_raises=True)
    cypher_tool = make_tool("cypher", return_value="[]")
    client.get_tools = AsyncMock(return_value=[list_repos_tool, cypher_tool])

    with patch("agent.prefetch.get_mcp_client", return_value=client):
        result = await prefetch_context("https://github.com/owner/repo/pull/1", "repo")

    assert result["changed_symbols"] == []
