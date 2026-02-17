"""Tests for the cache system (SQLiteCacheBackend, NoOp, make_key)."""

from __future__ import annotations

import asyncio
import json
import time

import pytest

from tools.cache.base import CacheBackend
from tools.cache import _NoOpCacheBackend


# ---------------------------------------------------------------------------
# CacheBackend.make_key (static, no backend needed)
# ---------------------------------------------------------------------------

class TestMakeKey:
    def test_standard_key(self):
        assert CacheBackend.make_key("aapl", "price", "2026-02-16") == "AAPL:price:2026-02-16"

    def test_empty_ticker(self):
        assert CacheBackend.make_key("", "vix", "2026-02-16") == ":vix:2026-02-16"

    def test_no_date(self):
        assert CacheBackend.make_key("TSLA", "financials") == "TSLA:financials:"


# ---------------------------------------------------------------------------
# SQLiteCacheBackend (uses tmp_cache fixture from conftest)
# ---------------------------------------------------------------------------

class TestSQLiteCacheBackend:
    @pytest.mark.asyncio
    async def test_put_get_roundtrip(self, tmp_cache):
        key = "AAPL:price:2026-02-16"
        data = b'{"price": 150}'
        await tmp_cache.put(key, data, ttl_seconds=3600, ticker="AAPL", data_type="price")
        result = await tmp_cache.get(key)
        assert result == data

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, tmp_cache):
        result = await tmp_cache.get("NONEXISTENT:key:2026-01-01")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiry(self, tmp_cache):
        key = "AAPL:price:2026-02-16"
        await tmp_cache.put(key, b'{"price": 150}', ttl_seconds=1, ticker="AAPL")
        # Immediately should be available
        assert await tmp_cache.get(key) is not None
        # After TTL expires
        time.sleep(1.1)
        assert await tmp_cache.get(key) is None

    @pytest.mark.asyncio
    async def test_exists(self, tmp_cache):
        key = "TSLA:financials:2026-02-16"
        assert await tmp_cache.exists(key) is False
        await tmp_cache.put(key, b"{}", ttl_seconds=3600, ticker="TSLA")
        assert await tmp_cache.exists(key) is True

    @pytest.mark.asyncio
    async def test_delete(self, tmp_cache):
        key = "TSLA:price:2026-02-16"
        await tmp_cache.put(key, b"{}", ttl_seconds=3600, ticker="TSLA")
        assert await tmp_cache.exists(key) is True
        await tmp_cache.delete(key)
        assert await tmp_cache.exists(key) is False

    @pytest.mark.asyncio
    async def test_invalidate_ticker(self, tmp_cache):
        await tmp_cache.put("AAPL:price:2026-02-16", b"{}", 3600, ticker="AAPL", data_type="price")
        await tmp_cache.put("AAPL:financials:2026-02-16", b"{}", 3600, ticker="AAPL", data_type="financials")
        await tmp_cache.put("TSLA:price:2026-02-16", b"{}", 3600, ticker="TSLA", data_type="price")

        deleted = await tmp_cache.invalidate_ticker("AAPL")
        assert deleted == 2
        # TSLA should still be there
        assert await tmp_cache.exists("TSLA:price:2026-02-16") is True

    @pytest.mark.asyncio
    async def test_purge_expired(self, tmp_cache):
        await tmp_cache.put("OLD:data:2026-01-01", b"{}", ttl_seconds=1, ticker="OLD")
        time.sleep(1.1)
        purged = await tmp_cache.purge_expired()
        assert purged >= 1

    @pytest.mark.asyncio
    async def test_get_stats(self, tmp_cache):
        await tmp_cache.put("AAPL:price:2026-02-16", b"{}", 3600, ticker="AAPL", data_type="price")
        await tmp_cache.put("TSLA:price:2026-02-16", b"{}", 3600, ticker="TSLA", data_type="price")

        stats = await tmp_cache.get_stats()
        assert stats["distinct_stocks"] == 2
        assert stats["total_entries"] == 2
        assert set(stats["tickers"]) == {"AAPL", "TSLA"}

    @pytest.mark.asyncio
    async def test_put_json_get_json(self, tmp_cache):
        key = "GOOGL:price:2026-02-16"
        data = {"status": "success", "price": 175.50}
        await tmp_cache.put_json(key, data, ttl_seconds=3600, ticker="GOOGL", data_type="price")
        result = await tmp_cache.get_json(key)
        assert result == data

    @pytest.mark.asyncio
    async def test_get_json_invalid_returns_none(self, tmp_cache):
        key = "BAD:json:2026-02-16"
        await tmp_cache.put(key, b"not json{{{", ttl_seconds=3600)
        result = await tmp_cache.get_json(key)
        assert result is None


# ---------------------------------------------------------------------------
# NoOpCacheBackend
# ---------------------------------------------------------------------------

class TestNoOpCacheBackend:
    @pytest.mark.asyncio
    async def test_always_misses(self):
        backend = _NoOpCacheBackend()
        await backend.put("key", b"data", ttl_seconds=3600)
        assert await backend.get("key") is None
        assert await backend.exists("key") is False

    @pytest.mark.asyncio
    async def test_stats_empty(self):
        backend = _NoOpCacheBackend()
        stats = await backend.get_stats()
        assert stats["total_entries"] == 0
        assert stats["tickers"] == []
