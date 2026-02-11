"""
technicals_fetcher – sub-agent that fetches technical indicators and generates the trading chart.
"""

from google.adk.agents import LlmAgent

from tools.config import AI_MODEL
from agent_tools.fetch_technical_indicators import fetch_technical_indicators
from agent_tools.generate_trading_chart import generate_trading_chart
from tools.save_artifacts import save_artifacts


technicals_fetcher = LlmAgent(
    name="technicals_fetcher",
    model=AI_MODEL,
    description="Fetches technical indicators (RSI, MACD, SMAs) and generates TradingView-style charts.",
    instruction="""
    You are a technical analysis specialist. Your tasks:

    1. **Fetch technical indicators**: Use 'fetch_technical_indicators' for the given ticker to get RSI, MACD, and SMA values.

    2. **Generate and save the chart**: Use 'generate_trading_chart' for the same ticker to create a TradingView-style chart (candlesticks, volume, RSI, MACD, SMAs). Pass timeframe (e.g. '6mo', '1y', '2y'); default is '1y'. 
    
    3. **Then use 'save_artifacts' to save the chart so it displays in the ADK UI.

    3. **Summarize**: Return the technical indicators in a structured format (RSI overbought/oversold, MACD momentum, SMA levels) and confirm the chart was generated. Emit your analysis in the 'technical_report' output.
    """,
    tools=[fetch_technical_indicators, generate_trading_chart, save_artifacts],
    output_key="technical_report",
)