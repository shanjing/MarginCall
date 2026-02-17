# Observability Strategy

This document covers the monitoring and observability design for MarginCall — what we monitor, what ADK provides natively, and how we implement each layer.

The core thesis: **an LLM agent pipeline has the same observability requirements as any distributed system** (latency, error rates, resource consumption, throughput) **plus LLM-specific concerns** (token cost, context window pressure, hallucination guardrails, cache economics). We instrument both.

---

## 1. What Needs to Be Monitored

### Application Layer (our tools and infrastructure)

| Metric | Why it matters | Current status |
|--------|---------------|----------------|
| **Cache hit/miss rate** | Each cache miss triggers an external API call + downstream LLM processing. Target: 80%+ hit rate. | Tracked per-run via `@cached` decorator and `run_context` registry |
| **Tool execution latency** | Identifies slow external dependencies (yfinance, Reddit, CNN). | Tracked per-run via `RunSummaryCollector` |
| **Tool error rate** | A failing tool degrades report quality. Persistent failures need alerting. | Logged via `log_tool_error()`, recorded in run registry |
| **Truncation events** | Signals that upstream data is growing — early warning for token budget pressure. | Tracked per-tool via `_truncation_occurred` context var |
| **Cache entry count / TTL distribution** | Monitors cache growth and staleness. | Available via `get_stats()` on cache backend |
| **Run wall-clock time** | End-to-end latency from user query to response. | Tracked by `RunSummaryCollector.total_seconds()` |

### Agent/LLM Layer (ADK provides this)

| Metric | Why it matters | ADK support |
|--------|---------------|-------------|
| **Input/output tokens per LLM call** | Direct cost driver. A single bloated tool response can 5x the token bill. | Built-in: `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` in OTEL spans |
| **LLM call latency** | Distinguishes slow tools from slow model inference. | Built-in: `generate_content` spans with duration |
| **Agent invocation count** | Tracks how many agent hops a query requires. Runaway loops = cost explosion. | Built-in: `invoke_agent` spans per agent |
| **Tool call count per agent** | Validates that the pipeline calls expected tools. Missing tools = incomplete data. | Built-in: `execute_tool` spans with `gen_ai.tool.name` |
| **LLM error rate** | API failures, timeouts, rate limits from the model provider. | Built-in: span status + `on_model_error_callback` |
| **Finish reasons** | Distinguishes normal completions from length cutoffs or safety filters. | Built-in: `gen_ai.response.finish_reasons` in spans |

### Infrastructure Layer (standard)

| Metric | Why it matters |
|--------|---------------|
| **HTTP request latency (p50/p95/p99)** | User-facing SLA. FastAPI middleware. |
| **Active SSE connections** | Monitors frontend load on log streaming. |
| **SQLite cache DB size** | Prevents disk exhaustion on long-running instances. |
| **Process memory / CPU** | Standard container health. Prometheus `process_*` metrics come free. |

---

## 2. What ADK Currently Offers

*(ADK API details below — callback names, span attributes, env vars — should be confirmed against your `adk-python` / `adk-docs` version when implementing.)*

### 2.1 Built-in OpenTelemetry Instrumentation

ADK (v1.21.0+) instruments every agent run with OpenTelemetry spans automatically. No application code needed — these spans exist the moment you use ADK's runner:

**Span hierarchy per request:**
```
invoke_agent (root agent)
  └─ generate_content {model}          ← LLM call with token counts
       └─ execute_tool {tool_name}     ← tool execution
  └─ invoke_agent (sub-agent)          ← pipeline agent
       └─ generate_content {model}
            └─ execute_tool ...
```

**Attributes on each span:**

| Span | Attributes |
|------|-----------|
| `invoke_agent` | `gen_ai.agent.name`, `gen_ai.agent.description`, `gen_ai.conversation_id` |
| `generate_content` | `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.response.finish_reasons` |
| `execute_tool` | `gen_ai.tool.name`, `gen_ai.tool.description`, `gen_ai.tool.type`, function_call_id |

**Source:** `google.adk.telemetry.tracing` module.

### 2.2 Callback Hooks

ADK exposes callbacks at every boundary — these are the integration points for custom Prometheus metrics:

```python
Agent(
    name="stock_analyst",
    before_agent_callback=on_agent_start,       # agent lifecycle
    after_agent_callback=on_agent_end,
    before_model_callback=on_model_start,       # LLM calls (access to LlmRequest)
    after_model_callback=on_model_end,          # LLM responses (access to LlmResponse with token counts)
    before_tool_callback=on_tool_start,         # tool execution
    after_tool_callback=on_tool_end,
    on_model_error_callback=on_model_error,     # LLM failures
    on_tool_error_callback=on_tool_error,       # tool failures
)
```

