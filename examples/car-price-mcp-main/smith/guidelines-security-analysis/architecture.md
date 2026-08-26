# Architecture: car-price-mcp-main

## Layers

### HTTP API Layer
- File: `agent.py` (`/chat`, `/extract_tool_call`, `/health`, FastAPI)
- Role: Accepts inbound HTTP requests carrying a natural-language `question` and an optional `user_profile` dict; builds a system prompt by embedding all `user_profile` key/values verbatim, then forwards to the LangGraph ReAct agent.
- Inputs: `question` (string), `user_profile` (optional dict — any key/value; caller-supplied; includes `user_role`, `user_name`, and any other fields the caller chooses to set).
- Outputs: System prompt string + user message passed to the Agent layer.
- Current enforcement: None — no authentication, no schema validation on `user_profile`, no role check.

### Agent Layer (LangGraph ReAct)
- File: `agent.py` (`build_system_prompt`, `create_react_agent`, `chat`, `extract_tool_call`)
- Role: Runs a LangGraph ReAct loop — the LLM reads the system prompt (which embeds `user_profile` key/values verbatim), decides which tool to call, and constructs the tool arguments (`brand_name`, `vehicle_type`) from the user message and system prompt context; launches `server.py` over stdio via `MultiServerMCPClient`.
- Inputs: System prompt (containing verbatim `user_profile` entries), user message.
- Outputs: MCP `tools/call` requests over stdio with `name` ∈ {`get_car_brands`, `search_car_price`, `get_vehicles_by_type`} and any arguments.
- Current enforcement: None — `user_profile` is advisory; the LLM may or may not respect role constraints stated in the system prompt.

### MCP Tool Server
- File: `server.py` (stdio transport, FastMCP)
- Role: Exposes three tools (`get_car_brands`, `search_car_price`, `get_vehicles_by_type`) as thin wrappers over `app.py` functions; applies only a minimal empty/whitespace guard on `brand_name` and `vehicle_type`.
- Inputs: JSON-RPC `tools/call` with `brand_name` (string, required for `search_car_price`) or `vehicle_type` (string, default `"carros"` for `get_vehicles_by_type`); `get_car_brands` has no parameters.
- Outputs: Formatted string responses from `app.py`.
- Current enforcement: FastMCP schema validation (parameter types). No authorization, no brand or vehicle-type allow/block list, no role check.

### Tool Implementation Layer
- File: `app.py` (`getCarBrands`, `searchCarPrice`, `getCarsByType`)
- Role: Calls the FIPE API; `searchCarPrice()` does a case-insensitive substring match of `brand_name` against all FIPE brand names (not exact equality); `getCarsByType()` maps `vehicle_type` to Portuguese via an internal dict — any unrecognized type silently coerces to `"carros"` (`type_mapping.get(vehicle_type.lower(), 'carros')`).
- Inputs: `brand_name` (string) for `searchCarPrice`; `vehicle_type` (string) for `getCarsByType`; no parameters for `getCarBrands`.
- Outputs: Formatted string containing brand list, model+price data, or vehicle-type brand list.
- Current enforcement: None — no brand allowlist, no vehicle-type validation, no role check. Silent fallback to `"carros"` for unrecognized vehicle types.

### External Service
- Service: FIPE API (`https://parallelum.com.br/fipe/api/v1/`)
- Role: Public Brazilian vehicle reference price database; called via HTTP GET with no authentication.
- Inputs: URL path components (vehicle type segment, brand code, model code, year code).
- Outputs: JSON arrays of brands, models, years, and price records.
- Current enforcement: None — returns whatever matches the query; no content filtering.

---

## Trust Boundaries

| Field | Source | Classification |
|---|---|---|
| `user_profile` (all keys) | HTTP caller (JSON body) | Self-reported — no cryptographic verification; caller can supply any key/value |
| `user_profile.user_role` | HTTP caller | Self-reported — caller asserts their own role (`fleet_manager`, `consumer`, `journalist`, `analyst`, `guest`) |
| `user_profile.user_name` | HTTP caller | Self-reported — informational only, not used for access control |
| `input.extensions.subject.user_role` | Caller-supplied `user_profile` | Self-reported |
| `input.name` (tool name, LLM-chosen) | Agent (LLM) | Self-reported — LLM-generated decision |
| `input.args.brand_name` | Agent (LLM) | Self-reported — LLM-chosen from user message; subject to brand allow/block rules |
| `input.args.vehicle_type` | Agent (LLM) | Self-reported — LLM-chosen; must match exact recognized values per policy |
| FIPE API responses (brand names, model names, prices) | `parallelum.com.br` external API | External/untrusted — third-party content; no integrity guarantee |

---

## Data Flow

