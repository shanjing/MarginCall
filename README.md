## MarginCall

Multi-agent stock research system built on Google ADK. Orchestrates AI agents to ingest unstructured web data and real-time market signals, synthesizing structured reports via a movie-inspired persona (Sam Rogers).

Built with infrastructure-grade patterns: contract-driven schemas, cost-aware caching, token budget management, and stateless horizontal scaling. See **[ENGINEERING.md](ENGINEERING.md)** for architecture decisions, scaling design, and infrastructure deep dives.

<img width="1777" height="1107" alt="margincall_ui_small" src="https://github.com/user-attachments/assets/1dae7abf-f1a7-4197-8d05-2481858fe5a8" />

<img width="1780" height="1112" alt="margincall_ui_small_1" src="https://github.com/user-attachments/assets/6d998fcb-6e7b-406d-97c7-0318027b51c7" />

<img width="1778" height="1111" alt="margincall_ui_small_2" src="https://github.com/user-attachments/assets/5ce87171-08e5-46b9-b65d-6da9602987c6" />


**Requirements to run the agent**

Must have a valid `GOOGLE_API_KEY` or other cloud API key (run ./setup.sh to load the API keys)
Current setup supports MacOS and Linux, Windows setup is W.I.P.


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

**LLM Models**
The agent is tested to work with gemini-2.5-flash, gemini-3-pro-preview.
It uses ADK's google_search tool and auto switches to brave.com search via MCP for non-gemini cloud based models.

Local LLM models must support tools.

**Credits**

The agentic design, project structure, data schema, infrastructure design and the core agent/utility code were created by **[Shan Jing](https://www.linkedin.com/in/shanjing/)** (mr.shanjing@gmail.com). Frontend UI code, most routine code was written with AI assistance or pair programming. The codebase is fully verified and maintained by the author.

**Disclaimer**
This project is for entertainment and technical demonstration only. It is not investment advice. AI can hallucinate; always verify data independently. 

**License & disclaimer**

This project is open source; use and modify it as you like. It is provided **as-is, without warranty**. The authors are not liable for any use of this software.