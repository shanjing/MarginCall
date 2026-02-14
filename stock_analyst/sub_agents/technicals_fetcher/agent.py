"""
technicals_fetcher – sub-agent that fetches technical indicators and generates the trading chart.
"""

from google.adk.agents import LlmAgent

from agent_tools.fetch_technical_indicators import fetch_technical_indicators
from agent_tools.generate_trading_chart import generate_trading_chart
from tools.config import AI_MODEL
from tools.save_artifacts import save_artifacts

from .prompts import INSTRUCTION as TECHNICALS_FETCHER_INSTRUCTION

technicals_fetcher = LlmAgent(
    name="technicals_fetcher",
    model=AI_MODEL,
    description="Fetches technical indicators (RSI, MACD, SMAs) and generates TradingView-style charts.",
    instruction=TECHNICALS_FETCHER_INSTRUCTION,
    tools=[fetch_technical_indicators, generate_trading_chart, save_artifacts],
    output_key="technical_report",
)