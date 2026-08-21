# Architecture: call-for-papers-mcp (get_events)

## Layers

### HTTP API Layer
- File: agent.py (`/chat`, `/extract_tool_call`)
- Role: Receives chat requests, builds a system prompt that embeds any supplied `user_profile` fields as free text, and hands the question to the Agent layer.
- Inputs: `question` (string), `user_profile` (dict, optional — arbitrary caller-supplied keys, e.g. role/dissertation_area)
- Outputs: system prompt (string, contains subject fields as prose) + user question, passed to the Agent layer
- Current enforcement: none

### Agent Layer
- File: agent.py (`create_react_agent`, `llm_with_tools`)
- Role: LLM reasoning loop. Decides which MCP tool to call and with what arguments, using tool schemas fetched from the MCP client. This is the only layer where both the proposed tool call (`tool_calls[0]`) and the caller's `user_profile` are simultaneously in scope as function-local data.
- Inputs: system prompt (containing subject fields as unstructured text), user question, MCP tool schemas
- Outputs: tool name + arguments (`get_events`, `{keywords, topic, limit}`) passed to the MCP client for execution
- Current enforcement: none — no check that the caller's role permits `get_events`, no check on `topic`/`limit` before execution

### MCP Tool Layer
- File: server.py (`get_events`)
- Role: Declares the `get_events` tool schema and forwards the call to `getEvents()` in app.py. The tool signature carries no caller-identity parameter.
- Inputs: `keywords` (str), `topic` (str), `limit` (int, default 10) — no subject/user field
- Outputs: forwards only `keywords` and `limit` to `getEvents()`. **`topic` is accepted into the schema but discarded here** — `server.py:21` calls `getEvents(keywords, limit)`, never passing `topic` through.
- Current enforcement: none

### Tool Implementation Layer
- File: app.py (`WikiCFPScraper`, `getEvents`)
- Role: Scrapes WikiCFP search results for `keywords`, truncates to `limit`.
- Inputs: `keywords` (str), `limit` (int) — `topic` is not received here at all (dropped one layer up)
- Outputs: `{status, count, events[]}` with event name/description/time/location/deadline/link scraped from an HTML table
- Current enforcement: none. `keywords` is placed directly into the outbound query string (`params={'q': query, ...}`) with no sanitisation.

### External Service
- File: n/a — `http://www.wikicfp.com` (third party)
- Role: Unauthenticated HTML site scraped via `requests` + `BeautifulSoup`. No API key, no auth.
- Inputs: HTTP GET with `q` and `year` params
- Outputs: raw HTML parsed into conference records
- Current enforcement: none (outside this system's control)

## Trust Boundaries

| Field | Source | Classification |
|---|---|---|
| `question` | HTTP request body (`ChatRequest.question`) | Self-reported |
| `user_profile.*` (e.g. `user_role`, `dissertation_area`) | HTTP request body (`ChatRequest.user_profile`), caller-supplied | Self-reported |
| `keywords` | LLM-generated tool argument | Self-reported (model output, unverified) |
| `topic` | LLM-generated tool argument; docstring claims exactly one of 3 values but nothing enforces this | Self-reported |
| `limit` | LLM-generated tool argument, default 10 | Self-reported |
| `research_area` / `dissertation_area` (`system_vars.json`) | Declared statically in `system_vars.json`; if threaded through `user_profile` at runtime, still caller-supplied | Self-reported |
| `queries_this_session` (`system_vars.json`) | Declared as a static value in `system_vars.json`. Nothing in this codebase increments or persists a real per-session count. | Self-reported, and not actually live |
| WikiCFP response HTML | Returned by external website | External/untrusted |

## Data Flow

`question` + `user_profile` → HTTP API layer → Agent layer (LLM reasoning + system prompt w/ subject vars as text) → MCP Tool layer (`get_events(keywords, topic, limit)`) → Tool impl layer (`getEvents(keywords, limit)` — **topic dropped**) → WikiCFP (external)

`events[]` ← Tool impl layer ← MCP Tool layer ← Agent layer (LLM composes final response) ← HTTP API layer

## Enforcement Points

### Current
- None. No layer performs validation, auth, or access control.

### Available (OPA-interceptable)
- **Agent layer**, immediately after the LLM proposes `tool_calls` and before `mcp_client` executes them: `input.name` and `input.arguments.*` (`keywords`/`topic`/`limit`) are structured and visible here. `req.user_profile` is also visible at this point (same request scope) — this is the **only** layer where `input.extensions.subject.*` could be constructed alongside the tool call.
- **MCP Tool layer** (server.py, before `getEvents` executes): `input.arguments.keywords/topic/limit` are visible, but caller identity is **not** — the tool signature carries no subject parameter. `input.extensions.subject.*` cannot be constructed here without changing the tool signature or passing session context out-of-band.

### Blind Spots
- LLM reasoning inside the Agent layer (why a given topic/keywords was chosen) — not interceptable.
- WikiCFP's response content/integrity — no enforcement possible on an external, unauthenticated scrape target.
- `queries_this_session` — declared in `system_vars.json` but never incremented or persisted anywhere in this codebase. Even if passed through as `input.extensions.subject.queries_this_session`, the value is not live.

### guidance.txt coverage sweep
Every numbered rule in `smith/guidance.txt` was checked against the enforcement points above:

| guidance.txt rule | Fields needed | Visible at Agent layer? | Visible at MCP Tool layer? |
|---|---|---|---|
| Role-based access (`faculty`/`phd_student` may use `get_events`; `guest` cannot) | `input.extensions.subject.user_role` | Yes | No — no subject param |
| PhD narrow-scope (`topic` must equal caller's `dissertation_area`) | `input.extensions.subject.dissertation_area`, `input.arguments.topic` | Yes | No — no subject param |
| Approved-topic / role limit caps / disallowed keywords | `input.arguments.topic`, `input.arguments.limit`, `input.arguments.keywords` | Yes | Yes |
| Max 5 `get_events` calls per session | live `queries_this_session` counter | No — not live anywhere | No — not live anywhere |

**Finding:** the two role/identity-dependent rules are enforceable ONLY if OPA is interposed at the Agent layer (where `user_profile` is still in scope), not at the MCP Tool layer where `server.py` currently sits. The session-count rule is a Blind Spot regardless of interception point — this matches the caveat guidance.txt already states about itself.
