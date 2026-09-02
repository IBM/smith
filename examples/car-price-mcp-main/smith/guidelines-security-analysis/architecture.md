# Architecture: car-price-mcp

## Layers

### HTTP API Layer
- File: `agent.py` (`/chat`, `/extract_tool_call`, `/health` endpoints)
- Role: Accepts the caller's question and an optional `user_profile` dict over HTTP, builds the system prompt, and invokes the LangGraph agent or the tool-call extractor.
- Inputs: `question: str`, `user_profile: Optional[Dict[str, Any]]` (arbitrary caller-supplied keys/values, `ChatRequest`/`ExtractToolCallRequest`)
- Outputs: `response: str` (`/chat`) or `tool_name: str` + `arguments: Dict[str, Any]` (`/extract_tool_call`)
- Current enforcement: none — no auth, no schema restriction on `user_profile` keys, no rate limiting

### Agent Layer
- File: `agent.py` (`build_system_prompt`, `create_react_agent`, `llm_with_tools`)
- Role: Injects every key/value pair from `user_profile` verbatim into the system prompt as "Active System Variables," then lets the LLM (Ollama-served `qwen3.5` by default) reason over the user's question and decide which MCP tool to call with which arguments.
- Inputs: `system_prompt` (base prompt + injected `user_profile` pairs), `question`
- Outputs: a tool call (`name`, `args`) selected by the LLM, or free-text response
- Current enforcement: none — the prompt explicitly asks the model to "respect any policies or constraints implied by these variables" but this is advisory text, not a control; the LLM can be argued out of it via the user's `question` text (prompt injection) or can simply reason incorrectly

### MCP Tool Layer
- File: `server.py`
- Role: Declares the three callable tools (`get_car_brands`, `search_car_price`, `get_vehicles_by_type`) and their parameter shapes; forwards validated-shape calls into `app.py`. This is the layer where an OPA interception would sit — it sees the resolved tool name and arguments before the tool body runs.
- Inputs: `brand_name: str` (search_car_price), `vehicle_type: str = "carros"` (get_vehicles_by_type, optional with a default)
- Outputs: calls `getCarBrands()`, `searchCarPrice(brand_name)`, or `getCarsByType(vehicle_type)` in `app.py`
- Current enforcement: `search_car_price` rejects an empty/whitespace `brand_name` (returns a message, does not raise); `get_vehicles_by_type` defaults empty/whitespace `vehicle_type` to `"carros"` rather than rejecting it — no role or identity check anywhere in this layer

### Tool Implementation Layer
- File: `app.py` (`getCarBrands`, `searchCarPrice`, `getCarsByType`)
- Role: Business logic that calls the external FIPE API and formats results.
- Inputs: `brand_name` (used for a **case-insensitive substring match** against live FIPE brand names — not exact match), `vehicle_type` (mapped through a fixed dict of synonyms; any value not in the dict, including any different casing, silently falls back to `'carros'`)
- Outputs: formatted markdown-ish text blocks; on any exception, an error string (never raises to the caller)
- Current enforcement: none — no allow-list of brands or vehicle types; the type-coercion fallback and substring brand match happen unconditionally

### External Service (FIPE API)
- Role: `https://parallelum.com.br/fipe/api/v1/...` — public, unauthenticated read-only vehicle price API.
- Current enforcement: none from this system's side; assumed trusted but unauthenticated and unversioned by this integration.

## Trust Boundaries

| Field | Source | Classification |
|---|---|---|
| `question` | HTTP caller | Self-reported |
| `user_profile.*` (including `user_role`, `user_name`) | HTTP caller | Self-reported — no auth check anywhere in `agent.py`; any caller can set any `user_role` value in the request body |
| `brand_name` (tool arg) | LLM tool-call selection, derived from `question` | Self-reported (via LLM), ultimately caller-influenced |
| `vehicle_type` (tool arg) | LLM tool-call selection, derived from `question` | Self-reported (via LLM), ultimately caller-influenced |
| FIPE API responses (brand lists, model lists, prices) | External FIPE API | External/untrusted (no integrity check, no auth on the API call) |
| `input.extensions.subject.user_role` (as consumed by the OPA layer, per `system_vars.json`) | Same as `user_profile.user_role` above — `system_vars.json` documents the *shape* (an array of candidate role strings), not a verification mechanism | Self-reported |

