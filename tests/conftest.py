"""Shared fixtures for MarginCall test suite."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root is on sys.path so `tools.*` and `agent_tools.*` resolve
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set required env vars BEFORE any project imports (config.py reads them at import time)
os.environ.setdefault("CLOUD_AI_MODEL", "gemini-2.5-flash")
os.environ.setdefault("ROOT_AGENT", "stock_analyst")
os.environ.setdefault(
    "SUB_AGENTS",
    "stock_analysis_pipeline,stock_data_collector,report_synthesizer,presenter,news_fetcher",
)
os.environ.setdefault("CACHE_BACKEND", "sqlite")
os.environ.setdefault("CACHE_DISABLED", "false")


# ---------------------------------------------------------------------------
# Cache fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_cache(tmp_path):
    """A real SQLiteCacheBackend backed by a temp file (isolated per test)."""
    from tools.cache.sqlite_backend import SQLiteCacheBackend

    return SQLiteCacheBackend(db_path=tmp_path / "test_cache.db")


@pytest.fixture(autouse=True)
def _reset_cache_singleton():
    """Reset the cache module singleton before each test so no state leaks."""
    import tools.cache as cache_mod

    cache_mod._cache_instance = None
    yield
    cache_mod._cache_instance = None


@pytest.fixture()
def noop_cache(tmp_path):
    """Patch get_cache to return a real SQLite backend on a temp DB (isolated, disposable).

    This avoids issues with _NoOpCacheBackend missing get_json/put_json that the
    @cached decorator expects. A throwaway SQLite DB is cheap and accurate.
    """
    from tools.cache.sqlite_backend import SQLiteCacheBackend

    backend = SQLiteCacheBackend(db_path=tmp_path / "noop_cache.db")
    with patch("tools.cache.get_cache", return_value=backend):
        yield backend


# ---------------------------------------------------------------------------
# External-service mocks
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_yfinance():
    """Patch yfinance.Ticker and return the mock instance for customisation."""
    mock_ticker_instance = MagicMock()
    mock_ticker_instance.info = {
        "currentPrice": 150.25,
        "trailingPE": 25.5,
        "forwardPE": 22.0,
        "marketCap": 2_500_000_000_000,
        "totalRevenue": 400_000_000_000,
        "netIncomeToCommon": 100_000_000_000,
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "longBusinessSummary": "A large technology company.",
    }
    with patch("yfinance.Ticker", return_value=mock_ticker_instance) as mock_cls:
        mock_cls._instance = mock_ticker_instance  # convenience accessor
        yield mock_ticker_instance


@pytest.fixture()
def mock_requests_get():
    """Patch requests.get and return the mock for customisation."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {}
    with patch("requests.get", return_value=mock_response) as mock_get:
        mock_get._response = mock_response  # convenience accessor
        yield mock_get
