"""
Cache invalidation tool — allows root_agent to force real-time data refresh.

Called when user explicitly requests fresh/real-time data.
"""

import logging

from tools.cache import get_cache
from tools.logging_utils import log_tool_error

from .tool_schemas import InvalidateCacheResult

logger = logging.getLogger(__name__)


async def invalidate_cache(ticker: str) -> dict:
    """
    Invalidate all cached data for a stock ticker, forcing fresh API calls.

    Use this when the user explicitly requests real-time or fresh data
    (e.g., "refresh AAPL", "get me real-time data for TSLA").

    Args:
        ticker: Stock symbol to invalidate cache for (e.g., "AAPL").

    Returns:
        dict with status and number of cache entries cleared.
    """
    logger.info("--- Tool: invalidate_cache called for %s ---", ticker)

    try:
        cache = get_cache()
        deleted = await cache.invalidate_ticker(ticker)
        return InvalidateCacheResult(
            ticker=ticker.upper(),
            entries_cleared=deleted,
            message=f"Cache cleared for {ticker.upper()}. Next analysis will use fresh data.",
        ).model_dump()
    except Exception as e:
        logger.error("Error invalidating cache for %s: %s", ticker, e)
        log_tool_error("invalidate_cache", str(e), ticker=ticker)
        return {
            "status": "error",
            "error": str(e),
        }
