"""
StockTwits social sentiment - crowd sentiment from traders.
"""

import logging

import requests

from tools.cache.decorators import TTL_INTRADAY, cached

from .tool_schemas import StockTwitsSentimentResult

logger = logging.getLogger(__name__)

STOCKTWITS_API_URL = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"


@cached(data_type="stocktwits", ttl_seconds=TTL_INTRADAY, ticker_param="ticker")
def fetch_stocktwits_sentiment(ticker: str) -> dict:
    """
    Fetch social sentiment for a stock from StockTwits.

    Analyzes recent messages to determine bullish/bearish sentiment
    from the trading community.

    Args:
        ticker: Stock symbol (e.g., "AAPL", "TSLA")

    Returns:
        dict with sentiment counts, ratio, and overall signal
    """
    logger.info(f"--- Tool: fetch_stocktwits_sentiment called for {ticker} ---")

    try:
        url = STOCKTWITS_API_URL.format(ticker=ticker.upper())
        headers = {"User-Agent": "Mozilla/5.0 (compatible; MarginCallAgent/1.0)"}

        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # Check for errors in response
        if data.get("response", {}).get("status") != 200:
            error_msg = data.get("errors", [{"message": "Unknown error"}])[0].get(
                "message"
            )
            return {"status": "error", "ticker": ticker.upper(), "error": error_msg}

        messages = data.get("messages", [])

        if not messages:
            return StockTwitsSentimentResult(
                ticker=ticker.upper(),
                message_count=0,
                bullish=0,
                bearish=0,
                neutral=0,
                sentiment_ratio=None,
                signal="NO_DATA",
                interpretation=f"No recent StockTwits messages found for {ticker.upper()}",
            ).model_dump()

        # Count sentiment from messages
        bullish = 0
        bearish = 0
        neutral = 0

        for msg in messages:
            sentiment = msg.get("entities", {}).get("sentiment", {})
            if sentiment:
                basic = sentiment.get("basic")
                if basic == "Bullish":
                    bullish += 1
                elif basic == "Bearish":
                    bearish += 1
                else:
                    neutral += 1
            else:
                neutral += 1

        total_with_sentiment = bullish + bearish

        # Calculate sentiment ratio (bullish / total with sentiment)
        if total_with_sentiment > 0:
            ratio = round(bullish / total_with_sentiment, 2)
        else:
            ratio = 0.5  # Neutral if no sentiment data

        # Determine signal
        if ratio >= 0.7:
            signal = "STRONG_BULLISH"
            sentiment_label = "Strongly Bullish"
        elif ratio >= 0.55:
            signal = "BULLISH"
            sentiment_label = "Bullish"
        elif ratio >= 0.45:
            signal = "NEUTRAL"
            sentiment_label = "Neutral"
        elif ratio >= 0.3:
            signal = "BEARISH"
            sentiment_label = "Bearish"
        else:
            signal = "STRONG_BEARISH"
            sentiment_label = "Strongly Bearish"

        # Get symbol info
        symbol_info = data.get("symbol", {})

        return StockTwitsSentimentResult(
            ticker=ticker.upper(),
            title=symbol_info.get("title", ticker.upper()),
            message_count=len(messages),
            bullish=bullish,
            bearish=bearish,
            neutral=neutral,
            sentiment_ratio=ratio,
            signal=signal,
            watchers=symbol_info.get("watchlist_count", 0),
            interpretation=(
                f"StockTwits sentiment for {ticker.upper()}: {sentiment_label} "
                f"({bullish} bullish, {bearish} bearish out of {len(messages)} messages)"
            ),
        ).model_dump()

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return {
                "status": "error",
                "ticker": ticker.upper(),
                "error": f"Symbol {ticker.upper()} not found on StockTwits",
            }
        logger.error(f"HTTP error fetching StockTwits sentiment: {e}")
        return {"status": "error", "ticker": ticker.upper(), "error": str(e)}
    except Exception as e:
        logger.error(f"Error fetching StockTwits sentiment: {e}")
        return {"status": "error", "ticker": ticker.upper(), "error": str(e)}
