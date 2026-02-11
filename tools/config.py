"""
This file is used to configure the model for the agent.
It is used to determine if the model is local or cloud, and to set the model object/wrapper for the agent.
It is also used to set the model name for the logger to identify the model.
It is also used to set the thoughts flag for the model if true when run in CLI with --thoughts flag.
It is also used to set the root agent and sub agents for the agent.
"""

import os
import re
from dotenv import load_dotenv
from google.adk.models.lite_llm import LiteLlm

load_dotenv()

# Never edit this file to change the model
# Instead, change the CLOUD_AI_MODEL or LOCAL_AI_MODEL in the .env file
CLOUD_MODEL = os.getenv("CLOUD_AI_MODEL")
LOCAL_MODEL = os.getenv("LOCAL_AI_MODEL", "qwen3:32b")

LOCAL_LLM = False

# AL_MODEL_NAME is a string/label for the logger to identify the model
# AI_MODEL:
# 1)is the model object/wrapper for the agent,
# 2)for local llm, it is the model object/wrapper for the agent
if CLOUD_MODEL:
    # We are in Cloud Mode
    AI_MODEL = CLOUD_MODEL
    AI_MODEL_NAME = CLOUD_MODEL
else:
    # We are in Local Mode (ollama)
    # Instantiate the wrapper for the Agent, but keep the name for the Logger
    AI_MODEL = LiteLlm(model=LOCAL_MODEL)
    AI_MODEL_NAME = f"local:{LOCAL_MODEL}"
    LOCAL_LLM = True

# This would log the thoughts of the model if true when run in CLI with --thoughts flag
INCLUDE_THOUGHTS = os.getenv("INCLUDE_THOUGHTS", "false").lower() == "true"

# Cache configuration
# Backend: "sqlite" (local dev) | "redis" (future) | "gcs" (future)
CACHE_BACKEND = os.getenv("CACHE_BACKEND", "sqlite")
# Set to "true" to disable caching entirely (always fetch fresh data)
CACHE_DISABLED = os.getenv("CACHE_DISABLED", "false").lower() == "true"

# Timeouts (seconds). Not too sensitive: LLM calls can be slow for large context.
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "120"))  # per LLM completion
RUNNER_TIMEOUT_SECONDS = int(os.getenv("RUNNER_TIMEOUT_SECONDS", "300"))  # full run; 0 = no limit

# ADK specific required variables
ROOT_AGENT = os.getenv("ROOT_AGENT", "SET_ROOT_AGENT_NAME_HERE")
# Support comma- or space-separated list; strip quotes if present
_SUB_AGENTS_RAW = os.getenv("SUB_AGENTS", "stock_analysis_pipeline,stock_data_collector,report_synthesizer,presenter,news_fetcher").strip().strip('"\'')
SUB_AGENTS = [s.strip() for s in re.split(r"[,\s]+", _SUB_AGENTS_RAW) if s.strip()]
