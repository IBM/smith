# OPA Policy Guidance Questionnaire
# Tool: car-price-mcp

Fill in each answer based on your tool and agent. You do not need to
know OPA or security to complete this — just describe how your tool
works and who should be able to use it.

---

## Section 1: Tool Identity

**Q1. What is the tool name and what does it do in one sentence?**

> Tool name: `car-price-mcp` (three tools: `get_car_brands`, `search_car_price`, `get_vehicles_by_type`)
> A FIPE-backed car pricing MCP server that lets callers list car brands, search prices by brand, and list brands by vehicle type. [derived from architecture]

---

**Q2. What external systems does it call?**

> `https://parallelum.com.br/fipe/api/v1/...` (FIPE Brazilian vehicle price API), HTTPS, unauthenticated, read-only. [derived from architecture]

---

**Q3. Does it read data, write data, or both?**

> Read only — all three tools issue GET requests to the FIPE API and return formatted text; no writes anywhere in the tool implementation. [derived from architecture]

---

**Q4. What are its parameters? For each: name, type, required or optional,
what counts as a valid value?**

| Parameter | Type | Required | Valid values |
|-----------|------|----------|--------------|
| `brand_name` (search_car_price) | string | Yes | Non-empty, non-whitespace-only string; guidance.txt requires exact case-sensitive match against role-specific allow/block lists [derived from guidance.txt] |
| `vehicle_type` (get_vehicles_by_type) | string | No (default `"carros"`) | Exactly one of `"carros"`, `"cars"`, `"motos"`, `"motorcycles"`, `"caminhoes"`, `"trucks"` per guidance.txt; any other value (including different casing) must be denied rather than allowed to fall through to the tool's own `"carros"` coercion [derived from guidance.txt] |
| (get_car_brands has no parameters) | — | — | — |

---

## Section 2: Who Uses It

**Q5. What are the types of users? List every role.**

> - `fleet_manager` — truck-fleet operations use case, restricted to truck-relevant vehicle types and brands
> - `consumer` — general public, restricted to car/passenger vehicle types, no brand restriction
> - `journalist` — restricted to car/passenger vehicle types and domestic-market brands
> - `analyst` — unrestricted across all tools, vehicle types, and brands
> - `guest` — may only call `get_car_brands`
> [derived from guidance.txt]

---

**Q6. Are those roles verified by your system, or supplied by the user themselves?**

> Self-reported. `agent.py`'s `/chat` and `/extract_tool_call` endpoints accept an arbitrary `user_profile` dict directly in the HTTP request body with no authentication step; `user_role` is one of its keys. `system_vars.json` documents the shape of this field (an array of the five candidate role strings) but is not itself a verification mechanism — it is a schema example, not an auth check. [derived from architecture]

---

**Q7. Is there a user ID? Where does it come from?**

> `user_name` appears in `system_vars.json` (e.g. `"Bob"`) alongside `user_role`, but like `user_role` it is caller-supplied via `user_profile` with no verification and is not used by any guidance.txt rule. [derived from architecture]

---

**Q8. Can a user belong to multiple roles at once?**

> No indication in guidance.txt or system_vars.json of multi-role assignment — `system_vars.json`'s `user_role` field lists the five *candidate* values the field can take, not that a single request can carry more than one simultaneously; each request is evaluated against whichever role value(s) are present in `input.extensions.subject.user_role`. [inferred — low confidence]

---

## Section 3: What Each Role Is Allowed To Do

**Q9. For each role, which tools are they allowed to use and with what
conditions or scope restrictions?**

| Tool | fleet_manager | consumer | journalist | analyst | guest | guidance.txt rule |
|------|----------|----------|----------|---------|-------|-------------------|
| `get_car_brands` | Allowed | Allowed | Allowed | Allowed | Allowed | Tool Access by Role |
| `search_car_price` | Allowed, brand restricted (see Q10) | Allowed, unrestricted | Allowed, brand restricted (see Q10) | Allowed, unrestricted | Denied | Tool Access by Role; Brand Restrictions |
| `get_vehicles_by_type` | Allowed, vehicle_type restricted (see Q10) | Allowed, vehicle_type restricted (see Q10) | Allowed, vehicle_type restricted (see Q10) | Allowed, unrestricted | Denied | Tool Access by Role; Vehicle Type Restrictions |

[derived from guidance.txt]

---

**Q10. Are there topics, values, or parameter combinations some roles
can use that others cannot?**

> Yes, two independent restriction axes:
> - **Vehicle type** (`get_vehicles_by_type`): fleet_manager → `caminhoes`/`trucks` only; consumer and journalist → `carros`/`cars` only; analyst → any of the six recognized values; guest → cannot call the tool at all. Matching is exact and case-sensitive against the lowercase canonical set.
> - **Brand name** (`search_car_price`): fleet_manager → 8 truck-relevant brands only (`Scania`, `Volvo`, `Mercedes-Benz`, `MAN`, `DAF`, `Iveco`, `Ford`, `Volkswagen`); journalist → 12 domestic-market brands only (`Fiat`, `Chevrolet`, `Volkswagen`, `Hyundai`, `Toyota`, `Renault`, `Honda`, `Nissan`, `Jeep`, `Peugeot`, `Citroën`, `Caoa Chery`), explicitly excluding 14 named luxury/import brands; consumer and analyst → unrestricted. `Mercedes-Benz` and `Volkswagen` intentionally appear on more than one role's list and are evaluated independently per role.
> [derived from guidance.txt]

