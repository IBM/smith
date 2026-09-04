# OPA Policy Guidance Questionnaire
# Tool: car-price-mcp

Fill in each answer based on your tool and agent. You do not need to
know OPA or security to complete this — just describe how your tool
works and who should be able to use it.

---

## Section 1: Tool Identity

**Q1. What is the tool name and what does it do in one sentence?**

> Tool names: `get_car_brands`, `search_car_price`, `get_vehicles_by_type`
> A FIPE-backed vehicle pricing MCP server that lets callers list car brands, look up models and prices by brand, and browse brands by vehicle type (cars/motorcycles/trucks). [derived from architecture]

---

**Q2. What external systems does it call?**

> `https://parallelum.com.br/fipe/api/v1/...` — public, unauthenticated, read-only FIPE Brazilian vehicle price API (HTTPS GET requests). [derived from architecture]

---

**Q3. Does it read data, write data, or both?**

> Read only — all three tools issue GET requests to the FIPE API and return formatted text; no writes or mutations anywhere in the tool implementation. [derived from architecture]

---

**Q4. What are its parameters? For each: name, type, required or optional, what counts as a valid value?**

| Parameter | Tool | Type | Required | Valid values |
|-----------|------|------|----------|--------------|
| `brand_name` | `search_car_price` | string | Yes | Non-empty, non-whitespace string. Must be the canonical FIPE brand name in Title Case (e.g. `"Toyota"`, `"Mercedes-Benz"`); partial or differently-cased names are not evaluated against allow/block lists and are denied. Empty or whitespace-only values are denied for all roles. [derived from guidance.txt] |
| `vehicle_type` | `get_vehicles_by_type` | string (optional, default `"carros"`) | No | Exactly one of: `"carros"`, `"cars"`, `"motos"`, `"motorcycles"`, `"caminhoes"`, `"trucks"` — case-sensitive exact match. Any other value (including different casing) is denied. The backend coerces unrecognized types to `"carros"` but the policy must reject them before that fallback runs. [derived from guidance.txt] |
| (none) | `get_car_brands` | — | — | No parameters; access is controlled by role only. [derived from architecture] |

---

## Section 2: Who Uses It

**Q5. What are the types of users? List every role.**

> - `fleet_manager` — manages a vehicle fleet; may call all three tools; restricted to truck-relevant brands and truck vehicle types [derived from guidance.txt]
> - `consumer` — individual buyer; may call all three tools; restricted to car vehicle types; may search any brand [derived from guidance.txt]
> - `journalist` — automotive media; may call all three tools; restricted to car vehicle types; may only search domestic-market brands [derived from guidance.txt]
> - `analyst` — market researcher; may call all three tools; may use any vehicle type or any brand without restriction [derived from guidance.txt]
> - `guest` — unauthenticated or low-trust caller; may only call `get_car_brands`; `search_car_price` and `get_vehicles_by_type` are denied [derived from guidance.txt]

---

**Q6. Are those roles verified by your system, or supplied by the user themselves?**

> Self-reported — `user_role` is passed as part of the `user_profile` dict in the HTTP POST request body; no authentication mechanism verifies it anywhere in `agent.py`. [derived from architecture]

---

**Q7. Is there a user ID? Where does it come from?**

> `user_name` is present in `system_vars.json` and is set as part of `user_profile` in the HTTP request. It is self-reported; there is no verified user ID. [derived from architecture]

---

**Q8. Can a user belong to multiple roles at once?**

> Yes — `user_role` in `system_vars.json` is declared as an array of possible role strings (`["fleet_manager", "consumer", "journalist", "analyst", "guest"]`), implying a single user may carry multiple role labels. `guidance.txt` evaluates each role's restrictions independently: e.g. a `fleet_manager` is allowed `"Mercedes-Benz"` while a `journalist` is denied it, so each role is checked independently, not as a union. [derived from guidance.txt + system_vars.json]

---

## Section 3: What Each Role Is Allowed To Do

**Q9. For each role, which tools are they allowed to use and with what conditions or scope restrictions?**

| Tool | fleet_manager | consumer | journalist | analyst | guest | guidance.txt rule |
|------|---------------|----------|------------|---------|-------|-------------------|
| `get_car_brands` | Allowed | Allowed | Allowed | Allowed | Allowed | Tool Access by Role |
| `search_car_price` | Allowed — truck-relevant brands only: Scania, Volvo, Mercedes-Benz, MAN, DAF, Iveco, Ford, Volkswagen | Allowed — any brand | Allowed — domestic-market brands only (Fiat, Chevrolet, Volkswagen, Hyundai, Toyota, Renault, Honda, Nissan, Jeep, Peugeot, Citroën, Caoa Chery); luxury/imported denied | Allowed — any brand | Denied | Tool Access + Brand Restrictions |
| `get_vehicles_by_type` | Allowed — `"caminhoes"` or `"trucks"` only | Allowed — `"carros"` or `"cars"` only | Allowed — `"carros"` or `"cars"` only | Allowed — any recognised value | Denied | Tool Access + Vehicle Type Restrictions |

