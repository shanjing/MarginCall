"""
FastAPI entry point for Docker / containerized deployment.

Launches the ADK API server and serves the custom frontend.
Usage: uvicorn server:app --host 0.0.0.0 --port $PORT
"""

import os

import uvicorn
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

app = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri=SESSION_SERVICE_URI,
    allow_origins=ALLOWED_ORIGINS,
    web=False,
)

# Serve custom frontend at / (must be mounted after API routes)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
