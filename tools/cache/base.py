"""
Abstract cache backend interface.

All backends (SQLite, Redis, GCS) implement this contract.
Tool functions only interact with this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class CacheBackend(ABC):
    """Abstract base for all cache backends."""

    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        """Retrieve cached data by key. Returns None if missing or expired."""

    @abstractmethod
    async def put(
        self,
        key: str,
        data: bytes,
        ttl_seconds: int,
        ticker: str = "",
        data_type: str = "",
        mime_type: str = "application/json",
    ) -> None:
        """Store data with TTL. Overwrites existing entry for the same key."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a single cache entry."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a valid (non-expired) entry exists for this key."""

    @abstractmethod
    async def invalidate_ticker(self, ticker: str) -> int:
        """
        Invalidate ALL cache entries for a given ticker.
        Used when user requests real-time/refresh data.
        Returns the number of entries deleted.
        """

    @abstractmethod
    async def purge_expired(self) -> int:
        """
        Delete all expired entries from the cache.
        Should be called periodically (auto-purge).
        Returns the number of entries purged.
        """

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources (close DB connections, etc.)."""

    @abstractmethod
    async def get_stats(self) -> dict:
        """
        Return cache statistics for "past stocks / reports" queries.

        Returns:
            dict with:
                - distinct_stocks: number of unique tickers with cached data
                - total_entries: total number of cache entries
                - tickers: list of ticker symbols (e.g. ["AAPL", "TSLA"])
        """

    # ── Convenience helpers (non-abstract) ──────────────────────────────

    @staticmethod
    def make_key(ticker: str, data_type: str, date: str = "") -> str:
        """
        Build a cache key from components.

        Examples:
            make_key("AAPL", "price", "2026-02-07") → "AAPL:price:2026-02-07"
            make_key("", "vix", "2026-02-07")       → ":vix:2026-02-07"
        """
        return f"{ticker.upper()}:{data_type}:{date}"
