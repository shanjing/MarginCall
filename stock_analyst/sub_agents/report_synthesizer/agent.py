"""
report_synthesizer – sub-agent that produces the final stock report from fetcher outputs.

Uses 80/20 weighting rule:
- 80% weight: Overall Market Sentiment (CNN Fear & Greed, VIX, StockTwits, Put/Call Ratio)
- 20% weight: Individual Stock Performance (price, financials, technicals)
"""

from agent_tools.schemas import StockReport
from google.adk.agents import LlmAgent
from tools.config import AI_MODEL

from .prompts import INSTRUCTION as REPORT_SYNTHESIZER_INSTRUCTION

report_synthesizer = LlmAgent(
    name="report_synthesizer",
    model=AI_MODEL,
    description="Senior analyst that synthesizes data into a report with weighted recommendations",
    instruction=REPORT_SYNTHESIZER_INSTRUCTION,
    # StockReport schema is the only place where schemas are used.
    # ADK does not support tools and output_schema together;
    # so we use output_schema only on agents without tools.
    output_schema=StockReport,
    output_key="stock_report",
)
