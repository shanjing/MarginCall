"""
Google Custom Search tool for LLM models that don't support Gemini's built-in google_search.
Uses the Programmable Search Engine (Custom Search) JSON API.
Caps result count and field lengths (Brave-style); truncation includes inline [truncated, N chars] signal.
"""

import os

import requests

from tools.truncate_for_llm import MAX_RESPONSE_STRING_BYTES, truncate_string_to_bytes

GOOGLE_CUSTOM_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

# Cap results and per-field size so search payload doesn't bloat LLM context.
GOOGLE_SEARCH_MAX_RESULTS = 10
GOOGLE_SEARCH_FIELD_MAX_BYTES = 2000


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
        "num": min(max(num_results, 1), GOOGLE_SEARCH_MAX_RESULTS),
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

    items = data.get("items", [])[:GOOGLE_SEARCH_MAX_RESULTS]
    if not items:
        return "No results found."

    lines = []
    for i, item in enumerate(items, 1):
        title = truncate_string_to_bytes(
            item.get("title", "") or "",
            max_bytes=GOOGLE_SEARCH_FIELD_MAX_BYTES,
            context="google_custom_search.title",
        )
        url = truncate_string_to_bytes(
            item.get("link", "") or "",
            max_bytes=GOOGLE_SEARCH_FIELD_MAX_BYTES,
            context="google_custom_search.url",
        )
        snippet = truncate_string_to_bytes(
            item.get("snippet", "") or "",
            max_bytes=GOOGLE_SEARCH_FIELD_MAX_BYTES,
            context="google_custom_search.snippet",
        )
        lines.append(f"{i}. {title}\n   {url}\n   {snippet}")
    out = "\n\n".join(lines)

    # Last checkpoint: cap total response length
    return truncate_string_to_bytes(
        out,
        MAX_RESPONSE_STRING_BYTES,
        suffix="\n\n(response truncated)",
        context="google_custom_search.response",
        include_size_signal=False,
    )
