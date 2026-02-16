"""Fetch key financials (revenue, net income, balance sheet, cash flow) for a stock ticker using yfinance."""

from datetime import datetime

import yfinance as yf

from tools.cache.decorators import TTL_DAILY, cached
from tools.logging_utils import log_tool_error, logger
from tools.truncate_for_llm import truncate_strings_for_llm

from .tool_schemas import FinancialsResult

# Keys we read from Ticker.info; use stable names and fallbacks
INFO_KEYS = [
    ("totalRevenue", "total_revenue"),
    ("revenuePerShare", "revenue_per_share"),
    ("netIncomeToCommon", "net_income"),
    ("grossProfits", "gross_profits"),
    ("ebitda", "ebitda"),
    ("totalDebt", "total_debt"),
    ("totalCash", "total_cash"),
    ("freeCashflow", "free_cash_flow"),
    ("operatingCashflow", "operating_cash_flow"),
    ("marketCap", "market_cap"),
    ("debtToEquity", "debt_to_equity"),
    ("currentRatio", "current_ratio"),
    ("trailingPE", "trailing_pe"),
    ("forwardPE", "forward_pe"),
    ("sector", "sector"),
    ("industry", "industry"),
    ("longBusinessSummary", "long_business_summary"),
]

# Market cap categories (USD)
MARKET_CAP_MEGA = 200e9
MARKET_CAP_LARGE = 10e9
MARKET_CAP_MID = 2e9
MARKET_CAP_SMALL = 300e6

# Cap long_business_summary so it doesn't bloat LLM context; report condenses to 4 lines anyway.
LONG_BUSINESS_SUMMARY_MAX_CHARS = 500
LONG_BUSINESS_SUMMARY_TRUNCATED_SUFFIX = " [truncated]"


@cached(data_type="financials", ttl_seconds=TTL_DAILY, ticker_param="ticker")
def fetch_financials(ticker: str) -> dict:
    """
    Fetch key financial metrics for a stock ticker from yfinance.

    Returns total revenue, net income, debt, cash, market cap, and related ratios when available.
    """
    logger.info("--- Tool: fetch_financials called for %s ---", ticker)

    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if not info:
            log_tool_error("fetch_financials", f"Could not fetch financials for {ticker}", ticker=ticker)
            return {
                "status": "error",
                "error_message": f"Could not fetch financials for {ticker}",
            }

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data = {}

        for info_key, out_key in INFO_KEYS:
            val = info.get(info_key)
            if val is not None:
                if out_key == "long_business_summary" and isinstance(val, str):
                    original_len = len(val)
                    if original_len > LONG_BUSINESS_SUMMARY_MAX_CHARS:
                        val = val[:LONG_BUSINESS_SUMMARY_MAX_CHARS].rstrip() + LONG_BUSINESS_SUMMARY_TRUNCATED_SUFFIX
                        logger.info(
                            "Truncation: dataset=fetch_financials.long_business_summary original_chars=%s truncated_chars=%s",
                            original_len,
                            len(val),
                        )
                data[out_key] = val

        if not data:
            log_tool_error("fetch_financials", f"No financial data available for {ticker}", ticker=ticker)
            return {
                "status": "error",
                "error_message": f"No financial data available for {ticker}",
            }

        # Latest quarter from quarterly income statement
        latest_quarter_end = None
        latest_quarter_revenue = None
        latest_quarter_net_income = None
        try:
            qis = stock.quarterly_income_stmt
            if qis is not None and not qis.empty:
                # First column is usually most recent quarter
                first_col = qis.iloc[:, 0]
                # Common row names in yfinance
                for rev_key in ("Total Revenue", "Revenue", "Operating Revenue"):
                    if rev_key in qis.index:
                        v = first_col.get(rev_key)
                        if v is not None and not (isinstance(v, float) and (v != v)):  # skip NaN
                            latest_quarter_revenue = float(v)
                            break
                for ni_key in (
                    "Net Income",
                    "Net Income Common Stockholders",
                    "Net Income Including Noncontrolling Interests",
                ):
                    if ni_key in qis.index:
                        v = first_col.get(ni_key)
                        if v is not None and not (isinstance(v, float) and (v != v)):
                            latest_quarter_net_income = float(v)
                            break
                col_name = qis.columns[0]
                if hasattr(col_name, "strftime"):
                    latest_quarter_end = col_name.strftime("%Y-%m-%d")
                else:
                    latest_quarter_end = str(col_name)
        except Exception as eq:
            logger.debug("Quarterly income stmt unavailable for %s: %s", ticker, eq)

        if latest_quarter_end is not None or latest_quarter_revenue is not None or latest_quarter_net_income is not None:
            data["latest_quarter_end"] = latest_quarter_end
            data["latest_quarter_revenue"] = latest_quarter_revenue
            data["latest_quarter_net_income"] = latest_quarter_net_income

        # Market cap category for company intro
        mc = data.get("market_cap")
        if mc is not None and isinstance(mc, (int, float)) and mc > 0:
            if mc >= MARKET_CAP_MEGA:
                data["market_cap_category"] = "Mega Cap"
            elif mc >= MARKET_CAP_LARGE:
                data["market_cap_category"] = "Large Cap"
            elif mc >= MARKET_CAP_MID:
                data["market_cap_category"] = "Mid Cap"
            elif mc >= MARKET_CAP_SMALL:
                data["market_cap_category"] = "Small Cap"
            else:
                data["market_cap_category"] = "Micro Cap"

        out = FinancialsResult(
            ticker=ticker, timestamp=current_time, **data
        ).model_dump(exclude_none=True)
        result, _ = truncate_strings_for_llm(out, tool_name="fetch_financials")
        return result

    except Exception as e:
        logger.exception("Error fetching financials for %s", ticker)
        log_tool_error("fetch_financials", str(e), ticker=ticker)
        return {
            "status": "error",
            "error_message": f"Error fetching financials: {str(e)}",
        }
