"""
FastAPI entry point for Docker / containerized deployment.

Launches the ADK web server with auto-discovered agents.
Usage: uvicorn server:app --host 0.0.0.0 --port $PORT
"""

import os

import uvicorn
from google.adk.cli.fast_api import get_fast_api_app

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_SERVICE_URI = os.environ.get(
    "SESSION_SERVICE_URI", "sqlite+aiosqlite:///./sessions.db"
)
ALLOWED_ORIGINS = ["http://localhost", "http://localhost:8080", "*"]

app = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri=SESSION_SERVICE_URI,
    allow_origins=ALLOWED_ORIGINS,
    web=True,
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
