"""
price_fetcher – sub-agent (placeholder).
"""

from google.adk.agents import LlmAgent

from tools.config import AI_MODEL
from agent_tools.fetch_stock_price import fetch_stock_price

# For consistency, python variable and agent name are identical
price_fetcher = LlmAgent(
    name="price_fetcher",
    model=AI_MODEL,
    description="A stock price fetcher agent",
    instruction="""
        You are a stock price fetcher agent.
        You will be given a stock symbol.
        Use the 'fetch_stock_price' tool to fetch the stock price.
        Return the stock price in the 'stock_price' output key with the following format:
        {
            "status": "success",
            "ticker": "AAPL",
            "price": 150.75,
            "timestamp": "2026-01-28 10:00:00"
        }
        If the tool fails, return the error message in the 'error_message' output key with the following format:
        {
            "status": "error",
            "error_message": "Error fetching stock price: Error message"
        }
    """,
    tools=[fetch_stock_price],
    output_key="stock_price",
)
