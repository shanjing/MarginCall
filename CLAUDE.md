# MarginCall — Claude Code Context

## What This Is

MarginCall is a multi-agent stock analyst built on **Google Agent Development Kit (ADK)** for Python. It uses a supervisor → sequential-pipeline pattern to fetch market data, synthesize reports, and present investment analysis. The persona is "Sam Rogers" from the movie *Margin Call*, working at "DiamondHands 💎🙌 Entertainment Group."

## Quick Reference

```
# Activate environment (from parent adk-lab directory)
cd ../adk-lab && source .venv/bin/activate && cd MarginCall

# Run via ADK web UI (dev only, localhost:8000, select "stock_analyst")
adk web

# Run via ADK interactive CLI
adk run stock_analyst

# Run via project CLI (custom, supports debug/thoughts)
python -m main run -i "tell me about GOOGL"
python -m main run -i "tell me about GOOGL" -d -t   # debug + thoughts

# API server (no UI, REST endpoints at localhost:8000/docs)
adk api_server

# Sanity check (verifies agent wiring, imports, config)
python check_env.py
```

## ADK CLI (`adk`)

The `adk` command is the primary development tool. All commands operate on agent directories (each containing `__init__.py` + `agent.py` with a `root_agent`).

### Development commands (daily use)

| Command | Purpose | Example |
|---|---|---|
| `adk web` | Web UI for testing agents (dev only) | `adk web` or `adk web --port 8080` |
| `adk run <agent>` | Interactive CLI session | `adk run stock_analyst` |
| `adk api_server` | REST API server (no UI) | `adk api_server --port 8080` |
| `adk create <name>` | Scaffold a new agent project | `adk create my_agent --model gemini-2.5-flash` |
| `adk eval <agent> <evalset>` | Run evaluations | `adk eval stock_analyst eval_set.json` |

### `adk web` (most common for MarginCall)
```
adk web [AGENTS_DIR] [OPTIONS]
  --port PORT           (default: 8000)
  --host HOST           (default: 127.0.0.1)
  --log_level LEVEL     DEBUG|INFO|WARNING|ERROR (default: INFO)
  -v / --verbose        shortcut for --log_level DEBUG
  --reload/--no-reload  auto-reload on code changes (default: True)
  --session_service_uri URI   e.g. sqlite:///sessions.db
  --artifact_service_uri URI  e.g. file://./artifacts
```
Opens browser UI at `http://localhost:PORT`. Select agent from sidebar. NOT for production.

### `adk run` (interactive CLI)
```
adk run <AGENT> [OPTIONS]
  --save_session        save session JSON on exit
  --session_id ID       session ID when saving
  --resume FILE         resume from saved session JSON
  --replay FILE         replay from input JSON (non-interactive)
  --session_service_uri URI
  --artifact_service_uri URI
```

### `adk api_server` (REST API)
```
adk api_server [AGENTS_DIR] [OPTIONS]
  (same options as adk web, plus:)
  --auto_create_session   auto-create session on /run
  --a2a                   enable Agent-to-Agent endpoint
```
Swagger docs at `http://localhost:PORT/docs`. Endpoints: `/run` (single), `/run_sse` (streaming).

### `adk eval` (evaluation)
```
adk eval <AGENT_PATH> <EVAL_SET_FILE> [OPTIONS]
  --config_file_path FILE     evaluation config
  --print_detailed_results    verbose output
  --eval_storage_uri URI      e.g. gs://bucket
```
Eval sets: JSON files with test scenarios. Can target specific evals: `eval_set.json:eval_1,eval_2`.

### `adk deploy` (production deployment)
```
adk deploy cloud_run --project=PROJECT --region=REGION [--with_ui] <AGENT>
adk deploy agent_engine --project=PROJECT --region=REGION <AGENT>
adk deploy gke --project=PROJECT --region=REGION --cluster_name=CLUSTER <AGENT>
```
Cloud Run is the simplest path. Pass extra gcloud flags after `--` separator.

### `adk create` (scaffolding)
```
adk create <APP_NAME> [--model MODEL] [--api_key KEY]
```
Creates agent directory with `__init__.py` and `agent.py` template. MarginCall already exists — use this for new sibling agents in the parent directory.

### Important notes
- `adk web` and `adk run` default to local `.adk/` storage for sessions/artifacts
- Agent directory must have `__init__.py` with `from . import agent` and `agent.py` defining `root_agent`
- The `AGENTS_DIR` for `adk web` / `adk api_server` is the PARENT directory containing agent folders (defaults to cwd)
- `--reload` (default on) watches for file changes — use `--no-reload` if hitting issues
- For MarginCall: `adk web` from the MarginCall parent dir, or `adk run stock_analyst` from MarginCall dir

## Environment

- Python virtual environment lives at `../adk-lab/.venv/`
- `.env` file at repo root (gitignored) — must contain `GOOGLE_API_KEY` and either `CLOUD_AI_MODEL` (e.g. `gemini-2.0-flash`) or `LOCAL_AI_MODEL` (e.g. `qwen3:32b`)
- Key env vars: `AGENT_APP_NAME`, `ROOT_AGENT=stock_analyst`, `SUB_AGENTS`, `CACHE_BACKEND=sqlite`, `BRAVE_API_KEY` (for non-Gemini news search)