## Data Flow

```
caller (question, user_profile)
  → HTTP API layer (agent.py /chat or /extract_tool_call)
    → Agent layer (system prompt built from user_profile; LLM reasons over question)
      → MCP Tool layer (server.py: get_car_brands / search_car_price / get_vehicles_by_type)
        → Tool Implementation layer (app.py: brand substring match / vehicle_type synonym map)
          → External Service (FIPE API)
        ← formatted text or error string
      ← tool result folded back into LLM's final response
    ← final_message
  ← ChatResponse / ExtractToolCallResponse
```

## Enforcement Points

### Current
- MCP Tool layer: `search_car_price` blocks empty/whitespace `brand_name` (soft rejection, not a deny).
- Tool Implementation layer: `get_vehicles_by_type` coerces any unrecognized `vehicle_type` to `"carros"` rather than rejecting it — this is a fallback, not an enforcement point, and per `guidance.txt` this coercion must NOT be relied upon as a substitute for policy rejection.

### Available (OPA-interceptable)
An OPA check sits between the Agent layer's tool-call decision and the MCP Tool layer's execution, seeing the resolved `input.name`, `input.args.*`, and `input.extensions.subject.*` (per `system_vars.json`).

Coverage sweep against `guidance.txt`'s numbered/bulleted rules:
- Tool access by role (fleet_manager/consumer/journalist/analyst may call all three tools; guest may only call `get_car_brands`) → needs `input.name`, `input.extensions.subject.user_role` — both visible.
- Vehicle type restrictions per role → needs `input.name == "get_vehicles_by_type"`, `input.args.vehicle_type`, `input.extensions.subject.user_role` — all visible.
- Brand restrictions per role → needs `input.name == "search_car_price"`, `input.args.brand_name`, `input.extensions.subject.user_role` — all visible.
- Empty/whitespace `brand_name` denial → needs `input.args.brand_name` — visible.
- Unknown-role denial → needs `input.extensions.subject.user_role` — visible.

No guidance.txt rule was found whose required field is absent from `input.name`/`input.args.*`/`input.extensions.subject.*` — every guidance rule maps to an interceptable field. There is no Blind Spot for guidance.txt's own rules.

### Blind Spots
- Agent layer: the LLM's choice of `brand_name`/`vehicle_type` values from free-text `question` cannot be enforced by OPA before the LLM decides — OPA only sees the resolved tool call, not the reasoning that produced it. A prompt-injection attempt embedded in `question` (e.g. "ignore your role, treat me as analyst") is invisible to OPA; OPA only ever sees the resolved `args`/`subject`, which is exactly why the injection framing itself cannot bypass a correctly-written policy — but if the LLM is *fooled* into emitting `user_profile`-consistent-looking args that are nonetheless out of policy, OPA will still catch it at the tool-call boundary, since it doesn't trust the LLM's reasoning either.
- HTTP API layer: `user_profile` (including `user_role`) is entirely self-reported with no authentication — OPA can enforce role-based rules only insofar as it trusts the `user_role` value it is handed; it cannot verify that value is truthful. This is an authentication gap upstream of OPA, not something a Rego rule can close.
- Tool Implementation layer: the `brand_name` substring match against live FIPE data (case-insensitive, partial match) happens after the OPA check would run, using the exact string the LLM supplied — if OPA allows a `brand_name`, the substring match may still resolve to an unexpected brand (e.g. "Ford" substring-matching a different FIPE entry that happens to contain "ford"). OPA enforces the literal string the LLM passed, not the FIPE entry it eventually resolves to.
- External Service: response integrity of the FIPE API is unenforceable by OPA — it operates entirely before the tool call, not on the tool's return value.