---

**Q11. Are there roles that have no restrictions?**

> `consumer` and `analyst` have no brand restriction on `search_car_price`; `analyst` additionally has no vehicle_type restriction on `get_vehicles_by_type` and is the only role with zero restrictions across both restricted tools. [derived from guidance.txt]

---

## Section 4: Hard Limits

**Q12. Are there parameter values that should always be blocked for
everyone, regardless of role?**

> - `vehicle_type` values outside the six recognized values (`carros`, `cars`, `motos`, `motorcycles`, `caminhoes`, `trucks`), including any different casing such as `"Caminhoes"` — denied for every role, not just role-restricted. The tool implementation (`app.py`'s `getCarsByType`) silently coerces any unrecognized value to `"carros"`; guidance.txt explicitly requires the policy to reject rather than rely on that fallback.
> - `brand_name` that is empty or whitespace-only — denied for every role, including consumer/analyst who otherwise have no brand restriction.
> [derived from guidance.txt]

---

**Q13. Is there a maximum value for any numeric parameter that no role
can exceed?**

> None — no numeric parameters exist on any of the three tools. [derived from architecture]

---

**Q13b. Are there approval paths — actions allowed conditionally when an
approval field is set?**

> None found in guidance.txt or system_vars.json — no approval-flag field exists in the subject schema. [derived from guidance.txt]

---

**Q14. Are there keywords or inputs that must always be rejected?**

> No free-text keyword-block list in guidance.txt. The closest analog is the brand-name allow/block-list matching in Q10/Q12, which is value-set matching on a structured field (`brand_name`), not free-text keyword filtering. [derived from guidance.txt]

---

## Section 5: Volume and Rate Limits

**Q15. Is there a maximum number of times this tool can be called in
a single conversation session?**

> No — no session-call-count field exists in `system_vars.json`, and guidance.txt does not mention rate limits. [derived from guidance.txt]

| Role | Max calls per session |
|------|-----------------------|
| (none defined) | — |

---

**Q16. Who keeps track of how many times the tool has been called —
your app, or should the policy enforce it?**

> Neither — no call-counting mechanism exists anywhere in `agent.py`, `server.py`, or `app.py`, and no such field is present in `system_vars.json` for the policy to read. [derived from architecture]

---

## Section 6: Response Filtering

**Q17. After the tool returns results, does anything need to be hidden,
flagged, or categorised before the user sees it?**

> None specified in guidance.txt. Note (architecture-level, not a guidance rule): `search_car_price`'s underlying substring match against live FIPE brand names means an allowed `brand_name` string can resolve to FIPE data for a *different* brand than the caller intended (e.g. a short substring matching an unexpected entry) — this is a tool-implementation behavior, out of policy scope, not a response-filtering requirement from guidance.txt. [derived from guidance.txt for the "none specified" answer; architecture note flagged separately]

---

**Q18. Are there fields in the response that should be suppressed for
certain roles?**

> None specified in guidance.txt — no role-based response-field suppression rule exists. [derived from guidance.txt]

---

**Q19. Are there conditions on a result that determine whether it is
"actionable"?**

> None specified in guidance.txt. [derived from guidance.txt]

---

## Section 7: Violations

**Q20. Should a blocked request be silently rejected, or should the
user receive an explanation?**

> guidance.txt does not state a preference explicitly; the generated policy in `assets/policy.rego` (prior iteration) emitted specific `deny` messages per violation type (e.g. distinguishing unknown-role denial from vehicle_type denial from brand denial), which is consistent with an explanation-bearing denial rather than a silent one. [inferred — low confidence]

---

**Q21. Are there different severity levels — hard block vs. warning?**

> guidance.txt does not define severity tiers — every stated restriction reads as an unconditional "must be denied," i.e. hard block only; no soft-block/redirect behavior is described.

| Level | Examples |
|-------|----------|
| Hard block | Unknown role; guest calling search_car_price/get_vehicles_by_type; disallowed vehicle_type per role; disallowed brand per role; empty/whitespace brand_name; unrecognized vehicle_type value |
| Soft block with redirect | None defined in guidance.txt |

[derived from guidance.txt]

---

**Q22. Do you need to log which rule was violated, or just that a
request was denied? Does an existing violation-code scheme need to be
reused (e.g. codes already emitted by the calling application or by
another policy)?**

> No pre-existing violation-code scheme is defined in guidance.txt, system_vars.json, or the source files — the prior policy iteration used descriptive `deny` message strings rather than a coded scheme (e.g. `"user_role X is not permitted to call tool Y"`), not formal codes.
>
> | Code | Meaning |
> |------|---------|
> | (none — no pre-existing scheme) | — |

[derived from guidance.txt]

---

## Confidence breakdown

- `[derived from guidance.txt]`: 16
- `[derived from architecture]`: 6
- `[inferred — low confidence]`: 2
- Blank: 0
