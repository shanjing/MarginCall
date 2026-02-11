"""
news_fetcher – sub-agent (placeholder).
Uses Brave search (MCP) for non-Gemini models, Google search for Gemini family.
"""

from google.adk.agents import LlmAgent
from google.adk.tools import google_search

from agent_tools import agent_mcp_toolset
from tools.config import AI_MODEL, AI_MODEL_NAME

# Gemini family → google_search; otherwise → Brave search (MCP)
_IS_GEMINI = AI_MODEL_NAME.lower().startswith("gemini")
_NEWS_SEARCH_TOOL = google_search if _IS_GEMINI else agent_mcp_toolset
_NEWS_SEARCH_TOOL_NAME = "google_search" if _IS_GEMINI else "brave_search"

# For consistency, python variable and agent name are identical
news_fetcher = LlmAgent(
    name="news_fetcher",
    model=AI_MODEL,
    description="A stock news fetcher agent",
    instruction=f"""
    You are a stock news fetcher agent.
    You have exactly one tool: '{_NEWS_SEARCH_TOOL_NAME}'. Use ONLY this tool to fetch news.
    Do NOT call any other tool names (e.g. check_internet, search_web, verify_connection).
    You will be given a stock symbol. Use '{_NEWS_SEARCH_TOOL_NAME}' to fetch the stock news.
    Limit to 3 news articles, total number of characters to 300.
    The news should be in the following format:
    [
        {{
            "title": "Stock news title",
            "url": "Stock news url",
            "snippet": "Stock news snippet",
            "date": "Stock news date"
        }},
    Return the stock news in the 'stock_news' output key with the following format:
    {{
        "status": "success",
        "news": [
            {{
                "title": "Stock news title",
                "url": "Stock news url",
                "snippet": "Stock news snippet",
                "date": "Stock news date"
            }},
            {{
                "title": "Stock news title",
                "url": "Stock news url",
                "snippet": "Stock news snippet",
                "date": "Stock news date"
            }}
        ]
    }}
    """,
    tools=[_NEWS_SEARCH_TOOL],
    output_key="stock_news",
)