**What's available in callbacks:**
- `callback_context.invocation_id` — correlates all events in a single run
- `callback_context.session.id` — session-level correlation
- `LlmResponse.usage_metadata.prompt_token_count` / `candidates_token_count`
- `tool_context.agent_name`, `tool_context.function_call_id`

### 2.3 OTLP Export (Environment-Driven)

ADK's `telemetry.setup` module auto-configures exporters via standard OTEL env vars:

```bash
# Generic OTLP endpoint (works with any collector)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Or split by signal type
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:4317
OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=http://localhost:4317
OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=http://localhost:4317
```

Set these env vars and ADK exports its built-in spans to any OTLP-compatible collector (OpenTelemetry Collector, Grafana Alloy, Datadog Agent, etc.).

### 2.4 Google Cloud Native Export

For GCP deployments, ADK provides direct integration:

```python
from google.adk.telemetry.google_cloud import get_gcp_exporters

exporters = get_gcp_exporters(
    enable_cloud_tracing=True,      # → Cloud Trace
    enable_cloud_metrics=True,      # → Cloud Monitoring
    enable_cloud_logging=True,      # → Cloud Logging
)
```

Also available via CLI: `adk deploy cloud_run --trace_to_cloud`.

### 2.5 BigQuery Analytics Plugin

Enterprise-grade event logging for offline analysis:

```python
from google.adk.plugins.bigquery_agent_analytics_plugin import BigQueryAgentAnalyticsPlugin

plugin = BigQueryAgentAnalyticsPlugin(project="my-project", dataset="agent_analytics")
runner = Runner(agents=[root_agent], plugins=[plugin])
```

Captures every event (LLM calls, tool executions, agent lifecycle) with full schema: timestamps, token usage, latency, trace IDs, content payloads. Useful for cost analysis and quality evaluation over time, not real-time monitoring.

---

## 3. What We Already Have

MarginCall has run-scoped observability built into the application layer. This is the foundation that Prometheus metrics will formalize:

### 3.1 RunSummaryCollector (`tools/logging_utils.py`)

Collects per-run data during `execute_agent_stream()`:

```
============================================================
RUN SUMMARY
============================================================
Model: gemini-2.5-flash
Total execution time: 45.32 s
- Tools / agents invoked (with duration):
  - fetch_stock_price (stock_data_collector) 2.15 s (cache hit)
  - fetch_reddit (stock_data_collector) 8.47 s
  - fetch_vix (stock_data_collector) 1.89 s (cache hit)
- Tool executions (run context; cache hit / executed / error):
  - fetch_stock_price: cache hit
  - fetch_reddit: executed
  - fetch_vix: cache hit
- Tools not invoked this run:
  - brave_search: not seen in root event stream; not in run registry
============================================================
```

**Data sources:** `record_event()` for timing, `_from_cache` flag for cache detection, `run_context` registry for execution status, session events for agent tracking.

### 3.2 Structured Logging Functions (`tools/logging_utils.py`)

| Function | Level | Format |
|----------|-------|--------|
| `log_tool_error(tool, msg)` | WARNING | `[MarginCall] type=tool_error tool={tool} message={msg}` |
| `log_agent_failure(agent, type, msg)` | ERROR | `[MarginCall] type={type} agent={agent} message={msg}` |
| `log_llm_error(msg)` | ERROR | `[MarginCall] type=llm_error message={msg}` |

### 3.3 Cache Backend Logging (`tools/cache/sqlite_backend.py`)

Every cache operation is logged:
- `Cache HIT: AAPL:price:2026-02-16`
- `Cache PUT: AAPL:price:2026-02-16 (TTL=900s)`
- `Cache MISS: AAPL:price:2026-02-16`
- `Cache INVALIDATE ticker=AAPL, deleted=5 entries`
- `Cache PURGE: removed 12 expired entries`

### 3.4 Truncation Tracking (`tools/truncate_for_llm.py`)

Per-tool context variable flags when content was shortened:
```
Truncation: dataset=fetch_reddit.posts[0].snippet original_bytes=4200 truncated_bytes=500
```

Tools set `result["truncation_applied"] = True` so the LLM knows data was cut.

### 3.5 SSE Log Streaming (`server.py`)

Real-time log delivery to the frontend:
- Thread-safe queue collects log records from all threads
- Async broadcast consumer pushes to connected SSE clients
- 400-line circular replay buffer for late-joining clients
- Heartbeat every 250ms prevents browser timeout

---

## 4. Implementation Plan

### Phase 1: Prometheus `/metrics` Endpoint

