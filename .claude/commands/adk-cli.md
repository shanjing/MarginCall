Full ADK CLI reference. Use this when you need detailed options for any `adk` command.

## adk web

Starts a FastAPI server with Web UI for agents. Development only — not for production.

```
adk web [AGENTS_DIR] [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `AGENTS_DIR` | `.` (cwd) | Parent directory containing agent folders |
| `--host` | `127.0.0.1` | Binding host |
| `--port` | `8000` | Port |
| `--log_level` | `INFO` | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `-v` / `--verbose` | | Shortcut for `--log_level DEBUG` |
| `--reload` / `--no-reload` | `True` | Auto-reload on file changes |
| `--reload_agents` | | Enable live reload for agent changes |
| `--a2a` | | Enable Agent-to-Agent endpoint |
| `--allow_origins` | | CORS origins (multiple, supports `regex:` prefix) |
| `--session_service_uri` | local `.adk/` | Session storage URI |
| `--artifact_service_uri` | local `.adk/artifacts` | Artifact storage URI |
| `--memory_service_uri` | | Memory service URI |
| `--use_local_storage` / `--no_use_local_storage` | `True` | Use local `.adk` when URIs unset |
| `--eval_storage_uri` | | Evals storage URI (e.g. `gs://bucket`) |
| `--trace_to_cloud` | | Enable Cloud Trace export |
| `--otel_to_cloud` | | Enable OpenTelemetry export to GCP |
| `--url_prefix` | | URL path prefix for reverse proxy (e.g. `/api/v1`) |
| `--logo-text` | | Custom text for Web UI logo |
| `--logo-image-url` | | Custom logo image URL |
| `--extra_plugins` | | Comma-separated plugin classes |
| `--enable_features` | | Comma-separated feature flags to enable |
| `--disable_features` | | Comma-separated feature flags to disable |

**Example:**
```bash
adk web                                    # current dir, port 8000
adk web --port 8080 -v                     # custom port, debug logging
adk web --session_service_uri sqlite:///sessions.db
adk web --no-reload                        # disable auto-reload (Windows fix)
```

---

## adk run

Interactive CLI for a single agent. Supports session save/resume/replay.

```
adk run <AGENT> [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `AGENT` | (required) | Path to agent source folder |
| `--save_session` | | Save session to JSON on exit |
| `--session_id` | | Session ID when saving |
| `--resume FILE` | | Resume from saved session JSON (exclusive with `--replay`) |
| `--replay FILE` | | Replay from input JSON, non-interactive (exclusive with `--resume`) |
| `--session_service_uri` | SQLite `.adk/session.db` | Session storage URI |
| `--artifact_service_uri` | local `.adk/artifacts` | Artifact storage URI |
| `--memory_service_uri` | | Memory service URI (warning: not fully supported) |
| `--use_local_storage` / `--no_use_local_storage` | `True` | Use local `.adk` when URIs unset |
| `--enable_features` | | Feature flags to enable |
| `--disable_features` | | Feature flags to disable |

**Example:**
```bash
adk run stock_analyst                      # interactive CLI
adk run --save_session stock_analyst       # save session on exit
adk run --save_session --session_id my_sess stock_analyst
adk run --resume stock_analyst/my_sess.session.json stock_analyst
adk run --replay input.json stock_analyst  # non-interactive
echo "Analyze AAPL" | adk run stock_analyst   # pipe input
```

---

## adk api_server

REST API server for agents (no Web UI). Swagger docs at `/docs`.

```
adk api_server [AGENTS_DIR] [OPTIONS]
```

Same options as `adk web`, plus:

| Option | Default | Description |
|---|---|---|
| `--auto_create_session` | | Auto-create session if missing on `/run` |

**API Endpoints:**
- `POST /run` — single response (JSON body with `appName`, `userId`, `sessionId`, `newMessage`)
- `POST /run_sse` — streaming response (Server-Sent Events)
- `GET /docs` — Swagger UI
- All request/response fields use **camelCase**

**Example:**
```bash
adk api_server                             # current dir, port 8000
adk api_server --port 8080 --auto_create_session

# Test with curl:
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "appName": "stock_analyst",
    "userId": "user_1",
    "sessionId": "s_1",
    "newMessage": {"role": "user", "parts": [{"text": "Analyze AAPL"}]}
  }'
