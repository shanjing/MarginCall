## MarginCall

MarginCall is a production-grade multi-agent research framework built on Google ADK. It orchestrates AI agents to ingest unstructured web data and real-time market signals, synthesizing high-fidelity reports delivered via a movie-inspired persona (Sam Rogers).

<img width="1777" height="1107" alt="margincall_ui_small" src="https://github.com/user-attachments/assets/1dae7abf-f1a7-4197-8d05-2481858fe5a8" />


**Design**

1. Agentic Pattern 
The system employs a supervisor-led, multi-agent collaboration design: 
- supervisor model at the top, sequential handoffs + expert team inside the pipeline
- “agent as a tool” used for both the pipeline and the news sub-agent. 
- MCP and tool-calling to provide real-time knowledge

2. Infrastructure 
- 3-tier cache for different data sources with 80%+ expected cache hits to reduce latency
- Token Monitoring and Rate-Limit to avoid flooding session states for cost control

3. Agent Development 
- System and Agentic two layers with separate schemas for quick development and easy debugging
- Strong data schemas to ensure data fidelity and to eliminate LLM hallucinations

4. Cloud Deployment
Stateless design for horizontal scalability, can run in:
- a Docker container/Kubernetes Pods or 
- a headless adk web or
- CLI for debugging

5. Observability [W.I.P]
- token monitoring to prevent bloating LLM context; (W.I.P)
- extensive logging in CLI;
- export metrics for Prometheus/Grafana stack;
- use third party tools such as AgentOps

6. AI Integration

Claude Code contexts, commands, and skills are provided for AI assistants.
```
git clone https://github.com/shanjing/MarginCall
cd MarginCall
claude
>/context
> tell me about this project, what it does, the structure, the requirements and how to run it
...
```



**Requirements to run the agent**

1. Must be in the virtual environment (see Initial Setup below)
2. Must have a valid `GOOGLE_API_KEY` defined in the repo root `.env` file.
   - Use env.example as a template to create your own .env file;
   - To create your Google API key, go to [Google AI Studio](https://aistudio.google.com/api-keys).)

The agent is tested to work with gemini-2.5-flash, gemini-3-pro-preview.
It uses ADK's google_search tool and auto switches to brave.com search via MCP for non-gemini cloud based models.
Local LLM models such as Qwen3 seems to have issues with tool calling.


**Initial setup**
Create a virtual environment and install required packages
```
python -m venv .venv
pip install -r reqiurements.txt
```

**Models and API keys**
- Cloud based models such as gemini-* is recommended for extensive tools support and google internal tools (searh etc).
- Must have API keys to use cloud based models (see env.example file)
- Local LLM (ollama) models must support tools, qwen3-coder-next.


**To start the agent**
(must set API key in .env file, see env.example as a template)
1. Run full UI version (the quickest way to see the full features)
```
cd MarginCall; source .venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8080

#open browser to localhost:8080
```
2. Start ADK UI
```
adk web
# a. Open browser to localhost:8000
# b. On the left side of the screen, select "stock_analyst"
# c. In the chat box, start talking to the agent "give me a real-time research on AAPL"
```

4. To run in CLI for debugging or text-based chat:
```
python -m main run --help
python -m main run -i "tell me about GOOGL"
python -m main run -i "what is AMZN's next earning report date?"
python -m main run -i "how crazy is the market today?"
python -m main run -i "what is AMZN's option put/call ratio right now?"
python -m main run -i "tell me about GOOGL" -d -t
```

5. To run in a docker container
```
(create .env file with API keys, see env.example)
docker build -t margincall:latest .

# Security check to ensure there is no api key leaking in the image
docker run --rm margincall:latest grep -r "sk-" /app

docker run -p 8080:8080 --env-file .env margincall:latest
#open a browser to localhost:8080
```

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
        v                       
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

**Credits**

The agentic design, project structure, data schema, infrastructure design and agent/utility code were created by **[Shan Jing](https://www.linkedin.com/in/shanjing/)** (mr.shanjing@gmail.com). Frontend UI code is 100%  done by AI/Cursor.


**License & disclaimer**

This project is open source; use and modify it as you like. It is provided **as-is, without warranty**. The authors are not liable for any use of this software.

Disclaimer: This project is for entertainment and technical demonstration only. It is not investment advice. AI can hallucinate; always verify data independently.
