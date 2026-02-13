"""
Composite function tool: fetches technical indicators, generates charts, and
returns structured data with pre-computed signals.

Combines fetch_technical_indicators + generate_trading_chart into one tool call.
Generates two default charts: 1-year daily and 90-day daily.
Charts: saved to ADK artifacts (when tool_context present) for ADK web UI;
also cached locally for /api/charts. Return value omits image_base64 for LLM.
"""

from __future__ import annotations

import base64
from datetime import date, datetime

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


async def _load_chart_base64_from_artifact(tool_context: object, png_filename: str) -> str | None:
    """Load PNG artifact and return base64 string for cache. Returns None on failure."""
    load_fn = getattr(tool_context, "load_artifact", None)
    if not load_fn:
        return None
    try:
        part = await load_fn(png_filename)
        if part is None:
            return None
        blob = getattr(part, "inline_data", None) or getattr(part, "inlineData", None)
        if blob is None:
            return None
        data = getattr(blob, "data", None)
        if data is None or len(data) == 0:
            return None
        return base64.b64encode(data).decode("ascii") if isinstance(data, bytes) else None
    except Exception as e:
        logger.debug("Could not load chart artifact %s: %s", png_filename, e)
        return None


def _strip_chart_base64(charts: dict) -> dict:
    """Remove image_base64 from chart entries so they are not sent to the LLM."""
    if not charts:
        return charts
    stripped = {}
    for k, v in charts.items():
        if isinstance(v, dict):
            stripped[k] = {kk: vv for kk, vv in v.items() if kk != "image_base64"}
        else:
            stripped[k] = v
    return stripped


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


async def fetch_technicals_with_chart(ticker: str, tool_context: object | None = None) -> dict:
    """
    Fetch technical indicators and generate TradingView-style charts.

    Runs locally: yfinance + Plotly. Charts stored in local cache.
    Full result (with chart base64) cached for /api/charts; returned value
    omits image_base64 to avoid LLM context bloat.

    This composite tool:
    1. Fetches RSI, MACD, SMA indicators (cached TTL_DAILY)
    2. Generates two default charts: 1-year daily and 90-day daily
    3. Computes rule-based signals (overbought/oversold, bullish/bearish)
    4. Caches full result for /api/charts; returns stripped (no base64) to agent

    Args:
        ticker: Stock symbol (e.g. 'AAPL').
        tool_context: Deprecated; ignored.

    Returns:
        dict with status, indicators, signals, and chart metadata (no image_base64).
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
        cached_data = dict(cached_data)
        cached_data["_from_cache"] = True
        logger.info("Cache HIT for technicals_with_chart: %s", ticker)
        # Return stripped version (no base64) so LLM does not receive chart blobs
        if "charts" in cached_data:
            cached_data["charts"] = _strip_chart_base64(cached_data["charts"])
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
        image_b64 = None
        if isinstance(chart_result, dict):
            image_b64 = chart_result.get("image_base64")
            status_str = chart_result.get("status", "")
            # When ADK path: generate_trading_chart returns status-only; load from artifact for cache
            if image_b64 is None and tool_context is not None:
                png_filename = f"{ticker}_chart_{timeframe}.png"
                image_b64 = await _load_chart_base64_from_artifact(tool_context, png_filename)
            result["charts"][timeframe] = {
                "label": label,
                "result": status_str,
                "image_base64": image_b64,
            }
        else:
            result["charts"][timeframe] = {
                "label": label,
                "result": str(chart_result),
                "image_base64": None,
            }

    # 4. Validate, cache full result (for /api/charts), return stripped (for LLM)
    validated = TechnicalsWithChartResult(**result).model_dump()
    await cache.put_json(
        cache_key,
        validated,
        TTL_DAILY,
        ticker=ticker.upper(),
        data_type="technicals_with_chart",
    )

    # Strip base64 before returning to agent—avoids 100-500KB in LLM context
    to_return = dict(validated)
    if "charts" in to_return:
        to_return["charts"] = _strip_chart_base64(to_return["charts"])
    return to_return
