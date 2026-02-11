"""
A local MCP server exposing Brave web search and sentiment tools.

Run as module: python -m agent_tools.server (from MarginCall directory)
"""

from mcp.server.fastmcp import FastMCP

from .brave_search import brave_search

mcp_server = FastMCP("MarginCall MCP Server")

mcp_server.tool()(brave_search)


if __name__ == "__main__":
    mcp_server.run(transport="stdio")
