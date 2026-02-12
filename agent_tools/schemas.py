"""
LLM output schemas — structured output contracts for agent responses.

LAYER 2 of the two-layer schema architecture:
  • tool_schemas.py  → what tool functions return (raw data contracts)
  • schemas.py       → what the LLM produces (report structure, analyzed output)

These schemas are used with LlmAgent's output_schema parameter to enforce
structured JSON output. See misc/adk/use_tools_with_schema.md for design rationale.
"""

from typing import Literal

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# News article (used in StockReport)
# ─────────────────────────────────────────────────────────────────────────────
class NewsArticle(BaseModel):
    """A single news article in the report."""

    title: str = Field(..., description="The title of the news article.")
    url: str = Field(..., description="The URL of the news article.")
    snippet: str = Field(..., description="The snippet of the news article.")
    date: str = Field(..., description="The date of the news article.")


# ─────────────────────────────────────────────────────────────────────────────
# Reddit post (used in StockReport)
# ─────────────────────────────────────────────────────────────────────────────
class RedditPost(BaseModel):
    """A single Reddit post in the report (title, link, short excerpt)."""

    subreddit: str = Field(..., description="Subreddit, e.g. r/wallstreetbets.")
    title: str = Field(..., description="Post title.")
    url: str = Field(..., description="URL to the post.")
    snippet: str = Field(
        default="",
        description="1-2 line excerpt of the post body. Empty if link-only.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Rating recommendation
# ─────────────────────────────────────────────────────────────────────────────
class StockRating(BaseModel):
    """Rating recommendation for a stock."""

    recommendation: Literal["Buy", "Sell", "Hold"] = Field(
        ..., description="The recommendation: Buy, Sell, or Hold."
    )
    confidence_percent: int = Field(
        ...,
        ge=0,
        le=100,
        description="Confidence level as a percentage (0-100).",
    )
    rationale: str = Field(..., description="Brief explanation for the rating.")


# ─────────────────────────────────────────────────────────────────────────────
# Sentiment analysis (4 indicators)
# ─────────────────────────────────────────────────────────────────────────────
class SentimentAnalysis(BaseModel):
    """Sentiment analysis section of the report (4 indicators)."""

    cnn_fear_greed_score: int = Field(
        ..., ge=0, le=100, description="CNN Fear & Greed score (0-100)."
    )
    cnn_fear_greed_rating: str = Field(
        ...,
        description="CNN rating: Extreme Fear, Fear, Neutral, Greed, Extreme Greed.",
    )
    vix_value: float = Field(..., description="VIX value.")
    vix_signal: str = Field(
        ..., description="VIX signal: GREED, NEUTRAL, FEAR, HIGH_FEAR, EXTREME_FEAR."
    )
    stocktwits_ratio: float = Field(
        ..., ge=0, le=1, description="StockTwits bullish ratio (0-1)."
    )
    stocktwits_signal: str = Field(
        ..., description="StockTwits signal: STRONG_BULLISH to STRONG_BEARISH."
    )
    pcr_volume: float = Field(
        ..., ge=0, description="Put/Call volume ratio (< 0.7 bullish, > 1.3 bearish)."
    )
    pcr_signal: str = Field(
        ..., description="PCR signal: BULLISH, NEUTRAL, CAUTIOUS, BEARISH."
    )
    overall_market_sentiment: Literal["BULLISH", "BEARISH", "NEUTRAL", "MIXED"] = Field(
        ..., description="Combined market sentiment from all 4 indicators."
    )
    sentiment_summary: str = Field(
        ..., description="1-2 sentence summary of market sentiment."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Key financial metrics (structured block in StockReport)
# ─────────────────────────────────────────────────────────────────────────────
class FinancialsSection(BaseModel):
    """Structured key financial metrics for the report. Use session.state financials; use null when missing."""

    trailing_pe: float | None = Field(
        None, description="Current (trailing) P/E ratio. Null if unavailable."
    )
    forward_pe: float | None = Field(
        None, description="Forward P/E ratio. Null if unavailable."
    )
    total_revenue: float | None = Field(
        None, description="Total revenue (TTM or latest fiscal year). Null if unavailable."
    )
    net_income: float | None = Field(
        None, description="Net income (TTM or latest fiscal year). Null if unavailable."
    )
    free_cash_flow: float | None = Field(
        None, description="Free cash flow. Null if unavailable."
    )
    operating_cash_flow: float | None = Field(
        None, description="Operating cash flow. Null if unavailable."
    )
    market_cap: float | None = Field(None, description="Market cap. Null if unavailable.")
    latest_quarter_end: str | None = Field(
        None, description="Latest quarter period end (e.g. 2025-09-30). Null if unavailable."
    )
    latest_quarter_revenue: float | None = Field(
        None, description="Revenue for latest quarter. Null if unavailable."
    )
    latest_quarter_net_income: float | None = Field(
        None, description="Net income for latest quarter. Null if unavailable."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Options analysis (short-term volatility section)
# ─────────────────────────────────────────────────────────────────────────────
class OptionsAnalysis(BaseModel):
    """Options analytics section of the report (short-term volatility)."""

    pcr_open_interest: float = Field(
        ..., ge=0, description="Put/Call open interest ratio."
    )
    pcr_volume: float = Field(..., ge=0, description="Put/Call volume ratio.")
    pcr_signal: str = Field(
        ..., description="PCR signal: BULLISH, NEUTRAL, CAUTIOUS, BEARISH."
    )
    max_pain_strike: float = Field(..., description="Max pain strike price.")
    max_pain_distance_pct: float = Field(
        ..., description="Distance from current price to max pain (%)."
    )
    unusual_activity_count: int = Field(
        ..., ge=0, description="Number of contracts with unusual volume/OI."
    )
    unusual_activity_summary: str = Field(
        ..., description="Summary of unusual options activity."
    )
    iv_mean: float = Field(
        ..., description="Volume-weighted average implied volatility (%)."
    )
    hv30: float = Field(..., description="30-day historical volatility (%).")
    iv_rank: int = Field(
        ..., ge=0, le=100, description="IV Rank (0-100), approx based on HV range."
    )
    iv_vs_hv: Literal["OVERPRICED", "FAIR", "UNDERPRICED", "UNKNOWN"] = Field(
        ...,
        description="Whether options are overpriced, fair, or underpriced vs historical vol.",
    )
    options_summary: str = Field(
        ..., description="2-3 sentence summary of options landscape."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Final stock report (used as output_schema for report_synthesizer)
# ─────────────────────────────────────────────────────────────────────────────
class StockReport(BaseModel):
    """Final stock analysis report output."""

    # Report header
    title: str = Field(..., description="Report title, e.g. 'Stock Analysis: AAPL'.")
    ticker: str = Field(..., description="The stock ticker symbol.")
    date: str = Field(..., description="Date of the report (YYYY-MM-DD).")
    analyst: str = Field(default="Sam Rogers", description="Name of the analyst.")
    firm: str = Field(
        default="DiamondHands 💎🙌 Entertainment Group", description="Name of the firm."
    )

    # Analysis sections
    company_intro: str = Field(
        ...,
        description="Brief introduction: what the company does, sector (e.g. Technology, Energy, Banking), and cap size (e.g. Large Cap). One paragraph, max 4 lines.",
    )
    price_summary: str = Field(
        ..., description="Summary of current price and recent movement."
    )
    financials_summary: str = Field(
        ..., description="1-2 sentence summary of key financial metrics."
    )
    financials: FinancialsSection = Field(
        ..., description="Structured key financial data: P/E, revenue, earnings, cash flow, latest quarter."
    )
    technicals_summary: str = Field(
        ..., description="Summary of technical indicators and signals."
    )
    sentiment: SentimentAnalysis = Field(
        ..., description="Market sentiment analysis from 4 indicators."
    )
    options_analysis: OptionsAnalysis = Field(
        ...,
        description="Options analytics: put/call ratio, max pain, IV, unusual activity.",
    )
    news_summary: str = Field(
        ..., description="1-2 sentence summary of overall news sentiment."
    )
    news_articles: list[NewsArticle] = Field(
        ..., description="List of recent news articles (title, url, snippet, date)."
    )
    reddit_posts: list[RedditPost] = Field(
        default_factory=list,
        description="Top Reddit posts about the stock (title, url, subreddit) from r/wallstreetbets, r/stocks, r/redditstock.",
    )

    # Earnings date
    next_earnings_date: str | None = Field(
        default=None,
        description="Next earnings date (YYYY-MM-DD). None if unavailable.",
    )
    days_until_earnings: int | None = Field(
        default=None,
        description="Days until next earnings. None if unavailable.",
    )

    # Final verdict
    rating: StockRating = Field(..., description="The final rating recommendation.")
    conclusion: str = Field(
        ..., description="Final conclusion and investment thesis (2-3 sentences)."
    )
