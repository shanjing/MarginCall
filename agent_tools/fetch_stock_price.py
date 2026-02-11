from datetime import datetime

import yfinance as yf

from tools.cache.decorators import TTL_REALTIME, cached
from tools.logging_utils import log_tool_error, logger

from .tool_schemas import StockPriceResult


@cached(data_type="price", ttl_seconds=TTL_REALTIME, ticker_param="ticker")
def fetch_stock_price(ticker: str) -> dict:
    """Retrieves current stock price and saves to session state."""
    logger.info(f"--- Tool: get_stock_price called for {ticker} ---")

    try:
        # Fetch stock data
        stock = yf.Ticker(ticker)
        current_price = stock.info.get("currentPrice")

        if current_price is None:
            log_tool_error("fetch_stock_price", f"Could not fetch price for {ticker}", ticker=ticker)
            return {
                "status": "error",
                "error_message": f"Could not fetch price for {ticker}",
            }

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Return the result in the StockPriceResult schema -SJ
        # model_dump() is used to convert the Pydantic model to a dictionary
        return StockPriceResult(
            ticker=ticker,
            price=current_price,
            timestamp=current_time,
        ).model_dump()

    except Exception as e:
        log_tool_error("fetch_stock_price", str(e), ticker=ticker)
        return {
            "status": "error",
            "error_message": f"Error fetching stock data: {str(e)}",
        }
