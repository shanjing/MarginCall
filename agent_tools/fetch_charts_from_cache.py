"""
Fetch chart images (base64) from local cache for a ticker.

Used when an agent needs chart data without re-generating. Charts are stored
by fetch_technicals_with_chart when the pipeline runs. Frontend uses /api/charts
which reads the same cache.
"""

from __future__ import annotations

from datetime import date

from tools.cache import get_cache
from tools.cache.base import CacheBackend
from tools.logging_utils import logger


async def fetch_charts_from_cache(ticker: str) -> dict:
    """
    Fetch chart images (base64) for a ticker from local cache.

    Charts are populated when fetch_technicals_with_chart runs (pipeline).
    Returns empty dict if no charts in cache.

    Args:
        ticker: Stock symbol (e.g. 'AAPL', 'IREN').

    Returns:
        dict with status, charts: { "1y": { "label": "...", "image_base64": "..." }, ... }
    """
    ticker_upper = ticker.upper()
    logger.info("--- Tool: fetch_charts_from_cache called for %s ---", ticker_upper)

    cache = get_cache()
    today = date.today().isoformat()
    cache_key = CacheBackend.make_key(ticker_upper, "technicals_with_chart", today)
    data = await cache.get_json(cache_key)

    if not data or "charts" not in data:
        return {
            "status": f"No chart data in cache for {ticker_upper}. Run stock analysis first.",
            "charts": {},
        }

    charts = data.get("charts", {})
    out = {}
    for k, v in charts.items():
        if isinstance(v, dict) and v.get("image_base64"):
            out[k] = {
                "label": v.get("label", k),
                "image_base64": v["image_base64"],
            }

    if not out:
        return {
            "status": f"Charts in cache for {ticker_upper} have no image_base64.",
            "charts": {},
        }

    return {
        "status": f"Found {len(out)} chart(s) for {ticker_upper} in local cache.",
        "charts": out,
    }
