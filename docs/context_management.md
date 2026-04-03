# Context Management: Conversational Memory in MarginCall

The companion document **[AGENTIC_ENGINEERING.md](../AGENTIC_ENGINEERING.md)** covers one context problem — managing what the LLM sees *within a single run* (context window, truncation, output key isolation). This document covers the other: what the LLM knows from *past runs* — conversational memory across sessions.

---

## The Two Context Problems

| Problem | Scope | Managed by |
|---|---|---|
| **Context window** | What the LLM sees *this run* | AGENTIC_ENGINEERING.md §1 — truncation pipeline, output_key isolation |
| **Conversational context** | What the LLM knows from *past runs* | This document — session reuse, event history |

Both matter. A perfectly managed context window is still useless if every CLI run starts from a blank slate, forcing the user to re-state what they asked five minutes ago.

---

## Three Persistence Layers (and Why They're Separate)

MarginCall has three distinct storage layers. Confusing them is a common design error.

```
┌─────────────────────────────────────────────────────────┐
│  session.events  (ADK — MarginCall_sessions.db)         │
│  Conversation history: user turns, agent responses,     │
│  tool call/response pairs. Persists forever.            │
├─────────────────────────────────────────────────────────┤
│  session.state   (ADK — MarginCall_sessions.db)         │
│  Structured data between pipeline agents: stock_data,   │
│  stock_report, presentation. Written each pipeline run. │
├─────────────────────────────────────────────────────────┤
│  Tool cache      (custom — cache/MarginCall_cache.db)   │
│  Raw API results keyed by TICKER:type:YYYY-MM-DD.       │
│  TTL-controlled: realtime/intraday/daily per data type. │
└─────────────────────────────────────────────────────────┘
```

**Why these are intentionally separate:**

- `session.events` is for the LLM's conversational awareness. It grows across turns and is loaded by ADK automatically when a session is reused.
- `session.state` is for structured data routing between pipeline agents. It uses `output_key` to pass `stock_data` → `report_synthesizer` → `presenter`. It is not a long-term memory store.
- The tool cache is the actual data freshness layer. It operates independently of both session layers. Stock data TTL is enforced here, not in `session.state`.

**The design error to avoid:** treating `session.state["stock_data"]` as the source of truth for data freshness. It isn't — the tool cache is. When the pipeline re-runs, `output_key="stock_data"` overwrites whatever was in state. The tool cache controls whether fresh data is fetched or a valid cached result is returned.

---

## What Is Time-Sensitive, What Is Not

Stock data is time-sensitive — but the relevant TTL is managed by the tool cache, not the session.

| Data | Where it lives | TTL mechanism | Cross-run behavior |
|---|---|---|---|
| Stock price, technicals, options | `cache/MarginCall_cache.db` | `TTL_REALTIME` / `TTL_INTRADAY` | Fetched fresh or returned from cache based on TTL |
| Financials, earnings | `cache/MarginCall_cache.db` | `TTL_DAILY` | Same |
| `session.state["stock_data"]` | `MarginCall_sessions.db` | None | Harmless to carry; overwritten when pipeline re-runs |
| `session.state["stock_report"]` | `MarginCall_sessions.db` | None | Same |
| `session.events` (conversation history) | `MarginCall_sessions.db` | None (forever) | Always reusable — this is the value |

**Why stale `session.state` is harmless:**

When the root_agent decides to run the pipeline (paths A, C in its routing logic), `stock_data_collector` calls its tools, the `@cached` decorator returns TTL-valid data or fetches fresh data, and `output_key="stock_data"` writes the result — overwriting anything from the prior run. The stale value is never read by any agent in the new run's pipeline.

When the root_agent decides NOT to run the pipeline (conversational paths), it answers from the LLM's conversation history (`session.events`), not from `session.state`. The stale state is invisible in this path too.

The 60/40 weighting rule in `report_synthesizer` is encoded in the system prompt and loaded from `report_rules.json` — it is never read from session.state. It applies fresh on every synthesis.

---

## Session Reuse Design

### The Problem (before)

