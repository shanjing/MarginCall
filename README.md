## MarginCall

MarginCall is a multi-agent stock reporting tool built on Google ADK: it extracts facts from major websites, collects market data, synthesizes a report, and presents it in character (Sam Rogers–style).
For entertainment only—not investment advice; do your own research.


**Requirements to run the agent**

1. Must be in the virtual environment (see Initial Setup below)
2. Must have a valid `GOOGLE_API_KEY` defined in the repo root `.env` file.
   - Use env.example as a template to create your own .env file;
   - To create your Google API key, go to [Google AI Studio](https://aistudio.google.com/api-keys).)

The agent is tested to work with gemini-2.5-flash, gemini-3-pro-preview.
It uses ADK's google_search tool and auto switches to brave.com search via MCP for non-gemini models.


**Initial setup**
Create a virtual environment and install required packages
```
python -m venv .venv
pip install -r reqiurements.txt
```

**To start the agent**
1. Start ADK UI
```
adk web
# a. Open browser to localhost:8000
# b. On the left side of the screen, select "stock_analyst"
# c. In the chat box, start talking to the agent "give me a real-time research on AAPL"
```

2. To run in CLI for debugging or text-based chat:
```
python -m main run --help
python -m main run -i "tell me about GOOGL"
python -m main run -i "what is AMZN's next earning report date?"
python -m main run -i "how crazy is the market today?"
python -m main run -i "what is AMZN's option put/call ratio right now?"
python -m main run -i "tell me about GOOGL" -d -t
```

**Architecture & infrastructure**

The project structure is crafted by a utility **agent_forge** (to be open sourced on GitHub soon); it is structured for clarity and future scale.

- **Config** — Env-driven (`tools/config.py`): model (cloud/local), cache backend, root and sub-agents, timeouts; no hardcoding.
- **Caching** — Pluggable backend (SQLite today; Redis or GCS later via `CACHE_BACKEND`), single key shape and TTL tiers so data tools stay backend-agnostic.
- **Sessions** — Configurable (`SESSION_SERVICE_URI`); FastAPI server and CLI load agents from config.
- **Automation** — Env/agent sanity checks (`check_env.py`), single Docker path with `--env-file`, runner that discovers and runs the pipeline from `ROOT_AGENT` and `SUB_AGENTS`.
- **Agentic layer** — Supervisor → pipeline → data/report/present is kept separate from this plumbing so adding tools or sub-agents stays straightforward.


**Deployment Options**
1. Local Docker Container
```
  # Build
  docker build -t margincall:latest .
  
  # SRE nuke test to ensure there is no api key leaking in the image
  docker run --rm margincall:latest grep -r "sk-" /app

  # Run (env vars from .env on the host; not baked into the image)
  docker run -p 8080:8080 --env-file .env margincall:latest
```
  Then access at http://localhost:8080 (web UI) or http://localhost:8080/docs (Swagger).

2. Agent Engine in Vertex AI
3. Cloud Run
4. Google Kubernetes Engine (GKE)

**Agentic Pattern**

Supervisor → AgentTool(sequential pipeline (data → report → present)):


```
    ┌─────────────────────────────────────────────────────────┐
    │ stock_analyst (root)                                    │
    │ tools: stock_analysis_pipeline, invalidate_cache         │
    └───────────────────────────┬─────────────────────────────┘
                                │
                                v
    ┌─────────────────────────────────────────────────────────┐
    │ stock_analysis_pipeline (sequential)                    │
    └───────────────────────────┬─────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        v                       v                       v
    ┌───────────────┐     ┌───────────────┐     ┌──────────────┐
    │stock_data_    │ ──> │report_        │ ──> │ presenter    │
    │collector      │     │synthesizer    │     │ (no tools)   │
    │               │     │ (no tools)    │     └──────────────┘
    │ tools:        │     │               │
    │ fetch_stock_  │     └───────────────┘
    │ price,        │
    │ fetch_        │
    │ financials,   │
    │ fetch_        │
    │ technicals_   │
    │ with_chart,   │
    │ fetch_cnn_    │
    │ greedy,       │
    │ fetch_vix,    │
    │ fetch_        │
    │ stocktwits_   │
    │ sentiment,    │
    │ fetch_        │
    │ options_      │
    │ analysis,     │
    │ news_fetcher  │
    └───────┬───────┘
            │
            v
    ┌───────────────┐
    │ news_fetcher  │
    │ google_search │
    │ | brave_search│
    └───────────────┘
```

**Troubleshooting**

1. Make sure you have created and activated the virtual environment; see the repo root's README.md.
2. Make sure you have a valid `GOOGLE_API_KEY` defined in `.env`.
3. Make sure you have a valid model defined in the `.env` file (e.g. `CLOUD_AI_MODEL=gemini-2.5-flash`).
4. **Docker: "Model 'gemini-2.5-flash' not found"** — When using a Google AI Studio API key (not Vertex AI), set `GOOGLE_GENAI_USE_VERTEXAI=false` in your `.env` so the registry uses the correct backend. Include it in `--env-file .env` when running the container.

**Credits**

The agentic design, project structure, majority code and infrastructure design were created by **[Shan Jing](https://www.linkedin.com/in/shanjing/)** (mr.shanjing@gmail.com). 

For educational use and ongoing feature development, Claude Code context, commands, and skills were added to the project.

**License & disclaimer**

This project is open source; use and modify it as you like. It is provided **as-is, without warranty**. The authors are not liable for any use of this software. This is not financial or investment advice—see the disclaimer at the top of this README.
