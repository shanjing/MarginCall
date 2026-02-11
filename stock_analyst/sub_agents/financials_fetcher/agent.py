""" 
financials_fetcher – sub-agent that fetches financials for a stock
"""

from google.adk.agents import LlmAgent

from tools.config import AI_MODEL
from agent_tools.fetch_financials import fetch_financials

# For consistency, python variable and agent name are identical
financials_fetcher = LlmAgent(
    name="financials_fetcher",
    model=AI_MODEL,
    description="A financials fetcher agent",
    instruction="""
    You are a financials fetcher agent.
    You will be given a stock symbol.
    Use the 'fetch_financials' tool to fetch the financial metrics (revenue, net income, debt, cash, market cap, ratios).
    The financials must be from the most recent quarter from today's date.
    If today's date is the earning report date, then the financials must be from the previous quarter.
    If the financials are not available, do not make up any data.
    Return the financials in the 'financials' output key with the following format:
    {
        "status": "success",
        "financials": {
            "total_revenue": ...,
            "net_income": ...,
            ...
        }
    }
    If the tool fails, return the error message in the 'error_message' output key with the following format:
    {
        "status": "error",
        "error_message": "Error fetching financials: Error message"
    }
    """,
    tools=[fetch_financials],
    output_key="financials",
)
