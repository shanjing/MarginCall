# MarginCall — Project Context

## Using Claude Code

Start from project root so this file loads: `cd /path/to/MarginCall && claude`. Check with `/context`; force-inject in print mode: `claude -p --append-system-prompt-file ./CLAUDE.md "query"`.

---

## What This Is

Multi-agent stock analyst on **Google ADK** (Python). Supervisor → sequential pipeline: data → report → presentation. Persona: "Sam Rogers" (Margin Call) at DiamondHands 💎🙌.

## Quick Commands

```bash
cd ../MarginCall ; ./setup.sh 
```

## Other ways to start the agent for developers

```bash
cd ../MarginCall && source .venv/bin/activate && cd MarginCall
uvicorn server:app --host 0.0.0.0 --port 8080
adk web                    # dev UI, localhost:8000
adk run stock_analyst      # interactive CLI
python -m main run -i "tell me about GOOGL" -d -t   # project CLI, debug
python check_env.py        # verify agent wiring
```

**ADK API and CLI:** Read `../adk-python/` and `../adk-docs/docs/` for full reference. In-session: run `/adk-reference` to load the ADK skill, or `/adk-cli` for CLI details.

---

## Paths (do not guess)

- **Sub-agents:** `stock_analyst/sub_agents/<name>/agent.py` (variable name = `name=` = directory name).
- **Function tools:** `agent_tools/<name>.py`.
- **Infra:** `tools/` (config, cache, runner_utils, etc.).

---

## Agent-as-tool pattern (this repo)

**stock_data_collector** already mixes function tools and **AgentTool(agent=news_fetcher)** in its `tools=[]`. To add another sub-agent as a tool: define the sub-agent, then add **AgentTool(agent=your_agent)** to the parent's `tools=[]`. No wrapper or `run_agent()` — ADK handles it. See `stock_analyst/sub_agents/stock_data_collector/agent.py`.

---

## Architecture (minimal)

```
stock_analyst (root) — tools: stock_analysis_pipeline (AgentTool), fetch_reddit, invalidate_cache, search_cache_stats
  └ stock_analysis_pipeline (SequentialAgent)
      ├ stock_data_collector → output_key="stock_data"  [9 function tools + AgentTool(agent=news_fetcher)]
      ├ report_synthesizer  → output_key="stock_report" (no tools, output_schema=StockReport)
      └ presenter           → output_key="presentation" (no tools)
```

Data flows via `session.state` and `output_key`. Root routes: research → pipeline; chat → no tools; refresh → invalidate_cache then pipeline; cache stats → search_cache_stats; Reddit-only → fetch_reddit.

---

## Hard rules

- **API Key:** Must have an API Key to access cloud based LLM, gemini-* recommended.
- **Naming:** Agent variable = `name=` = directory name. Enforced by `check_env.py`.
- **Model:** Always `model=AI_MODEL` from `tools/config.py`. Never hardcode.
- **Schemas:** `agent_tools/tool_schemas.py` = tool return contracts. `agent_tools/schemas.py` = LLM output (e.g. StockReport). Do not merge. **output_schema** only on agents with **no** `tools=[]` (ADK limitation).
- **Cache:** `@cached` from `tools/cache/decorators.py`. Key format: `{TICKER}:{data_type}:{YYYY-MM-DD}`. TTL: TTL_REALTIME / TTL_INTRADAY / TTL_DAILY.
- **Errors:** Tools return `{"status": "error", "error_message": "..."}`; do not raise.
- **SUB_AGENTS:** Add new sub-agent name to `SUB_AGENTS` in `.env`.
- **80/20:** report_synthesizer uses 80% market sentiment / 20% stock fundamentals. Do not change without discussion.

---

## Adding a tool

1. `agent_tools/<name>.py` — function returns `dict`; schema in `tool_schemas.py`; `@cached(...)`; success → `Result(...).model_dump()`, error → `{"status": "error", "error_message": "..."}`.
2. Add to agent's `tools=[]` and update that agent's `instruction`.
3. Run `python check_env.py`. See `agent_tools/fetch_stock_price.py` as reference.

Full checklist: `/add-tool` or `.claude/commands/add-tool.md`.

---

## Adding a sub-agent

1. `stock_analyst/sub_agents/<name>/` with `__init__.py` and `agent.py`; variable name = `name=` = directory name.
2. Wire: pipeline step → parent's `sub_agents=[]`; or as tool → **AgentTool(agent=name)** in parent's `tools=[]` (see stock_data_collector + news_fetcher).
3. Add to `SUB_AGENTS` in `.env`. Set `output_key` if downstream needs output. Use `model=AI_MODEL`. Run `python check_env.py`.

Full checklist: `/add-agent` or `.claude/commands/add-agent.md`.

---

## Environment

- Venv: `../MarginCall/.venv/`. `.env` at repo root: `GOOGLE_API_KEY`, `CLOUD_AI_MODEL` or `LOCAL_AI_MODEL`, `ROOT_AGENT=stock_analyst`, `SUB_AGENTS`, `CACHE_BACKEND=sqlite`, `BRAVE_API_KEY` (non-Gemini news).

---

## What NOT to do

- Use `output_schema` on an agent that has `tools=[]`.
- Merge `tool_schemas.py` and `schemas.py`.
- Hardcode model names; use `AI_MODEL`.
- Put file paths in cache keys.
- Put SQLite-specific logic in tool code (use cache interface only).
- Change 80/20 weighting without discussion.
- Add data-fetching tools without `@cached`.
