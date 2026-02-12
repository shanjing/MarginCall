from datetime import datetime

import yfinance as yf

from tools.cache.decorators import TTL_DAILY, cached
from tools.logging_utils import log_tool_error, logger

from .tool_schemas import EarningsDateResult


@cached(data_type="earnings_date", ttl_seconds=TTL_DAILY, ticker_param="ticker")
def fetch_earnings_date(ticker: str) -> dict:
    """Retrieves the next upcoming earnings date for a stock ticker."""
    logger.info(f"--- Tool: fetch_earnings_date called for {ticker} ---")

    try:
        stock = yf.Ticker(ticker)
        calendar = stock.calendar

        if calendar is None or (isinstance(calendar, dict) and not calendar):
            return EarningsDateResult(
                ticker=ticker,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                next_earnings_date=None,
                is_estimated=True,
                days_until_earnings=None,
            ).model_dump()

        # yfinance .calendar returns a dict with 'Earnings Date' key
        # or may have other formats depending on version
        earnings_date = None

        if isinstance(calendar, dict):
            # calendar dict may have 'Earnings Date' as a list of datetime(s)
            raw = calendar.get("Earnings Date")
            if raw is not None:
                if isinstance(raw, list) and len(raw) > 0:
                    earnings_date = raw[0]
                elif hasattr(raw, "strftime"):
                    earnings_date = raw
        elif hasattr(calendar, "columns"):
            # DataFrame format (older yfinance versions)
            if "Earnings Date" in calendar.columns:
                vals = calendar["Earnings Date"].dropna()
                if not vals.empty:
                    earnings_date = vals.iloc[0]

        if earnings_date is None:
            return EarningsDateResult(
                ticker=ticker,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                next_earnings_date=None,
                is_estimated=True,
                days_until_earnings=None,
            ).model_dump()

        # Normalize to date string
        if hasattr(earnings_date, "strftime"):
            earnings_date_str = earnings_date.strftime("%Y-%m-%d")
            earnings_dt = (
                earnings_date.date()
                if hasattr(earnings_date, "date")
                else earnings_date
            )
        else:
            earnings_date_str = str(earnings_date)[:10]
            earnings_dt = datetime.strptime(earnings_date_str, "%Y-%m-%d").date()

        today = datetime.now().date()
        days_until = (earnings_dt - today).days
        days_until = max(days_until, 0)

        return EarningsDateResult(
            ticker=ticker,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            next_earnings_date=earnings_date_str,
            is_estimated=True,
            days_until_earnings=days_until,
        ).model_dump()

    except Exception as e:
        log_tool_error("fetch_earnings_date", str(e), ticker=ticker)
        return {
            "status": "error",
            "error_message": f"Error fetching earnings date: {str(e)}",
        }
