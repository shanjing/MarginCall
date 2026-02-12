---
name: google-adk
description: Use Google ADK (Python SDK, CLI, streaming). Read adk-python and adk-docs for API/CLI; repo CLAUDE.md for MarginCall patterns.
allowed-tools: Read
---

# Google ADK

For ADK API, CLI, and patterns:

1. **Python SDK source:** Read `../adk-python/` (sibling repo) — agents, tools, runners, sessions, planners, models, apps.
2. **ADK docs:** Read `../adk-docs/docs/` — get-started, agents, tools, runtime (web, run, api_server), streaming (e.g. `streaming/custom-streaming-ws.md`), evaluate, deploy.
3. **This project (MarginCall):** Read repo root **CLAUDE.md** for paths, agent-as-tool pattern, and conventions. Do not duplicate ADK content there; use adk-python and adk-docs as the source of truth for ADK.

When the user asks about ADK, read the relevant files above and summarize what applies. For MarginCall-specific wiring (e.g. adding a sub-agent as a tool), follow CLAUDE.md and the add-agent / add-tool checklists.
