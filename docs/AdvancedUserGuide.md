
MarginCall is a multi-agent stock research tool built on Google ADK. Orchestrates AI agents to ingest unstructured web data and real-time market signals, synthesizing structured reports via a movie-inspired persona (Sam Rogers).

Built with infrastructure-grade patterns: contract-driven schemas, cost-aware caching, token budget management, and stateless horizontal scaling. See **[ENGINEERING.md](ENGINEERING.md)** for architecture decisions, scaling design, and infrastructure deep dives.

**To manually start the headless agent with ADK (for developer to debug)**

```
1. cd MarginCall; ./setup.sh (select 'n' at Start the agent now? (y/n): )
2. adk web
3. open a browser to localhost:8000
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