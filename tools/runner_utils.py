import asyncio
import uuid
import os
from pathlib import Path
from dotenv import load_dotenv

from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from .config import AI_MODEL_NAME, LOCAL_LLM, RUNNER_TIMEOUT_SECONDS
from .logging_utils import (
    log_agent_failure,
    log_event,
    log_llm_error,
    log_run_summary,
    log_session_state,
    logger,
    RunSummaryCollector,
)
from .run_context import get_run_tool_registry, init_run_tool_registry

# Load the .env relative to the project root
load_dotenv(dotenv_path=Path(os.getcwd()) / ".env")

# In project .env set AGENT_APP_NAME, USER_ID, AGENT_ENV
# Strip quotes so values like "MarginCall" from Docker --env-file work as identifiers
def _env_id(key: str, default: str) -> str:
    return os.getenv(key, default).strip().strip("'\"")

APP_NAME = _env_id("AGENT_APP_NAME", "noname_app")
DB_PATH = Path(os.getcwd()) / f"{APP_NAME}_sessions.db"
DB_URL = f"sqlite+aiosqlite:///{DB_PATH.resolve().as_posix()}"

# Singleton Session Service
session_service = DatabaseSessionService(db_url=DB_URL)


def build_user_message(text: str) -> types.Content:
    """
    Standardizes input for the ADK runner.
    1. Role: 'user' is mandatory for LiteLLM and multi-turn routing.
    2. Parts: Must be a list to allow for future multi-modal (image/file) expansion.
    3. Dict Format: More serializable for logging than raw class objects.
    Note:
    # Using the dictionary format is often more robust for the runner's internal mapping
    # later add support for other message types, such as images, files, etc.
    """
    if not text or not text.strip():
        # Fail fast on invalid input before hitting the API
        raise ValueError("User input text cannot be empty.")

    return types.Content(role="user", parts=[types.Part(text=text)])


async def execute_agent_stream(app, input_text, initial_state=None, debug=False):
    """
    (Runner Utility) Executes an agent stream with logging and state inspection.
    Args:
        app: The ADK app to execute.
        input_text: The user input text to send to the agent.
        initial_state: The initial state to start the session with.
        debug: Whether to enable debug mode.
    Returns:
        The final response text.
    """
    run_summary = RunSummaryCollector()
    run_summary.set_expected_from_app(app)
    run_summary.model_name = AI_MODEL_NAME
    init_run_tool_registry()

    runner = Runner(app=app, session_service=session_service)
    session_id = str(uuid.uuid4())
    user_id = _env_id("USER_ID", "default_user")

    await session_service.create_session(
        app_name=app.name,
        user_id=user_id,
        session_id=session_id,
        state=initial_state or {},
    )
    if debug:
        # 1. Inspect STARTING state
        curr_session = await session_service.get_session(
            app_name=app.name,
            user_id=user_id,
            session_id=session_id,
        )
        log_session_state(curr_session.state, label="PRE-FLIGHT STATE", session_id=session_id)

    final_text_parts = []
    _run_status = "success"

    async def _stream():
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=build_user_message(input_text),
        ):
            run_summary.record_event(event)
            if debug:
                await log_event(event)
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        final_text_parts.append(part.text)

    try:
        if RUNNER_TIMEOUT_SECONDS > 0:
            await asyncio.wait_for(_stream(), timeout=RUNNER_TIMEOUT_SECONDS)
        else:
            await _stream()
    except (asyncio.TimeoutError, TimeoutError) as e:
        _run_status = "timeout"
        log_agent_failure(
            agent_name="runner",
            error_type="timeout",
            message=f"Run exceeded {RUNNER_TIMEOUT_SECONDS}s: {e}",
            session_id=session_id,
        )
        raise
    except Exception as e:
        err_str = str(e).lower()
        if "timeout" in err_str or "timed out" in err_str:
            _run_status = "timeout"
            log_agent_failure(
                agent_name="runner",
                error_type="timeout",
                message=str(e),
                session_id=session_id,
                exc_info=True,
            )
        elif "apiconnectionerror" in type(e).__name__.lower() or "ollama" in err_str or "500" in err_str or "litellm" in err_str:
            _run_status = "llm_error"
            log_llm_error(message=str(e), session_id=session_id, exc_info=True)
        else:
            _run_status = "agent_error"
            log_agent_failure(
                agent_name="runner",
                error_type="agent_error",
                message=str(e),
                session_id=session_id,
                exc_info=True,
            )
        raise

    finally:
        run_summary.finish_run()
        run_summary.tool_execution_registry = get_run_tool_registry()
        # ── Prometheus metrics ──
        try:
            from tools.metrics import METRICS_ENABLED
            if METRICS_ENABLED:
                from tools.metrics import run_duration_seconds, run_total
                run_duration_seconds.observe(run_summary.total_seconds())
                run_total.labels(status=_run_status).inc()
        except Exception:  # noqa: BLE001
            pass
        final_session = await session_service.get_session(
            app_name=app.name,
            user_id=user_id,
            session_id=session_id,
        )
        if final_session is not None:
            run_summary.set_session(final_session)
        log_run_summary(run_summary)
        if debug and final_session is not None:
            log_session_state(final_session.state, label="POST-FLIGHT STATE", session_id=session_id)

    return "".join(final_text_parts) if final_text_parts else "(no final response text)"