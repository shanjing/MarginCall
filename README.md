## MarginCall

MarginCall is a multi-agent stock research tool. It feteches real-time market signals (financial data, chart, news, reddit posts), synthesizing structured reports via a movie-inspired persona (Sam Rogers). The opensourced version offers simple sentiment analysis while the private version offers advanced sentiment analysis based on paid real time financial data.


**To start the agent (the quickest way to use it the first time)**

```
git clone https://github.com/shanjing/MarginCall.git
cd MarginCall; ./setup.sh

# recommended model for setup:
# gemini-2.5-flash(cloud) or gemma4:8B (ollama)
```

**Requirements to run the agent**

Must have a valid `GOOGLE_API_KEY` or other cloud API key (run ./setup.sh to load the API keys)
Current release supports MacOS and Linux, Windows setup is W.I.P.

## UI 

<img width="1777" height="1107" alt="margincall_ui_small" src="https://github.com/user-attachments/assets/1dae7abf-f1a7-4197-8d05-2481858fe5a8" />
<img width="1780" height="1112" alt="margincall_ui_small_1" src="https://github.com/user-attachments/assets/6d998fcb-6e7b-406d-97c7-0318027b51c7" />
<img width="1778" height="1111" alt="margincall_ui_small_2" src="https://github.com/user-attachments/assets/5ce87171-08e5-46b9-b65d-6da9602987c6" />

**LLM Models**

The agent is tested to work with google gemini* models and gemma4.
It uses ADK's google_search tool and auto switches to brave.com search via MCP for non-gemini cloud based models.

If using a local model, it must support tool callings.

**Credits**

The agentic design, project structure, data schema, infrastructure design and the core agent/utility code were created by **[Shan Jing](https://www.linkedin.com/in/shanjing/)** (mr.shanjing@gmail.com). Frontend UI code, most routine code was written with Cursor/AI assistance pair programming. The codebase is fully verified and maintained by the author.

**Disclaimer**

This project is for entertainment and technical demonstration only. It is not investment advice. AI can hallucinate; always verify data independently. 
It is provided **as-is, without warranty**. The authors are not liable for any use of this software.