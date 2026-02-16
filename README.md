## MarginCall

MarginCall is a multi-agent research AI tool built on Google ADK. It orchestrates AI agents to ingest unstructured web data and real-time market signals, synthesizing high-fidelity reports delivered via a movie-inspired persona (Sam Rogers).

<img width="1777" height="1107" alt="margincall_ui_small" src="https://github.com/user-attachments/assets/1dae7abf-f1a7-4197-8d05-2481858fe5a8" />

<img width="1780" height="1112" alt="margincall_ui_small_1" src="https://github.com/user-attachments/assets/6d998fcb-6e7b-406d-97c7-0318027b51c7" />

<img width="1778" height="1111" alt="margincall_ui_small_2" src="https://github.com/user-attachments/assets/5ce87171-08e5-46b9-b65d-6da9602987c6" />


**Requirements to run the agent**

Must have a valid `GOOGLE_API_KEY` or other cloud API key (run ./setup.sh to load the API keys)

**To start the agent (the quickest way to use it the first time)**

```
git clone https://github.com/shanjing/MarginCall.git
cd MarginCall; ./setup.sh
```

**To manually start the headless agent with ADK (for developer to debug)**

```
cd MarginCall; ./setup.sh (select 'n' at Start the agent now? (y/n): )
adk web
# Open a browser to localhost:8000
```

To run in CLI for debugging or text-based chat:

```
cd MarginCall; ./setup.sh (select 'n' at Start the agent now? (y/n): )
python -m main run --help
python -m main run -i "what is AMZN's next earning report date?"
python -m main run -i "tell me about GOOGL"
python -m main run -i "how crazy is the market today?"
python -m main run -i "what is AMZN's option put/call ratio right now?"
python -m main run -i "tell me about GOOGL" -d -t
```

To run in a docker container

```
(run setup.sh and create .env file with a valid API key)
docker build -t margincall:latest .

# Security check to ensure there is no api key leaking in the image
docker run --rm margincall:latest grep -r "sk-" /app

docker run -p 8080:8080 --env-file .env margincall:latest
#open a browser to localhost:8080
```


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
> tell me about this project
...
```

**LLM Models**
The agent is tested to work with gemini-2.5-flash, gemini-3-pro-preview.
It uses ADK's google_search tool and auto switches to brave.com search via MCP for non-gemini cloud based models.

Local LLM models must support tools.



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
