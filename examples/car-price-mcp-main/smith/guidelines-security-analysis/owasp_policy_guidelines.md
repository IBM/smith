# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines
# Tool: car-price-mcp-main

---

## Architecture Summary

The `car-price-mcp-main` system is a two-layer stack: a FastAPI agent layer (`agent.py`) that accepts caller-supplied `user_profile` context and constructs a LangGraph ReAct agent, which invokes one of three MCP tools (`get_car_brands`, `search_car_price`, `get_vehicles_by_type` in `server.py`) over a local stdio transport. All identity fields (`user_role`) are self-reported by the caller with no cryptographic verification, and both tool arguments (`brand_name`, `vehicle_type`) are LLM-generated — making OPA enforcement at the MCP invocation boundary the only structural control point for role-based access and parameter validation.

---

## OWASP Top 10 for Agentic AI Security — Scope Assessment

### ASI01 — Agent Goal Hijack
**Risk:** Caller-controlled `user_profile` fields are injected verbatim into the system prompt, enabling prompt injection that redirects the LLM's tool-argument decisions (e.g., brand or vehicle-type selection).
**Verdict:** Partial — The downstream effect (LLM selects a disallowed `brand_name` or `vehicle_type`) is OPA-enforceable at invocation time; the injection mechanism itself (inside LLM system-prompt reasoning) is not.

### ASI02 — Tool Misuse and Exploitation
**Risk:** LLM-generated arguments (`brand_name`, `vehicle_type`) and `app.py`'s silent coercion behaviors allow parameter-pollution, wrong-case bypass, and unrecognized-type fallback to reach the FIPE API unchecked.
**Verdict:** Partial — `input.args.vehicle_type` and `input.args.brand_name` are present as structured fields at invocation time and can be checked by OPA; call-volume loop amplification has no structured field at invocation time.

### ASI03 — Identity and Privilege Abuse
**Risk:** `user_role` is entirely self-reported, enabling role escalation (guest → analyst, journalist → analyst, fleet_manager → consumer) and unknown-role access.
**Verdict:** In scope — `input.extensions.subject.user_role` and `input.name` are present as structured fields at invocation time; all role-based access rules are enforceable.

### ASI04 — Agentic Supply Chain Vulnerabilities
**Risk:** Third-party library `requests` could be compromised to tamper with FIPE API responses.
**Verdict:** Out of scope — library loading occurs at import time, not at tool invocation; no structured field is available at interception that reflects library integrity.

### ASI05 — Unexpected Code Execution (RCE)
**Risk:** Not applicable — the tool has no code-generation, eval, or shell execution capability.
**Verdict:** Out of scope — N/A.

### ASI06 — Memory & Context Poisoning
**Risk:** Not applicable — the agent is stateless with no persistent memory store.
**Verdict:** Out of scope — N/A.

### ASI07 — Insecure Inter-Agent Communication
**Risk:** Not applicable — single-agent, single-tool-server system with local stdio transport only.
**Verdict:** Out of scope — N/A.

### ASI08 — Cascading Failures
**Risk:** Not applicable — single tool chain, no delegation, no multi-session propagation.
**Verdict:** Out of scope — N/A.

### ASI09 — Human-Agent Trust Exploitation
**Risk:** LLM may fabricate or supplement FIPE price data without source attribution.
**Verdict:** Out of scope — hallucination occurs post-tool-call during response generation, not at a structured tool-invocation intercept point.

### ASI10 — Rogue Agents
**Risk:** Not applicable — single-agent system with no multi-agent coordination.
**Verdict:** Out of scope — N/A.

---

## Summary Table

| OWASP Category | In OPA scope? | Out-of-scope owner |
|---|---|---|
| ASI01 — Agent Goal Hijack | Partial | Agent layer (prompt sanitization) |
| ASI02 — Tool Misuse and Exploitation | Partial | Infrastructure (rate limiting) |
| ASI03 — Identity and Privilege Abuse | Yes | — |
| ASI04 — Agentic Supply Chain Vulnerabilities | No | Infrastructure/deployment (dependency pinning) |
| ASI05 — Unexpected Code Execution (RCE) | No | N/A |
| ASI06 — Memory & Context Poisoning | No | N/A |
| ASI07 — Insecure Inter-Agent Communication | No | N/A |
| ASI08 — Cascading Failures | No | N/A |
| ASI09 — Human-Agent Trust Exploitation | No | Agent layer (response attribution) |
| ASI10 — Rogue Agents | No | N/A |

Categories flowing into the OPA policy: ASI01 (partial), ASI02 (partial), ASI03

---

## Gap Register

| Threat | Layer | Recommended action |
|---|---|---|
| ASI01: `user_profile` fields injected verbatim into system prompt — injection mechanism itself | Agent layer | Sanitize and validate all `user_profile` values before embedding in system prompt; strip or escape natural-language instruction patterns |
| ASI02: No per-session call-volume cap on any tool | Infrastructure | Implement server-side rate limiting or session call counter; a session counter field is not present in `system_vars.json` so OPA cannot enforce this |
| ASI03: `user_role` entirely self-reported with no verification | Application layer | Integrate an authenticated identity provider that issues verified role claims; do not rely solely on OPA for role-based controls when the role value is caller-supplied |
| ASI04: `requests` library unpinned, no hash verification | Infrastructure/deployment | Pin library versions in `requirements.txt` with hashes, use a lockfile, and scan with a vulnerability scanner |
| ASI09: LLM may fabricate or supplement FIPE data without attribution | Agent layer | Attach source attribution to agent responses; add a disclaimer when the LLM supplements results beyond what FIPE returned |

