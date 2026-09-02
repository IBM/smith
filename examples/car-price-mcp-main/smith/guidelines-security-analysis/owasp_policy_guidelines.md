# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines
# Tool: car-price-mcp

---

## Architecture Summary

car-price-mcp is a single-agent, single-tool-server system with no persistent memory: a FastAPI HTTP layer (`agent.py`) accepts a free-text `question` and a fully self-reported, unauthenticated `user_profile` dict, hands both to a LangGraph LLM agent that decides which of three read-only FIPE-pricing tools to call (`server.py`/`app.py`), and returns the result with no further checks. The OPA interception point sits between the Agent layer's tool-call decision and the MCP Tool layer's execution, seeing `input.name`, `input.args.*` (`brand_name`, `vehicle_type`), and `input.extensions.subject.user_role` — every guidance.txt rule's required field is visible there, but the caller identity behind `user_role` itself is never authenticated at any layer.

---

## OWASP Top 10 for Agentic AI Security — Scope Assessment

### ASI01 — Agent Goal Hijack
**Risk:** A caller's free-text `question` manipulates the LLM's tool-selection reasoning (via prompt injection or plain reasoning error) into producing an out-of-policy tool call.
**Verdict:** Out of scope for the manipulation step itself, but the *resulting* tool call is fully in scope — OPA cannot see or judge the LLM's reasoning, but it evaluates the resolved `input.name`/`input.args.*`/`input.extensions.subject.user_role` regardless of what reasoning path produced them, which is exactly the boundary this category needs.

### ASI02 — Tool Misuse and Exploitation
**Risk:** The LLM calls a tool the caller's role should not be able to use, or with a parameter value outside the caller's role-restricted set, or relies on the tool's silent `vehicle_type` coercion fallback as if it were a safe default.
**Verdict:** In scope — every instance resolves to a check on `input.name`, `input.args.brand_name`, `input.args.vehicle_type`, or `input.extensions.subject.user_role`, all visible at invocation time.

### ASI03 — Identity and Privilege Abuse
**Risk:** A caller asserts a higher-privilege `user_role` (or a different identity request-to-request) than they actually hold, since `user_profile` is entirely self-reported with no authentication anywhere in `agent.py`.
**Verdict:** Out of scope — OPA can only condition rules on the `user_role` value it is handed; it has no mechanism to verify that value is truthful. This is an authentication gap upstream of the OPA checkpoint, not a Rego-closable condition.

### ASI04 — Agentic Supply Chain Vulnerabilities
**Risk:** The FIPE API is called unauthenticated over HTTPS with no response-integrity check; a compromised or spoofed endpoint could return fabricated pricing data.
**Verdict:** Out of scope — this risk lives entirely after the OPA checkpoint (the tool's return value and the external call's own transport security), not on any pre-execution structured field.

### ASI05 — Unexpected Code Execution (RCE)
**Risk:** N/A.
**Verdict:** Out of scope — no code-generation, eval, or shell-invocation surface exists anywhere in this tool.

### ASI06 — Memory & Context Poisoning
**Risk:** N/A.
**Verdict:** Out of scope — no persistent memory, session state, or RAG store exists; every request is stateless.

### ASI07 — Insecure Inter-Agent Communication
**Risk:** N/A.
**Verdict:** Out of scope — no peer agents or inter-agent protocol exists; this is a single agent calling its own local MCP subprocess.

### ASI08 — Cascading Failures
**Risk:** N/A.
**Verdict:** Out of scope — no persistence or multi-agent fan-out substrate exists for a fault to propagate across.

### ASI09 — Human-Agent Trust Exploitation
**Risk:** The agent presents FIPE-derived pricing as authoritative with no disclaimer about data staleness or `search_car_price`'s substring (not exact) brand matching, risking a caller acting on a price for an unintended brand.
**Verdict:** Out of scope — this is a response-content/output-fidelity concern, not a pre-execution structured-field condition; OPA cannot inspect or annotate the tool's return value.

### ASI10 — Rogue Agents
**Risk:** N/A.
**Verdict:** Out of scope — no multi-agent ecosystem exists for a rogue agent to operate within.

---

## Summary Table

| OWASP Category | In OPA scope? | Out-of-scope owner |
|---|---|---|
| ASI01 | Partial | Agent layer (LLM reasoning/prompt injection resistance) |
| ASI02 | Yes | — |
| ASI03 | No | Agent/Infra layer (caller authentication) |
| ASI04 | No | Infra/Tool implementation layer (API integrity, transport pinning) |
| ASI05 | No | N/A |
| ASI06 | No | N/A |
| ASI07 | No | N/A |
| ASI08 | No | N/A |
| ASI09 | No | Agent/Tool implementation layer (response disclaimers, exact-match enforcement) |
| ASI10 | No | N/A |

Categories flowing into the OPA policy: ASI01 (resolved-call boundary only), ASI02

---

## Gap Register

