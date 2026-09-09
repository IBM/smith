# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines
# Tool: car-price-mcp

---

## Architecture Summary

`car-price-mcp` is a five-layer system: an HTTP API layer accepts an unauthenticated `question` and a self-reported `user_profile` dict, an LLM-based Agent layer resolves which of three FIPE tools to call, an MCP Tool layer is the OPA interception point, a Tool Implementation layer performs HTTP GET calls against the public FIPE API, and the External Service layer is the unauthenticated FIPE price API. All three tools are read-only; no writes or mutations exist anywhere in the system.

---

## OWASP Top 10 for Agentic AI Security — Scope Assessment

### ASI01 — Agent Goal Hijack
**Risk:** Crafted `question` or `user_profile` values redirect the LLM's tool-selection reasoning away from the caller's authorized scope.
**Verdict:** Partial (Out of scope for OPA, in scope for Agent layer) — The `question` field and the injected `user_profile` text live in the LLM's context; they are not structured fields OPA can evaluate. OPA sees only the resolved tool name and arguments after the LLM has already reasoned, so it catches the *output* of goal hijacking but cannot prevent the LLM from being manipulated in the first place.

### ASI02 — Tool Misuse and Exploitation
**Risk:** Callers or the LLM pass disallowed `brand_name` or `vehicle_type` values, bypassing role-based restrictions.
**Verdict:** In scope — `input.args.brand_name` and `input.args.vehicle_type` are visible at OPA interception time and Rego rules can enforce exact-match allow-lists and recognized-value checks against them.

### ASI03 — Identity and Privilege Abuse
**Risk:** Callers self-assign high-privilege roles (e.g. `analyst`) in the unverified `user_profile.user_role` field.
**Verdict:** In scope — `input.extensions.subject.user_role` is visible at OPA interception time; Rego rules can enforce which tools a given role may call and with which parameter values.

### ASI04 — Agentic Supply Chain Vulnerabilities
**Risk:** Compromised third-party libraries (`mcp`, `langchain`, `requests`) or a tampered FIPE API response inject malicious behavior.
**Verdict:** Out of scope — library loading occurs before any request; FIPE API responses are the tool's return value, after OPA has already acted. Both are infrastructure/deployment concerns.

### ASI05 — Unexpected Code Execution
**Risk:** Repeated `search_car_price` calls exhaust the FIPE API's rate limit (up to ~8 sub-requests per invocation).
**Verdict:** Out of scope — OPA has no call-count state and no rate-limiting capability at the invocation boundary. This belongs to infrastructure (API gateway rate limiting).

### ASI06 — Memory & Context Poisoning
**Risk:** Within a request's conversation window, fragmented injections poison the LLM's context.
**Verdict:** Out of scope — conversation history lives in the Agent layer; OPA only sees the resolved tool call, not the reasoning that produced it.

### ASI07 — Insecure Inter-Agent Communication
**Risk:** N/A — single-agent system with no inter-agent communication.
**Verdict:** Out of scope — not applicable.

### ASI08 — Cascading Failures
**Risk:** LangGraph retry loops compound FIPE API calls.
**Verdict:** Out of scope — retry logic is in the Agent layer; OPA sees individual calls but not loop depth or aggregate call count.

### ASI09 — Human-Agent Trust Exploitation
**Risk:** Misleading `user_profile` context or LLM hallucinations cause the agent to present false pricing as authoritative.
**Verdict:** Out of scope — the misleading text in system prompt and the tool's return value are post-execution; OPA enforces pre-execution only.

### ASI10 — Rogue Agents
**Risk:** N/A — single-agent system with no multi-agent coordination.
**Verdict:** Out of scope — not applicable.

---

## Summary Table

| OWASP Category | In OPA scope? | Out-of-scope owner |
|---|---|---|
| ASI01 Agent Goal Hijack | Partial (OPA catches resolved args; prompt injection itself is Agent layer) | Agent layer — system prompt hardening, prompt injection detection |
| ASI02 Tool Misuse and Exploitation | Yes | — |
| ASI03 Identity and Privilege Abuse | Yes | Infrastructure — authentication upstream of OPA |
| ASI04 Agentic Supply Chain Vulnerabilities | No | Infrastructure/deployment — dependency pinning, SBOM, API integrity |
| ASI05 Unexpected Code Execution | No | Infrastructure — API gateway rate limiting |
| ASI06 Memory & Context Poisoning | No | Agent layer — context window size limits, per-request session isolation |
| ASI07 Insecure Inter-Agent Communication | No | N/A (not applicable) |
| ASI08 Cascading Failures | No | Agent layer / Infrastructure — LangGraph loop limits, API rate limiting |
| ASI09 Human-Agent Trust Exploitation | No | Agent layer / Monitoring — output verification, provenance metadata |
| ASI10 Rogue Agents | No | N/A (not applicable) |

