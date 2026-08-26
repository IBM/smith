# OPA Policy Guidance Questionnaire
# Tool: hr-agent (HR Copilot — all 6 tools)

Fill in each answer based on your tool and agent. You do not need to
know OPA or security to complete this — just describe how your tool
works and who should be able to use it.

---

## Section 1: Tool Identity

**Q1. What is the tool name and what does it do in one sentence?**

> Tool name: `hr-agent` (exposes 6 tools via a single MCP server)
>
> - `get_compensation` — returns an employee's salary, bonus, department, title, and optionally SSN. [derived from architecture]
> - `display_compensation` — returns a band-only compensation summary (no salary figures). [derived from architecture]
> - `get_directory` — lists the employee directory, optionally filtered by department. [derived from architecture]
> - `send_email` — sends an email (simulated). [derived from architecture]
> - `search_repos` — searches internal GitHub Enterprise repositories by name substring and/or visibility. [derived from architecture]
> - `adjust_compensation` — adjusts an employee's salary by a dollar amount; amounts over $10,000 require prior manager approval. [derived from architecture]

---

**Q2. What external systems does it call?**

> - **Ollama LLM inference** (direct, not proxied): `host.docker.internal:11434` — read-only inference, no auth in demo config. [derived from architecture]
> - **HR MCP server** (:9100): JSON-RPC over HTTP, identity carried via `X-User-Token` + `Authorization` headers, governed by cpex sidecar forward proxy. [derived from architecture]
> - **GitHub Enterprise** (simulated in server.py fixtures): repository search, read-only. [derived from architecture]
> - **Email service** (simulated in server.py): send-only. [derived from architecture]
> - **Keycloak** (via cpex RFC 8693 delegation): handled by sidecar, not OPA-visible. [derived from architecture]

---

**Q3. Does it read data, write data, or both?**

> Both.
> - Reads: `get_compensation`, `display_compensation`, `get_directory`, `search_repos`.
> - Writes: `send_email` (creates a sent-mail record), `adjust_compensation` (mutates salary). [derived from architecture]

---

**Q4. What are its parameters? For each: name, type, required or optional, what counts as a valid value?**

| Parameter | Tool | Type | Required | Valid values |
|-----------|------|------|----------|--------------|
| `employee_id` | `get_compensation`, `display_compensation`, `adjust_compensation` | string | Yes | Employee identifier, e.g. `EMP-001234` |
| `include_ssn` | `get_compensation` | boolean | No (default: false) | `true` only when user explicitly asks for SSN |
| `department` | `get_directory` | string | No (default: `""`) | Department name or empty for all |
| `to` | `send_email` | string | Yes | Email address |
| `subject` | `send_email` | string | Yes | Any string |
| `body` | `send_email` | string | Yes | Any string |
| `repo_name` | `search_repos` | string | No (default: `""`) | Substring filter |
| `visibility` | `search_repos` | string | Yes | `internal`, `public`, or `external` |
| `amount` | `adjust_compensation` | integer | Yes | Dollar amount; approval required if > $10,000 |

> [derived from architecture] — confirmed against `tool_definitions.json` and `agent.py TOOLS`

---

## Section 2: Who Uses It

**Q5. What are the types of users? List every role.**

> - `hr` — HR staff; compensation access and adjustments.
> - `engineer` — Engineering staff; repo search.
> - `marketing` — Marketing staff; general access.
> - `finance` — Finance staff; general access.
> - `platform` — Platform/SRE staff; general access.
> - `security` — Security team; internal and external repo search.
>
> [derived from architecture] — from `system_vars.json` `roles` array.

---

**Q6. Are those roles verified by your system, or supplied by the user themselves?**

> **Verified** — roles are extracted from the cryptographically signed user JWT (`X-User-Token`) by the cpex sidecar and surfaced as `input.extensions.subject.roles`. [derived from architecture]

---

**Q7. Is there a user ID? Where does it come from?**

> Identity is role + permission based from the JWT. No explicit `user_id` field in `system_vars.json`. [derived from architecture]

---

**Q8. Can a user belong to multiple roles at once?**

> Yes — `input.extensions.subject.roles` is an array. A caller may hold `["hr", "finance"]` simultaneously. [derived from architecture]

---

## Section 3: What Each Role Is Allowed To Do

**Q9. For each role, which tools are they allowed to use and with what conditions or scope restrictions?**

