"""Tests for Pydantic schema validation (tool_schemas + schemas)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_tools.tool_schemas import (
    CacheStatsResult,
    CNNFearGreedResult,
    FinancialsResult,
    InvalidateCacheResult,
    MACDValues,
    RedditPostEntry,
    RedditPostsResult,
    StockPriceResult,
    TechnicalIndicatorsResult,
    VIXResult,
)


# ---------------------------------------------------------------------------
# StockPriceResult
# ---------------------------------------------------------------------------

class TestStockPriceResult:
    def test_valid(self):
        r = StockPriceResult(ticker="AAPL", price=150.0, timestamp="2026-02-16 10:00:00")
        assert r.status == "success"
        assert r.price == 150.0

    def test_negative_price_rejected(self):
        with pytest.raises(ValidationError):
            StockPriceResult(ticker="AAPL", price=-1.0, timestamp="2026-02-16")

    def test_missing_ticker_rejected(self):
        with pytest.raises(ValidationError):
            StockPriceResult(price=100.0, timestamp="2026-02-16")


# ---------------------------------------------------------------------------
# FinancialsResult
# ---------------------------------------------------------------------------

class TestFinancialsResult:
    def test_minimal_valid(self):
        r = FinancialsResult(ticker="TSLA", timestamp="2026-02-16")
        assert r.status == "success"
        assert r.total_revenue is None
        assert r.market_cap is None

    def test_all_optional_fields(self):
        r = FinancialsResult(
            ticker="TSLA",
            timestamp="2026-02-16",
            total_revenue=1e9,
            market_cap=500e9,
            trailing_pe=30.0,
            sector="Technology",
            market_cap_category="Mega Cap",
        )
        assert r.total_revenue == 1e9
        assert r.sector == "Technology"


# ---------------------------------------------------------------------------
# CNNFearGreedResult
# ---------------------------------------------------------------------------

class TestCNNFearGreedResult:
    def test_valid(self):
        r = CNNFearGreedResult(score=65, rating="Greed", interpretation="CNN Fear & Greed Index: 65 (Greed)")
        assert r.score == 65

    def test_score_out_of_range(self):
        with pytest.raises(ValidationError):
            CNNFearGreedResult(score=101, rating="X", interpretation="X")

        with pytest.raises(ValidationError):
            CNNFearGreedResult(score=-1, rating="X", interpretation="X")


# ---------------------------------------------------------------------------
# VIXResult
# ---------------------------------------------------------------------------

class TestVIXResult:
    def test_valid(self):
        r = VIXResult(
            vix=18.5,
            previous_close=17.0,
            change=1.5,
            change_percent=8.82,
            level="Normal",
            sentiment="Neutral",
            signal="NEUTRAL",
            interpretation="VIX at 18.5",
        )
        assert r.signal == "NEUTRAL"


# ---------------------------------------------------------------------------
# TechnicalIndicatorsResult
# ---------------------------------------------------------------------------

class TestTechnicalIndicatorsResult:
    def test_valid(self):
        r = TechnicalIndicatorsResult(
            ticker="AAPL",
            timestamp="2026-02-16",
            sma_20=148.0,
            sma_50=145.0,
            macd=MACDValues(line=1.5, signal=1.2, histogram=0.3),
            rsi_14=55.0,
        )
        assert r.macd.histogram == 0.3


# ---------------------------------------------------------------------------
# RedditPostEntry — field validators truncate oversized strings
# ---------------------------------------------------------------------------

class TestRedditPostEntry:
    def test_normal_entry(self):
        e = RedditPostEntry(
            subreddit="r/stocks",
            title="AAPL earnings beat",
            url="https://reddit.com/r/stocks/abc",
            snippet="Great quarter.",
        )
        assert e.title == "AAPL earnings beat"

    def test_oversized_title_truncated(self):
        long_title = "A" * 5000
        e = RedditPostEntry(
            subreddit="r/stocks",
            title=long_title,
            url="https://example.com",
        )
        assert len(e.title.encode("utf-8")) <= 2100  # MAX_STRING_BYTES + suffix overhead

    def test_oversized_snippet_truncated(self):
        long_snippet = "B" * 5000
        e = RedditPostEntry(
            subreddit="r/stocks",
            title="Title",
            url="https://example.com",
            snippet=long_snippet,
        )
        assert len(e.snippet.encode("utf-8")) <= 2100


# ---------------------------------------------------------------------------
# RedditPostsResult
# ---------------------------------------------------------------------------

class TestRedditPostsResult:
    def test_empty_posts(self):
        r = RedditPostsResult(
            ticker="AAPL",
            posts=[],
            subreddits_queried=["r/wallstreetbets"],
            message="Reddit isn't showing this much love.",
        )
        assert r.message is not None
        assert len(r.posts) == 0

    def test_with_posts(self):
        entry = RedditPostEntry(
            subreddit="r/stocks", title="AAPL", url="https://reddit.com/x"
        )
        r = RedditPostsResult(
            ticker="AAPL",
            posts=[entry],
            by_subreddit={"r/stocks": [entry]},
            subreddits_queried=["r/stocks"],
        )
        assert len(r.posts) == 1


# ---------------------------------------------------------------------------
# CacheStatsResult / InvalidateCacheResult
# ---------------------------------------------------------------------------

class TestCacheStatsResult:
    def test_valid(self):
        r = CacheStatsResult(distinct_stocks=3, total_entries=10, tickers=["AAPL", "TSLA", "GOOGL"])
        assert r.distinct_stocks == 3

    def test_negative_rejected(self):
        with pytest.raises(ValidationError):
            CacheStatsResult(distinct_stocks=-1, total_entries=0, tickers=[])


class TestInvalidateCacheResult:
    def test_valid(self):
        r = InvalidateCacheResult(ticker="AAPL", entries_cleared=5, message="Cleared")
        assert r.entries_cleared == 5

    def test_negative_entries_rejected(self):
        with pytest.raises(ValidationError):
            InvalidateCacheResult(ticker="AAPL", entries_cleared=-1, message="Cleared")
