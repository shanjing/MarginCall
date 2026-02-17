"""Load report_rules.json. Single source of truth for report_synthesizer rules."""

import json
from pathlib import Path

_RULES_PATH = Path(__file__).resolve().parent / "report_rules.json"
with _RULES_PATH.open() as f:
    REPORT_RULES = json.load(f)

_weighting = REPORT_RULES.get("recommendation_weighting", {})
MARKET_SENTIMENT_PCT = _weighting.get("market_sentiment_pct", 60)
STOCK_PERFORMANCE_PCT = _weighting.get("stock_performance_pct", 40)
