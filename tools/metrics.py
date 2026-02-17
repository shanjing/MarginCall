"""
Central Prometheus metric definitions for MarginCall.

All metrics are defined here and imported by instrumentation points.
Metric naming convention: margincall_{subsystem}_{metric}_{unit}

Import guard: the app runs fine without prometheus_client installed.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Gauge, Histogram

    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False
    logger.info("prometheus_client not installed; metrics disabled")

if METRICS_ENABLED:
    # ── Tool layer ─────────────────────────────────────────────────────
    tool_calls_total = Counter(
        "margincall_tool_calls_total",
        "Tool invocations",
        ["tool_name", "cache_hit"],
    )
    tool_duration_seconds = Histogram(
        "margincall_tool_duration_seconds",
        "Tool execution time",
        ["tool_name"],
        buckets=[0.1, 0.5, 1, 2, 5, 10, 15, 30, 60],
    )
    tool_errors_total = Counter(
        "margincall_tool_errors_total",
        "Tool errors",
        ["tool_name"],
    )

    # ── Cache economics ────────────────────────────────────────────────
    cache_operations_total = Counter(
        "margincall_cache_ops_total",
        "Cache operations",
        ["operation", "result"],
    )

    # ── Truncation ─────────────────────────────────────────────────────
    truncation_events_total = Counter(
        "margincall_truncation_total",
        "Truncation events",
        ["tool_name"],
    )

    # ── Run layer ──────────────────────────────────────────────────────
    run_duration_seconds = Histogram(
        "margincall_run_duration_seconds",
        "Full pipeline run time",
        buckets=[1, 5, 10, 20, 30, 45, 60, 90, 120, 180, 300],
    )
    run_total = Counter(
        "margincall_runs_total",
        "Total agent runs",
        ["status"],
    )

    # ── LLM cost ───────────────────────────────────────────────────────
    llm_tokens_total = Counter(
        "margincall_llm_tokens_total",
        "LLM tokens consumed",
        ["direction", "model"],
    )
    llm_call_duration_seconds = Histogram(
        "margincall_llm_call_duration_seconds",
        "LLM inference time",
        ["model"],
        buckets=[0.5, 1, 2, 5, 10, 20, 30, 60],
    )

    # ── Infrastructure ─────────────────────────────────────────────────
    active_sse_connections = Gauge(
        "margincall_active_sse_connections",
        "Currently connected SSE log stream clients",
    )
