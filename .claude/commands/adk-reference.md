Before changing ADK-related behavior (agents, tools, runners, sessions, streaming), read the local ADK sources — do not rely on memory alone.

1. **Python SDK:** `../adk-python/` — `google.adk.agents`, `google.adk.tools` (AgentTool, LlmAgent, etc.), `google.adk.runners`, `google.adk.sessions`, `google.adk.planners`, `google.adk.models`, `google.adk.apps`
2. **Docs:** `../adk-docs/docs/` — get-started, agents, tools, runtime (web, run, api_server), streaming (custom-streaming-ws.md), evaluate, deploy
3. **This project’s patterns:** Repo root **CLAUDE.md** (paths, agent-as-tool, conventions). MarginCall does not duplicate ADK; it follows ADK and adds project rules in CLAUDE.md.

Summarize what from the ADK source/docs applies to the current task.