**Goal:** Expose application-level metrics that Prometheus can scrape. No OTEL collector needed — just `prometheus_client` library and a `/metrics` route.

**Metrics to expose:**

```python
# Cache economics
cache_operations_total     = Counter("margincall_cache_ops_total", "Cache operations", ["operation", "result"])
                             # labels: operation=get|put|invalidate, result=hit|miss|error

# Tool performance
tool_duration_seconds      = Histogram("margincall_tool_duration_seconds", "Tool execution time", ["tool_name"])
tool_errors_total          = Counter("margincall_tool_errors_total", "Tool errors", ["tool_name"])
tool_calls_total           = Counter("margincall_tool_calls_total", "Tool invocations", ["tool_name", "cache_hit"])

# Token budget
truncation_events_total    = Counter("margincall_truncation_total", "Truncation events", ["tool_name"])

# Run-level
run_duration_seconds       = Histogram("margincall_run_duration_seconds", "Full pipeline run time")
run_total                  = Counter("margincall_runs_total", "Total agent runs", ["status"])
                             # labels: status=success|timeout|llm_error|agent_error

# LLM cost (from ADK callbacks)
llm_tokens_total           = Counter("margincall_llm_tokens_total", "LLM tokens consumed", ["direction", "model"])
                             # labels: direction=input|output
llm_call_duration_seconds  = Histogram("margincall_llm_call_duration_seconds", "LLM inference time", ["model"])
```

**Integration points:**

1. **Cache metrics** — Instrument `SQLiteCacheBackend.get()` / `put()` to increment `cache_operations_total`.
2. **Tool metrics** — Instrument the `@cached` decorator to record `tool_duration_seconds`, `tool_calls_total`, and `tool_errors_total`.
3. **Truncation metrics** — Instrument `truncate_string_to_bytes()` to increment `truncation_events_total`.
4. **Run metrics** — Instrument `execute_agent_stream()` in `runner_utils.py` to record `run_duration_seconds` and `run_total`.
5. **LLM metrics** — Use ADK's `after_model_callback` to extract `usage_metadata` and record `llm_tokens_total` and `llm_call_duration_seconds`.
6. **FastAPI route** — `GET /metrics` returns `prometheus_client.generate_latest()`.

**Files to modify:**
- `tools/cache/sqlite_backend.py` — add counter increments to get/put/delete
- `tools/cache/decorators.py` — add histogram/counter around tool execution
- `tools/truncate_for_llm.py` — add counter on truncation
- `tools/runner_utils.py` — add run-level histogram
- `stock_analyst/agent.py` — add `after_model_callback` for token tracking
- `server.py` — add `/metrics` endpoint
- New: `tools/metrics.py` — central metric definitions

### Phase 2: OTEL Collector + Distributed Tracing

**Goal:** Export ADK's built-in spans to an OpenTelemetry Collector, which fans out to Prometheus (metrics) and Tempo/Jaeger (traces). This gives us the full request waterfall: user query → supervisor → pipeline → tools → external APIs.

**Architecture:**

```
MarginCall (FastAPI + ADK)
  │
  │  OTLP/gRPC (port 4317)
  v
OpenTelemetry Collector
  ├──→ Prometheus (metrics, port 9090)
  ├──→ Tempo or Jaeger (traces, port 3200/16686)
  └──→ Loki (logs, optional, port 3100)
         │
         v
      Grafana (dashboards + trace explorer)
```

**Configuration:**

```bash
# .env additions
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=margincall
```

ADK auto-exports its spans when these env vars are set. No code changes needed for the built-in agent/LLM/tool spans.

**OTEL Collector config (`otel-collector.yaml`):**
```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

exporters:
  prometheus:
    endpoint: 0.0.0.0:8889
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true

service:
  pipelines:
    metrics:
      receivers: [otlp]
      exporters: [prometheus]
    traces:
      receivers: [otlp]
      exporters: [otlp/tempo]
```

**What this unlocks:**
- Waterfall trace view: see exactly where time is spent (LLM inference vs. tool execution vs. data fetching)
- Token cost attribution: which agent/tool combination consumes the most tokens
- Error correlation: trace a failed run from the user query through to the specific external API that timed out
- Latency heatmaps across runs

### Phase 3: GCP Cloud Operations (Production)

**Goal:** For Cloud Run deployment, use GCP-native exporters instead of self-hosted collector.

```python
# server.py or startup hook
from google.adk.telemetry.google_cloud import get_gcp_exporters

if os.getenv("GOOGLE_CLOUD_PROJECT"):
    get_gcp_exporters(
        enable_cloud_tracing=True,
        enable_cloud_metrics=True,
        enable_cloud_logging=True,
    )
```