```

---

## adk create

Scaffolds a new agent project with template files.

```
adk create <APP_NAME> [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `APP_NAME` | (required) | Directory name for the agent |
| `--model` | | Model for root agent (e.g. `gemini-2.5-flash`) |
| `--api_key` | | Google AI API key |
| `--project` | | Google Cloud project (Vertex AI) |
| `--region` | | Google Cloud region (Vertex AI) |

Creates: `APP_NAME/__init__.py` + `APP_NAME/agent.py` with a basic `root_agent` template.

**Example:**
```bash
adk create my_new_agent --model gemini-2.5-flash
```

---

## adk eval

Evaluates an agent against test scenarios.

```
adk eval <AGENT_PATH> <EVAL_SET_FILES...> [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `AGENT_PATH` | (required) | Path to agent module (directory with `__init__.py`) |
| `EVAL_SET_FILES` | (required) | Eval set file(s). Multiple allowed. Can target specific evals: `file.json:eval_1,eval_2` |
| `--config_file_path` | | Evaluation criteria config file |
| `--print_detailed_results` | | Verbose output to console |
| `--eval_storage_uri` | | Storage URI (e.g. `gs://bucket`) |
| `--log_level` | `INFO` | Logging level |
| `--enable_features` | | Feature flags to enable |
| `--disable_features` | | Feature flags to disable |

**Built-in evaluation criteria:**
- `tool_trajectory_avg_score` — exact tool call trajectory match (default threshold: 1.0)
- `response_match_score` — ROUGE-1 similarity (default threshold: 0.8)
- `final_response_match_v2` — LLM-judged semantic match
- `rubric_based_final_response_quality_v1` — LLM-judged response quality
- `rubric_based_tool_use_quality_v1` — LLM-judged tool usage quality
- `hallucinations_v1` — groundedness check
- `safety_v1` — safety check

**Example:**
```bash
adk eval stock_analyst eval_set.json
adk eval stock_analyst eval_set.json:eval_1,eval_2 --print_detailed_results
```

---

## adk eval_set

Manage eval sets (create, add test cases).

```
adk eval_set create <AGENT_PATH> <EVAL_SET_ID> [--eval_storage_uri URI]
adk eval_set add_eval_case <AGENT_PATH> <EVAL_SET_ID> --scenarios_file FILE --session_input_file FILE
```

---

## adk deploy cloud_run

Deploy agent to Google Cloud Run.

```
adk deploy cloud_run <AGENT> [OPTIONS] [-- GCLOUD_FLAGS...]
```

| Option | Default | Description |
|---|---|---|
| `AGENT` | (required) | Path to agent source folder |
| `--project` | gcloud default | Google Cloud project |
| `--region` | | Google Cloud region |
| `--service_name` | `adk-default-service-name` | Cloud Run service name |
| `--app_name` | folder name | ADK app name |
| `--port` | `8000` | Server port |
| `--with_ui` | | Deploy Web UI alongside API (dev only) |
| `--trace_to_cloud` | | Enable Cloud Trace |
| `--otel_to_cloud` | | Enable OpenTelemetry export |
| `--a2a` | | Enable Agent-to-Agent endpoint |
| `--adk_version` | current | ADK version to use |
| `--log_level` | `INFO` | Logging level |
| `--session_service_uri` | | Session storage URI |
| `--artifact_service_uri` | | Artifact storage URI |
| `--memory_service_uri` | | Memory service URI |
| `--use_local_storage` | `False` | Use local `.adk` (default False for deploy) |
| `--allow_origins` | | CORS origins |
| `--temp_folder` | timestamped | Temp folder for build files |

Pass extra `gcloud run deploy` flags after `--`:
```bash
adk deploy cloud_run --project=my-proj --region=us-central1 stock_analyst \
  -- --no-allow-unauthenticated --min-instances=2
```

---

## adk deploy agent_engine

Deploy to Vertex AI Agent Engine.

```
adk deploy agent_engine <AGENT> [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `AGENT` | (required) | Path to agent source folder |
| `--project` | | Google Cloud project |
| `--region` | | Google Cloud region |
| `--api_key` | | API key for Express Mode |
| `--display_name` | folder name | Display name in Agent Engine |
| `--description` | | Description |
| `--agent_engine_id` | | Existing engine ID to update (creates new if unset) |
| `--trace_to_cloud` | | Enable Cloud Trace |
| `--env_file` | `.env` in agent dir | Path to `.env` file |
| `--requirements_file` | `requirements.txt` in agent dir | Path to requirements |

```bash
# Express Mode (API key)
adk deploy agent_engine --api_key=KEY stock_analyst

# Standard Vertex AI
adk deploy agent_engine --project=my-proj --region=us-central1 --display_name="Stock Analyst" stock_analyst
```

---

## adk deploy gke

Deploy to Google Kubernetes Engine.

```
adk deploy gke <AGENT> [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `AGENT` | (required) | Path to agent source folder |
| `--project` | gcloud default | Google Cloud project |
| `--region` | | Google Cloud region |
| `--cluster_name` | (required) | GKE cluster name |
| `--service_name` | `adk-default-service-name` | Service name |
| `--with_ui` | | Deploy Web UI |

```bash
adk deploy gke --project=my-proj --region=us-central1 --cluster_name=my-cluster stock_analyst
```

---

## adk conformance

Conformance testing tools.

```bash
adk conformance record [PATHS...]          # generate test YAMLs (default: tests/)
adk conformance test [PATHS...]            # run conformance tests
adk conformance test --mode=live tests/    # live mode (not replay)
adk conformance test --generate_report --report_dir=reports
```

---

## adk migrate session

Migrate session database schema.

```bash
adk migrate session --source_db_url=sqlite:///old.db --dest_db_url=sqlite:///new.db
```

---

## Service URI Formats

| Service | URI Format | Description |
|---|---|---|
| Session | `sqlite:///path/to/db` | SQLite database |
| Session | `memory://` | In-memory (lost on restart) |
| Session | `agentengine://<id>` | Agent Engine managed |
| Artifact | `file:///path/to/dir` | Local filesystem |
| Artifact | `gs://bucket` | Google Cloud Storage |
| Artifact | `memory://` | In-memory |
| Memory | `rag://<corpus_id>` | Vertex AI RAG |
| Memory | `agentengine://<id>` | Agent Engine |

## Agent Directory Convention

For any `adk` command to recognize an agent, the directory must follow:
```
my_agent/
├── __init__.py    # Must contain: from . import agent
└── agent.py       # Must define: root_agent = Agent(...)
```

The variable MUST be named `root_agent`. The `AGENTS_DIR` passed to `adk web` / `adk api_server` is the parent directory that contains one or more agent folders.
