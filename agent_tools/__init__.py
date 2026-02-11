"""
MarginCall agent tools: function tools and MCP server integration.

Agents can import:
  - agent_mcp_toolset: McpToolset for the local MCP server (brave_search, etc.).
    Use in tools=[...]; each agent uses the tools it needs (e.g. news_fetcher → brave_search,
    sentiment agent → fetch_cnn_greedy).
  - mcp_server: FastMCP server instance (e.g. for running: mcp_server.run(transport="stdio"))
"""

from __future__ import annotations

import os
import sys

from . import schemas, tool_schemas
from .server import mcp_server

__all__ = [
    "agent_mcp_toolset",
    "mcp_server",
    "schemas",
    "tool_schemas",
]

# Lazy-build MCP toolset so ADK MCP deps are only required when used
_agent_mcp_toolset = None


def __getattr__(name: str):
    if name == "agent_mcp_toolset":
        global _agent_mcp_toolset
        if _agent_mcp_toolset is None:
            _agent_mcp_toolset = _make_agent_mcp_toolset()
        return _agent_mcp_toolset
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _make_agent_mcp_toolset():
    """Build McpToolset for the local MCP server (stdio). Exposes brave_search, etc."""
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
    from mcp import StdioServerParameters

    # Run as module so server.py has package context (python -m agent_tools.server)
    agent_tools_dir = os.path.dirname(os.path.abspath(__file__))
    cwd = os.path.dirname(agent_tools_dir)  # MarginCall directory
    env = os.environ.copy()
    if "BRAVE_API_KEY" in os.environ:
        env["BRAVE_API_KEY"] = os.environ["BRAVE_API_KEY"]

    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["-m", "agent_tools.server"],
                env=env,
                cwd=cwd,
            ),
        ),
        tool_filter=["brave_search"],
    )


# agent_mcp_toolset is provided via __getattr__ (lazy) so ADK MCP deps
# are only loaded when an agent actually uses it.
