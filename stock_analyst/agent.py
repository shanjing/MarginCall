"""
stock_analyst – supervisor/root agent (MarginCall-style).

Architecture:
- root_agent (LlmAgent supervisor): Greets, decides if stock research or chat
  - If stock research: calls stock_analysis_pipeline
  - If general chat: responds directly, no tools called
- stock_analysis_pipeline (SequentialAgent): Full analysis flow
  - stock_data_agent: Fetches all data
  - report_synthesizer: Produces structured report
  - closer_agent: Renders report beautifully
"""

import contextvars
import time as _time

from agent_tools.fetch_cnn_greedy import fetch_cnn_greedy
from agent_tools.fetch_earnings_date import fetch_earnings_date
from agent_tools.fetch_financials import fetch_financials
from agent_tools.fetch_options_analysis import fetch_options_analysis
from agent_tools.fetch_reddit import fetch_reddit
from agent_tools.fetch_stocktwits_sentiment import fetch_stocktwits_sentiment
from agent_tools.fetch_vix import fetch_vix
from agent_tools.invalidate_cache import invalidate_cache
from agent_tools.search_cache_stats import search_cache_stats
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import AgentTool
from tools.config import AI_MODEL

from .prompts import ROOT_INSTRUCTION
from .sub_agents.presenter import presenter
from .sub_agents.report_synthesizer import report_synthesizer
from .sub_agents.stock_analysis_pipeline import stock_analysis_pipeline
from .sub_agents.stock_data_collector import stock_data_collector

# ── Prometheus LLM callbacks ──────────────────────────────────────────────────
_llm_call_start: contextvars.ContextVar[float] = contextvars.ContextVar(
    "llm_call_start", default=0.0
)


def _before_model_callback(callback_context, llm_request):
    """Record LLM call start time for latency tracking."""
    _llm_call_start.set(_time.perf_counter())


def _after_model_callback(callback_context, llm_response):
    """Record LLM token usage and call latency via Prometheus metrics."""
    try:
        from tools.metrics import METRICS_ENABLED
        if not METRICS_ENABLED:
            return
        from tools.metrics import llm_call_duration_seconds, llm_tokens_total

        model = str(AI_MODEL) if not hasattr(AI_MODEL, "model") else AI_MODEL.model

        # Token usage
        usage = getattr(llm_response, "usage_metadata", None)
        if usage:
            input_tokens = getattr(usage, "prompt_token_count", 0) or 0
            output_tokens = getattr(usage, "candidates_token_count", 0) or 0
            llm_tokens_total.labels(direction="input", model=model).inc(input_tokens)
            llm_tokens_total.labels(direction="output", model=model).inc(output_tokens)

        # Call duration
        start = _llm_call_start.get(0.0)
        if start > 0:
            llm_call_duration_seconds.labels(model=model).observe(
                _time.perf_counter() - start
            )
    except Exception:  # noqa: BLE001
        pass


# Root agent decides: research, chat, refresh, cache stats, or single-tool calls.
root_agent = LlmAgent(
    name="stock_analyst",
    model=AI_MODEL,
    description="Sam Rogers - Stock data research supervisor",
    instruction=ROOT_INSTRUCTION,
    tools=[
        AgentTool(agent=stock_analysis_pipeline),
        fetch_earnings_date,
        fetch_financials,
        fetch_options_analysis,
        fetch_cnn_greedy,
        fetch_vix,
        fetch_stocktwits_sentiment,
        fetch_reddit,
        invalidate_cache,
        search_cache_stats,
    ],
    before_model_callback=_before_model_callback,
    after_model_callback=_after_model_callback,
)