---

**Q10. Are there topics, values, or parameter combinations some roles can use that others cannot?**

> Yes, two axes:
>
> **`brand_name` (on `search_car_price`):**
> - `fleet_manager`: only truck-relevant brands (Scania, Volvo, Mercedes-Benz, MAN, DAF, Iveco, Ford, Volkswagen)
> - `journalist`: only domestic-market brands (Fiat, Chevrolet, Volkswagen, Hyundai, Toyota, Renault, Honda, Nissan, Jeep, Peugeot, Citroën, Caoa Chery); luxury/imported brands denied
> - `consumer`, `analyst`: any brand allowed (no restriction)
>
> **`vehicle_type` (on `get_vehicles_by_type`):**
> - `fleet_manager`: only `"caminhoes"` / `"trucks"`; cars and motorcycles denied
> - `consumer`, `journalist`: only `"carros"` / `"cars"`; motorcycles and trucks denied
> - `analyst`: any of the six recognised values
>
> [derived from guidance.txt]

---

**Q11. Are there roles that have no restrictions?**

> `analyst` has no brand restrictions and no vehicle type restrictions for `search_car_price` and `get_vehicles_by_type`; they may call all three tools freely. `consumer` has no brand restriction (any brand). [derived from guidance.txt]

---

## Section 4: Hard Limits

**Q12. Are there parameter values that should always be blocked for everyone, regardless of role?**

> Yes:
> - Any `brand_name` that is empty or whitespace-only → denied for all roles.
> - Any `vehicle_type` value not in the recognised set (`"carros"`, `"cars"`, `"motos"`, `"motorcycles"`, `"caminhoes"`, `"trucks"`) → denied for all roles (including `analyst`). Different casing (e.g. `"Caminhoes"`) is explicitly denied.
> - Any call from an `unknown` role (not one of the five defined roles) → denied for every tool, including `get_car_brands`. [derived from guidance.txt]

---

**Q13. Is there a maximum value for any numeric parameter that no role can exceed?**

> None — no numeric parameters in any of the three tools. [derived from tool_definitions.json]

---

**Q13b. Are there approval paths — actions allowed conditionally when an approval field is set?**

> None — `guidance.txt` defines no conditional approval fields. [derived from guidance.txt]

---

**Q14. Are there keywords or inputs that must always be rejected?**

> Effectively yes via the exact-match allow/deny lists:
> - `brand_name`: fleet_managers and journalists have explicit allow-lists; anything outside them is denied (block-by-default for those roles). Denied luxury/imported brands for journalists include BMW, Mercedes-Benz, Audi, Porsche, Jaguar, Land Rover, Lexus, Maserati, Ferrari, Lamborghini, Bentley, Rolls-Royce, Mini, Alfa Romeo.
> - `vehicle_type`: any value not in the six-element recognised set is a hard reject for all roles.
> - Empty/whitespace `brand_name`: always rejected.
> [derived from guidance.txt]

---

## Section 5: Volume and Rate Limits

**Q15. Is there a maximum number of times this tool can be called in a single conversation session?**

> None defined in `guidance.txt`. [derived from guidance.txt]

---

**Q16. Who keeps track of how many times the tool has been called — your app, or should the policy enforce it?**

> Not applicable — no session call limit defined. [derived from guidance.txt]

---

## Section 6: Response Filtering

**Q17. After the tool returns results, does anything need to be hidden, flagged, or categorised before the user sees it?**

> None specified in `guidance.txt`. [derived from guidance.txt]

---

**Q18. Are there fields in the response that should be suppressed for certain roles?**

> None specified in `guidance.txt`. [derived from guidance.txt]

---

**Q19. Are there conditions on a result that determine whether it is "actionable"?**

> None specified in `guidance.txt`. [derived from guidance.txt]

---

## Section 7: Violations

**Q20. Should a blocked request be silently rejected, or should the user receive an explanation?**

> `guidance.txt` does not specify violation messaging. Based on architecture.md's pattern (the existing server.py returns a string on soft-reject rather than an exception), violations should return an explanatory deny message identifying the violated rule. [inferred — low confidence]

---

**Q21. Are there different severity levels — hard block vs. warning?**

> All blocks in `guidance.txt` are framed as hard denials ("must be denied"). No warnings or soft blocks are defined. [derived from guidance.txt]

---

**Q22. Do you need to log which rule was violated, or just that a request was denied? Does an existing violation-code scheme need to be reused?**

> No pre-existing violation-code scheme is defined in `guidance.txt` or any other source file. Log the specific rule violated (e.g. ROLE_BLOCKED, BRAND_BLOCKED, VEHICLE_TYPE_BLOCKED) following the same pattern used in the `call-for-papers-mcp` example. [inferred — low confidence]
>
> No pre-existing violation-code table to carry forward.

---

*Confidence summary: 18 answers [derived from guidance.txt], 6 answers [derived from architecture], 2 answers [inferred — low confidence] (Q20, Q22 — violation messaging and logging scheme), 0 blank.*
