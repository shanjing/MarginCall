Add a new sub-agent. Paths and agent-as-tool pattern: see **CLAUDE.md** (paths, "Agent-as-tool pattern" section). Example of an agent used as a tool: `stock_analyst/sub_agents/stock_data_collector/agent.py` — it has `AgentTool(agent=news_fetcher)` in its `tools=[]`. For ADK API details use `../adk-python/` and `../adk-docs/docs/` or run `/adk-reference`.

Checklist:

1. Create `stock_analyst/sub_agents/<name>/` with `__init__.py` and `agent.py`
2. Variable name = `name=` = directory name: `name = LlmAgent(name="name", ...)`
3. Export in `__init__.py`: `from .agent import name`
4. Wire: pipeline step → parent's `sub_agents=[]`; or as tool → `AgentTool(agent=name)` in parent's `tools=[]`
5. Add name to `SUB_AGENTS` in `.env`
6. Set `output_key` if downstream needs output; use `model=AI_MODEL` from `tools/config.py`
7. `output_schema` only if agent has no tools (ADK limitation)
8. Run `python check_env.py`

Reference: `stock_analyst/sub_agents/news_fetcher/agent.py`
