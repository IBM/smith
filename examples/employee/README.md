# Enterprise Employee Hub

SQLite-backed employee hub with a pure-Python API layer, a FastMCP tool server,
and a LangGraph ReAct agent.

## Setup

```bash
uv python install 3.12
uv sync
uv run python init_db.py     # create employee_hub.db
```

## Run the tests

```bash
uv run pytest -v
```

## Run the MCP server (stdio)

```bash
uv run python server.py
```

## Configure the API key

Copy `.env.example` to `.env` and fill it in (loaded automatically by both
`agent.py` and `web.py`):

```bash
cp .env.example .env
```

- `LLM_API_KEY` — API key for the LLM.
- `LLM_API_BASE` — endpoint base URL, e.g. a LiteLLM proxy. Omit to call
  Anthropic directly.
- A plain `ANTHROPIC_API_KEY` still works as a fallback when `LLM_API_KEY` is
  unset. Exported env vars take precedence over `.env`.

## Run the agent (REPL)

```bash
uv run python agent.py
```

Example prompts:
- "Add an employee: Ada Lovelace, ada@corp.com, Engineer, country US."
- "Set Ada's Vacation allotment to 20 days."
- "Create a vacation request for user 1 from 2026-03-02 to 2026-03-06 and approve it."
- "What is user 1's remaining vacation balance for 2026?"

## Chat UI

A browser chat UI talks to the agent over HTTP. It runs as two processes:

```bash
uv run python web.py                          # agent server on 127.0.0.1:8000
uv run python -m http.server 5500 -d ui       # UI on 127.0.0.1:5500
```

Then open http://127.0.0.1:5500. The left pane is the conversation; the right
pane shows the agent's tool calls and results in order (toggle with "Show tool
calls"). In VSCode, use the **Chat (server + UI)** compound in the Run and
Debug panel to launch both at once (reads the key from `.env`).

## Architecture

`sqlite3` → `api/` (pure functions, all logic) → `server.py` (`@mcp.tool()` wrappers)
→ `agent.py` (LangGraph `create_react_agent`). See
`docs/superpowers/specs/2026-07-14-enterprise-employee-hub-design.md`.
