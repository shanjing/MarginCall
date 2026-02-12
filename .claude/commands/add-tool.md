Add a new agent tool. Paths and caching rules: see **CLAUDE.md** (paths, "Hard rules", "Adding a tool"). For ADK tool API use `../adk-python/` and `../adk-docs/docs/` or run `/adk-reference`.

Checklist:

1. Create `agent_tools/<name>.py` — function returns `dict`; add schema to `agent_tools/tool_schemas.py`
2. Use `@cached(data_type="...", ttl_seconds=TTL_*, ticker_param="ticker")` from `tools/cache/decorators.py` (TTL_REALTIME / TTL_INTRADAY / TTL_DAILY; `ticker_param=None` for market-wide)
3. Success → `MyResult(...).model_dump()`; error → `{"status": "error", "error_message": "..."}`
4. Add to the right agent's `tools=[]` and update that agent's `instruction`
5. Run `python check_env.py`

Reference: `agent_tools/fetch_stock_price.py`
