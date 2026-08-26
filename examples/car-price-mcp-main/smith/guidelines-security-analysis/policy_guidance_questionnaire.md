# OPA Policy Guidance Questionnaire
# Tool: car-price-mcp-main (get_car_brands / search_car_price / get_vehicles_by_type)

Fill in each answer based on your tool and agent. You do not need to
know OPA or security to complete this — just describe how your tool
works and who should be able to use it.

---

## Section 1: Tool Identity

**Q1. What is the tool name and what does it do in one sentence?**

> Tool name: `get_car_brands` — returns a list of up to 20 car brands from the Brazilian FIPE vehicle reference price database, grouped alphabetically. [derived from architecture]
>
> Tool name: `search_car_price` — looks up car models and current market prices from FIPE for a given `brand_name`. [derived from architecture]
>
> Tool name: `get_vehicles_by_type` — returns up to 15 brands for the specified vehicle category (`carros`, `motos`, or `caminhoes`) from FIPE. [derived from architecture]

---

**Q2. What external systems does it call?**

> - **FIPE API** (`https://parallelum.com.br/fipe/api/v1/`): HTTP GET, read-only, no authentication. Called by all three tools via `app.py`. [derived from architecture]

---

**Q3. Does it read data, write data, or both?**

> Read only — all three tools fetch data from FIPE and return it; no writes. [derived from architecture]

---

**Q4. What are its parameters? For each: name, type, required or optional, what counts as a valid value?**

| Parameter | Type | Required | Valid values |
|-----------|------|----------|--------------|
| *(none)* — `get_car_brands` | — | — | No parameters |
| `brand_name` — `search_car_price` | string | Yes | Exact Title Case FIPE brand spelling (e.g. `"Toyota"`, `"Mercedes-Benz"`); empty or whitespace-only denied for all roles; role-specific allow/block lists apply |
| `vehicle_type` — `get_vehicles_by_type` | string | No (default `"carros"`) | Exactly one of: `"carros"`, `"cars"`, `"motos"`, `"motorcycles"`, `"caminhoes"`, `"trucks"` (exact, case-sensitive); any other value denied for all roles |

> [derived from guidance.txt] — confirmed against `tool_definitions.json` and `architecture.md`

---

## Section 2: Who Uses It

**Q5. What are the types of users? List every role.**

> - `fleet_manager` — manages a vehicle fleet; restricted to truck-related vehicle types and truck-brand price lookups.
> - `consumer` — individual buyer; restricted to car vehicle types; unrestricted brand search.
> - `journalist` — media professional; restricted to car vehicle types and domestic-market brands only.
> - `analyst` — data/market analyst; unrestricted vehicle type and brand access.
> - `guest` — unauthenticated or anonymous caller; may only call `get_car_brands`.
>
> [derived from guidance.txt]

---

**Q6. Are those roles verified by your system, or supplied by the user themselves?**

> **Self-reported** — `user_role` comes from the caller's `user_profile` JSON body field, injected verbatim into the system prompt. No authentication or cryptographic verification. [derived from architecture]

---

**Q7. Is there a user ID? Where does it come from?**

> `user_name` is in `system_vars.json` but is not used for access control. No authenticated user ID for authorization purposes. [derived from architecture]

---

**Q8. Can a user belong to multiple roles at once?**

> `user_role` is a single string in `system_vars.json` (not an array). A caller has exactly one role at a time. [derived from architecture]

---

## Section 3: What Each Role Is Allowed To Do

**Q9. For each role, which tools are they allowed to use and with what conditions?**

| Tool | `fleet_manager` | `consumer` | `journalist` | `analyst` | `guest` | guidance.txt rule |
|------|-----------------|------------|--------------|-----------|---------|-------------------|
| `get_car_brands` | Allowed | Allowed | Allowed | Allowed | Allowed | "Tool Access by Role" section |
| `search_car_price` | Allowed; `brand_name` must be in truck-brand allowlist | Allowed; any brand | Allowed; `brand_name` must be in domestic-market allowlist | Allowed; any brand | **Blocked** | "Tool Access by Role" + "Brand Restrictions" sections |
| `get_vehicles_by_type` | Allowed; `vehicle_type` must be `"caminhoes"` or `"trucks"` only | Allowed; `vehicle_type` must be `"carros"` or `"cars"` only | Allowed; `vehicle_type` must be `"carros"` or `"cars"` only | Allowed; any recognized `vehicle_type` | **Blocked** | "Tool Access by Role" + "Vehicle Type Restrictions" sections |

> [derived from guidance.txt]

---

**Q10. Are there topics, values, or parameter combinations some roles can use that others cannot?**

