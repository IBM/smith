# Architecture: call-for-papers-mcp

## Layers

### HTTP API Layer
- File: `agent.py` (`/chat`, `/extract_tool_call`, `/health`, FastAPI on :9000)
- Role: Accepts inbound HTTP requests with an optional `user_profile` dict and the user's natural-language question; builds the system prompt by embedding `user_profile` key/values verbatim, then forwards to the LangGraph ReAct agent.
- Inputs: `question` (string), `user_profile` (optional dict — any key/value; caller-supplied).
- Outputs: System prompt string + user message passed to the agent layer.
- Current enforcement: None — no authentication, no schema validation on `user_profile`, no role check.

### Agent Layer (LangGraph ReAct)
- File: `agent.py` (`build_agent`, `build_system_prompt`, `chat`, `extract_tool_call`)
- Role: Runs a LangGraph ReAct loop — the LLM reads the system prompt (which embeds `user_profile` key/values verbatim), decides to call `get_events`, and constructs `keywords`, `topic`, and `limit` arguments. Launches `server.py` over stdio via `MultiServerMCPClient`.
- Inputs: System prompt (containing verbatim `user_profile` entries), user message.
- Outputs: MCP `tools/call` requests over stdio with `name=get_events`, `arguments={keywords, topic, limit}`.
- Current enforcement: None — `user_profile` is advisory; LLM may or may not respect role constraints stated in the system prompt.

### MCP Tool Server
- File: `server.py` (stdio transport, FastMCP)
- Role: Single tool `get_events` — thin wrapper that forwards `keywords` and `limit` to `app.getEvents()`; `topic` is carried for policy scoping only and does not affect the WikiCFP query.
- Inputs: JSON-RPC `tools/call` with `keywords` (string, required), `topic` (string, required), `limit` (int, default 10).
- Outputs: `{"status", "count", "events": [...]}` dict from WikiCFP scrape.
- Current enforcement: FastMCP schema validation (parameter types). No authorization, no topic enforcement, no limit cap.

### Tool Implementation Layer
- File: `app.py` (`WikiCFPScraper`, `getEvents`)
- Role: Scrapes WikiCFP (`http://www.wikicfp.com/cfp/servlet/tool.search`) using the `keywords` query string; `topic` is ignored entirely by `getEvents` — it only passes `keywords` and `limit` to the scraper.
- Inputs: `keywords` (string), `limit` (int or None).
- Outputs: List of conference dicts (`event_name`, `event_description`, `event_time`, `event_location`, `deadline`, `event_link`).
- Current enforcement: None — `limit` is applied as a Python slice after retrieval; no domain or keyword filtering.

### External Service
- Service: WikiCFP (`http://www.wikicfp.com`)
- Role: Third-party conference listing site; scraped via HTTP GET with no authentication.
- Inputs: `q` (query string), `year` (hardcoded `'t'` = this year).
- Outputs: HTML page parsed into conference records.
- Current enforcement: None — WikiCFP returns whatever matches the query; no topic or content filtering on the external side.

---

## Trust Boundaries

| Field | Source | Classification |
|---|---|---|
| `user_profile` (all keys) | HTTP caller (JSON body) | Self-reported — no cryptographic verification; caller can supply any key/value |
| `user_profile.user_role` | HTTP caller | Self-reported — caller asserts their own role (`faculty`, `phd_student`, `guest`) |
| `user_profile.dissertation_area` | HTTP caller | Self-reported — caller asserts their PhD dissertation area |
| `user_profile.queries_this_session` | HTTP caller | Self-reported — caller asserts their session query count; trivially forgeable |
| `input.extensions.subject.user_role` | Caller-supplied `user_profile` | Self-reported |
| `input.extensions.subject.dissertation_area` | Caller-supplied `user_profile` | Self-reported |
| `input.extensions.subject.queries_this_session` | Caller-supplied `user_profile` | Self-reported |
| `input.extensions.subject.research_area` | Caller-supplied `user_profile` | Self-reported |
| `input.name` (tool name, LLM-chosen) | Agent (LLM) | Self-reported — LLM-generated |
| `input.args.keywords` | Agent (LLM) | Self-reported — LLM-chosen from user message |
| `input.args.topic` | Agent (LLM) | Self-reported — LLM-chosen; must be one of three approved values per tool docstring |
| `input.args.limit` | Agent (LLM) | Self-reported — LLM-chosen; no cap enforced at tool layer |
| WikiCFP response data (event names, descriptions, links) | WikiCFP external website | External/untrusted — third-party content; no integrity guarantee |

