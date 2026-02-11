Add a new sub-agent to MarginCall. Follow this checklist:

1. Create directory `stock_analyst/sub_agents/$ARGUMENTS/` with `__init__.py` and `agent.py`
2. In `agent.py`, define the agent variable with the SAME name as the directory: `$ARGUMENTS = LlmAgent(name="$ARGUMENTS", ...)`
3. Export the agent from `__init__.py`: `from .agent import $ARGUMENTS`
4. Wire the agent:
   - If it's a pipeline step: add to parent SequentialAgent's `sub_agents=[]`
   - If it's a tool for another agent: wrap with `AgentTool(agent=$ARGUMENTS)` and add to parent's `tools=[]`
5. Add `$ARGUMENTS` to the `SUB_AGENTS` list in `.env`
6. If the agent produces output for downstream agents, set `output_key="..."` so data flows via `session.state`
7. If the agent has no tools and should produce structured output, use `output_schema=MyPydanticModel`
   - NEVER combine `output_schema` with `tools` on the same agent (ADK limitation)
8. Always use `model=AI_MODEL` from `tools/config.py` — never hardcode model names
9. Run `python check_env.py` to verify wiring

Refer to `stock_analyst/sub_agents/news_fetcher/agent.py` as a simple agent example.
