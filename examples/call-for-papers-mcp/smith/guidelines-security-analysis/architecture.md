# Architecture Analysis

## Layers

| Layer | File | Role | Inputs | Outputs | Current enforcement |
|---|---|---|---|---|---|
| Agent/client | agent.py | FastAPI HTTP endpoints (/chat, /extract_tool_call, /health); builds LLM system prompt from caller-supplied user_profile; runs LangGraph create_react_agent that selects and invokes MCP tools; also exposes a non-executing tool-call extraction path | HTTP request body (question, user_profile) | ChatResponse text / ExtractToolCallResponse(tool_name, arguments) | None |
| MCP | server.py | FastMCP tool registration over stdio transport; declares get_events(keywords, topic, limit) and forwards to app.getEvents | Tool-call arguments from the LLM (keywords, topic, limit) | Dict returned by app.getEvents | None |
| Tool implementation | app.py | WikiCFPScraper + getEvents(): builds HTTP GET to WikiCFP, parses HTML response, truncates results to limit | keywords, limit (topic not received here) | {status, count, events} | None |
| External service | app.py (WikiCFPScraper.search_conferences) | Outbound HTTP GET to http://www.wikicfp.com/cfp/servlet/tool.search with query params q=keywords, year='t' (hardcoded) | keywords | Raw HTML page | None |

### Runtime Subject Context

| Field | Provider | Provenance | Verification / integrity | OPA-visible? |
|---|---|---|---|---|
| input.extensions.subject.user_role | system_vars.json (declared) | Not read by any code path; only reaches the process if a caller supplies it inside the free-form user_profile dict to /chat, where it is stringified into the LLM system prompt | None — no schema validation, no signature, caller-asserted | No (never placed in a structured input.extensions.subject.* field by any code) |
| input.extensions.subject.dissertation_area | system_vars.json (declared) | Not read by any code path; same caller-asserted user_profile path as user_role if used at all | None | No |
| input.extensions.subject.research_area | system_vars.json (declared) | Not read by any code path | None | No |
| input.extensions.subject.queries_this_session | system_vars.json (declared) | Not read, tracked, or incremented anywhere in agent.py/server.py/app.py; no session-count state exists in the implementation | None | No |
| input.extensions.subject.user_name | system_vars.json (declared) | Not read by any code path; only reaches the process if included in caller-supplied user_profile | None | No |

### Tool Arguments

| Field | Tool | Origin / influence | Disposition |
|---|---|---|---|
| input.args.keywords | get_events | LLM-chosen free-text search term, passed through server.py directly into app.getEvents(keywords, limit) and then into WikiCFPScraper.search_conferences as the `q` query parameter | Acts on |
| input.args.topic | get_events | Declared as a required string parameter in both server.py's function signature and tool_definitions.json; server.py's tool body calls `getEvents(keywords, limit)` — topic is never forwarded, and app.py's getEvents has no topic parameter at all | Ignored |
| input.args.limit | get_events | LLM-chosen integer (default 10), passed through server.py into app.getEvents(keywords, limit); used to slice the result list via conferences[:limit] | Acts on |

### Prompt Inputs

| Field or data | Source | Consumer | Trust / influence |
|---|---|---|---|
| question | HTTP caller (ChatRequest.question) | agent.py: LangGraph react agent as the user message | Directly drives tool selection and arguments (keywords, topic, limit) via the LLM |
| user_profile | HTTP caller (ChatRequest.user_profile, arbitrary dict) | agent.py build_system_prompt(): stringified key/value lines appended to the system prompt | Caller-asserted, unvalidated; only advisory text for the LLM — no code path enforces any constraint derived from it, so it is trust input only insofar as the LLM chooses to honor it |

### External Data

| Data | Source | Verification / integrity | Consumer |
|---|---|---|---|
| WikiCFP search results HTML (conference name, description, dates, location, deadline, link) | http://www.wikicfp.com/cfp/servlet/tool.search (plain HTTP GET, fixed host) | None — no TLS, no response signature/checksum, no allow-listing beyond the hardcoded base_url/search_url constants | app.py _parse_conference_pair/_parse_conference_table build the events list, which is returned as tool output to the MCP client, the LLM, and ultimately the HTTP caller |

## Enforcement Points

