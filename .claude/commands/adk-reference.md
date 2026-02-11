Before making changes that involve Google ADK (agents, tools, runners, sessions, streaming), consult the local ADK reference repos:

1. Read the relevant source in `../adk-python/` to understand the ADK Python SDK classes, especially:
   - `google.adk.agents` — LlmAgent, SequentialAgent, ParallelAgent, LoopAgent
   - `google.adk.tools` — AgentTool, McpToolset, google_search, ToolContext, FunctionTool
   - `google.adk.runners` — Runner
   - `google.adk.sessions` — DatabaseSessionService, InMemorySessionService
   - `google.adk.planners` — BuiltInPlanner
   - `google.adk.models` — LiteLlm (local model wrapper)
   - `google.adk.apps` — App

2. Read `../adk-docs/docs/` for ADK documentation, especially:
   - `../adk-docs/docs/streaming/custom-streaming-ws.md` — bidi-streaming / WebSocket patterns
   - `../adk-docs/docs/get-started/` — quickstart, installation, project structure
   - `../adk-docs/docs/agents/` — agent types, configuration, multi-agent patterns
   - `../adk-docs/docs/tools/` — function tools, MCP tools, built-in tools
   - `../adk-docs/docs/runtime/` — runner, web UI, API server, sessions
   - `../adk-docs/docs/evaluate/` — evaluation framework, eval sets, criteria
   - `../adk-docs/docs/deploy/` — Cloud Run, Agent Engine, GKE deployment
   - Any docs relevant to the specific feature being worked on

3. For ADK CLI usage (`adk web`, `adk run`, `adk deploy`, etc.), use `/project:adk-cli` for the full reference.

4. Key ADK constraints to remember:
   - `output_schema` CANNOT be used on agents that have `tools=[]` (ADK limitation)
   - Agent `name=` must match the python variable name and directory name
   - `output_key` stores agent output in `session.state.<key>` for downstream agents
   - `AgentTool(agent=...)` wraps a sub-agent as a callable tool
   - Agent directory must have `__init__.py` (with `from . import agent`) and `agent.py` (defining `root_agent`)
   - `adk web` AGENTS_DIR is the parent containing agent folders, not the agent folder itself

Summarize what you learned from the ADK source/docs that is relevant to the current task.