## ADK Framework

This project uses `google-adk` (Agent Development Kit). Before making changes, consult the local ADK references:

- **Python SDK source**: `../adk-python/` (sibling repo — read to understand ADK classes, runners, sessions)
- **ADK docs**: `../adk-docs/docs/` (sibling repo — streaming, custom agents, tool patterns)
- **Streaming/WebSocket**: `../adk-docs/docs/streaming/custom-streaming-ws.md`

Key ADK concepts used in this project:
- `LlmAgent` — LLM-powered agent with tools and instructions
- `SequentialAgent` — runs sub-agents in order (no tools of its own)
- `AgentTool` — wraps an agent as a callable tool for another agent
- `McpToolset` / `StdioConnectionParams` — MCP server integration (Brave search)
- `Runner` / `DatabaseSessionService` — async execution with SQLite-backed sessions
- `BuiltInPlanner` / `ThinkingConfig` — chain-of-thought reasoning
- `output_key` — stores agent output in `session.state.<key>`
- `output_schema` — enforces Pydantic schema on agent output (only for agents WITHOUT tools)
- `ToolContext` — passed to tool functions for artifact saving

## Architecture

```
stock_analyst (root LlmAgent — supervisor)
├── tools: stock_analysis_pipeline (AgentTool), fetch_reddit, invalidate_cache, search_cache_stats
│
└── stock_analysis_pipeline (SequentialAgent)
    ├── stock_data_collector (LlmAgent) → output_key="stock_data"
    │   ├── fetch_stock_price, fetch_financials, fetch_technicals_with_chart
    │   ├── fetch_cnn_greedy, fetch_vix, fetch_stocktwits_sentiment, fetch_options_analysis
    │   ├── fetch_reddit
    │   └── news_fetcher (AgentTool → LlmAgent) → output_key="stock_news"
    │       └── google_search (Gemini) OR brave_search (MCP, non-Gemini)
    │
    ├── report_synthesizer (LlmAgent, no tools) → output_key="stock_report"
    │   └── output_schema=StockReport (Pydantic)
    │
    └── presenter (LlmAgent, no tools) → output_key="presentation"
```

### Data Flow

1. User query → **root_agent** decides: research (A), chat (B), refresh (C), cache stats (D), or Reddit-only (E)
2. If research: root calls `stock_analysis_pipeline` as AgentTool
3. **stock_data_collector** calls all 9 tools (parallel where possible), stores in `session.state.stock_data`
4. **report_synthesizer** reads `session.state.stock_data`, outputs structured JSON via `StockReport` schema to `session.state.stock_report`
5. **presenter** reads `session.state.stock_report`, renders formatted markdown report

## Project Structure

```
MarginCall/
├── main.py                      # CLI entry point (click-based)
├── check_env.py                 # Sanity checker for agent wiring
├── requirements.txt             # Pinned dependencies
├── .env                         # Secrets (gitignored)
│
├── stock_analyst/               # Root agent package (name must match ROOT_AGENT env var)
│   ├── agent.py                 # root_agent definition
│   └── sub_agents/
│       ├── stock_analysis_pipeline/agent.py   # SequentialAgent
│       ├── stock_data_collector/agent.py      # Data fetcher (9 tools)
│       ├── report_synthesizer/agent.py        # JSON report (output_schema)
│       ├── presenter/agent.py                 # Markdown renderer
│       ├── news_fetcher/agent.py              # News search agent
│       ├── financials_fetcher/agent.py
│       ├── price_fetcher/agent.py
│       └── technicals_fetcher/agent.py
│
├── agent_tools/                 # Function tools (called by agents)
│   ├── __init__.py              # MCP toolset lazy-loader
│   ├── server.py                # FastMCP server (Brave search)
│   ├── schemas.py               # LLM output schemas (StockReport, etc.)
│   ├── tool_schemas.py          # Tool return-value schemas (raw data)
│   ├── fetch_stock_price.py
│   ├── fetch_financials.py
│   ├── fetch_technicals_with_chart.py
│   ├── fetch_cnn_greedy.py
│   ├── fetch_vix.py
│   ├── fetch_stocktwits_sentiment.py
│   ├── fetch_options_analysis.py
│   ├── fetch_reddit.py
│   ├── invalidate_cache.py
│   ├── search_cache_stats.py
│   ├── brave_search.py
│   ├── google_custom_search.py
│   └── generate_trading_chart.py
│
└── tools/                       # Shared infrastructure
    ├── config.py                # Model selection, env loading, cache config
    ├── logging_utils.py         # Structured logging, RunSummaryCollector
    ├── runner_utils.py          # execute_agent_stream, session management
    ├── run_context.py           # Per-run tool execution registry (contextvars)
    ├── save_artifacts.py        # ADK artifact saving (charts → session)
    ├── cache/
    │   ├── base.py              # CacheBackend ABC
    │   ├── decorators.py        # @cached decorator, TTL presets
    │   └── sqlite_backend.py    # SQLite cache (dev backend)
    ├── CacheStrategy.md         # Cache design doc
    └── ERROR_HANDLING_AND_LOGGING_PLAN.md
```