| Layer | Current | Available (OPA-interceptable) | Blind spots |
|---|---|---|---|
| MCP tool boundary (server.py get_events, before calling app.getEvents) | None implemented | keywords, topic, limit are all structured, fully visible tool arguments at this boundary before any external call is made — an OPA policy call inserted here could evaluate topic membership, limit bounds/role caps, and role/guest gating using input.args.* and input.extensions.subject.* (if subject fields were actually threaded through as structured data instead of free text) | topic is dropped before reaching app.py, so even if it were policy-checked at the MCP boundary, nothing downstream re-derives or re-validates it; queries_this_session has no server-side counter, so per-session query-count limits cannot be enforced without the caller supplying a running count as a genuine structured system variable |
| HTTP ingress (agent.py /chat, /extract_tool_call) | None implemented | user_profile is a structured dict at this boundary and could be validated/whitelisted before being folded into the prompt or passed onward as input.extensions.subject.* | Currently user_profile is free-form and unauthenticated; the LLM, not code, decides whether to honor any embedded constraint, so prompt-text-only propagation is a true blind spot until subject fields are carried as structured, verifiable data |
| External call (app.py WikiCFPScraper) | None implemented | Not OPA-interceptable in a meaningful sense beyond the pre-execution tool boundary above — this layer performs the already-authorized network call | Response content is unauthenticated scraped HTML; no verification of WikiCFP content integrity before it is surfaced to the LLM/user |

## Undeclared Fields

| Field | Referenced by guidance rule # | Declared by | Consequence |
|---|---|---|---|
| dissertation_area | PhD Student Narrow-Scope Rule (guidance.txt lines 38-46) | Declared nowhere in the governed tool schema (get_events has no such argument); declared only in system_vars.json as a subject field, but no code path reads system_vars.json or threads it into input.extensions.subject at runtime | The per-student topic-narrowing rule cannot be enforced today: the policy has no verified runtime source for dissertation_area, and guidance.txt explicitly warns that substituting the shared research_area list would silently defeat the narrowing |
| queries_this_session | 5-searches-per-session cap (guidance.txt lines 21-25) | Declared nowhere in the governed tool schema; declared only in system_vars.json, with no code that increments or supplies a truthful running count | Guidance itself notes this rule is enforceable only if the agent supplies the running count as a system variable; with the current static/unpopulated value this rule cannot be enforced by a stateless policy |
| user_role | Role gating for get_events / limit caps (guidance.txt lines 15-19) | Declared nowhere in the governed tool schema; declared in system_vars.json as a list of possible roles (not a resolved single role) with no code that resolves or forwards the caller's actual role into input.extensions.subject.user_role | Faculty/phd_student/guest gating and the associated limit caps (15 vs 10) cannot be enforced until the runtime subject's actual role is threaded through as a structured, verifiable field distinct from the enumerated possibilities in system_vars.json |

## Phase Handoff

- Status: PASS
- Artifact schema: architecture-v2
- Summary: Sources: agent.py, server.py, app.py (3 implementation files, 0 unresolved paths). Tools: 1 declared (get_events) — implementation matches tool_definitions.json in name and required/optional signature (keywords required, topic required, limit optional default 10); every declared argument (keywords, topic, limit) has an implementation-derived disposition. Layers: 4 (agent/client, MCP, tool implementation, external service) — no runtime context/enforcement layer exists in code today. Runtime subject fields: 5 declared in system_vars.json (user_role, dissertation_area, research_area, queries_this_session, user_name); none are read by any code path or exposed as OPA-visible input.extensions.subject.* fields — all are effectively undeclared-at-runtime despite being declared in the system-vars file. Undeclared fields relative to the governed schema: 3 guidance dependencies (dissertation_area, queries_this_session, user_role) have no verified runtime path into the tool schema or subject context. Key gap: the `topic` argument is required by the tool schema and used for policy-level scoping intent, but server.py silently drops it before calling app.getEvents, so it reaches the MCP boundary but never the implementation — classify as Ignored, not proof of a schema mismatch (tool_definitions.json and server.py agree on the declared signature). No enforcement exists anywhere in the current implementation; the only viable pre-execution enforcement point is the MCP tool boundary in server.py, which has full visibility into keywords/topic/limit but no verified way today to obtain user_role, dissertation_area, or queries_this_session as trustworthy structured subject data.