```
HTTP caller
  │  POST /chat  {question, user_profile: {user_role, user_name, ...}}
  ▼
agent.py HTTP API layer
  │  build_system_prompt() — embeds user_profile key/values verbatim into system prompt
  ▼
LangGraph ReAct agent (LLM)
  │  LLM: reads system prompt + user question → selects tool → constructs arguments
  ▼  stdio (MultiServerMCPClient)
server.py MCP tool server
  │  get_car_brands()               → app.getCarBrands()
  │  search_car_price(brand_name)   → app.searchCarPrice(brand_name)
  │  get_vehicles_by_type(vehicle_type) → app.getCarsByType(vehicle_type)
  ▼
app.py Tool Implementation
  │  HTTP GET(s) to https://parallelum.com.br/fipe/api/v1/...
  ▼
FIPE API (external)
  ▼
Response ← app ← server ← LLM (formatted answer) ← HTTP caller
```

---

## Enforcement Points

### Current
- **MCP Tool Server**: FastMCP schema validation only (parameter types; empty/whitespace guard on `brand_name` and `vehicle_type`). No authorization, no brand allow/block list, no vehicle-type restriction, no role check.
- **No authorization or access-control layer exists anywhere in this system today.**

### Available (OPA-interceptable)
OPA intercepts at the Agent → MCP server boundary. Fields present as structured data at that point:

**From `input.extensions.subject.*` (populated from `user_profile`):**
- `input.extensions.subject.user_role` — string: one of `fleet_manager`, `consumer`, `journalist`, `analyst`, `guest` (self-reported)
- `input.extensions.subject.user_name` — string (informational, not used for policy)

**From `input.args.*`:**
- `input.args.brand_name` — string (required for `search_car_price`)
- `input.args.vehicle_type` — string (optional for `get_vehicles_by_type`, default `"carros"`)

**From `input.name`:**
- `input.name` — tool name: `get_car_brands`, `search_car_price`, or `get_vehicles_by_type`

**guidance.txt coverage sweep:**

| Rule | Fields needed | Available? | Verdict |
|---|---|---|---|
| Only known roles may call any tool | `subject.user_role` | Available | OPA-enforceable |
| Guest: only `get_car_brands` allowed; `search_car_price` and `get_vehicles_by_type` denied | `subject.user_role`, `input.name` | Available | OPA-enforceable |
| `fleet_manager`: `get_vehicles_by_type` only with `"caminhoes"` or `"trucks"` | `subject.user_role`, `args.vehicle_type` | Available | OPA-enforceable |
| `consumer`: `get_vehicles_by_type` only with `"carros"` or `"cars"` | `subject.user_role`, `args.vehicle_type` | Available | OPA-enforceable |
| `journalist`: `get_vehicles_by_type` only with `"carros"` or `"cars"` | `subject.user_role`, `args.vehicle_type` | Available | OPA-enforceable |
| `analyst`: any recognized `vehicle_type` | `subject.user_role`, `args.vehicle_type` | Available | OPA-enforceable |
| `vehicle_type` exact case-sensitive match only; unrecognized values denied for all | `args.vehicle_type` | Available | OPA-enforceable |
| `fleet_manager`: `search_car_price` restricted to truck brands | `subject.user_role`, `args.brand_name` | Available | OPA-enforceable |
| `journalist`: `search_car_price` restricted to domestic-market brands | `subject.user_role`, `args.brand_name` | Available | OPA-enforceable |
| `consumer`/`analyst`: `search_car_price` unrestricted | `subject.user_role`, `args.brand_name` | Available | OPA-enforceable |
| `guest`: `search_car_price` denied | `subject.user_role`, `input.name` | Available | OPA-enforceable |
| Empty or whitespace `brand_name` denied for all | `args.brand_name` | Available | OPA-enforceable |

### Blind Spots
- **`app.py` internal brand lookup**: `searchCarPrice()` performs a case-insensitive substring match internally (e.g. `"volvo"` matches `"Volvo"`). The policy must enforce exact Title Case matching at interception time — OPA cannot inspect how `app.py` resolves the brand after the call is allowed through.
- **`app.py` silent vehicle-type fallback**: `getCarsByType()` silently coerces any unrecognized `vehicle_type` to `"carros"`. OPA must reject unrecognized values before they reach the tool; guidance.txt explicitly requires this.
- **LLM reasoning**: the LLM constructs `brand_name` and `vehicle_type` from natural language; prompt injection in `user_profile` or the user message could cause the LLM to select a disallowed brand or vehicle type, bypassing the advisory system-prompt constraints.
- **FIPE API responses**: OPA intercepts before tool execution; it cannot inspect the returned brand or price data. The content of FIPE responses is entirely post-execution.
- **`user_role` authenticity**: the policy enforces role-based rules on `subject.user_role`, but the value is entirely self-reported — a caller can assert any role.