---

## Policy Rules (OPA scope only)

### Input Schema
| Field | Source |
|---|---|
| `input.name` | Tool name (`get_car_brands`, `search_car_price`, `get_vehicles_by_type`) |
| `input.args.brand_name` | `tool_definitions.json` — string, required for `search_car_price` |
| `input.args.vehicle_type` | `tool_definitions.json` — string, optional for `get_vehicles_by_type`, default `"carros"` |
| `input.extensions.subject.user_role` | `system_vars.json` — string, one of: `fleet_manager`, `consumer`, `journalist`, `analyst`, `guest` |

### Known values
```
recognized_vehicle_types = {
  "carros", "cars", "motos", "motorcycles", "caminhoes", "trucks"
}

fleet_manager_vehicle_types = { "caminhoes", "trucks" }
consumer_journalist_vehicle_types = { "carros", "cars" }

fleet_manager_brands = {
  "Scania", "Volvo", "Mercedes-Benz", "MAN", "DAF", "Iveco", "Ford", "Volkswagen"
}

journalist_brands = {
  "Fiat", "Chevrolet", "Volkswagen", "Hyundai", "Toyota", "Renault",
  "Honda", "Nissan", "Jeep", "Peugeot", "Citroën", "Caoa Chery"
}

defined_roles = { "fleet_manager", "consumer", "journalist", "analyst", "guest" }

guest_allowed_tools = { "get_car_brands" }
tools_requiring_role_check = { "search_car_price", "get_vehicles_by_type" }
```

### Rule: CAR-ROLE-001
- OWASP: ASI03
- Severity: Hard block
- Condition: Deny any tool call when `input.extensions.subject.user_role` is not in `defined_roles` (i.e. unknown or missing role)
- Matching: Set membership (exact)

### Rule: CAR-ROLE-002
- OWASP: ASI03 / ASI02
- Severity: Hard block
- Condition: Deny `search_car_price` or `get_vehicles_by_type` when `input.extensions.subject.user_role` is `guest`
- Matching: Exact equality on role; set membership on tool name

### Rule: CAR-VTYPE-001
- OWASP: ASI02 / ASI01
- Severity: Hard block
- Condition: Deny `get_vehicles_by_type` when `input.args.vehicle_type` is not in `recognized_vehicle_types`; applies to every role including `analyst`. Matching is exact and case-sensitive — `"Caminhoes"` is not the same as `"caminhoes"` and must be denied.
- Matching: Set membership (exact, case-sensitive)

### Rule: CAR-VTYPE-002
- OWASP: ASI03 / ASI02
- Severity: Hard block
- Condition: Deny `get_vehicles_by_type` when `input.extensions.subject.user_role` is `fleet_manager` and `input.args.vehicle_type` is not in `fleet_manager_vehicle_types` (`"caminhoes"` or `"trucks"`)
- Matching: Set membership (exact, case-sensitive)

### Rule: CAR-VTYPE-003
- OWASP: ASI03 / ASI02
- Severity: Hard block
- Condition: Deny `get_vehicles_by_type` when `input.extensions.subject.user_role` is `consumer` or `journalist` and `input.args.vehicle_type` is not in `consumer_journalist_vehicle_types` (`"carros"` or `"cars"`)
- Matching: Set membership (exact, case-sensitive)

### Rule: CAR-BRAND-001
- OWASP: ASI02 / ASI01
- Severity: Hard block
- Condition: Deny `search_car_price` when `input.args.brand_name` is empty or contains only whitespace characters
- Matching: String emptiness / whitespace-only check

### Rule: CAR-BRAND-002
- OWASP: ASI03 / ASI02
- Severity: Hard block
- Condition: Deny `search_car_price` when `input.extensions.subject.user_role` is `fleet_manager` and `input.args.brand_name` is not in `fleet_manager_brands`. Matching is exact and case-sensitive — `"volvo"` and `"VOLVO"` are not `"Volvo"` and must be denied.
- Matching: Set membership (exact, case-sensitive)

### Rule: CAR-BRAND-003
- OWASP: ASI03 / ASI01
- Severity: Hard block
- Condition: Deny `search_car_price` when `input.extensions.subject.user_role` is `journalist` and `input.args.brand_name` is not in `journalist_brands`. Matching is exact and case-sensitive.
- Matching: Set membership (exact, case-sensitive)

---

## Violation Code Reference

| Code | OWASP | Severity |
|---|---|---|
| CAR-ROLE-001 | ASI03 | Hard block |
| CAR-ROLE-002 | ASI03 / ASI02 | Hard block |
| CAR-VTYPE-001 | ASI02 / ASI01 | Hard block |
| CAR-VTYPE-002 | ASI03 / ASI02 | Hard block |
| CAR-VTYPE-003 | ASI03 / ASI02 | Hard block |
| CAR-BRAND-001 | ASI02 / ASI01 | Hard block |
| CAR-BRAND-002 | ASI03 / ASI02 | Hard block |
| CAR-BRAND-003 | ASI03 / ASI01 | Hard block |
