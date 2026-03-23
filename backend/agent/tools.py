import os

from langchain_mcp_adapters.client import MultiServerMCPClient


def _server_config() -> dict:
    return {
        "github": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {
                **os.environ,
                # The GitHub MCP server expects GITHUB_PERSONAL_ACCESS_TOKEN
                "GITHUB_PERSONAL_ACCESS_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
            },
        },
        "gitnexus": {
            "transport": "stdio",
            "command": "gitnexus",
            "args": ["mcp"],
            "env": {**os.environ},
        },
    }


def get_mcp_client() -> MultiServerMCPClient:
    """
    Returns a MultiServerMCPClient context manager.

    Usage:
        async with get_mcp_client() as client:
            tools = await client.get_tools()
    """
    return MultiServerMCPClient(_server_config())
