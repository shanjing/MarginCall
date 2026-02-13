import logging
import json
import os
import sys
import time
from typing import Any

import click
import google.adk
import litellm

# Theme for consistent cross-repo observability
THEME = {
    "thought": {"fg": "cyan", "italic": True},
    "call": {"fg": "yellow", "bold": True},
    "res": {"fg": "green"},
    "err": {"fg": "red", "bold": True}
}

# Global Logger for this module
logger = logging.getLogger(__name__)


def get_log_level(debug: bool = False) -> int:
    """Single source of truth for app log level. Used by setup_logging and server log stream.
    Set LOG_LEVEL=DEBUG|INFO|WARNING|ERROR|CRITICAL to override; otherwise DEBUG if debug else INFO."""
    level_str = os.getenv("LOG_LEVEL", "").strip().upper()
    if level_str in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        return getattr(logging, level_str)
    return logging.DEBUG if debug else logging.INFO


def setup_logging(debug: bool = False, model_name: str = "unknown"):
    """ADK logging configuration with version and model tracking."""
    log_level = get_log_level(debug)

    # Preserve any LogStreamHandler (added by server.py for SSE log streaming)
    # before basicConfig(force=True) wipes the root handler list.
    root = logging.getLogger()
    _saved_handlers = [h for h in root.handlers if type(h).__name__ == "LogStreamHandler"]

    # base station for all logging
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(filename)s:%(funcName)s:%(lineno)d | %(message)s",
        stream=sys.stdout,
        force=True,
    )

    # Re-attach preserved handlers
    for h in _saved_handlers:
        if h not in root.handlers:
            root.addHandler(h)

    adk_ver = getattr(google.adk, "__version__", "unknown")
    litellm_ver = getattr(litellm, "__version__", "unknown")
    

    # --- STARTUP METADATA ---
    # This ensures every log file/stream starts with the technical context
    logger.info("="*50)
    logger.info(f"SYSTEM STARTUP | Model: {model_name}")
    logger.info(f"ADK Version: {adk_ver} | LiteLLM: {litellm_ver}")
    logger.info("="*50)

    # Mute noisy internal ADK/SQL logic
    silence = logging.DEBUG if debug else logging.WARNING
    logging.getLogger("google.adk").setLevel(silence)
    logging.getLogger("litellm").setLevel(silence)

    # Mute the specific warning about non-text parts in responses
    logging.getLogger("google.genai.types").setLevel(logging.ERROR)

    # Mute noisy internal SQL logic
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.orm").setLevel(logging.WARNING)
    
    # Mute the underlying async driver (aiosqlite)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)

    # 'core.py' noise from aiosqlite
    logging.getLogger("sqlite3").setLevel(logging.WARNING)

async def log_event(event):
    """Processes ADK events for the CLI trace."""
    if hasattr(event, 'thought') and event.thought:
        click.secho(f"\n[Thought]: {event.thought}", **THEME["thought"])

    calls = event.get_function_calls()
    if calls:
        for call in calls:
            click.secho(f"  ➜ [Tool Call]: {call.name}", **THEME["call"])
            click.secho(f"    [Arguments]: {call.args}", fg="yellow")

    responses = event.get_function_responses()
    if responses:
        for resp in responses:
            click.secho(f"  ✔ [Tool Result]: {resp.name} -> {resp.response}", **THEME["res"])

    if hasattr(event, "error") and event.error:
        click.secho(f"  ✘ [Error]: {event.error}", **THEME["err"])
        # Also log so UI/server stderr gets it when not using click
        logger.error("[MarginCall] type=agent_error message=%s", str(event.error))


def log_agent_failure(
    agent_name: str,
    error_type: str,
    message: str,
    session_id: str | None = None,
    exc_info: bool = False,
) -> None:
    """Structured log for agent/pipeline failures. Logger only (no click) for CLI and UI."""
    parts = [f"type={error_type}", f"agent={agent_name}", f"message={message}"]
    if session_id:
        parts.append(f"session_id={session_id}")
    logger.error("[MarginCall] %s", " ".join(parts), exc_info=exc_info)


def log_tool_error(
    tool_name: str,
    message: str,
    session_id: str | None = None,
    **kwargs: str,
) -> None:
    """Structured log when a tool returns status=error. Logger only for CLI and UI."""
    parts = [f"type=tool_error", f"tool={tool_name}", f"message={message}"]
    if session_id:
        parts.append(f"session_id={session_id}")
    for k, v in kwargs.items():
        if v is not None:
            parts.append(f"{k}={v}")
    logger.warning("[MarginCall] %s", " ".join(parts))


