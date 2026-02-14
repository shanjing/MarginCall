"""
FastAPI entry point for Docker / containerized deployment.

Launches the ADK API server and serves the custom frontend.
Usage: uvicorn server:app --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

import agentops
import asyncio
import json
import logging
import os
import queue
from collections import deque
from datetime import date

import uvicorn
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(AGENT_DIR, "frontend")
SESSION_SERVICE_URI = os.environ.get(
    "SESSION_SERVICE_URI", "sqlite+aiosqlite:///./sessions.db"
)
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost,http://localhost:8080,*"
).split(",")

# Initialize AgentOps for observability 
# https://google.github.io/adk-docs/integrations/agentops/#how-agentops-instruments-adk
agentops.init(
    api_key=os.getenv("AGENTOPS_API_KEY"), # Your AgentOps API Key
    trace_name="margincall-ui-adk-app-trace"  # Optional: A name for your trace
    # auto_start_session=True is the default.
    # Set to False if you want to manually control session start/end.
)

app = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri=SESSION_SERVICE_URI,
    allow_origins=ALLOWED_ORIGINS,
    web=False,
)

# ── Log stream (real-time: thread-safe queue + async consumer + replay buffer) ─────────
_log_subscribers: list[asyncio.Queue[str]] = []
_shared_log_queue: queue.Queue[str] = queue.Queue()
_log_replay: deque[str] = deque(maxlen=400)
_consumer_started: bool = False


class LogStreamHandler(logging.Handler):
    """Pushes log records into a thread-safe queue (no event loop needed)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record).replace("\n", " ").strip()
            if not msg:
                return
            try:
                _shared_log_queue.put_nowait(msg)
            except Exception:
                pass
        except Exception:
            self.handleError(record)


# Module-level handler — created and attached at import time so it works
# regardless of whether on_startup fires (adk web vs uvicorn server:app).
_log_handler = LogStreamHandler()
_log_handler.setLevel(logging.DEBUG)
_log_handler.setFormatter(
    logging.Formatter("[%(asctime)s] %(levelname)-8s %(message)s", datefmt="%m/%d/%y %H:%M:%S")
)
_root = logging.getLogger()
_root.setLevel(logging.INFO)
_root.addHandler(_log_handler)
_shared_log_queue.put_nowait("[LOG STREAM] Handler attached at module load.")


def _ensure_log_handler():
    """(Re-)attach the LogStreamHandler to root if missing (e.g. after basicConfig(force=True))."""
    root = logging.getLogger()
    if _log_handler not in root.handlers:
        root.addHandler(_log_handler)
    if root.level > logging.INFO:
        root.setLevel(logging.INFO)


def _get_log_line():
    try:
        return _shared_log_queue.get(timeout=0.12)
    except queue.Empty:
        return None


async def _log_broadcast_consumer():
    """Moves log lines from thread-safe queue to all subscriber queues and replay buffer."""
    loop = asyncio.get_event_loop()
    _heal_counter = 0
    while True:
        try:
            _heal_counter += 1
            if _heal_counter >= 10:
                _ensure_log_handler()
                _heal_counter = 0

            line = await loop.run_in_executor(None, _get_log_line)
            if line is not None:
                _log_replay.append(line)
                for q in list(_log_subscribers):
                    try:
                        q.put_nowait(line)
                    except Exception:
                        pass
        except Exception:
            await asyncio.sleep(0.05)


def _ensure_consumer_started():
    """Start the broadcast consumer task if not already running.

    Safe to call from any async context (startup hook, first SSE request, etc.).
    """
    global _consumer_started
    if _consumer_started:
        return
    _consumer_started = True
    asyncio.create_task(_log_broadcast_consumer())


# Charts API: fetch chart images from cache (populated when pipeline runs)
# Tool responses are not streamed to client when pipeline runs as sub-agent
charts_router = APIRouter(prefix="/api", tags=["charts"])


@charts_router.get("/charts")
async def get_charts(ticker: str):
    """Return chart images (base64) for a ticker from cache. Used by frontend after report."""
    if not ticker or len(ticker) > 10:
        raise HTTPException(400, "Invalid ticker")
    from tools.cache import get_cache
    from tools.cache.base import CacheBackend

    cache = get_cache()
    today = date.today().isoformat()
    cache_key = CacheBackend.make_key(ticker.upper(), "technicals_with_chart", today)
    data = await cache.get_json(cache_key)
    if not data or "charts" not in data:
        return {"charts": {}}
    charts = data.get("charts", {})
    out = {}
    for k, v in charts.items():
        if isinstance(v, dict) and v.get("image_base64"):
            out[k] = {"label": v.get("label", k), "image_base64": v["image_base64"]}
    return {"charts": out}


@charts_router.get("/log_stream")
async def log_stream():
    """SSE stream of server logs. Replays recent buffer then streams new lines in real time."""
    # Ensure consumer is running (covers case where on_startup didn't fire)
    _ensure_consumer_started()
    _ensure_log_handler()

    client_queue: asyncio.Queue[str] = asyncio.Queue()
    _log_subscribers.append(client_queue)

    async def generate():
        # Flush-busting padding so first chunk is sent immediately
        yield ": " + (" " * 2046) + "\n\n"
        # Replay recent logs so client sees context immediately
        for line in _log_replay:
            yield f"data: {json.dumps({'log': line})}\n\n"
        try:
            while True:
                try:
                    line = await asyncio.wait_for(client_queue.get(), timeout=0.25)
                    if line is None:
                        break
                    yield f"data: {json.dumps({'log': line})}\n\n"
                except asyncio.TimeoutError:
                    yield ": k\n\n"
                except asyncio.CancelledError:
                    break
        finally:
            if client_queue in _log_subscribers:
                _log_subscribers.remove(client_queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",
        },
    )


@app.on_event("startup")
async def on_startup():
    _ensure_log_handler()
    _ensure_consumer_started()


app.include_router(charts_router)

# Serve custom frontend at / (must be mounted after API routes)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