## Two-Layer Schema Architecture

Schemas are split into two layers — **do not merge them**:

1. **`agent_tools/tool_schemas.py`** — raw data contracts (what tool functions return)
   - `StockPriceResult`, `FinancialsResult`, `TechnicalsWithChartResult`, `VIXResult`, etc.
2. **`agent_tools/schemas.py`** — LLM output contracts (what agents produce)
   - `StockReport`, `SentimentAnalysis`, `OptionsAnalysis`, `StockRating`, `FinancialsSection`

ADK limitation: `output_schema` cannot be used on agents that have `tools=[]` set. Only `report_synthesizer` (no tools) uses `output_schema=StockReport`.

## Caching

- All tool functions use the `@cached` decorator from `tools/cache/decorators.py`
- TTL tiers: `TTL_REALTIME` (15min), `TTL_INTRADAY` (4hr), `TTL_DAILY` (24hr)
- Cache key format: `{TICKER}:{data_type}:{YYYY-MM-DD}` (e.g. `AAPL:price:2026-02-07`)
- Backend: pluggable via `CacheBackend` ABC; currently SQLite only
- Planned backends: Redis, GCS (see `tools/CacheStrategy.md`)
- `invalidate_cache` tool clears all entries for a ticker
- `search_cache_stats` returns distinct stocks, total entries, ticker list
- Pass `real_time=True` or `_force_refresh=True` to bypass cache

## Conventions and Patterns

### Agent naming
- Agent python variable name MUST match the `name=` parameter and the directory name
- e.g. `stock_data_collector` variable, `name="stock_data_collector"`, directory `sub_agents/stock_data_collector/`
- `check_env.py` validates this invariant

### Adding a new tool
1. Create `agent_tools/<tool_name>.py` with a function that returns a `dict`
2. Define return schema in `agent_tools/tool_schemas.py` (Pydantic BaseModel)
3. Use `@cached(data_type="...", ttl_seconds=TTL_*, ticker_param="ticker")` decorator
4. The function should return `SomeResult(...).model_dump()` on success
5. On error, return `{"status": "error", "error_message": "..."}`
6. Add the tool to the appropriate agent's `tools=[...]` list
7. Update the agent's instruction to describe the new tool

### Adding a new sub-agent
1. Create `stock_analyst/sub_agents/<name>/` with `__init__.py` and `agent.py`
2. Agent variable name must match directory name and `name=` parameter
3. Export from `__init__.py`
4. Add to parent agent's `sub_agents=[]` or wrap with `AgentTool(agent=...)`
5. Add name to `SUB_AGENTS` in `.env`
6. Run `python check_env.py` to verify wiring

### Model configuration
- Never hardcode model names in agent files
- Use `AI_MODEL` from `tools/config.py` (reads from `.env`)
- Cloud models: set `CLOUD_AI_MODEL` in `.env` (string passed directly)
- Local models: set `LOCAL_AI_MODEL` in `.env` (wrapped in `LiteLlm`)

### Session state
- Data flows between agents via `session.state` using `output_key`
- `stock_data_collector` → `session.state.stock_data`
- `report_synthesizer` → `session.state.stock_report`
- `presenter` → `session.state.presentation`
- `news_fetcher` → `session.state.stock_news`

### Error handling
- Tools return `{"status": "error", "error_message": "..."}` (never raise to the agent)
- `report_synthesizer` has explicit instructions for handling missing/error data
- Tool execution is tracked via `tools/run_context.py` (per-run contextvars registry)
- Runner has timeout handling (`RUNNER_TIMEOUT_SECONDS`, default 300s)

### Recommendation logic (80/20 rule)
- 80% weight: market sentiment (CNN Fear & Greed, VIX, StockTwits, Put/Call Ratio)
- 20% weight: stock fundamentals (price, financials, technicals)
- This is enforced in `report_synthesizer` instruction — do not change without discussion

## Dependencies

Key packages (see `requirements.txt` for versions):
- `google-adk[database]` — Agent Development Kit with SQLite sessions
- `google-genai` — Google Generative AI SDK
- `litellm` — local LLM support (Ollama, etc.)
- `yfinance` — stock data (price, financials, options)
- `pandas` + `pandas-ta-classic` — technical indicators
- `plotly` + `kaleido` — chart generation (HTML + PNG)
- `httpx` — async HTTP client
- `pydantic` — schema validation
- `click` — CLI framework
- `mcp` — Model Context Protocol (Brave search server)

## What NOT To Do

- Do not combine `output_schema` with `tools` on the same agent (ADK limitation)
- Do not merge `tool_schemas.py` and `schemas.py` (see two-layer architecture above)
- Do not hardcode model names — always use `AI_MODEL` from config
- Do not store file paths in cache keys (breaks future GCS migration)
- Do not put SQLite-specific queries in tool code (tools call `cache.get()` / `cache.put()` only)
- Do not change the 80/20 recommendation weighting without explicit discussion
- Do not skip the `@cached` decorator on new data-fetching tools
