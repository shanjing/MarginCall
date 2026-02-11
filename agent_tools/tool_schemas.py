"""
Tool-layer schemas — data contracts for tool function return values.

LAYER 1 of the two-layer schema architecture:
  • tool_schemas.py  → what tool functions return (raw data contracts)
  • schemas.py       → what the LLM produces (report structure, analyzed output)

These layers are intentionally separate. Tool schemas describe raw data from
external sources; LLM schemas describe analyzed/presented data for the final report.
Coupling them leads to brittle changes — see misc/adk/use_tools_with_schema.md §6-7.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# fetch_stock_price
# ─────────────────────────────────────────────────────────────────────────────
class StockPriceResult(BaseModel):
    """Return contract for fetch_stock_price."""

    status: str = Field(default="success")
    ticker: str = Field(..., description="Stock ticker symbol.")
    price: float = Field(
        ..., ge=0, description="Current stock price."
    )  # No negative prices
    timestamp: str = Field(..., description="Timestamp of the fetch.")


# ─────────────────────────────────────────────────────────────────────────────
# fetch_financials
# ─────────────────────────────────────────────────────────────────────────────
class FinancialsResult(BaseModel):
    """Return contract for fetch_financials. Optional fields absent from yfinance are None."""

    status: str = Field(default="success")
    ticker: str = Field(..., description="Stock ticker symbol.")
    timestamp: str = Field(..., description="Timestamp of the fetch.")
    # Annual/TTM from Ticker.info
    total_revenue: float | None = None
    revenue_per_share: float | None = None
    net_income: float | None = None
    gross_profits: float | None = None
    ebitda: float | None = None
    total_debt: float | None = None
    total_cash: float | None = None
    free_cash_flow: float | None = None
    operating_cash_flow: float | None = None
    market_cap: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    # Latest quarter (from quarterly_income_stmt)
    latest_quarter_end: str | None = None
    latest_quarter_revenue: float | None = None
    latest_quarter_net_income: float | None = None
    # Company profile (for intro)
    sector: str | None = None
    industry: str | None = None
    long_business_summary: str | None = None
    market_cap_category: str | None = None  # e.g. "Mega Cap", "Large Cap", "Mid Cap", "Small Cap", "Micro Cap"


# ─────────────────────────────────────────────────────────────────────────────
# fetch_technical_indicators
# ─────────────────────────────────────────────────────────────────────────────
class MACDValues(BaseModel):
    """MACD indicator sub-components."""

    line: float = Field(..., description="MACD line (EMA12 − EMA26).")
    signal: float = Field(..., description="Signal line (EMA9 of MACD line).")
    histogram: float = Field(..., description="MACD histogram (line − signal).")


class TechnicalIndicatorsResult(BaseModel):
    """Return contract for fetch_technical_indicators."""

    status: str = Field(default="success")
    ticker: str = Field(..., description="Stock ticker symbol.")
    timestamp: str = Field(..., description="Timestamp of the fetch.")
    sma_20: float = Field(..., description="20-day simple moving average.")
    sma_50: float = Field(..., description="50-day simple moving average.")
    macd: MACDValues = Field(..., description="MACD indicator values.")
    rsi_14: float = Field(..., description="14-day RSI (0-100).")


# ─────────────────────────────────────────────────────────────────────────────
# fetch_vix
# ─────────────────────────────────────────────────────────────────────────────
class VIXResult(BaseModel):
    """Return contract for fetch_vix."""

    status: str = Field(default="success")
    vix: float = Field(..., description="Current VIX value.")
    previous_close: float = Field(..., description="Previous closing VIX value.")
    change: float = Field(..., description="Change from previous close.")
    change_percent: float = Field(..., description="Percentage change.")
    level: str = Field(..., description="Level: Low, Normal, Elevated, High, Extreme.")
    sentiment: str = Field(..., description="Sentiment label.")
    signal: str = Field(
        ..., description="Signal: GREED, NEUTRAL, FEAR, HIGH_FEAR, EXTREME_FEAR."
    )
    interpretation: str = Field(..., description="Human-readable interpretation.")


# ─────────────────────────────────────────────────────────────────────────────
# fetch_cnn_greedy
# ─────────────────────────────────────────────────────────────────────────────
class CNNFearGreedResult(BaseModel):
    """Return contract for fetch_cnn_greedy."""

    status: str = Field(default="success")
    score: int = Field(..., ge=0, le=100, description="Fear & Greed score (0-100).")
    rating: str = Field(..., description="Rating label.")
    interpretation: str = Field(..., description="Human-readable interpretation.")


# ─────────────────────────────────────────────────────────────────────────────
# fetch_stocktwits_sentiment
# ─────────────────────────────────────────────────────────────────────────────
class StockTwitsSentimentResult(BaseModel):
    """Return contract for fetch_stocktwits_sentiment."""

    status: str = Field(default="success")
    ticker: str = Field(..., description="Stock ticker symbol.")
    title: str | None = Field(default=None, description="Company name from StockTwits.")
    message_count: int = Field(..., ge=0, description="Number of messages analyzed.")
    bullish: int = Field(..., ge=0, description="Bullish message count.")
    bearish: int = Field(..., ge=0, description="Bearish message count.")
    neutral: int = Field(..., ge=0, description="Neutral message count.")
    sentiment_ratio: float | None = Field(
        default=None, description="Bullish ratio (0-1). None if no data."
    )
    signal: str = Field(
        ..., description="Signal: STRONG_BULLISH to STRONG_BEARISH, or NO_DATA."
    )
    watchers: int | None = Field(
        default=None, description="StockTwits watchlist count."
    )
    interpretation: str = Field(..., description="Human-readable interpretation.")


# ─────────────────────────────────────────────────────────────────────────────
# fetch_options_analysis — sub-components
# ─────────────────────────────────────────────────────────────────────────────
class PutCallRatio(BaseModel):
    """Put/Call ratio breakdown by open interest and volume."""

    pcr_open_interest: float | None = Field(
        default=None, description="PCR by open interest."
    )
    pcr_volume: float | None = Field(default=None, description="PCR by volume.")
    signal: str = Field(
        ..., description="Signal: BULLISH, NEUTRAL, CAUTIOUS, BEARISH, NO_DATA."
    )
    total_call_oi: int = Field(..., description="Total call open interest.")
    total_put_oi: int = Field(..., description="Total put open interest.")
    total_call_volume: int = Field(..., description="Total call volume.")
    total_put_volume: int = Field(..., description="Total put volume.")


class MaxPain(BaseModel):
    """Max pain calculation result."""

    strike: float | None = Field(default=None, description="Max pain strike price.")
    current_price: float = Field(..., description="Current stock price.")
    distance_pct: float | None = Field(
        default=None,
        description="Percentage distance from current price to max pain.",
    )


class UnusualContract(BaseModel):
    """A single unusually active options contract."""

    strike: float
    expiry: str
    side: str  # "call" or "put"
    volume: int
    open_interest: int
    vol_oi_ratio: float


class UnusualActivity(BaseModel):
    """Unusual options activity summary."""

    count: int = Field(..., ge=0, description="Total unusual contracts found.")
    top_contracts: list[UnusualContract] = Field(
        default_factory=list, description="Top unusual contracts by vol/OI ratio."
    )
    summary: str = Field(..., description="Summary of unusual activity.")


class IVMetrics(BaseModel):
    """Implied and historical volatility metrics."""

    iv_mean: float | None = Field(
        default=None, description="Volume-weighted avg implied volatility (%)."
    )
    hv30: float | None = Field(
        default=None, description="30-day historical volatility (%)."
    )
    iv_rank: int | None = Field(default=None, description="IV Rank (0-100).")
    iv_vs_hv: str = Field(
        ..., description="Comparison: OVERPRICED, FAIR, UNDERPRICED, UNKNOWN."
    )
    interpretation: str = Field(..., description="Human-readable IV interpretation.")


# ─────────────────────────────────────────────────────────────────────────────
# fetch_options_analysis — top-level result
# ─────────────────────────────────────────────────────────────────────────────
class OptionsAnalysisResult(BaseModel):
    """Return contract for fetch_options_analysis."""

    status: str = Field(default="success")
    ticker: str = Field(..., description="Stock ticker symbol.")
    timestamp: str = Field(..., description="Timestamp of the analysis.")
    expirations_analyzed: list[str] = Field(
        ..., description="Expiration dates analyzed."
    )
    put_call_ratio: PutCallRatio
    max_pain: MaxPain
    unusual_activity: UnusualActivity
    implied_volatility: IVMetrics
    interpretation: str = Field(..., description="Overall options interpretation.")


# ─────────────────────────────────────────────────────────────────────────────
# fetch_technicals_with_chart — sub-components
# ─────────────────────────────────────────────────────────────────────────────
class TechnicalsIndicators(BaseModel):
    """Indicator values extracted by fetch_technicals_with_chart."""

    rsi_14: float | None = None
    sma_20: float | None = None
    sma_50: float | None = None
    macd: MACDValues | None = None


class TechnicalsSignals(BaseModel):
    """Rule-based signals computed from indicators."""

    rsi_signal: str | None = None
    macd_signal: str | None = None
    macd_crossover: str | None = None
    sma_trend: str | None = None


class ChartEntry(BaseModel):
    """Chart generation result for one timeframe."""

    label: str = Field(..., description="Chart label, e.g. '1-Year Daily'.")
    result: str = Field(..., description="Chart generation status / artifact path.")


# ─────────────────────────────────────────────────────────────────────────────
# fetch_technicals_with_chart — top-level result
# ─────────────────────────────────────────────────────────────────────────────
class TechnicalsWithChartResult(BaseModel):
    """Return contract for fetch_technicals_with_chart."""

    status: str = Field(default="success")
    ticker: str = Field(..., description="Stock ticker symbol.")
    timestamp: str = Field(..., description="Timestamp of the fetch.")
    indicators: TechnicalsIndicators
    signals: TechnicalsSignals
    charts: dict[str, ChartEntry] = Field(
        ..., description="Charts keyed by timeframe (e.g. '1y', '3mo')."
    )


# ─────────────────────────────────────────────────────────────────────────────
# invalidate_cache
# ─────────────────────────────────────────────────────────────────────────────
class InvalidateCacheResult(BaseModel):
    """Return contract for invalidate_cache."""

    status: str = Field(default="success")
    ticker: str = Field(..., description="Ticker that was invalidated.")
    entries_cleared: int = Field(
        ..., ge=0, description="Number of cache entries removed."
    )
    message: str = Field(..., description="Human-readable confirmation.")


# ─────────────────────────────────────────────────────────────────────────────
# fetch_reddit
# ─────────────────────────────────────────────────────────────────────────────
class RedditPostEntry(BaseModel):
    """Single Reddit post (title, link, 1-2 line excerpt)."""

    subreddit: str = Field(..., description="Subreddit name, e.g. r/wallstreetbets.")
    title: str = Field(..., description="Post title.")
    url: str = Field(..., description="URL to the post.")
    snippet: str = Field(
        default="",
        description="1-2 line excerpt of the post body (plain text). Empty if link-only.",
    )


class RedditPostsResult(BaseModel):
    """Return contract for fetch_reddit."""

    status: str = Field(default="success")
    ticker: str = Field(..., description="Stock ticker queried.")
    posts: list[RedditPostEntry] = Field(
        default_factory=list,
        description="All posts (top N per subreddit) with title and url.",
    )
    by_subreddit: dict[str, list[RedditPostEntry]] = Field(
        default_factory=dict,
        description="Posts grouped by subreddit.",
    )
    subreddits_queried: list[str] = Field(
        default_factory=list,
        description="Subreddits that were queried.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# search_cache_stats
# ─────────────────────────────────────────────────────────────────────────────
class CacheStatsResult(BaseModel):
    """Return contract for search_cache_stats."""

    status: str = Field(default="success")
    distinct_stocks: int = Field(
        ..., ge=0, description="Number of unique tickers with cached data."
    )
    total_entries: int = Field(
        ..., ge=0, description="Total number of cached data entries (price, financials, technicals, etc.)."
    )
    tickers: list[str] = Field(
        ..., description="List of ticker symbols currently in cache."
    )