def log_llm_error(
    message: str,
    session_id: str | None = None,
    exc_info: bool = True,
) -> None:
    """Structured log for LLM/API errors (500, timeout, connection). Logger only for CLI and UI."""
    parts = [f"type=llm_error", f"message={message}"]
    if session_id:
        parts.append(f"session_id={session_id}")
    logger.error("[MarginCall] %s", " ".join(parts), exc_info=exc_info)


def log_session_state(state: dict, label: str = "CURRENT STATE", session_id: str | None = None):
    """
    Displays session state in a formatted way. Optionally includes session_id in the header.
    """
    if state or session_id is not None:
        header = f"\n--- {label}"
        if session_id:
            header += f" (session_id: {session_id})"
        header += " ---"
        click.secho(header, fg="magenta", bold=True)
        if session_id and not state:
            click.secho("(empty state)", fg="magenta")
        elif state:
            state_json = json.dumps(state, indent=2)
            click.secho(state_json, fg="magenta")


# -----------------------------------------------------------------------------
# Run summary: tools/agents called, durations, skipped (with reason)
# -----------------------------------------------------------------------------


def _tool_name(tool) -> str | None:
    """Get display name for a tool (function or AgentTool)."""
    name = getattr(tool, "name", None)
    if name:
        return name
    agent = getattr(tool, "agent", None)
    if agent is not None:
        return getattr(agent, "name", None)
    return getattr(tool, "__name__", None)


def _collect_expected_from_agent(agent, tools: set, agents: set) -> None:
    """Recursively collect expected tool names and agent names from an agent."""
    if agent is None:
        return
    agents.add(getattr(agent, "name", "") or "unknown")
    # Sub-agents (SequentialAgent, etc.)
    for sub in getattr(agent, "sub_agents", []) or []:
        _collect_expected_from_agent(sub, tools, agents)
    # Tools (LlmAgent)
    for t in getattr(agent, "tools", []) or []:
        name = _tool_name(t)
        if name:
            tools.add(name)
        child = getattr(t, "agent", None)
        if child is not None:
            _collect_expected_from_agent(child, tools, agents)


def collect_expected_from_app(app) -> tuple[set[str], set[str]]:
    """Collect expected tool names and agent names from an ADK App (root_agent)."""
    tools: set[str] = set()
    agents: set[str] = set()
    root = getattr(app, "root_agent", None)
    if root is not None:
        _collect_expected_from_agent(root, tools, agents)
    return tools, agents


