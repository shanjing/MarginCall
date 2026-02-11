"""
Google Custom Search tool for LLM models that don't support Gemini's built-in google_search.
Uses the Programmable Search Engine (Custom Search) JSON API.
"""

import os

import requests

GOOGLE_CUSTOM_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"


def google_custom_search(query: str, num_results: int = 5) -> str:
    """Search the web using Google Custom Search API. Use for LLMs that don't support Gemini's google_search."""
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_SEARCH_API_KEY")
    cx = os.environ.get("GOOGLE_SEARCH_ENGINE_ID") or os.environ.get("GOOGLE_CX")

    if not api_key:
        return "Error: GOOGLE_API_KEY or GOOGLE_SEARCH_API_KEY environment variable is not set."
    if not cx:
        return "Error: GOOGLE_SEARCH_ENGINE_ID or GOOGLE_CX environment variable is not set. Create a Programmable Search Engine at https://programmablesearchengine.google.com/"

    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": min(max(num_results, 1), 10),
    }

    try:
        response = requests.get(
            GOOGLE_CUSTOM_SEARCH_URL,
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        return f"Error calling Google Custom Search API: {e}"
    except ValueError as e:
        return f"Error parsing Google Custom Search response: {e}"

    items = data.get("items", [])
    if not items:
        return "No results found."

    lines = []
    for i, item in enumerate(items, 1):
        title = item.get("title", "")
        url = item.get("link", "")
        snippet = item.get("snippet", "")
        lines.append(f"{i}. {title}\n   {url}\n   {snippet}")
    return "\n\n".join(lines)
