"""
CNN Fear & Greed Index fetcher.
"""

import logging
from typing import Any

import requests

from tools.cache.decorators import TTL_INTRADAY, cached
from tools.truncate_for_llm import truncate_strings_for_llm

from .tool_schemas import CNNFearGreedResult

logger = logging.getLogger(__name__)

# CNN Fear & Greed API endpoints (try multiple in case one is blocked)
CNN_FEAR_GREED_URLS = [
    "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
    "https://production.dataviz.cnn.io/index/feargreed/graphdata",
]

# Headers to avoid bot detection
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.cnn.com/markets/fear-and-greed",
}


@cached(data_type="cnn_fear_greed", ttl_seconds=TTL_INTRADAY, ticker_param=None)
def fetch_cnn_greedy() -> dict:
    """
    Return the current CNN Fear & Greed Index.

    Returns:
        dict with score (0-100), rating, and interpretation
    """
    logger.info("--- Tool: fetch_cnn_greedy called ---")

    last_error = None
    for url in CNN_FEAR_GREED_URLS:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            score, rating = _parse_fear_greed(data)
            if score is not None:
                out = CNNFearGreedResult(
                    score=score,
                    rating=rating,
                    interpretation=f"CNN Fear & Greed Index: {score} ({rating})",
                ).model_dump()
                result, _ = truncate_strings_for_llm(out, tool_name="fetch_cnn_greedy")
                return result
        except requests.RequestException as e:
            last_error = str(e)
            logger.warning(f"CNN API error for {url}: {e}")
            continue
        except ValueError as e:
            last_error = str(e)
            logger.warning(f"CNN parse error for {url}: {e}")
            continue

    # All endpoints failed
    return {
        "status": "error",
        "error_message": f"Failed to fetch CNN Fear & Greed data: {last_error}",
    }


def _parse_fear_greed(data: Any) -> tuple[int | None, str]:
    """Extract score (0-100) and rating string from CNN Fear & Greed API response."""
    if isinstance(data, dict):
        inner = data.get("fear_and_greed") or data.get("score") or data
        if isinstance(inner, dict):
            s = inner.get("score") or inner.get("value")
            r = inner.get("rating") or inner.get("label") or ""
            if s is not None:
                return int(s), r or _rating_from_score(s)
        if "score" in data and "rating" in data:
            return int(data["score"]), data.get("rating", "")
    if isinstance(data, list) and data:
        last = data[-1]
        if isinstance(last, dict):
            s = last.get("score") or last.get("value") or last.get("y")
            if s is not None:
                return int(s), last.get("rating", "") or _rating_from_score(s)
    return None, ""


def _rating_from_score(score: float) -> str:
    """Map 0-100 score to label."""
    if score <= 24:
        return "Extreme Fear"
    if score <= 44:
        return "Fear"
    if score <= 55:
        return "Neutral"
    if score <= 74:
        return "Greed"
    return "Extreme Greed"
