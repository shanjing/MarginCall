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

from .prompts import INSTRUCTION as STOCK_DATA_COLLECTOR_INSTRUCTION

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
    instruction=STOCK_DATA_COLLECTOR_INSTRUCTION,
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
