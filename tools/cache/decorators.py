"""
Cache decorators for agent tool functions.

Usage:
    from tools.cache.decorators import cached

    @cached(data_type="price", ttl_seconds=900)
    def fetch_stock_price(ticker: str) -> dict:
        ...  # Only runs on cache miss

    @cached(data_type="vix", ttl_seconds=14400, ticker_param=None)
    def fetch_vix() -> dict:
        ...  # No ticker param (market-wide data)
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from datetime import date

from .base import CacheBackend

logger = logging.getLogger(__name__)


def _record_tool_run(name: str, cache_hit: bool, error: str | None = None) -> None:
    try:
        from tools.run_context import record_tool_execution
        record_tool_execution(name, cache_hit, error=error)
    except Exception:  # noqa: BLE001
        pass


def _error_from_result(result: dict) -> str | None:
    """Extract a short error message from a tool result dict (status=error)."""
    if result.get("status") != "error":
        return None
    msg = result.get("error_message") or result.get("error")
    if isinstance(msg, str):
        return msg[:500]  # cap length for summary
    return str(msg)[:500] if msg is not None else "error"

# ── TTL presets (seconds) ──────────────────────────────────────────────
# Tier 1: Slow-changing data (daily)
TTL_DAILY = 86400  # 24 hours
# Tier 2: Medium-changing data (intraday)
TTL_INTRADAY = 14400  # 4 hours
# Tier 3: Fast-changing data
TTL_REALTIME = 900  # 15 minutes


def cached(
    data_type: str,
    ttl_seconds: int = TTL_DAILY,
    ticker_param: str | None = "ticker",
):
    """
    Decorator that adds caching to a tool function.

    Args:
        data_type: Cache category (e.g., "price", "financials", "vix").
        ttl_seconds: Time-to-live in seconds. Use TTL_* presets.
        ticker_param: Name of the parameter that contains the ticker symbol.
            Set to None for market-wide tools (VIX, CNN Fear & Greed).

    The decorated function must return a dict. On cache hit, the cached dict
    is returned with an extra "_from_cache": True field.

    To force a cache miss (real-time refresh), pass _force_refresh=True
    or real_time=True to the decorated function. Both are stripped from
    kwargs before calling the underlying function.
    """

    def decorator(func):
        # Get the cache lazily (avoids import-time initialization)
        _cache: CacheBackend | None = None

        def _get_cache() -> CacheBackend:
            nonlocal _cache
            if _cache is None:
                from tools.cache import get_cache

                _cache = get_cache()
            return _cache

        def _build_key(kwargs_or_args: dict) -> tuple[str, str]:
            """Return (cache_key, ticker) from function arguments."""
            ticker = ""
            if ticker_param is not None:
                ticker = kwargs_or_args.get(ticker_param, "")
                if isinstance(ticker, str):
                    ticker = ticker.upper()
            today = date.today().isoformat()
            key = CacheBackend.make_key(ticker, data_type, today)
            return key, ticker

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Extract force-refresh flags (stripped so underlying func doesn't see them)
                force_refresh = kwargs.pop("_force_refresh", False) or kwargs.pop(
                    "real_time", False
                )

                # Build kwargs dict from positional + keyword args
                sig = inspect.signature(func)
                bound = sig.bind_partial(*args, **kwargs)
                bound.apply_defaults()
                all_kwargs = dict(bound.arguments)
                # Remove tool_context from cache key consideration
                all_kwargs.pop("tool_context", None)

                cache = _get_cache()
                key, ticker = _build_key(all_kwargs)

                # Check cache (unless forced refresh)
                if not force_refresh:
                    cached_data = await cache.get_json(key)
                    if cached_data is not None:
                        cached_data["_from_cache"] = True
                        _record_tool_run(func.__name__, True)
                        return cached_data

                # Cache miss → call the actual function
                try:
                    result = await func(*args, **kwargs)
                except Exception as e:
                    _record_tool_run(func.__name__, False, error=str(e)[:500])
                    raise
                err_msg = isinstance(result, dict) and _error_from_result(result)
                _record_tool_run(func.__name__, False, error=err_msg)

                # Only cache successful results
                if isinstance(result, dict) and result.get("status") != "error":
                    await cache.put_json(
                        key,
                        result,
                        ttl_seconds,
                        ticker=ticker,
                        data_type=data_type,
                    )

                return result

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Extract force-refresh flags (stripped so underlying func doesn't see them)
                force_refresh = kwargs.pop("_force_refresh", False) or kwargs.pop(
                    "real_time", False
                )

                # Build kwargs dict from positional + keyword args
                sig = inspect.signature(func)
                bound = sig.bind_partial(*args, **kwargs)
                bound.apply_defaults()
                all_kwargs = dict(bound.arguments)

                cache = _get_cache()
                key, ticker = _build_key(all_kwargs)

                # Check cache (unless forced refresh)
                # Run async cache methods in a sync context
                loop = None
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    # We're inside an async context (ADK runtime)
                    # Use a thread to avoid blocking the event loop
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        if not force_refresh:
                            cached_data = pool.submit(
                                lambda: asyncio.run(cache.get_json(key))
                            ).result()
                            if cached_data is not None:
                                cached_data["_from_cache"] = True
                                _record_tool_run(func.__name__, True)
                                return cached_data

                        # Cache miss → call the actual function
                        try:
                            result = func(*args, **kwargs)
                        except Exception as e:
                            _record_tool_run(func.__name__, False, error=str(e)[:500])
                            raise
                        err_msg = isinstance(result, dict) and _error_from_result(result)
                        _record_tool_run(func.__name__, False, error=err_msg)

                        if isinstance(result, dict) and result.get("status") != "error":
                            pool.submit(
                                lambda: asyncio.run(
                                    cache.put_json(
                                        key,
                                        result,
                                        ttl_seconds,
                                        ticker=ticker,
                                        data_type=data_type,
                                    )
                                )
                            ).result()

                        return result
                else:
                    # No event loop — simple sync path
                    if not force_refresh:
                        cached_data = asyncio.run(cache.get_json(key))
                        if cached_data is not None:
                            cached_data["_from_cache"] = True
                            _record_tool_run(func.__name__, True)
                            return cached_data

                    try:
                        result = func(*args, **kwargs)
                    except Exception as e:
                        _record_tool_run(func.__name__, False, error=str(e)[:500])
                        raise
                    err_msg = isinstance(result, dict) and _error_from_result(result)
                    _record_tool_run(func.__name__, False, error=err_msg)

                    if isinstance(result, dict) and result.get("status") != "error":
                        asyncio.run(
                            cache.put_json(
                                key,
                                result,
                                ttl_seconds,
                                ticker=ticker,
                                data_type=data_type,
                            )
                        )

                    return result

            return sync_wrapper

    return decorator