---

## Data Flow

```
HTTP caller
  │  POST /chat  {question, user_profile: {user_role, dissertation_area, queries_this_session, ...}}
  ▼
agent.py HTTP API layer (:9000)
  │  build_system_prompt() — embeds user_profile key/values verbatim into SYSTEM_PROMPT_BASE
  ▼
LangGraph ReAct agent
  │  LLM: reads system prompt + user question → selects get_events → constructs {keywords, topic, limit}
  ▼  stdio (MultiServerMCPClient)
server.py MCP tool server
  │  get_events(keywords, topic, limit) → calls app.getEvents(keywords, limit)
  │  NOTE: topic is NOT passed to getEvents; it only exists as an OPA policy field
  ▼
app.py WikiCFPScraper
  │  HTTP GET to http://www.wikicfp.com/cfp/servlet/tool.search?q=<keywords>&year=t
  ▼
WikiCFP (external)
  ▼
Response ← app ← server ← LLM (formatted answer) ← HTTP caller
```

---

## Enforcement Points

### Current
- **MCP Tool Server**: FastMCP schema validation only (parameter types, `keywords` and `topic` required). No topic filtering, no limit cap, no role check.
- **No authorization or content-filtering layer exists anywhere in this system today.**

### Available (OPA-interceptable)
OPA intercepts at the agent → MCP server boundary. Fields present as structured data at that point:

**From `input.extensions.subject.*` (populated from `user_profile`):**
- `input.extensions.subject.user_role` — string: `faculty`, `phd_student`, or `guest`
- `input.extensions.subject.dissertation_area` — string: one of the three approved areas (PhD students only)
- `input.extensions.subject.queries_this_session` — integer: running per-session call count (self-reported)
- `input.extensions.subject.research_area` — array of approved topics

**From `input.args.*`:**
- `input.args.keywords` — string (free text)
- `input.args.topic` — string (must be one of three approved values)
- `input.args.limit` — integer (default 10)

**guidance.txt coverage sweep:**
| Rule | Fields needed | Available? | Verdict |
|---|---|---|---|
| Only `faculty`/`phd_student` may use `get_events` | `subject.user_role` | Available | OPA-enforceable |
| `topic` must be one of three approved areas | `args.topic` | Available | OPA-enforceable |
| `limit` between 1 and role cap (faculty ≤15, phd_student ≤10) | `args.limit`, `subject.user_role` | Available | OPA-enforceable |
| No more than 5 searches per session | `subject.queries_this_session` | Available (self-reported) | OPA-enforceable only if caller honestly reports count |
| Disallowed `keywords` substrings | `args.keywords` | Available | OPA-enforceable (case-insensitive substring match) |
| PhD student must use own `dissertation_area` as `topic` | `args.topic`, `subject.dissertation_area`, `subject.user_role` | Available | OPA-enforceable |

### Blind Spots
- **WikiCFP response content**: OPA intercepts before tool execution; it cannot inspect the returned conference list. A disallowed topic could be indirectly reached via innocuous keywords that happen to return off-topic results.
- **`queries_this_session` is self-reported**: a caller can set this to 0 to reset the session counter; the per-session cap is only enforced against an honest client.
- **`dissertation_area` is self-reported**: a PhD student can claim any `dissertation_area` to unlock a broader topic; identity is not verified.
- **`topic` is not forwarded to WikiCFP**: `app.getEvents` ignores the `topic` argument entirely — the actual search is driven only by `keywords`. OPA can block a disallowed `topic` value, but a caller can supply an approved `topic` while using `keywords` that target an off-topic domain (the `keywords` blocklist partially mitigates this).
- **LLM reasoning**: the LLM constructs `topic` and `keywords` from natural language; prompt injection in the user message could cause the LLM to select a disallowed `topic` or blocked `keywords` value, bypassing the advisory system-prompt constraints.
