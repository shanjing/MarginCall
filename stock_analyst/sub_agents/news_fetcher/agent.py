"""
news_fetcher – sub-agent for stock news.
Uses Brave search (MCP) for non-Gemini models, Google search for Gemini family.
"""

from google.adk.agents import LlmAgent
from google.adk.tools import google_search

from agent_tools import agent_mcp_toolset
from tools.config import AI_MODEL, AI_MODEL_NAME

from .prompts import get_instruction as get_news_fetcher_instruction

# Gemini family uses google_search; otherwise Brave search via MCP.
_IS_GEMINI = AI_MODEL_NAME.lower().startswith("gemini")
_NEWS_SEARCH_TOOL = google_search if _IS_GEMINI else agent_mcp_toolset
_NEWS_SEARCH_TOOL_NAME = "google_search" if _IS_GEMINI else "brave_search"

news_fetcher = LlmAgent(
    name="news_fetcher",
    model=AI_MODEL,
    description="A stock news fetcher agent",
    instruction=get_news_fetcher_instruction(_NEWS_SEARCH_TOOL_NAME),
    tools=[_NEWS_SEARCH_TOOL],
    output_key="stock_news",
)