class RunSummaryCollector:
    """
    Collects tool/agent invocations and timing from ADK stream events.
    Call record_event(event) for each event, then finish_run() and log_run_summary().
    """

    def __init__(self) -> None:
        self.run_start: float = time.perf_counter()
        self.run_end: float | None = None
        self.pending_calls: list[tuple[str, str, float]] = []  # (tool_name, author, start_time)
        self.tool_invocations: list[dict] = []  # {name, agent, duration_sec, cache_hit?}
        self.agents_seen: set[str] = set()
        self.expected_tools: set[str] = set()
        self.expected_agents: set[str] = set()
        # Run-scoped registry from run_context (tools that actually ran + cache_hit); set by runner
        self.tool_execution_registry: list[dict] | None = None
        # Session from ADK after run (has .events and .state); set by runner for agent detection
        self.session: Any = None
        # Model name (e.g. AI_MODEL_NAME); set by runner
        self.model_name: str = "unknown"

    def set_expected_from_app(self, app) -> None:
        """Set expected tools and agents from app graph (for skipped/reason)."""
        self.expected_tools, self.expected_agents = collect_expected_from_app(app)

    def set_session(self, session: Any) -> None:
        """Set the ADK session (has .events and .state) for agent-run detection. Call after run."""
        self.session = session

    def _agents_from_session(self) -> set[str]:
        """
        Agents that ran this run: from session.events (and session.state) when available.
        Falls back to stream-derived agents_seen when session is not set.
        """
        if self.session is None:
            return self.agents_seen
        # extract agents from multiple sources but they are unique -SJ
        agents = set()
        events = getattr(self.session, "events", None)
        if events:
            for ev in events:
                author = getattr(ev, "author", None)
                if author and author != "user":
                    agents.add(author)
        state = getattr(self.session, "state", None) or {}
        if state and isinstance(state, dict):
            # extract agents from hints in state -SJ
            if state.get("stock_data") is not None:
                agents.add("stock_data_collector")
            if state.get("stock_report") is not None:
                agents.add("report_synthesizer")
                agents.add("presenter")
        return agents if agents else self.agents_seen

    def record_event(self, event) -> None:
        """Record one ADK event: author, function calls (start), function responses (end + duration)."""
        author = getattr(event, "author", None) or "unknown"
        ts = getattr(event, "timestamp", None)
        if ts is None:
            ts = time.time()

        self.agents_seen.add(author)

        for call in event.get_function_calls():
            name = getattr(call, "name", None) or "unknown"
            self.pending_calls.append((name, author, ts))

        for resp in event.get_function_responses():
            name = getattr(resp, "name", None) or "unknown"
            duration_sec = 0.0
            inv_agent = author
            for i, (pname, pauthor, pstart) in enumerate(self.pending_calls):
                if pname == name:
                    self.pending_calls.pop(i)
                    duration_sec = ts - pstart
                    inv_agent = pauthor
                    break
            # Detect cache hit from tool response (cached decorator sets _from_cache)
            raw = getattr(resp, "response", None)
            cache_hit = isinstance(raw, dict) and raw.get("_from_cache") is True
            self.tool_invocations.append({
                "name": name,
                "agent": inv_agent,
                "duration_sec": round(duration_sec, 2),
                "cache_hit": cache_hit,
            })

    def finish_run(self) -> None:
        """Mark run end time (for total execution time)."""
        self.run_end = time.perf_counter()

    def total_seconds(self) -> float:
        """Total run duration in seconds."""
        end = self.run_end if self.run_end is not None else time.perf_counter()
        return round(end - self.run_start, 2)

    def _tools_that_ran(self) -> set[str]:
        """Set of tool names that actually ran this run (from run_context registry)."""
        if not self.tool_execution_registry:
            return set()
        return {e["tool"] for e in self.tool_execution_registry}

    def _skipped_tools_with_reason(self) -> list[tuple[str, str]]:
        """
        List (tool_name, reason) for tools that were expected but not seen in the event stream
        and did not run (per run_context). Tools that ran (sub-agent) are excluded.
        """
        called = {inv["name"] for inv in self.tool_invocations}
        ran = self._tools_that_ran()
        skipped = []
        for name in sorted(self.expected_tools):
            if name in ran:
                continue  # Actually ran (e.g. via sub-agent); not skipped
            if name not in called:
                skipped.append((
                    name,
                    "not seen in root event stream; not in run registry (planner did not invoke)",
                ))
        return skipped

    def _skipped_agents_with_reason(self) -> list[tuple[str, str]]:
        """List (agent_name, reason) for agents that were expected but not seen in session.events/state."""
        agents_ran = self._agents_from_session()
        skipped = []
        for name in sorted(self.expected_agents):
            if name == "user":
                continue
            if name not in agents_ran:
                skipped.append((name, "not reached (no events/state from this agent)"))
        return skipped


def log_run_summary(collector: RunSummaryCollector) -> None:
    """
    Log a run summary: tools/agents called with duration, total time, and skipped with reasons.
    """
    total_sec = collector.total_seconds()
    sep = "=" * 60
    logger.info(sep)
    logger.info("RUN SUMMARY")
    logger.info(sep)
    logger.info("Model: %s", getattr(collector, "model_name", None) or "unknown")
    logger.info("Total execution time: %.2f s", total_sec)

    # Tools called
    logger.info("- Tools / agents invoked (with duration):")
    if not collector.tool_invocations:
        logger.info("  (none)")
    else:
        for inv in collector.tool_invocations:
            suffix = " (cache hit)" if inv.get("cache_hit") else ""
            logger.info(
                "  - %s (agent: %s) %.2f s%s",
                inv["name"],
                inv["agent"],
                inv["duration_sec"],
                suffix,
            )

    # Agents that ran (from session.events + session.state when available)
    agents_ran = collector._agents_from_session()
    logger.info(
        "- Agents that ran (session.events + state): %s",
        sorted(agents_ran) or "(none)",
    )

    # Tool executions (run context: actually ran + cache hit / executed / error)
    if collector.tool_execution_registry:
        logger.info("- Tool executions (run context; cache hit / executed / error):")
        for e in collector.tool_execution_registry:
            if e.get("error") is not None:
                status = "error"
                logger.warning("  - %s: %s | %s", e["tool"], status, e["error"])
            else:
                status = "cache hit" if e.get("cache_hit") else "executed"
                logger.info("  - %s: %s", e["tool"], status)
    else:
        logger.info("- Tool executions (run context): (none)")

    # Skipped tools (not seen at root stream and not in run registry)
    skipped_tools = collector._skipped_tools_with_reason()
    if skipped_tools:
        logger.info("- Tools not invoked this run (not in root events or run registry):")
        for name, reason in skipped_tools:
            if name not in ["google_search","news_fetcher"]:
                logger.info("  - %s: %s", name, reason)
    elif collector.expected_tools:
        logger.info("- All expected tools were called.")

    logger.info(sep)