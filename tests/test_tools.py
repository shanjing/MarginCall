"""Tests for agent tool functions (mocked externals, NoOp cache)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helper functions (pure logic, no mock needed)
# ---------------------------------------------------------------------------

class TestRatingFromScore:
    """fetch_cnn_greedy._rating_from_score"""

    def _fn(self, score):
        from agent_tools.fetch_cnn_greedy import _rating_from_score
        return _rating_from_score(score)

    def test_extreme_fear(self):
        assert self._fn(10) == "Extreme Fear"
        assert self._fn(24) == "Extreme Fear"

    def test_fear(self):
        assert self._fn(25) == "Fear"
        assert self._fn(44) == "Fear"

    def test_neutral(self):
        assert self._fn(45) == "Neutral"
        assert self._fn(55) == "Neutral"

    def test_greed(self):
        assert self._fn(56) == "Greed"
        assert self._fn(74) == "Greed"

    def test_extreme_greed(self):
        assert self._fn(75) == "Extreme Greed"
        assert self._fn(100) == "Extreme Greed"


class TestParseFearGreed:
    """fetch_cnn_greedy._parse_fear_greed"""

    def _fn(self, data):
        from agent_tools.fetch_cnn_greedy import _parse_fear_greed
        return _parse_fear_greed(data)

    def test_dict_with_fear_and_greed_key(self):
        data = {"fear_and_greed": {"score": 65, "rating": "Greed"}}
        score, rating = self._fn(data)
        assert score == 65
        assert rating == "Greed"

    def test_dict_with_score_and_rating(self):
        data = {"score": 30, "rating": "Fear"}
        score, rating = self._fn(data)
        assert score == 30
        assert rating == "Fear"

    def test_nested_value_key(self):
        data = {"fear_and_greed": {"value": 80}}
        score, rating = self._fn(data)
        assert score == 80
        assert "Greed" in rating  # auto-mapped from score

    def test_list_format(self):
        data = [{"score": 50}]
        score, rating = self._fn(data)
        assert score == 50

    def test_returns_none_on_garbage(self):
        score, rating = self._fn("not a dict")
        assert score is None


class TestSnippetFromSelftext:
    """fetch_reddit._snippet_from_selftext"""

    def _fn(self, text):
        from agent_tools.fetch_reddit import _snippet_from_selftext
        return _snippet_from_selftext(text)

    def test_short_text(self):
        assert self._fn("Hello world") == "Hello world"

    def test_empty(self):
        assert self._fn("") == ""
        assert self._fn(None) == ""

    def test_html_entities_decoded(self):
        result = self._fn("Price &gt; $100 &#x200B;")
        assert "&gt;" not in result
        assert ">" in result

    def test_oversized_truncated(self):
        long_text = "A" * 2000
        result = self._fn(long_text)
        assert len(result.encode("utf-8")) <= 503  # SNIPPET_MAX_BYTES + "..."

    def test_whitespace_collapsed(self):
        result = self._fn("hello\n\n\n   world")
        assert result == "hello world"


class TestMentionsTicker:
    """fetch_reddit._mentions_ticker"""

    def _fn(self, text, ticker):
        from agent_tools.fetch_reddit import _mentions_ticker
        return _mentions_ticker(text, ticker)

    def test_case_insensitive(self):
        assert self._fn("I love aapl", "AAPL") is True
        assert self._fn("AAPL is great", "aapl") is True

    def test_not_found(self):
        assert self._fn("I love TSLA", "AAPL") is False

    def test_empty_inputs(self):
        assert self._fn("", "AAPL") is False
        assert self._fn("AAPL", "") is False


# ---------------------------------------------------------------------------
# fetch_stock_price
# ---------------------------------------------------------------------------

class TestFetchStockPrice:
    def test_success(self, noop_cache, mock_yfinance):
        from agent_tools.fetch_stock_price import fetch_stock_price

        result = fetch_stock_price("AAPL", _force_refresh=True)
        assert result["status"] == "success"
        assert result["price"] == 150.25
        assert result["ticker"] == "AAPL"

    def test_none_price_returns_error(self, noop_cache, mock_yfinance):
        mock_yfinance.info = {"currentPrice": None}
        from agent_tools.fetch_stock_price import fetch_stock_price

        result = fetch_stock_price("FAKE", _force_refresh=True)
        assert result["status"] == "error"
        assert "error_message" in result

    def test_exception_returns_error(self, noop_cache):
        with patch("agent_tools.fetch_stock_price.yf.Ticker", side_effect=Exception("network down")):
            from agent_tools.fetch_stock_price import fetch_stock_price

            result = fetch_stock_price("AAPL", _force_refresh=True)
            assert result["status"] == "error"
            assert "network down" in result["error_message"]


# ---------------------------------------------------------------------------
# fetch_vix
# ---------------------------------------------------------------------------

class TestFetchVix:
    def test_success(self, noop_cache):
        mock_ticker = MagicMock()
        hist = pd.DataFrame({"Close": [18.0, 19.0, 20.5, 21.0, 22.0]})
        mock_ticker.history.return_value = hist
        with patch("agent_tools.fetch_vix.yf.Ticker", return_value=mock_ticker):
            from agent_tools.fetch_vix import fetch_vix

            result = fetch_vix(_force_refresh=True)
            assert result["status"] == "success"
            assert result["vix"] == 22.0
            assert result["level"] == "Elevated"
            assert result["signal"] == "FEAR"

    def test_empty_history_returns_error(self, noop_cache):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        with patch("agent_tools.fetch_vix.yf.Ticker", return_value=mock_ticker):
            from agent_tools.fetch_vix import fetch_vix

            result = fetch_vix(_force_refresh=True)
            assert result["status"] == "error"

    def test_low_vix_greed(self, noop_cache):
        mock_ticker = MagicMock()
        hist = pd.DataFrame({"Close": [12.0, 13.0, 12.5, 13.5, 14.0]})
        mock_ticker.history.return_value = hist
        with patch("agent_tools.fetch_vix.yf.Ticker", return_value=mock_ticker):
            from agent_tools.fetch_vix import fetch_vix

            result = fetch_vix(_force_refresh=True)
            assert result["signal"] == "GREED"
            assert result["level"] == "Low"


# ---------------------------------------------------------------------------
# fetch_cnn_greedy
# ---------------------------------------------------------------------------

class TestFetchCnnGreedy:
    def test_success(self, noop_cache, mock_requests_get):
        mock_requests_get._response.json.return_value = {
            "fear_and_greed": {"score": 72, "rating": "Greed"}
        }
        from agent_tools.fetch_cnn_greedy import fetch_cnn_greedy

        result = fetch_cnn_greedy(_force_refresh=True)
        assert result["status"] == "success"
        assert result["score"] == 72
        assert result["rating"] == "Greed"

    def test_all_endpoints_fail(self, noop_cache):
        import requests as req_mod

        with patch("agent_tools.fetch_cnn_greedy.requests.get", side_effect=req_mod.RequestException("timeout")):
            from agent_tools.fetch_cnn_greedy import fetch_cnn_greedy

            result = fetch_cnn_greedy(_force_refresh=True)
            assert result["status"] == "error"
            assert "Failed to fetch" in result["error_message"]


# ---------------------------------------------------------------------------
# fetch_reddit
# ---------------------------------------------------------------------------

class TestFetchReddit:
    def test_success_with_matching_posts(self, noop_cache, mock_requests_get):
        mock_requests_get._response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "AAPL earnings are amazing",
                            "selftext": "Apple beat expectations this quarter.",
                            "permalink": "/r/stocks/comments/abc/aapl_earnings/",
                        }
                    },
                    {
                        "data": {
                            "title": "Unrelated post about cats",
                            "selftext": "I love cats.",
                            "permalink": "/r/stocks/comments/def/cats/",
                        }
                    },
                ]
            }
        }
        from agent_tools.fetch_reddit import fetch_reddit

        result = fetch_reddit("AAPL", subreddits=["stocks"], _force_refresh=True)
        assert result["status"] == "success"
        assert result["ticker"] == "AAPL"
        # Only the AAPL post should match
        assert len(result["posts"]) >= 1
        assert any("AAPL" in p["title"] for p in result["posts"])

    def test_no_matching_posts(self, noop_cache, mock_requests_get):
        mock_requests_get._response.json.return_value = {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "Unrelated post",
                            "selftext": "Nothing about stocks.",
                            "permalink": "/r/stocks/comments/xyz/unrelated/",
                        }
                    }
                ]
            }
        }
        from agent_tools.fetch_reddit import fetch_reddit

        result = fetch_reddit("AAPL", subreddits=["stocks"], _force_refresh=True)
        assert result["status"] == "success"
        assert result["message"] == "Reddit isn't showing this much love."
        assert len(result["posts"]) == 0

    def test_request_failure(self, noop_cache):
        import requests as req_mod

        with patch("agent_tools.fetch_reddit.requests.get", side_effect=req_mod.RequestException("403")):
            from agent_tools.fetch_reddit import fetch_reddit

            result = fetch_reddit("AAPL", subreddits=["stocks"], _force_refresh=True)
            assert result["status"] == "success"  # still returns success with empty posts
            assert len(result["posts"]) == 0
