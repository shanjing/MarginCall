Add a new agent tool to MarginCall. Follow this checklist:

1. Create `agent_tools/$ARGUMENTS.py` with a function named `$ARGUMENTS` that returns a `dict`
2. Define the return schema as a Pydantic BaseModel in `agent_tools/tool_schemas.py`
3. Apply the `@cached` decorator: `@cached(data_type="...", ttl_seconds=TTL_*, ticker_param="ticker")`
   - Use `TTL_REALTIME` (15min) for fast-changing data (price)
   - Use `TTL_INTRADAY` (4hr) for medium-changing data (sentiment, VIX)
   - Use `TTL_DAILY` (24hr) for slow-changing data (financials)
   - Set `ticker_param=None` for market-wide tools (no ticker)
4. Return `MySchema(...).model_dump()` on success
5. Return `{"status": "error", "error_message": "..."}` on error (never raise exceptions to the agent)
6. Import and add the tool to the appropriate agent's `tools=[...]` in its `agent.py`
7. Update the agent's `instruction=` string to describe the new tool
8. Run `python check_env.py` to verify nothing broke

Refer to `agent_tools/fetch_stock_price.py` as a reference implementation.
