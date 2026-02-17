"""
report_synthesizer – sub-agent that produces the final stock report from fetcher outputs.

Rules (weighting, etc.) are read from report_rules.json via .rules. Add new top-level keys for new rules.
"""

from agent_tools.schemas import StockReport
from google.adk.agents import LlmAgent
from tools.config import AI_MODEL

from .prompts import INSTRUCTION as REPORT_SYNTHESIZER_INSTRUCTION
from .rules import MARKET_SENTIMENT_PCT, STOCK_PERFORMANCE_PCT

report_synthesizer = LlmAgent(
    name="report_synthesizer",
    model=AI_MODEL,
    description=(
        f"Senior analyst that synthesizes data into a report with weighted recommendations "
        f"({MARKET_SENTIMENT_PCT}% market sentiment, {STOCK_PERFORMANCE_PCT}% stock performance)."
    ),
    instruction=REPORT_SYNTHESIZER_INSTRUCTION,
    # StockReport schema is the only place where schemas are used.
    # ADK does not support tools and output_schema together;
    # so we use output_schema only on agents without tools.
    output_schema=StockReport,
    output_key="stock_report",
)
