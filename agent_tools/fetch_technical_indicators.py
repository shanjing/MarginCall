"""Fetch technical indicators (SMA, MACD, RSI) for a stock ticker using yfinance."""

from datetime import datetime

import yfinance as yf

from tools.cache.decorators import TTL_DAILY, cached
from tools.logging_utils import logger
from tools.truncate_for_llm import truncate_strings_for_llm

from .tool_schemas import MACDValues, TechnicalIndicatorsResult


def _sma(series, window: int):
    """Simple moving average."""
    return series.rolling(window=window, min_periods=window).mean()


def _ema(series, span: int):
    """Exponential moving average."""
    return series.ewm(span=span, adjust=False).mean()


def _rsi(series, period: int = 14):
    """Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


@cached(data_type="technicals", ttl_seconds=TTL_DAILY, ticker_param="ticker")
def fetch_technical_indicators(ticker: str) -> dict:
    """
    Fetch SMA (20, 50), MACD, and RSI (14) for a stock ticker.

    Uses yfinance history; requires enough history for 50-day SMA and MACD (26+9).
    """
    logger.info("--- Tool: fetch_technical_indicators called for %s ---", ticker)

    try:
        stock = yf.Ticker(ticker)
        # Request enough history for 50-day SMA and MACD (26+9)
        hist = stock.history(period="6mo")
        if hist is None or hist.empty or len(hist) < 50:
            return {
                "status": "error",
                "error_message": f"Insufficient history for {ticker} (need at least 50 days)",
            }

        close = hist["Close"]

        # SMA 20 and 50 (latest)
        sma_20 = _sma(close, 20).iloc[-1]
        sma_50 = _sma(close, 50).iloc[-1]

        # MACD: line = EMA12 - EMA26, signal = EMA9 of line
        ema_12 = _ema(close, 12)
        ema_26 = _ema(close, 26)
        macd_line = ema_12 - ema_26
        macd_signal = _ema(macd_line, 9)
        macd_hist = macd_line - macd_signal
        macd_line_val = macd_line.iloc[-1]
        macd_signal_val = macd_signal.iloc[-1]
        macd_hist_val = macd_hist.iloc[-1]

        # RSI 14 (latest); use 100 if no losses in period (avg_loss -> 0)
        rsi_series = _rsi(close, 14)
        rsi_val = rsi_series.iloc[-1]
        if rsi_val != rsi_val:  # nan check
            rsi_val = 100.0

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        out = TechnicalIndicatorsResult(
            ticker=ticker,
            timestamp=current_time,
            sma_20=round(float(sma_20), 4),
            sma_50=round(float(sma_50), 4),
            macd=MACDValues(
                line=round(float(macd_line_val), 4),
                signal=round(float(macd_signal_val), 4),
                histogram=round(float(macd_hist_val), 4),
            ),
            rsi_14=round(float(rsi_val), 2),
        ).model_dump()
        result, _ = truncate_strings_for_llm(out, tool_name="fetch_technical_indicators")
        return result

    except Exception as e:
        logger.exception("Error fetching technical indicators for %s", ticker)
        return {
            "status": "error",
            "error_message": str(e),
        }
