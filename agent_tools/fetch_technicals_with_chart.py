"""
Composite function tool: fetches technical indicators, generates charts, and
returns structured data with pre-computed signals.

Combines fetch_technical_indicators + generate_trading_chart into one tool call.
Generates two default charts: 1-year daily and 90-day daily.
Caches the full result (indicators + signals + chart metadata) for TTL_DAILY.
"""

from __future__ import annotations

from datetime import date, datetime

from google.adk.tools import ToolContext
from tools.cache.decorators import TTL_DAILY
from tools.logging_utils import logger

from .fetch_technical_indicators import fetch_technical_indicators
from .generate_trading_chart import generate_trading_chart
from .tool_schemas import TechnicalsWithChartResult

# Default charts generated for every stock analysis
DEFAULT_CHARTS = [
    {"timeframe": "1y", "label": "1-Year Daily"},
    {"timeframe": "3mo", "label": "90-Day Daily"},
]


def _compute_signals(indicators: dict) -> dict:
    """Compute rule-based signals from raw indicator values."""
    signals = {}

    # RSI signals
    rsi = indicators.get("rsi_14")
    if rsi is not None:
        if rsi > 70:
            signals["rsi_signal"] = "overbought"
        elif rsi < 30:
            signals["rsi_signal"] = "oversold"
        else:
            signals["rsi_signal"] = "neutral"

    # MACD signals
    macd = indicators.get("macd", {})
    histogram = macd.get("histogram", 0)
    if histogram > 0:
        signals["macd_signal"] = "bullish"
    elif histogram < 0:
        signals["macd_signal"] = "bearish"
    else:
        signals["macd_signal"] = "neutral"

    # MACD crossover detection
    line = macd.get("line", 0)
    signal_line = macd.get("signal", 0)
    if line > signal_line:
        signals["macd_crossover"] = "bullish (line above signal)"
    elif line < signal_line:
        signals["macd_crossover"] = "bearish (line below signal)"
    else:
        signals["macd_crossover"] = "neutral"

    # SMA trend signals
    sma_20 = indicators.get("sma_20")
    sma_50 = indicators.get("sma_50")
    if sma_20 is not None and sma_50 is not None:
        if sma_20 > sma_50:
            signals["sma_trend"] = "short-term bullish (SMA20 > SMA50)"
        elif sma_20 < sma_50:
            signals["sma_trend"] = "short-term bearish (SMA20 < SMA50)"
        else:
            signals["sma_trend"] = "neutral"

    return signals


async def fetch_technicals_with_chart(
    ticker: str,
    tool_context: ToolContext | None = None,
) -> dict:
    """
    Fetch technical indicators and generate TradingView-style charts.

    This composite tool:
    1. Fetches RSI, MACD, SMA indicators (cached TTL_DAILY)
    2. Generates two default charts: 1-year daily and 90-day daily
    3. Computes rule-based signals (overbought/oversold, bullish/bearish)
    4. Caches the full result for TTL_DAILY (24 hours)

    Args:
        ticker: Stock symbol (e.g. 'AAPL').
        tool_context: ADK ToolContext for saving chart artifacts.

    Returns:
        dict with status, indicators, signals, and chart info for both timeframes.
    """
    logger.info(
        "--- Tool: fetch_technicals_with_chart called for %s ---",
        ticker,
    )

    # ── Check cache first ───────────────────────────────────────────────
    from tools.cache import get_cache
    from tools.cache.base import CacheBackend

    cache = get_cache()
    today = date.today().isoformat()
    cache_key = CacheBackend.make_key(ticker.upper(), "technicals_with_chart", today)
    cached_data = await cache.get_json(cache_key)

    if cached_data is not None:
        cached_data["_from_cache"] = True
        logger.info("Cache HIT for technicals_with_chart: %s", ticker)
        return cached_data

    # ── Cache miss — run full pipeline ──────────────────────────────────
    result = {
        "status": "success",
        "ticker": ticker,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 1. Fetch technical indicators (inner call is cached separately)
    indicators = fetch_technical_indicators(ticker)
    if indicators.get("status") == "error":
        return indicators  # Return error as-is

    result["indicators"] = {
        "rsi_14": indicators.get("rsi_14"),
        "sma_20": indicators.get("sma_20"),
        "sma_50": indicators.get("sma_50"),
        "macd": indicators.get("macd"),
    }

    # 2. Compute rule-based signals
    result["signals"] = _compute_signals(indicators)

    # 3. Generate default charts (1-year + 90-day)
    result["charts"] = {}
    for chart_config in DEFAULT_CHARTS:
        timeframe = chart_config["timeframe"]
        label = chart_config["label"]
        logger.info(
            "--- Generating %s chart for %s ---",
            label,
            ticker,
        )
        chart_result = await generate_trading_chart(
            ticker=ticker,
            timeframe=timeframe,
            tool_context=tool_context,
        )
        result["charts"][timeframe] = {
            "label": label,
            "result": chart_result,
        }

    # 4. Validate through schema and cache the full result
    validated = TechnicalsWithChartResult(**result).model_dump()
    await cache.put_json(
        cache_key,
        validated,
        TTL_DAILY,
        ticker=ticker.upper(),
        data_type="technicals_with_chart",
    )

    return validated
