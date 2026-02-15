"""
price_fetcher – sub-agent that fetches stock price.
"""

from google.adk.agents import LlmAgent

from agent_tools.fetch_stock_price import fetch_stock_price
from tools.config import AI_MODEL

from .prompts import INSTRUCTION as PRICE_FETCHER_INSTRUCTION

price_fetcher = LlmAgent(
    name="price_fetcher",
    model=AI_MODEL,
    description="A stock price fetcher agent",
    instruction=PRICE_FETCHER_INSTRUCTION,
    tools=[fetch_stock_price],
    output_key="stock_price",
)
