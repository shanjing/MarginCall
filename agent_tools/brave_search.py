"""
Search tools for the MarginCall MCP server (e.g. Brave web search).
This is for non-gemini models to search the web.
Uses Pydantic schemas to cap result size; final string is truncated as last checkpoint.
"""

import os

import requests

from tools.truncate_for_llm import MAX_RESPONSE_STRING_BYTES, truncate_string_to_bytes

from .tool_schemas import BraveSearchEntry, BraveSearchResult

BRAVE_WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


def brave_search(query: str) -> str:
    """Search the web for a given query using Brave Search."""
    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        return "Error: BRAVE_API_KEY environment variable is not set."

    params = {"q": query}
    headers = {"X-Subscription-Token": api_key}

    try:
        response = requests.get(
            BRAVE_WEB_SEARCH_URL,
            params=params,
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        return f"Error calling Brave Search API: {e}"
    except ValueError as e:
        return f"Error parsing Brave Search response: {e}"

    raw_results = data.get("web", {}).get("results", [])
    if not raw_results:
        return "No results found."

    # Build validated entries (Pydantic truncates each field)
    entries = [
        BraveSearchEntry(
            title=r.get("title", "") or "",
            url=r.get("url", "") or "",
            description=r.get("description", "") or "",
        )
        for r in raw_results
    ]
    validated = BraveSearchResult(results=entries)

    lines = []
    for i, e in enumerate(validated.results, 1):
        lines.append(f"{i}. {e.title}\n   {e.url}\n   {e.description}")
    out = "\n\n".join(lines)

    # Last checkpoint before injecting into LLM: cap total response length
    return truncate_string_to_bytes(
        out,
        MAX_RESPONSE_STRING_BYTES,
        suffix="\n\n(response truncated)",
        context="brave_search.response",
    )
