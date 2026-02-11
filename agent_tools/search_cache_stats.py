"""
Search cache stats — how many stocks were discussed and how many entries are stored.

Use when the user asks about past stocks, cached reports, or what has been analyzed.
"""

import logging

from tools.cache import get_cache

from .tool_schemas import CacheStatsResult

logger = logging.getLogger(__name__)


async def search_cache_stats() -> dict:
    """
    Search the cache and return how many stocks were discussed and how many entries are stored.

    Use this when the user asks about past stocks, cached reports, or what has been analyzed
    (e.g. "What stocks have we looked at?", "How many reports are in the cache?").

    Returns:
        dict with status, distinct_stocks, total_entries, and tickers list.
    """
    logger.info("--- Tool: search_cache_stats called ---")

    try:
        cache = get_cache()
        stats = await cache.get_stats()
        return CacheStatsResult(
            status="success",
            distinct_stocks=stats["distinct_stocks"],
            total_entries=stats["total_entries"],
            tickers=stats["tickers"],
        ).model_dump()
    except Exception as e:
        logger.error("Error getting cache stats: %s", e)
        return {
            "status": "error",
            "error": str(e),
            "distinct_stocks": 0,
            "total_entries": 0,
            "tickers": [],
        }