```python
# runner_utils.py — old behavior
session_id = str(uuid.uuid4())   # new UUID every run
await session_service.create_session(...)
```

Every CLI invocation created a new session. Conversation history accumulated in `MarginCall_sessions.db` but was never retrieved. Each run started from a blank slate.

### The Fix (now)

```python
# runner_utils.py — new behavior
session_id = f"{app.name}--{user_id}"   # stable: one session per user per app

# Get-or-create: reuse if it exists, start fresh if it doesn't
curr_session = await session_service.get_session(
    app_name=app.name,
    user_id=user_id,
    session_id=session_id,
    config=GetSessionConfig(num_recent_events=SESSION_HISTORY_EVENTS),
)
if curr_session is None:
    await session_service.create_session(...)
# else: runner.run_async reuses the session with its full event history
```

**How ADK injects history:** When `runner.run_async(session_id=existing_id, new_message=...)` is called on an existing session, ADK loads the event list and passes it as conversation context to the LLM. No explicit "fetch" is needed — the history is injected transparently. The root_agent sees:

```
[User: "analyze AAPL", Agent: "Here's the report...", User: "is it still bearish?"]
```

and can answer the follow-up using the prior analysis without re-running the pipeline.

### What This Enables

| User query | Before | After |
|---|---|---|
| "Is AAPL still bearish?" | Full pipeline re-run (blank context) | Root_agent answers from prior analysis in history |
| "How does MSFT compare to the AAPL report?" | Full pipeline re-run for MSFT, no AAPL context | MSFT pipeline runs; root_agent compares to AAPL from history |
| "Give me fresh numbers on AAPL" | Full pipeline re-run | Full pipeline re-run + cache invalidation (unchanged routing path) |
| "What was the last ticker I asked about?" | Unknown | Answered from history |

The root_agent's routing paths (A-G in its instruction) are unchanged. Conversational history simply enriches the context the LLM reasons over when deciding which path to take.

---

## Context Window Safety

**The risk:** Long sessions accumulate many events. Event history grows unbounded and will eventually overflow the context window.

**The mitigation:** `GetSessionConfig(num_recent_events=N)` — ADK loads only the last N events when retrieving a session.

```python
# tools/config.py
SESSION_HISTORY_EVENTS = int(os.getenv("SESSION_HISTORY_EVENTS", "50"))
```

At ~50 events per session, this covers approximately 5-10 full analysis turns (each turn produces ~5-10 events: user message, tool calls, tool responses, agent response). This is enough for rich conversational context without risking context overflow.

To adjust: set `SESSION_HISTORY_EVENTS` in `.env`. Set to `0` to load all events with no cap (not recommended for long-running sessions).

**Future option:** ADK supports native event compaction — summarizing old events into a single compaction event. This preserves semantic memory while bounding context size. Not yet implemented; the `SESSION_HISTORY_EVENTS` cap is sufficient for now.

---

## Web UI vs CLI Parity

| Aspect | Web UI (server.py) | CLI (runner_utils.py) |
|---|---|---|
| Session service | ADK-managed via `session_service_uri` | `DatabaseSessionService(db_url=...)` |
| Session ID | Created via REST API, stored in browser `sessionStorage` | `f"{app_name}--{user_id}"` |
| Multi-turn | Yes — frontend sends same session_id across requests | Yes — stable session_id persists across process restarts |
| DB file | `sessions.db` (env: `SESSION_SERVICE_URI`) | `MarginCall_sessions.db` |
| Survives restart | Yes (SQLite) | Yes (SQLite) |

Both paths now have equivalent conversational memory. The databases are separate files (CLI and web UI maintain independent session histories), which is intentional — CLI sessions are developer/debugging sessions; web UI sessions are user-facing.

---

## References

- [AGENTIC_ENGINEERING.md](../AGENTIC_ENGINEERING.md) — Context window management (truncation, output_key isolation)
- [ENGINEERING.md](../ENGINEERING.md) — Cache strategy, infrastructure
- `tools/runner_utils.py` — `execute_agent_stream` implementation
- `tools/config.py` — `SESSION_HISTORY_EVENTS` config
