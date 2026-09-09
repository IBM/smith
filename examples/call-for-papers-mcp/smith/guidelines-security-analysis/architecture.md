# Architecture: call-for-papers-mcp

## Layers

### HTTP API Layer
- File: agent.py
- Role: Exposes `/chat` and `/extract_tool_call` POST endpoints; accepts `question` and `user_profile` from callers, builds the system prompt by embedding `user_profile` keys verbatim, and forwards the combined message to the agent.
- Inputs: `question` (str), `user_profile` (Optional[Dict[str, Any]]) — both caller-supplied
- Outputs: System prompt string (with embedded user_profile), user message — forwarded to the Agent Layer
- Current enforcement: none

### Agent Layer
- File: agent.py (LangGraph ReAct agent, `create_react_agent`)
- Role: LLM-driven reasoning layer that decides which tool to call and with what arguments, based on the system prompt and user question.
- Inputs: System prompt (containing embedded `user_profile`), user `question`
- Outputs: Tool call decisions — `input.name`, `input.args.keywords`, `input.args.topic`, `input.args.limit`
- Current enforcement: none (no pre-call argument validation)

### MCP Tool Layer
- File: server.py (`get_events` FastMCP tool)
- Role: Declares the `get_events` tool schema (`keywords`, `topic`, `limit`) and forwards calls to the tool implementation; `topic` is declared as a required parameter here but is not forwarded to `app.py`.
- Inputs: `keywords` (str, required), `topic` (str, required), `limit` (int, optional, default 10)
- Outputs: Calls `getEvents(keywords, limit)` — `topic` is dropped here
- Current enforcement: none

### Tool Implementation Layer
- File: app.py (`WikiCFPScraper`, `getEvents`)
- Role: Constructs and sends an HTTP GET to WikiCFP (`q=<keywords>&year=t`), parses the HTML response, and returns structured conference data up to `limit` entries.
- Inputs: `keywords` (str), `limit` (Optional[int])
- Outputs: Dict with `status`, `count`, and `events` array (name, description, dates, location, deadline, link)
- Current enforcement: none (no sanitisation of `keywords` before URL construction)

### External Service
- File: n/a (WikiCFP HTTP API, `http://www.wikicfp.com/cfp/servlet/tool.search`)
- Role: Third-party academic conference index; receives keyword query, returns HTML listing of matching conferences.
- Inputs: `q` query param, `year` filter
- Outputs: HTML page scraped for conference data — untrusted external content
- Current enforcement: n/a

---

## Trust Boundaries

| Field | Source | Classification | Disposition |
|---|---|---|---|
| `question` | Caller POST body | Self-reported | n/a (processed by LLM, never a tool argument) |
| `user_profile.*` (all keys including `user_role`, `dissertation_area`, `queries_this_session`, `research_area`, `user_name`) | Caller POST body | Self-reported | n/a (injected verbatim into system prompt; no tool argument; never reaches OPA interception surface as `input.args.*`) |
| `keywords` (LLM-generated tool arg) | Agent LLM reasoning | Self-reported (LLM) | **Acts on** — passed as `q=` URL param to WikiCFP HTTP GET in app.py |
| `topic` (LLM-generated tool arg) | Agent LLM reasoning | Self-reported (LLM) | **Echoed** — server.py accepts it and documents it as a policy-scoping parameter, but `getEvents()` is called as `getEvents(keywords, limit)` — `topic` is never forwarded to app.py and has no effect on the WikiCFP query or result filtering |
| `limit` (LLM-generated tool arg) | Agent LLM reasoning | Self-reported (LLM) | **Acts on** — used in `conferences[:limit]` to slice the result list in app.py |
| `input.extensions.subject.user_role` | system_vars.json schema | Self-reported | n/a (available at OPA interception time; not a tool arg) |
| `input.extensions.subject.dissertation_area` | system_vars.json schema | Self-reported | n/a (available at OPA interception time; not a tool arg) |
| `input.extensions.subject.queries_this_session` | system_vars.json schema | Self-reported | n/a (available at OPA interception time; not a tool arg) |
| `input.extensions.subject.research_area` | system_vars.json schema | Self-reported | n/a (available at OPA interception time; not a tool arg) |
| WikiCFP response (HTML) | External HTTP service | External/untrusted | Acts on — scraped and parsed; returned as event data to the agent |

---

## Data Flow