| Tool | `hr` | `engineer` | `marketing` | `finance` | `platform` | `security` | guidance source |
|------|------|------------|-------------|-----------|------------|------------|-----------------|
| `get_compensation` | Allowed | Blocked | Blocked | Blocked | Blocked | Blocked | `whole_guidance.txt` rule 1 |
| `display_compensation` | Allowed | Blocked | Blocked | Blocked | Blocked | Blocked | [inferred — low confidence; band-only view of compensation, same scope implied] |
| `get_directory` | Allowed | Allowed | Allowed | Allowed | Allowed | Allowed | [inferred — low confidence; no rule restricts directory access] |
| `send_email` | Allowed | Allowed | Allowed | Allowed | Allowed | Allowed | [inferred — low confidence; no role restriction, but SSN-in-body must be blocked] |
| `search_repos` | Blocked | Allowed (internal/public only) | Blocked | Blocked | Blocked | Allowed (internal + external) | `whole_guidance.txt` rules 3–4 |
| `adjust_compensation` | Allowed (≤$10,000 w/o approval; >$10,000 requires `has_approval == "true"`) | Blocked | Blocked | Blocked | Blocked | Blocked | `whole_guidance.txt` rules 6–7 |

---

**Q10. Are there topics, values, or parameter combinations some roles can use that others cannot?**

> - `include_ssn=true` on `get_compensation`: only callers with `view_ssn` in `permissions`. [derived from `whole_guidance.txt` rule 2]
> - `visibility=external` on `search_repos`: only `security` role. [derived from `whole_guidance.txt` rule 4]
> - `amount > 10000` on `adjust_compensation`: requires `has_approval == "true"`. [derived from `whole_guidance.txt` rule 7]
> - Email body/subject containing SSN pattern: blocked for all roles. [derived from `whole_guidance.txt` rule 5]

---

**Q11. Are there roles that have no restrictions?**

> No — every role has at least one restriction. [derived from `whole_guidance.txt`]

---

## Section 4: Hard Limits

**Q12. Are there parameter values that should always be blocked for everyone, regardless of role?**

> - Email body/subject containing SSN pattern `\d{3}-\d{2}-\d{4}` — blocked for all roles. [derived from `whole_guidance.txt` rule 5]

---

**Q13. Is there a maximum value for any numeric parameter that no role can exceed?**

> No absolute hard cap. `adjust_compensation.amount` has a conditional threshold: > $10,000 requires `has_approval == "true"`; with approval the amount is unbounded. [derived from `whole_guidance.txt` rules 6–7]

---

**Q13b. Are there approval paths — actions allowed conditionally when an approval field is set?**

> | Parameter condition | Approval field | guidance source |
> |---------------------|----------------|-----------------|
> | `input.name == "adjust_compensation"` AND `input.arguments.amount > 10000` | `input.extensions.subject.has_approval == "true"` | `whole_guidance.txt` rule 7 |

---

**Q14. Are there keywords or inputs that must always be rejected?**

> SSN-pattern content (`\d{3}-\d{2}-\d{4}`) in `send_email.body` or `send_email.subject`. [derived from `whole_guidance.txt` rule 5]

---

## Section 5: Volume and Rate Limits

**Q15. Is there a maximum number of times this tool can be called in a single conversation session?**

> No rate limit specified. [inferred — low confidence]

---

**Q16. Who keeps track of how many times the tool has been called?**

> No call-count tracking field in `system_vars.json`. OPA cannot enforce rate limits without a structured counter field. [inferred — low confidence]

---

## Section 6: Response Filtering

**Q17. After the tool returns results, does anything need to be hidden before the user sees it?**

> `get_compensation` returns `ssn` if `include_ssn=true`. For callers without `view_ssn`, SSN redaction is performed by the cpex sidecar — out of OPA scope. [derived from architecture]

---

**Q18. Are there fields in the response that should be suppressed for certain roles?**

> - `ssn` in `get_compensation` response: redacted by cpex sidecar for callers without `view_ssn`. Out of OPA scope. [derived from architecture]

---

**Q19. Are there conditions on a result that determine whether it is "actionable"?**

> No post-execution actionability check needed — OPA blocks pre-execution. [derived from architecture]

---

## Section 7: Violations

**Q20. Should a blocked request be silently rejected, or should the user receive an explanation?**

> JSON-RPC error envelope returned; agent relays politely without revealing the internal violation code. [derived from architecture]

---

**Q21. Are there different severity levels — hard block vs. warning?**

> | Level | Examples |
> |-------|----------|
> | Hard block | All policy violations — no soft-block paths identified. |
> | Soft block with redirect | None. |

---

**Q22. Do you need to log which rule was violated? Does an existing violation-code scheme need to be reused?**

> No pre-existing OPA violation-code scheme documented for this agent. New codes will be minted in Step D.
>
> | Code | Meaning |
> |------|---------|
> | (none pre-existing) | — |

---

**Confidence breakdown:** `[derived from guidance.txt / whole_guidance.txt]`: 11 | `[derived from architecture]`: 18 | `[inferred — low confidence]`: 5 | blank: 0
