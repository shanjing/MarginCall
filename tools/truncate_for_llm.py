"""
Limit string sizes in tool return values so they stay safe for LLM context.

Tool outputs are merged into session.state and passed to the report synthesizer.
Very long strings (e.g. Reddit snippets with thousands of newlines) can blow
token count and cause truncated JSON. This module recursively caps every string
in a dict/list so the overall payload stays bounded.

When truncation happens, sets a context var so tools can add truncation_applied
to their return, and logs dataset/path and sizes (same visibility as cache hits).
"""

from __future__ import annotations

import contextvars
from typing import Any

from tools.logging_utils import logger


def _inc_truncation_metric(tool_name: str) -> None:
    """Increment Prometheus truncation counter."""
    try:
        from tools.metrics import METRICS_ENABLED
        if METRICS_ENABLED:
            from tools.metrics import truncation_events_total
            truncation_events_total.labels(tool_name=tool_name).inc()
    except Exception:  # noqa: BLE001
        pass

# Context var: set to True when any truncation happens (Pydantic or truncate_strings_for_llm).
# Tools reset at start and read at end to set truncation_applied in their return.
_truncation_occurred: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "truncation_occurred", default=False
)


def reset_tool_truncation_occurred() -> None:
    """Reset at start of a tool so truncation_applied reflects only this tool's run."""
    _truncation_occurred.set(False)


def get_tool_truncation_occurred() -> bool:
    """True if truncation happened during this tool run (Pydantic or truncate_strings_for_llm)."""
    return _truncation_occurred.get()


def _set_truncation_occurred() -> None:
    _truncation_occurred.set(True)


# Max bytes per string field. Keeps snippets/summaries usable but prevents 70K+ tokens.
MAX_STRING_BYTES = 2000

# Max bytes for a single tool response that is one big string (e.g. brave_search formatted output).
MAX_RESPONSE_STRING_BYTES = 50_000

# Message shown when a string is over the limit (keeps structure valid for downstream).
OVER_LIMIT_TEMPLATE = "value exceeds size limit ({size} bytes, max {max_bytes}) [content truncated for context limit]"

def truncate_string_to_bytes(
    s: str,
    max_bytes: int = MAX_STRING_BYTES,
    suffix: str = "...",
    context: str | None = None,
    include_size_signal: bool = True,
) -> str:
    """
    Truncate a string to max_bytes (UTF-8). If truncated, append suffix and optionally
    " [truncated, N chars total]" so the LLM knows content was shortened.
    When truncation happens, sets the tool truncation flag and logs (dataset, sizes).
    """
    if not isinstance(s, str):
        return s
    encoded = s.encode("utf-8")
    if len(encoded) <= max_bytes:
        return s
    suffix_b = suffix.encode("utf-8")
    # Reserve space for inline signal so LLM sees incomplete data
    signal_tail = f" [truncated, {len(s)} chars total]" if include_size_signal else ""
    signal_b = signal_tail.encode("utf-8")
    reserve = len(suffix_b) + (len(signal_b) if include_size_signal else 0)
    allowed = encoded[: max_bytes - reserve]
    truncated = allowed.decode("utf-8", errors="ignore").rstrip() + suffix + signal_tail
    truncated_size = len(truncated.encode("utf-8"))
    _set_truncation_occurred()
    _inc_truncation_metric(context or "unknown")
    logger.info(
        "Truncation: dataset=%s original_bytes=%s truncated_bytes=%s",
        context or "unknown",
        len(encoded),
        truncated_size,
    )
    return truncated


def _truncate_string(
    s: str,
    max_bytes: int,
    path: str,
    tool_name: str | None,
) -> tuple[str, bool]:
    """Return (s or replacement message with inline truncated signal, True if truncated)."""
    if not isinstance(s, str):
        return s, False
    encoded = s.encode("utf-8")
    if len(encoded) <= max_bytes:
        return s, False
    msg = OVER_LIMIT_TEMPLATE.format(size=len(encoded), max_bytes=max_bytes)
    _set_truncation_occurred()
    dataset = f"{tool_name or 'tool'}.{path}" if path else (tool_name or "tool")
    _inc_truncation_metric(dataset)
    logger.info(
        "Truncation: dataset=%s original_bytes=%s truncated_bytes=%s",
        dataset,
        len(encoded),
        len(msg.encode("utf-8")),
    )
    return msg, True


def truncate_strings_for_llm(
    obj: Any,
    max_bytes: int = MAX_STRING_BYTES,
    tool_name: str | None = None,
    _path: str = "",
) -> tuple[Any, bool]:
    """
    Recursively walk dicts/lists and replace any string longer than max_bytes
    with a short message. Non-dict/list, non-string values are returned as-is.
    Returns (deep copy with truncated strings, any_truncated: bool).
    When truncation happens, sets the tool truncation flag and logs (dataset, sizes).
    """
    if isinstance(obj, str):
        s, truncated = _truncate_string(obj, max_bytes, _path, tool_name)
        return s, truncated
    if isinstance(obj, dict):
        out = {}
        any_truncated = False
        for k, v in obj.items():
            child_path = f"{_path}.{k}" if _path else k
            v2, t = truncate_strings_for_llm(v, max_bytes, tool_name, child_path)
            out[k] = v2
            any_truncated = any_truncated or t
        return out, any_truncated
    if isinstance(obj, list):
        out = []
        any_truncated = False
        for i, item in enumerate(obj):
            child_path = f"{_path}[{i}]" if _path else f"[{i}]"
            v2, t = truncate_strings_for_llm(item, max_bytes, tool_name, child_path)
            out.append(v2)
            any_truncated = any_truncated or t
        return out, any_truncated
    return obj, False
