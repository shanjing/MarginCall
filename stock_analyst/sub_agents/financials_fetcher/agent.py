"""financials_fetcher – sub-agent that fetches financials for a stock."""

from google.adk.agents import LlmAgent

from agent_tools.fetch_financials import fetch_financials
from tools.config import AI_MODEL

from .prompts import INSTRUCTION as FINANCIALS_FETCHER_INSTRUCTION

financials_fetcher = LlmAgent(
    name="financials_fetcher",
    model=AI_MODEL,
    description="A financials fetcher agent",
    instruction=FINANCIALS_FETCHER_INSTRUCTION,
    tools=[fetch_financials],
    output_key="financials",
)
