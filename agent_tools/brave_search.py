"""
Search tools for the MarginCall MCP server (e.g. Brave web search).
This is for non-gemini models to search the web.
"""

import os

import requests

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

    results = data.get("web", {}).get("results", [])
    if not results:
        return "No results found."

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        url = r.get("url", "")
        desc = r.get("description", "")
        lines.append(f"{i}. {title}\n   {url}\n   {desc}")
    return "\n\n".join(lines)
