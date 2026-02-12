For full ADK CLI options and usage, read the ADK docs (do not rely on memory alone):

- **Runtime (web, run, api_server):** `../adk-docs/docs/runtime/` — web-interface.md, command-line.md, api-server.md
- **Deploy:** `../adk-docs/docs/deploy/` — cloud-run, agent-engine, gke
- **Eval:** `../adk-docs/docs/evaluate/`
- **CLI implementation:** `../adk-python/` — search for the `adk` entry point and click command definitions

Quick reference from memory: `adk web`, `adk run <agent>`, `adk api_server`, `adk create <name>`, `adk eval <agent> <evalset>`, `adk deploy cloud_run|agent_engine|gke`. Options (--port, --session_service_uri, etc.) are in the docs above.

Summarize the relevant CLI options from the docs for the user's current task.