> **`vehicle_type` for `get_vehicles_by_type`:**
> - `fleet_manager`: only `"caminhoes"` or `"trucks"`; `"carros"`, `"cars"`, `"motos"`, `"motorcycles"` denied. [derived from guidance.txt]
> - `consumer`: only `"carros"` or `"cars"`; `"motos"`, `"motorcycles"`, `"caminhoes"`, `"trucks"` denied. [derived from guidance.txt]
> - `journalist`: only `"carros"` or `"cars"`; `"motos"`, `"motorcycles"`, `"caminhoes"`, `"trucks"` denied. [derived from guidance.txt]
> - `analyst`: any of the six recognized values. [derived from guidance.txt]
>
> **`brand_name` for `search_car_price`:**
> - `fleet_manager`: only `"Scania"`, `"Volvo"`, `"Mercedes-Benz"`, `"MAN"`, `"DAF"`, `"Iveco"`, `"Ford"`, `"Volkswagen"`. [derived from guidance.txt]
> - `journalist`: only `"Fiat"`, `"Chevrolet"`, `"Volkswagen"`, `"Hyundai"`, `"Toyota"`, `"Renault"`, `"Honda"`, `"Nissan"`, `"Jeep"`, `"Peugeot"`, `"Citroën"`, `"Caoa Chery"`. [derived from guidance.txt]
> - `consumer` and `analyst`: any brand, no restriction. [derived from guidance.txt]
> - `"Mercedes-Benz"` and `"Volkswagen"` appear on both the `fleet_manager` allowlist and the `journalist` allowlist; each role is evaluated independently. [derived from guidance.txt]

---

**Q11. Are there roles that have no restrictions?**

> `analyst` — may call all three tools with any recognized `vehicle_type` and any brand. Still subject to the universal rules: `vehicle_type` must be one of the six recognized values (exact, case-sensitive), and `brand_name` must be non-empty/non-whitespace Title Case. [derived from guidance.txt]

---

## Section 4: Hard Limits

**Q12. Are there parameter values that should always be blocked for everyone, regardless of role?**

> **`vehicle_type`:** Any value not in the set `{"carros", "cars", "motos", "motorcycles", "caminhoes", "trucks"}` is denied for every role, including `analyst`. Values must match exactly (case-sensitive); `"Caminhoes"`, `"CARROS"`, etc. are denied. [derived from guidance.txt]
>
> **`brand_name`:** An empty string or whitespace-only value is denied for all roles. [derived from guidance.txt]
>
> **`brand_name` matching:** `brand_name` is compared against allow/block lists by exact, case-sensitive string equality. Partial or differently-cased names (e.g. `"mercedes"`, `"volvo"`) are denied. [derived from guidance.txt]
>
> **`vehicle_type` fallback:** The backend (`app.py`) silently coerces unrecognized `vehicle_type` values to `"carros"`; the policy must reject them before they reach the tool. [derived from architecture]

---

**Q13. Is there a maximum value for any numeric parameter that no role can exceed?**

> None — no numeric parameters exist in any of the three tools. [derived from tool_definitions.json]

---

**Q13b. Are there approval paths?**

> None. [derived from guidance.txt]

---

**Q14. Are there keywords or inputs that must always be rejected?**

> - Empty or whitespace-only `brand_name` for `search_car_price` — denied for all roles. [derived from guidance.txt]
> - Any `vehicle_type` value outside the recognized set — denied for all roles. [derived from guidance.txt]
> - For role-specific brand blocks: luxury/imported brands (`"BMW"`, `"Audi"`, `"Porsche"`, `"Jaguar"`, `"Land Rover"`, `"Lexus"`, `"Maserati"`, `"Ferrari"`, `"Lamborghini"`, `"Bentley"`, `"Rolls-Royce"`, `"Mini"`, `"Alfa Romeo"`) are denied for `journalist`. [derived from guidance.txt]

---

## Section 5: Volume and Rate Limits

**Q15. Is there a maximum number of times this tool can be called in a single session?**

> No session rate limit is specified in guidance.txt or system_vars.json. [derived from guidance.txt]

---

**Q16. Who keeps track of how many times the tool has been called?**

> Not applicable — no rate limit is defined. [derived from guidance.txt]

---

## Section 6: Response Filtering

**Q17. After the tool returns results, does anything need to be hidden, flagged, or categorised before the user sees it?**

> No response filtering is specified. FIPE results are returned as-is. [derived from guidance.txt]

---

**Q18. Are there fields in the response that should be suppressed for certain roles?**

> None specified. [derived from guidance.txt]

---

**Q19. Are there conditions on a result that determine whether it is "actionable"?**

> No post-execution actionability checks. OPA blocks pre-execution. [derived from architecture]

---

## Section 7: Violations

**Q20. Should a blocked request be silently rejected, or should the user receive an explanation?**

> Not explicitly specified in guidance.txt. OPA denials will surface as a denial response through the agent. [inferred — low confidence]

---

**Q21. Are there different severity levels — hard block vs. warning?**

> | Level | Examples |
> |-------|----------|
> | Hard block | All identified violations — guest calling `search_car_price`, `fleet_manager` requesting `vehicle_type = "carros"`, `journalist` searching `"BMW"`, unrecognized `vehicle_type` for any role, empty `brand_name` for any role, unknown `user_role`. |
> | Soft block | None specified. |
>
> [derived from guidance.txt]

---

**Q22. Do you need to log which rule was violated, or just that a request was denied? Does an existing violation-code scheme need to be reused?**

> No pre-existing OPA violation-code scheme for this agent. New codes will be minted in Step D.
>
> | Code | Meaning |
> |------|---------|
> | (none pre-existing) | — |

---

**Confidence breakdown:** `[derived from guidance.txt]`: 18 | `[derived from architecture]`: 7 | `[inferred — low confidence]`: 1 (Q20) | blank: 0