- **Cloud Trace** replaces Tempo/Jaeger — same waterfall view, zero infrastructure
- **Cloud Monitoring** replaces Prometheus — auto-scales, no storage management
- **Cloud Logging** replaces Loki — structured logs with trace correlation

---

## 5. Grafana Dashboard Design

### Dashboard 1: Agent Health (operational)

| Panel | Metric | Visualization |
|-------|--------|--------------|
| Run success rate | `margincall_runs_total` by status | Stat + time series |
| Run latency p50/p95/p99 | `margincall_run_duration_seconds` | Heatmap |
| Active runs | `margincall_runs_total` rate | Gauge |
| Error rate by tool | `margincall_tool_errors_total` | Stacked bar |

### Dashboard 2: Cost & Tokens (cost engineering)

| Panel | Metric | Visualization |
|-------|--------|--------------|
| Tokens per run (input vs output) | `margincall_llm_tokens_total` | Stacked time series |
| Token cost estimate ($/hour) | `llm_tokens_total * price_per_token` | Stat with threshold |
| Cache hit rate | `margincall_cache_ops_total{result=hit}` / total | Gauge (target: >80%) |
| Cache savings (avoided LLM calls) | `cache_ops{result=hit}` * avg_tokens_per_miss | Stat |
| Truncation frequency | `margincall_truncation_total` | Time series |

### Dashboard 3: Tool Performance (debugging)

| Panel | Metric | Visualization |
|-------|--------|--------------|
| Tool latency by tool | `margincall_tool_duration_seconds` | Box plot per tool |
| Tool call distribution | `margincall_tool_calls_total` | Pie chart |
| Cache hit/miss by tool | `margincall_tool_calls_total` by cache_hit | Stacked bar |
| LLM inference time | `margincall_llm_call_duration_seconds` | Histogram |

### Dashboard 4: Trace Explorer (Phase 2)

Grafana's Tempo data source provides:
- Search by trace ID, agent name, or tool name
- Waterfall view of full request lifecycle
- Span-level token counts and latency
- Error highlighting in trace view

---

## 6. Alerting Rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| High error rate | `rate(margincall_tool_errors_total[5m]) > 0.1` | Warning |
| Run timeout spike | `rate(margincall_runs_total{status="timeout"}[5m]) > 0.05` | Warning |
| Cache hit rate drop | `cache_hit_rate < 0.6` for 10 minutes | Warning |
| Token cost spike | `rate(margincall_llm_tokens_total[1h]) > threshold` | Critical |
| LLM provider errors | `rate(margincall_runs_total{status="llm_error"}[5m]) > 0.1` | Critical |
| Tool consistently failing | `margincall_tool_errors_total{tool="X"}` increase > 5 in 10m | Warning |

---

## 7. Token Budget Monitoring — Why Truncation Is Not an Antipattern

A note on the truncation metrics: monitoring `truncation_events_total` is not about limiting the AI. It's about **managing the signal-to-noise ratio of LLM inputs** — the same way you'd monitor payload sizes for any metered API.

What truncation prevents:
- **Cost blowup** — The TPM bloat incident sent 300-500KB per run (125K+ tokens). After truncation: 20-50KB (15-30K tokens). See [TPM Bloat Fix](how-we-fixed-llm-tpm-bloat-from-session-state.md).
- **Lost-in-the-middle degradation** — LLMs demonstrably pay less attention to content in the middle of long contexts. Less noise = better reasoning.
- **Rate limit pressure** — Fewer tokens per request = more requests per minute within provider TPM limits.

What truncation does NOT do:
- It never cuts the user's query
- It never removes data the LLM needs for reasoning (structured metadata is preserved)
- Tools set `truncation_applied: true` so the LLM knows data was shortened and won't hallucinate missing sections

Monitoring truncation frequency tells us when upstream data sources are growing — an early warning to review field caps or add a summarization pass before it becomes a cost problem.

---

## References

- [Cache Strategy](CacheStrategy.md) — Cache backend design, TTL tiers, migration path
- [TPM Bloat Fix](how-we-fixed-llm-tpm-bloat-from-session-state.md) — Base64 chart incident and fix
- [Token Bloat Prevention](how-to-prevent-datasets-bloat-llm-deep-dive-part1.md) — Systematic LLM context management
- [Error Handling Plan](ErrorHandlingLoggingPlan.md) — Structured logging patterns
- ADK Telemetry: `google.adk.telemetry.tracing` / `google.adk.telemetry.setup`
- ADK Callbacks: `google.adk.agents.callback_context`
- ADK Cloud Trace: `google.adk.telemetry.google_cloud`
