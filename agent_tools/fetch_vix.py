"""
VIX (CBOE Volatility Index) - Market fear gauge.
VIX > 30 = high fear, VIX < 15 = complacency/greed.
"""

import logging

import yfinance as yf

from tools.cache.decorators import TTL_INTRADAY, cached

from .tool_schemas import VIXResult

logger = logging.getLogger(__name__)


@cached(data_type="vix", ttl_seconds=TTL_INTRADAY, ticker_param=None)
def fetch_vix() -> dict:
    """
    Fetch the current VIX (CBOE Volatility Index) value.

    VIX interpretation:
    - < 15: Low volatility, market complacency (bullish sentiment)
    - 15-20: Normal volatility
    - 20-30: Elevated volatility, increasing fear
    - > 30: High fear, market stress
    - > 40: Extreme fear, panic selling

    Returns:
        dict with VIX value, interpretation, and sentiment signal
    """
    logger.info("--- Tool: fetch_vix called ---")

    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="5d")

        if hist.empty:
            return {"status": "error", "error": "Could not fetch VIX data"}

        current_vix = round(hist["Close"].iloc[-1], 2)
        prev_vix = round(hist["Close"].iloc[-2], 2) if len(hist) > 1 else current_vix
        change = round(current_vix - prev_vix, 2)
        change_pct = round((change / prev_vix) * 100, 2) if prev_vix else 0

        # Interpret VIX level
        if current_vix < 15:
            level = "Low"
            sentiment = "Complacency/Bullish"
            signal = "GREED"
        elif current_vix < 20:
            level = "Normal"
            sentiment = "Neutral"
            signal = "NEUTRAL"
        elif current_vix < 30:
            level = "Elevated"
            sentiment = "Cautious/Fearful"
            signal = "FEAR"
        elif current_vix < 40:
            level = "High"
            sentiment = "High Fear"
            signal = "HIGH_FEAR"
        else:
            level = "Extreme"
            sentiment = "Panic/Extreme Fear"
            signal = "EXTREME_FEAR"

        return VIXResult(
            vix=current_vix,
            previous_close=prev_vix,
            change=change,
            change_percent=change_pct,
            level=level,
            sentiment=sentiment,
            signal=signal,
            interpretation=f"VIX at {current_vix} indicates {level.lower()} volatility ({sentiment})",
        ).model_dump()

    except Exception as e:
        logger.error(f"Error fetching VIX: {e}")
        return {"status": "error", "error": str(e)}
