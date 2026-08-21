# Architecture: call-for-papers-mcp

## Layers

### HTTP API Layer
- File: agent.py
- Role: Exposes `/chat` and `/extract_tool_call` FastAPI endpoints that receive user questions and optional user_profile context, then invoke the agent or LLM-with-tools.
- Inputs: `question` (string), `user_profile` (optional dict — arbitrary key/value pairs including role, dissertation_area, queries_this_session)
- Outputs: Natural-language response string (`/chat`) or structured `{tool_name, arguments}` (`/extract_tool_call`)
- Current enforcement: None. `user_profile` is accepted as-is and injected verbatim into the system prompt with no validation or type checking.

### Agent / LLM Layer
- File: agent.py (`build_system_prompt`, `create_react_agent`)
- Role: Constructs the system prompt from the base instruction string plus any `user_profile` key-value pairs, then invokes the LLM (via LangGraph ReAct agent or `llm_with_tools`) to plan and execute tool calls.
- Inputs: System prompt (base + user_profile variables), user question
- Outputs: Tool call decisions (`tool_name`, `arguments`) passed to the MCP layer
- Current enforcement: None. System prompt variables are injected from the unvalidated `user_profile` dict. The LLM decides which tool to call and with what arguments.

### MCP Tool Layer
- File: server.py
- Role: Defines and exposes the `get_events` MCP tool over stdio transport via FastMCP. Accepts `keywords`, `topic`, and `limit` and delegates to `app.py`.
- Inputs: `keywords` (string, required), `topic` (string, required), `limit` (integer, optional, default 10)
- Outputs: Return value of `getEvents(keywords, limit)` — a dict with `status`, `count`, and `events` list
- Current enforcement: None. `topic` is accepted but not validated against allowed values before delegation to `app.py`. `limit` has no bounds check. `keywords` has no blocklist check.

### Tool Implementation Layer
- File: app.py (`WikiCFPScraper`, `getEvents`)
- Role: Sends an HTTP GET to `http://www.wikicfp.com/cfp/servlet/tool.search` with the caller-supplied `keywords` and a fixed `year` parameter, scrapes the HTML response, and returns up to `limit` conference records.
- Inputs: `keywords` (string), `limit` (integer or None)
- Outputs: `{status, count, events[]}` where each event has `event_name`, `event_description`, `event_time`, `event_location`, `deadline`, `event_link`
- Current enforcement: None. `keywords` is passed directly to WikiCFP with no sanitization. `topic` is not forwarded to `app.py` at all — it is accepted by `server.py` but silently discarded before the external call.

### External Service
- File: N/A (remote — `http://www.wikicfp.com`)
- Role: WikiCFP search endpoint that returns HTML conference listings.
- Inputs: `q` (search query), `year` filter
- Outputs: HTML page scraped for conference records
- Current enforcement: None (external, uncontrolled).

---

## Trust Boundaries

| Field | Source | Classification |
|---|---|---|
| `question` | Caller (HTTP POST body) | Self-reported / Untrusted |
| `user_profile.user_role` | Caller (HTTP POST body) | Self-reported — no authentication or verification |
| `user_profile.dissertation_area` | Caller (HTTP POST body) | Self-reported — no authentication or verification |
| `user_profile.queries_this_session` | Caller (HTTP POST body) | Self-reported — caller controls the session counter |
| `user_profile.research_area` | Caller (HTTP POST body) | Self-reported |
| `user_profile.user_name` | Caller (HTTP POST body) | Self-reported |
| `args.keywords` | LLM output (agent decision) | Untrusted — LLM-generated, influenced by user input |
| `args.topic` | LLM output (agent decision) | Untrusted — LLM-generated, influenced by user input |
| `args.limit` | LLM output (agent decision) | Untrusted — LLM-generated, influenced by user input |
| WikiCFP HTML response | External web scrape | External/untrusted — no integrity guarantee |

---

## Data Flow

```
User → POST /chat or /extract_tool_call (question + user_profile)
     → Agent Layer (system prompt built from user_profile, LLM decides tool + args)
     → MCP Tool Layer: get_events(keywords, topic, limit)
     → Tool Implementation Layer: WikiCFPScraper.search_conferences(keywords)
     → External: wikicfp.com HTTP GET
     ← HTML response scraped into events[]
     ← {status, count, events[]} returned to MCP layer
     ← tool result returned to agent LLM
     ← natural-language answer returned to caller
```

---

## Enforcement Points

### Current
- None at any layer. No access control, input validation, or policy check exists anywhere in the stack.

### Available (OPA-interceptable)
OPA can intercept at the MCP tool invocation boundary — after the agent decides to call `get_events` but before `app.py` executes the WikiCFP request. At that point the following structured fields are available:

| Field | OPA path | Available? |
|---|---|---|
| Tool name | `input.name` | ✅ Yes |
| Topic value | `input.args.topic` | ✅ Yes (`tool_definitions.json`) |
| Keywords string | `input.args.keywords` | ✅ Yes (`tool_definitions.json`) |
| Result limit | `input.args.limit` | ✅ Yes (`tool_definitions.json`) |
| Caller role | `input.extensions.subject.user_role` | ✅ Yes (`system_vars.json`) |
| Dissertation area | `input.extensions.subject.dissertation_area` | ✅ Yes (`system_vars.json`) |
| Session query count | `input.extensions.subject.queries_this_session` | ✅ Yes (`system_vars.json`) — but value is self-reported |

**Guidance coverage sweep:**
- Rule: Only `faculty` and `phd_student` may use `get_events` → `input.extensions.subject.user_role` — ✅ available
- Rule: `topic` must be one of 3 approved values → `input.args.topic` — ✅ available
- Rule: `limit` ≤ cap per role (faculty=15, phd_student=10) → `input.args.limit` + `input.extensions.subject.user_role` — ✅ both available
- Rule: `keywords` must not contain blocked terms → `input.args.keywords` — ✅ available
- Rule: ≤ 5 searches per session → `input.extensions.subject.queries_this_session` — ✅ available as a field, but value is **self-reported by the caller** — enforcement has no integrity guarantee
- Rule: PhD student `topic` must equal `dissertation_area` → `input.args.topic` + `input.extensions.subject.dissertation_area` — ✅ both available

### Blind Spots
- **`topic` discarded before WikiCFP call** — `server.py` accepts `topic` but `app.py`'s `getEvents` does not receive or use it. OPA enforces on it at invocation time, but if OPA is bypassed, the tool still runs without the topic constraint.
- **WikiCFP response content** — OPA cannot inspect or filter the returned conference records after the external call. Off-topic results returned by WikiCFP are invisible to OPA.
- **LLM reasoning and system prompt injection** — The agent's decision to call `get_events` and its choice of argument values are made inside the LLM, which is invisible to OPA. A prompt injection in `user_profile` could influence the LLM to pick topic/keyword values that bypass guidance before OPA sees the call.
- **`queries_this_session` integrity** — The session counter is self-reported by the caller. OPA can read it and enforce the cap, but a caller who under-reports the counter defeats the rate limit silently.
- **`user_role` and `dissertation_area` integrity** — Both are self-reported with no cryptographic verification. OPA enforces policies based on their values, but a caller can claim any role or area.
