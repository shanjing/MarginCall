"""
Cache package – pluggable caching for MarginCall agent tools.

Usage:
    from tools.cache import get_cache

    cache = get_cache()
    await cache.get("AAPL:price:2026-02-07")
    await cache.put("AAPL:price:2026-02-07", data, ttl_seconds=900)

Decorator usage:
    from tools.cache.decorators import cached, TTL_DAILY

    @cached(data_type="price", ttl_seconds=TTL_DAILY)
    def fetch_stock_price(ticker: str) -> dict: ...
"""

from .base import CacheBackend
from .sqlite_backend import SQLiteCacheBackend

__all__ = ["CacheBackend", "SQLiteCacheBackend", "get_cache"]

# Singleton cache instance
_cache_instance: CacheBackend | None = None


def get_cache() -> CacheBackend:
    """Return the singleton cache backend (lazy-initialized)."""
    global _cache_instance
    if _cache_instance is None:
        from tools.config import CACHE_DISABLED

        if CACHE_DISABLED:
            _cache_instance = _NoOpCacheBackend()
        else:
            _cache_instance = SQLiteCacheBackend()
    return _cache_instance


class _NoOpCacheBackend(CacheBackend):
    """No-op backend used when CACHE_DISABLED=true. Always misses."""

    async def get(self, key: str) -> bytes | None:
        return None

    async def put(self, key: str, data: bytes, ttl_seconds: int, **kw) -> None:
        pass

    async def delete(self, key: str) -> None:
        pass

    async def exists(self, key: str) -> bool:
        return False

    async def invalidate_ticker(self, ticker: str) -> int:
        return 0

    async def purge_expired(self) -> int:
        return 0

    async def close(self) -> None:
        pass

    async def get_stats(self) -> dict:
        return {"distinct_stocks": 0, "total_entries": 0, "tickers": []}
