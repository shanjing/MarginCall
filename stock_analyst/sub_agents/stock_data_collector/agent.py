from agent_tools.fetch_cnn_greedy import fetch_cnn_greedy
from agent_tools.fetch_earnings_date import fetch_earnings_date
from agent_tools.fetch_financials import fetch_financials
from agent_tools.fetch_options_analysis import fetch_options_analysis
from agent_tools.fetch_reddit import fetch_reddit
from agent_tools.fetch_stock_price import fetch_stock_price
from agent_tools.fetch_stocktwits_sentiment import fetch_stocktwits_sentiment
from agent_tools.fetch_technicals_with_chart import fetch_technicals_with_chart
from agent_tools.fetch_vix import fetch_vix
from google.adk.agents import LlmAgent
from google.adk.planners.built_in_planner import BuiltInPlanner
from google.adk.tools import AgentTool
from google.genai import types
from tools.config import AI_MODEL, INCLUDE_THOUGHTS

from ..news_fetcher import news_fetcher

stock_data_collector = LlmAgent(
    name="stock_data_collector",
    model=AI_MODEL,
    description="Fetches stock data: price, financials, technicals, options, news, and market sentiment",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.5,
        max_output_tokens=1000,
    ),
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(include_thoughts=INCLUDE_THOUGHTS)
    ),
    instruction="""
    You are a stock data collector at DiamondHands 💎🙌 Group.
    Fetch all data for the given stock ticker.

    You have 10 tools organized in 4 groups:

    STOCK DATA (function tools):
    - fetch_stock_price: current price and quote
    - fetch_financials: financial statements and ratios
    - fetch_technicals_with_chart: technical indicators + two charts (1yr + 90d)
    - fetch_earnings_date: next upcoming earnings date for the ticker

    SENTIMENT & OPTIONS DATA (function tools):
    - fetch_cnn_greedy: CNN Fear & Greed Index (overall market mood)
    - fetch_vix: VIX volatility index (market fear gauge)
    - fetch_stocktwits_sentiment: social sentiment for the ticker
    - fetch_options_analysis: options analytics (put/call ratio, max pain, IV, unusual activity)

    REDDIT (function tool):
    - fetch_reddit: top 3 posts per source from r/wallstreetbets, r/stocks. Pass ticker; if the user asked for real-time/refresh/fresh/live data, also pass real_time=True so Reddit is queried live (not from cache).

    NEWS (agent tool):
    - news_fetcher: recent news for the ticker (uses web search)

    For every stock ticker you MUST:
    1. Call ALL 10 tools
    2. Pass the ticker symbol to tools that need it
    3. For fetch_technicals_with_chart, just pass the ticker (it auto-generates 1yr + 90d charts)
    4. For fetch_reddit: pass the ticker; if the user's request indicates real-time or fresh data (e.g. refresh, real-time, live, update), pass real_time=True so Reddit is fetched from the API instead of cache.

    IMPORTANT: Call function tools in parallel when possible:
    - Group 1 (parallel): fetch_stock_price, fetch_financials, fetch_technicals_with_chart, fetch_earnings_date
    - Group 2 (parallel): fetch_cnn_greedy, fetch_vix, fetch_stocktwits_sentiment, fetch_options_analysis, fetch_reddit
    - Group 3: news_fetcher (agent tool)

    Store results in session.state (output_key=stock_data):
    {
        "ticker": {
            "price": <fetch_stock_price result>,
            "financials": <fetch_financials result>,
            "technicals": <fetch_technicals_with_chart result>,
            "cnn_fear_greed": <fetch_cnn_greedy result>,
            "vix": <fetch_vix result>,
            "stocktwits": <fetch_stocktwits_sentiment result>,
            "options_analysis": <fetch_options_analysis result>,
            "reddit": <fetch_reddit result>,
            "news": <news_fetcher result>,
            "earnings_date": <fetch_earnings_date result>
        }
    }
    """,
    tools=[
        # Stock data tools
        fetch_stock_price,
        fetch_financials,
        fetch_technicals_with_chart,
        fetch_earnings_date,
        # Sentiment & options tools
        fetch_cnn_greedy,
        fetch_vix,
        fetch_stocktwits_sentiment,
        fetch_options_analysis,
        # Reddit
        fetch_reddit,
        # News agent tool
        AgentTool(agent=news_fetcher),
    ],
    # NOTE: Cannot use output_schema here - automatic function calling fails to parse
    # nested schema (StockDataTicker). Use instruction-based structure instead.
    output_key="stock_data",
)