**Categories flowing into the OPA policy: ASI02, ASI03**

---

## Gap Register

| Threat | Layer | Recommended action |
|---|---|---|
| ASI01 — Goal hijack via `question` field prompt injection | Agent layer | Add prompt-injection detection middleware; consider sandboxed system-prompt templates that reject natural-language overrides |
| ASI01 — Goal hijack via `user_profile` value injection into system prompt | Agent layer | Sanitize `user_profile` values before embedding in system prompt; strip or escape natural-language instruction patterns |
| ASI03 — `user_role` is entirely self-reported, no authentication | Infrastructure/deployment | Add authentication (e.g. JWT with role claims) at the HTTP API layer; OPA enforces the role it receives but cannot verify it is truthful |
| ASI04 — Unpinned third-party dependencies (`mcp`, `langchain`, `requests`) | Infrastructure/deployment | Pin all dependencies to exact versions; generate an SBOM; scan for typosquats and malicious packages before install |
| ASI04 — FIPE API response integrity not verified | Tool Implementation | Add response schema validation in `app.py`; consider caching brand lists to reduce exposure to poisoned live responses |
| ASI05 — FIPE API quota exhaustion from repeated `search_car_price` calls | Infrastructure/deployment | Add an API gateway or middleware rate limiter (per-IP or per-session); `search_car_price` makes up to ~8 sub-calls per invocation |
| ASI06 — In-request context poisoning via fragmented `question` turns | Agent layer | Limit conversation history retained per session; validate that message sequence does not contain known injection patterns |
| ASI08 — LangGraph retry loop fan-out on FIPE API errors | Agent layer / Infrastructure | Set a hard maximum iteration count in the LangGraph ReAct agent; log and alert on loop depth exceeding threshold |
| ASI09 — LLM presenting hallucinated pricing data as authoritative | Agent layer / Monitoring | Add a disclaimer in the system prompt that results are from the FIPE API (not the agent's own knowledge); consider response validation against the raw FIPE data |
| ASI09 — Misleading `user_profile` text in system prompt influencing output trust | Agent layer | Sanitize `user_profile` values before embedding (same as ASI01 gap); do not embed raw user input as "authoritative system context" |

---

## Policy Rules (OPA scope only)

### Input Schema

| Field | Source |
|---|---|
| `input.name` | MCP tool name (one of: `get_car_brands`, `search_car_price`, `get_vehicles_by_type`) |
| `input.args.brand_name` | Tool argument — declared on `search_car_price` only |
| `input.args.vehicle_type` | Tool argument — declared on `get_vehicles_by_type` only |
| `input.extensions.subject.user_role` | Self-reported role array from `system_vars.json`; exact values from the recognised five-role set |

### Known values

**Recognised roles:** `fleet_manager`, `consumer`, `journalist`, `analyst`, `guest`

**Truck-brand allow-list (fleet_manager):** `Scania`, `Volvo`, `Mercedes-Benz`, `MAN`, `DAF`, `Iveco`, `Ford`, `Volkswagen`

**Domestic-brand allow-list (journalist):** `Fiat`, `Chevrolet`, `Volkswagen`, `Hyundai`, `Toyota`, `Renault`, `Honda`, `Nissan`, `Jeep`, `Peugeot`, `Citroën`, `Caoa Chery`

**Luxury/imported-brand block-list (journalist):** `BMW`, `Mercedes-Benz`, `Audi`, `Porsche`, `Jaguar`, `Land Rover`, `Lexus`, `Maserati`, `Ferrari`, `Lamborghini`, `Bentley`, `Rolls-Royce`, `Mini`, `Alfa Romeo`
*(Implementation note: use the domestic allow-list as a positive test — deny any `brand_name` not in the allow-list — rather than the luxury block-list as a negative test, to avoid gaps from newly added luxury brands.)*

**Recognised vehicle types:** `carros`, `cars`, `motos`, `motorcycles`, `caminhoes`, `trucks`

**Fleet-manager allowed vehicle types:** `caminhoes`, `trucks`

**Consumer/journalist allowed vehicle types:** `carros`, `cars`

**Role note:** `user_role` is an array. A user may carry multiple roles. For deny rules that are role-specific, a deny fires when the caller's role array contains the restricted role but NOT a more-privileged role that would override it (e.g. if a caller is simultaneously `fleet_manager` and `analyst`, the analyst privilege should take precedence for brand/vehicle-type checks). Evaluate per-role checks as: deny if the restricted role is present AND no overriding role is present. For the `guest` tool-access block, deny if the role array contains `guest` and no non-guest role is present.

---

### Rule: ROLE_BLOCKED
- OWASP: ASI03 — Identity and Privilege Abuse
- Severity: Hard block
- Condition: `input.name` is any of the three tools AND `input.extensions.subject.user_role` contains no value that is a member of the five recognised roles (`fleet_manager`, `consumer`, `journalist`, `analyst`, `guest`)
- Matching: exact set-membership check against the five-element role set
- Source: ASI03 threat instances (Critical, Caller); questionnaire Q9 "Unknown Roles" rule

### Rule: GUEST_TOOL_BLOCKED
- OWASP: ASI03 — Identity and Privilege Abuse
- Severity: Hard block
- Condition: `input.name` is `search_car_price` or `get_vehicles_by_type` AND `input.extensions.subject.user_role` contains `guest` AND `input.extensions.subject.user_role` contains no non-guest role
- Matching: exact tool-name match; exact set-membership check on role array
- Source: ASI03 threat instances; questionnaire Q9 guest access rule; guidance.txt "Tool Access by Role" (guest section)

### Rule: BRAND_EMPTY
- OWASP: ASI02 — Tool Misuse and Exploitation
- Severity: Hard block
- Condition: `input.name` is `search_car_price` AND `input.args.brand_name` is empty string or whitespace-only (after trimming)
- Matching: exact equality to empty string or string containing only whitespace characters
- Source: ASI02 threat instance (Caller, High); questionnaire Q12; guidance.txt "Brand Restrictions" (empty/whitespace brand)

### Rule: BRAND_BLOCKED_FLEET
- OWASP: ASI02 — Tool Misuse and Exploitation
- Severity: Hard block
- Condition: `input.name` is `search_car_price` AND `input.extensions.subject.user_role` contains `fleet_manager` AND NOT `analyst` AND `input.args.brand_name` is not a member of the truck-brand allow-list {Scania, Volvo, Mercedes-Benz, MAN, DAF, Iveco, Ford, Volkswagen}
- Matching: exact case-sensitive set-membership against the truck-brand allow-list
- Source: ASI02 threat instance (Caller, High); questionnaire Q9/Q10; guidance.txt "Brand Restrictions" (fleet_manager)

### Rule: BRAND_BLOCKED_JOURNALIST
- OWASP: ASI02 — Tool Misuse and Exploitation
- Severity: Hard block
- Condition: `input.name` is `search_car_price` AND `input.extensions.subject.user_role` contains `journalist` AND NOT `analyst` AND `input.args.brand_name` is not a member of the domestic-brand allow-list {Fiat, Chevrolet, Volkswagen, Hyundai, Toyota, Renault, Honda, Nissan, Jeep, Peugeot, Citroën, Caoa Chery}
- Matching: exact case-sensitive set-membership against the domestic-brand allow-list
- Source: ASI02 threat instance (Caller, High); questionnaire Q9/Q10; guidance.txt "Brand Restrictions" (journalist)

### Rule: VEHICLE_TYPE_BLOCKED
- OWASP: ASI02 — Tool Misuse and Exploitation
- Severity: Hard block
- Condition: `input.name` is `get_vehicles_by_type` AND `input.args.vehicle_type` is not a member of the recognized set {carros, cars, motos, motorcycles, caminhoes, trucks}
- Matching: exact case-sensitive set-membership (e.g. `"Caminhoes"` with capital C is NOT in the set and must be denied)
- Source: ASI02 threat instance (Caller, Medium — vehicle_type wrong casing); questionnaire Q12; guidance.txt "Vehicle Type Restrictions" (any other value denied for every role)

### Rule: VEHICLE_TYPE_FLEET_BLOCKED
- OWASP: ASI02 — Tool Misuse and Exploitation
- Severity: Hard block
- Condition: `input.name` is `get_vehicles_by_type` AND `input.extensions.subject.user_role` contains `fleet_manager` AND NOT `analyst` AND `input.args.vehicle_type` is not a member of {caminhoes, trucks}
- Matching: exact case-sensitive set-membership against the fleet_manager allowed vehicle types
- Source: ASI02 threat instance (Caller, High); questionnaire Q9/Q10; guidance.txt "Vehicle Type Restrictions" (fleet_manager)

### Rule: VEHICLE_TYPE_CONSUMER_BLOCKED
- OWASP: ASI02 — Tool Misuse and Exploitation
- Severity: Hard block
- Condition: `input.name` is `get_vehicles_by_type` AND `input.extensions.subject.user_role` contains `consumer` AND NOT `analyst` AND `input.args.vehicle_type` is not a member of {carros, cars}
- Matching: exact case-sensitive set-membership against the consumer allowed vehicle types
- Source: ASI02 threat instance (Caller, High); questionnaire Q9/Q10; guidance.txt "Vehicle Type Restrictions" (consumer)

### Rule: VEHICLE_TYPE_JOURNALIST_BLOCKED
- OWASP: ASI02 — Tool Misuse and Exploitation
- Severity: Hard block
- Condition: `input.name` is `get_vehicles_by_type` AND `input.extensions.subject.user_role` contains `journalist` AND NOT `analyst` AND `input.args.vehicle_type` is not a member of {carros, cars}
- Matching: exact case-sensitive set-membership against the journalist allowed vehicle types
- Source: ASI02 threat instance (Caller, High); questionnaire Q9/Q10; guidance.txt "Vehicle Type Restrictions" (journalist)

---

## Violation Code Reference

| Code | OWASP | Severity |
|---|---|---|
| ROLE_BLOCKED | ASI03 | Hard block |
| GUEST_TOOL_BLOCKED | ASI03 | Hard block |
| BRAND_EMPTY | ASI02 | Hard block |
| BRAND_BLOCKED_FLEET | ASI02 | Hard block |
| BRAND_BLOCKED_JOURNALIST | ASI02 | Hard block |
| VEHICLE_TYPE_BLOCKED | ASI02 | Hard block |
| VEHICLE_TYPE_FLEET_BLOCKED | ASI02 | Hard block |
| VEHICLE_TYPE_CONSUMER_BLOCKED | ASI02 | Hard block |
| VEHICLE_TYPE_JOURNALIST_BLOCKED | ASI02 | Hard block |

---

*STEP 6b citation verification: All 9 rules verified. `brand_name` declared by `search_car_price.parameters`; `vehicle_type` declared by `get_vehicles_by_type.parameters`; `user_role` declared by `system_vars.json`. All governed tool assignments correct (no rule references a tool that lacks the cited field). All brand and vehicle-type values present in `guidance.txt` and `tool_definitions.json` descriptions. Citations verified: 9/9.*

*STEP 7 candidate list: 9 candidates total — 9 from OWASP (ASI02: 7 rules, ASI03: 2 rules) + 9 from questionnaire Q9/Q10/Q12 (all overlap with OWASP candidates, deduplicated). Final list: 9 unique rules, all tagged [ASI02 or ASI03] + [questionnaire Q9/Q10/Q12].*

*STEP 8 coverage scratch table:*
| Candidate | Verified (tool, field) | Field | Operator | Value set | Matching guidance.txt rule | Covered? |
|---|---|---|---|---|---|---|
| ROLE_BLOCKED | all tools / subject.user_role | input.extensions.subject.user_role | set-membership (not in 5 roles) | {fleet_manager,consumer,journalist,analyst,guest} | "Unknown Roles" section | Yes |
| GUEST_TOOL_BLOCKED | search_car_price, get_vehicles_by_type / subject.user_role | input.name + subject.user_role | exact name match + set-membership | guest only | "Tool Access by Role" guest section | Yes |
| BRAND_EMPTY | search_car_price / args.brand_name | input.args.brand_name | empty/whitespace check | "" or whitespace | "Brand Restrictions" last rule | Yes |
| BRAND_BLOCKED_FLEET | search_car_price / args.brand_name | input.args.brand_name | exact set-membership (allow-list) | truck brands | "Brand Restrictions" fleet_manager | Yes |
| BRAND_BLOCKED_JOURNALIST | search_car_price / args.brand_name | input.args.brand_name | exact set-membership (allow-list) | domestic brands | "Brand Restrictions" journalist | Yes |
| VEHICLE_TYPE_BLOCKED | get_vehicles_by_type / args.vehicle_type | input.args.vehicle_type | exact set-membership | 6 recognised values | "Vehicle Type Restrictions" any-other-value sentence | Yes |
| VEHICLE_TYPE_FLEET_BLOCKED | get_vehicles_by_type / args.vehicle_type | input.args.vehicle_type + subject.user_role | exact set-membership | {caminhoes,trucks} | "Vehicle Type Restrictions" fleet_manager | Yes |
| VEHICLE_TYPE_CONSUMER_BLOCKED | get_vehicles_by_type / args.vehicle_type | input.args.vehicle_type + subject.user_role | exact set-membership | {carros,cars} | "Vehicle Type Restrictions" consumer | Yes |
| VEHICLE_TYPE_JOURNALIST_BLOCKED | get_vehicles_by_type / args.vehicle_type | input.args.vehicle_type + subject.user_role | exact set-membership | {carros,cars} | "Vehicle Type Restrictions" journalist | Yes |

All 9 candidates are covered by existing `guidance.txt` rules. No new lines needed in `guidance_updated.txt`.

*STEP 8b redundancy self-check: No new rules to add; no pairs to compare. Result: Redundancy self-check: no new rules proposed — nothing to scan.*

*STEP 8c regression check: Prior `guidance_updated.txt` was empty (first run or prior run also found full coverage). No regressions — prior run's outcome is consistent with this run.*
