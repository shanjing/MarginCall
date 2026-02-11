"""
Run-scoped tool execution registry (for run summary: who ran, cache hit, or error).

Uses contextvars so state is per-run in async; safe for concurrent runs.
The runner calls init_run_tool_registry() at run start; tools (e.g. cache decorator)
call record_tool_execution() or record_tool_error(); log_run_summary reads get_run_tool_registry().
"""

from __future__ import annotations

import contextvars
from typing import Any

# Run-scoped list of {"tool": str, "cache_hit": bool, "error": str | None}. Set at run start, read at run end.
_RUN_TOOL_REGISTRY: contextvars.ContextVar[list[dict[str, Any]]] = contextvars.ContextVar(
    "run_tool_registry",
    default=[],
)


def init_run_tool_registry() -> list[dict[str, Any]]:
    """Initialize the registry for this run. Call at run start (e.g. in runner)."""
    reg: list[dict[str, Any]] = []
    _RUN_TOOL_REGISTRY.set(reg)
    return reg


def record_tool_execution(
    tool_name: str,
    cache_hit: bool,
    error: str | None = None,
) -> None:
    """Record that a tool ran: cache_hit, executed OK, or executed but failed (error set)."""
    try:
        reg = _RUN_TOOL_REGISTRY.get()
    except LookupError:
        reg = []
        _RUN_TOOL_REGISTRY.set(reg)
    entry: dict[str, Any] = {"tool": tool_name, "cache_hit": cache_hit}
    if error is not None:
        entry["error"] = error
    reg.append(entry)


def record_tool_error(tool_name: str, message: str) -> None:
    """Record that a tool was called but failed (e.g. returned status=error or raised). Non-cached tools can call this."""
    record_tool_execution(tool_name, cache_hit=False, error=message)


def get_run_tool_registry() -> list[dict[str, Any]]:
    """Return the current run's tool execution list. Empty if not initialized."""
    try:
        return _RUN_TOOL_REGISTRY.get()
    except LookupError:
        return []