| Threat | Layer | Recommended action |
|---|---|---|
| Caller asserts a higher-privilege `user_role` than actually held (ASI03) | Agent/Infra | Add an authentication step to `agent.py` (e.g. verified session token → role lookup) so `user_role` is not caller-assertable; until then, OPA rules trust this field by necessity |
| No user-ID/session binding distinct from self-reported `user_name` (ASI03) | Agent/Infra | Introduce a verified session or API-key identity separate from the free-form `user_profile` dict |
| FIPE API responses trusted with no integrity or endpoint-pinning check (ASI04) | Tool implementation/Infra | Add response validation (e.g. schema check, TLS certificate pinning) in `app.py`'s FIPE client calls |
| No disclaimer on data staleness or substring-match brand resolution in tool output (ASI09) | Tool implementation/Agent | Have `app.py` annotate responses when `searchCarPrice`'s substring match resolves to a brand name different from the caller-supplied string, and/or switch to exact matching to align with guidance.txt's stated intent |
| LLM reasoning/prompt-injection resistance for tool-call selection (ASI01) | Agent | Harden `build_system_prompt` and/or add an LLM-level instruction-injection defense; independent of and in addition to the OPA boundary check, which already catches any resulting out-of-policy resolved call |

---

## Policy Rules (OPA scope only)

### Input Schema
| Field | Source |
|---|---|
| `input.name` | Resolved MCP tool name (`get_car_brands`, `search_car_price`, `get_vehicles_by_type`) |
| `input.args.brand_name` | `search_car_price` argument |
| `input.args.vehicle_type` | `get_vehicles_by_type` argument (optional, tool-side default `"carros"`) |
| `input.extensions.subject.user_role` | Self-reported caller role, per `system_vars.json` |

### Known values
- Recognized roles: `fleet_manager`, `consumer`, `journalist`, `analyst`, `guest`
- Recognized `vehicle_type` values (lowercase, exact): `carros`, `cars`, `motos`, `motorcycles`, `caminhoes`, `trucks`
- `fleet_manager` vehicle types: `caminhoes`, `trucks`
- `consumer`/`journalist` vehicle types: `carros`, `cars`
- `analyst` vehicle types: all six recognized values
- `fleet_manager` brands: `Scania`, `Volvo`, `Mercedes-Benz`, `MAN`, `DAF`, `Iveco`, `Ford`, `Volkswagen`
- `journalist` brands: `Fiat`, `Chevrolet`, `Volkswagen`, `Hyundai`, `Toyota`, `Renault`, `Honda`, `Nissan`, `Jeep`, `Peugeot`, `Citroën`, `Caoa Chery`

### Rule: GUEST_TOOL_DENY
- OWASP: ASI02
- Severity: Hard block
- Condition: `input.extensions.subject.user_role == "guest"` AND `input.name != "get_car_brands"`
- Matching: exact

### Rule: UNKNOWN_ROLE_DENY
- OWASP: ASI02
- Severity: Hard block
- Condition: `input.extensions.subject.user_role` is not one of the five recognized roles
- Matching: exact / set-membership (negated)

### Rule: VEHICLE_TYPE_ROLE_RESTRICTION
- OWASP: ASI02
- Severity: Hard block
- Condition: `input.name == "get_vehicles_by_type"` AND `input.args.vehicle_type` is not in the calling role's allowed vehicle-type set
- Matching: exact, case-sensitive, set-membership

### Rule: VEHICLE_TYPE_UNRECOGNIZED_DENY
- OWASP: ASI02
- Severity: Hard block
- Condition: `input.name == "get_vehicles_by_type"` AND `input.args.vehicle_type` is not one of the six recognized values (any role, including analyst) — do not rely on the tool implementation's silent fallback to `"carros"`
- Matching: exact, case-sensitive, set-membership (negated)

### Rule: BRAND_ROLE_RESTRICTION
- OWASP: ASI02
- Severity: Hard block
- Condition: `input.name == "search_car_price"` AND `input.args.brand_name` is not in the calling role's allowed brand set (only `fleet_manager` and `journalist` are restricted)
- Matching: exact, case-sensitive, set-membership

### Rule: BRAND_EMPTY_DENY
- OWASP: ASI02
- Severity: Hard block
- Condition: `input.name == "search_car_price"` AND `input.args.brand_name` is empty or whitespace-only
- Matching: exact (string emptiness check, all roles)

---

## Violation Code Reference

| Code | OWASP | Severity |
|---|---|---|
| GUEST_TOOL_DENY | ASI02 | Hard block |
| UNKNOWN_ROLE_DENY | ASI02 | Hard block |
| VEHICLE_TYPE_ROLE_RESTRICTION | ASI02 | Hard block |
| VEHICLE_TYPE_UNRECOGNIZED_DENY | ASI02 | Hard block |
| BRAND_ROLE_RESTRICTION | ASI02 | Hard block |
| BRAND_EMPTY_DENY | ASI02 | Hard block |

`Citations verified: 6/6` — every `input.args.*` field (`brand_name`, `vehicle_type`) appears in `tool_definitions.json`; `input.extensions.subject.user_role` appears in `system_vars.json` and architecture.md's Trust Boundaries table; every rule traces to a threat_model.md ASI02 threat instance; no rule's value set derives from a questionnaire answer tagged `[inferred — low confidence]` (all role/vehicle_type/brand value sets are `[derived from guidance.txt]`).