```
Caller → [HTTP API Layer: POST /chat] → [Agent Layer: system-prompt + question] → [MCP Tool Layer: get_events(keywords, topic, limit)] → [Tool Impl: getEvents(keywords, limit) — topic dropped] → [WikiCFP HTTP GET ?q=keywords&year=t]
                                                                                                                                                                                                               ↓
Caller ← [HTTP API Layer: ChatResponse] ← [Agent Layer: final message] ← [MCP Tool Layer: result dict] ← [Tool Impl: parsed conference list] ← [WikiCFP HTML response]
```

---

## Enforcement Points

### Current
- None in any layer. No access control, no argument validation, no authentication.

### Available (OPA-interceptable)
- **MCP Tool Layer (pre-execution interception):** OPA can intercept the `get_events` call before it reaches `getEvents()`. At this point the following structured fields are visible:
  - `input.name` = `"get_events"`
  - `input.args.keywords` (str)
  - `input.args.topic` (str) — **deny-path rules are sound; permit-path rules are not** (topic is echoed — it has no effect on what the tool does)
  - `input.args.limit` (int)
  - `input.extensions.subject.user_role` (string or list — system_vars.json declares it as a list)
  - `input.extensions.subject.dissertation_area` (str)
  - `input.extensions.subject.queries_this_session` (int)
  - `input.extensions.subject.research_area` (list of str)
  - `input.extensions.subject.user_name` (str)

### Blind Spots
- **HTTP API Layer:** `user_profile` key/value injection — any key can be embedded in the system prompt verbatim, enabling prompt injection into the agent's reasoning. No OPA-enforceable structured field exists for prompt-injection detection at this layer.
- **Agent Layer:** LLM argument selection — OPA cannot intercept before the LLM decides which `keywords`, `topic`, or `limit` values to produce. It can only check the resulting arguments.
- **Tool Implementation Layer:** `keywords` is used unsanitised in the WikiCFP URL `q=` parameter. This is a tool-implementation concern; OPA can block known bad keyword substrings but cannot prevent novel injection payloads it was not written to match.
- **External Service Layer:** WikiCFP response content is untrusted and could contain adversarial data. OPA sees only the pre-call arguments; it cannot inspect or filter the response.
- **Session rate limit:** `queries_this_session` is self-reported by the caller; a dishonest caller sets it to 0 to defeat the session cap. OPA can enforce the rule as written but cannot verify the count.
- **`topic` permit-path:** Any rule that permits a call *because* `topic` is an approved value provides false assurance — the WikiCFP search executes identically regardless of what `topic` carries. Deny-path rules (blocking unapproved `topic` values) remain enforceable and useful.

---

## Undeclared Fields

Undeclared fields: none. Every field referenced by a guidance.txt rule is declared either in `tool_definitions.json` (for `input.args.*`: `keywords`, `topic`, `limit`) or in `system_vars.json` (for `input.extensions.subject.*`: `user_role`, `dissertation_area`, `queries_this_session`, `research_area`).

---

## Step A Summary

The system has 5 layers (HTTP API, Agent/LLM, MCP Tool, Tool Implementation, External Service). The key self-reported fields driving access-control rules are `user_profile.*` keys — specifically `user_role`, `dissertation_area`, and `queries_this_session` — which are injected into the system prompt at the HTTP layer and made available as `input.extensions.subject.*` fields at OPA interception time. The sole OPA interception point is the MCP Tool Layer pre-call intercept, where `input.args.*` and `input.extensions.subject.*` are both visible as structured data.

The most significant finding is the **`topic` disposition: Echoed**. `topic` is declared as a required tool argument with the appearance of an access-control parameter, but `server.py` calls `getEvents(keywords, limit)` — `topic` is never forwarded to `app.py` and does not affect the WikiCFP query or result filtering. OPA deny-path rules keyed on `topic` (blocking calls whose `topic` is not an approved value) are sound and useful because they stop the call outright. Any permit-path rule (allowing a call *because* `topic` is an approved value) is not sound — it would pass calls that behave identically whether `topic` is approved or not.

Main blind spots: (1) `user_profile` key injection at the HTTP layer enabling prompt injection into the LLM system prompt; (2) WikiCFP response content — fully untrusted and invisible to OPA; (3) `queries_this_session` is self-reported and can be set to 0 to defeat the session rate limit. Undeclared fields: none.
