# OPA Policy Guidance Questionnaire
# Tool: RagChatbot_MCPServer

Fill in each answer based on your tool and agent. You do not need to
know OPA or security to complete this — just describe how your tool
works and who should be able to use it.

---

## Section 1: Tool Identity

**Q1. What is the tool name and what does it do in one sentence?**

> Tool name: `RagChatbot_MCPServer` (11 active tools)
> An HR assistant MCP server that exposes tools for viewing and exporting team compensation data, sending emails and compensation reports, ticketing, purchasing, product returns, and work-policy queries — dispatched by an LLM agent over SSE. [derived from architecture]

---

**Q2. What external systems does it call?**

> - **In-memory HR/compensation database** (`data_sources/hr_database.py`): read-only; no authentication; returns employee records, compensation, and sensitive PII including SSN, home_address, bank_account, personal_email. [derived from architecture]
> - **RAG pipeline** (`rag_pipeline.py`): reads a preloaded PDF (HuggingFace BAAI/bge-small-en-v1.5 embeddings); no authentication; read-only. [derived from architecture]
> - **OPA server** (`http://localhost:8181`): policy evaluation; HTTP POST; currently wired into `opa_client.py` but all `@policy_check` decorators are commented out — not actively called at runtime. [derived from architecture]

---

**Q3. Does it read data, write data, or both?**

> Both. Most tools read HR/compensation data or RAG content. `purchase` / `return_product` simulate write operations (approval responses). `send_email` and `email_compensation_report` simulate sending (echo-only; no real SMTP). `create_ticket` / `submit_ticket` simulate ticket creation. [derived from architecture]

---

**Q4. What are its parameters? For each: name, type, required or optional, what counts as a valid value?**

| Parameter | Type | Required | Valid values | Tool |
|-----------|------|----------|--------------|------|
| `ticket_content` | string | Yes | Any text | `create_ticket`, `submit_ticket` |
| `recipient_email` | string | Yes | Email address string | `send_email` |
| `subject` | string | Yes | Any text | `send_email` |
| `body` | string | Yes | Any text | `send_email` |
| `email_content` | string | Yes | Any text | `send_email` |
| `attached_file` | string | Yes | Filename string | `send_email` |
| `data` | string | Yes | Any text/data content | `export_content_as_file` |
| `file_name` | string | Yes | Filename string | `export_content_as_file` |
| `question` | string | Yes | Any text | `ask_for_workpolicy` |
| `amount` | integer | Yes | Dollar amount (positive integer) | `return_product`, `purchase` |
| `product_name` | string | Yes | Product name string | `return_product`, `purchase` |
| `department` | string | Yes | One of: IT, HR, Sales, Finance, Legal, Operations, Marketing | `view_team_compensation` |
| `select_fields` | list[str] or null | No (default: null = all fields) | Subset of: employee_name, title, department, level, hire_date, base_salary, bonus_target, actual_bonus_2024, performance_rating, next_review_date, ssn, personal_email, home_address, emergency_contact, bank_account, healthcare_plan, healthcare_id, stock_grant_value, benefits_value, total_compensation | `view_team_compensation` |
| `id` | string or null | No (default: null) | Employee ID string | `view_team_compensation`, `export_compensation_data` |
| `time_range` | string | No (default: "last_quarter") | "last_quarter", "current_year", "last_year" | `view_team_compensation` |
| `format` | string | No (default: "JSON") | "JSON", "CSV" | `view_team_compensation` |
| `include_benefits` | boolean | No (default: true) | true / false | `view_team_compensation` |
| `select_fields` | list[str] or null | No (default: null = all fields) | Subset of: employee_id, name, title, level, current_salary, total_comp_2024, performance_rating, salary_history, bonus_history — **NOTE: body also adds ssn, personal_email, home_address, bank_account from sensitive_data unconditionally before filtering** | `export_compensation_data` |
| `format` | string | No (default: "CSV") | "CSV", "PDF", "JSON" | `export_compensation_data` |
| `time_range` | string | No (default: "last_quarter") | Any string (echoed only) | `export_compensation_data` |
| `export_type` | string | No (default: "aggregated") | "aggregated", "detailed" | `export_compensation_data` |
| `business_justification` | string | No (default: "") | Any text (echoed only) | `export_compensation_data` |
| `external_sharing` | boolean | No (default: false) | true / false | `export_compensation_data`, `email_compensation_report` |
| `destination` | string | Yes | Email address string | `email_compensation_report` |
| `report_data` | string | Yes | Any text | `email_compensation_report` |
| `encryption_required` | boolean | No (default: true) | true / false — **NOTE: echoed only; no encryption applied** | `email_compensation_report` |
| `category` | string or null | No (default: null) | Any string — **NOTE: immediately overwritten by `category = None` in function body; Ignored** | `purchase` |
| `justification` | string or null | No (default: null) | Any text — **NOTE: ignored in function body; never read after declaration** | `purchase` |

[derived from architecture] [derived from tool_definitions.json]

---

## Section 2: Who Uses It

**Q5. What are the types of users? List every role.**

> - `employee` — Regular employee; limited access; cannot view or export team compensation data, cannot buy products ≥$200 without manager approval. [derived from guidance.txt, system_vars.json]
> - `manager` — Manager with elevated access; can view and export their team's compensation data (excluding sensitive PII fields), can buy products under $1,000, can send compensation reports internally. [derived from guidance.txt, system_vars.json]
>
> **Runtime note:** `set_user_role` is currently commented out in `mcp_server.py`. The process-global `current_user_context` is initialised at server start with `user_role = "user"` and cannot be changed at runtime. All OPA role rules will evaluate against `"user"` (not `"employee"`) until the server is updated. `system_vars.json` declares `roles: ["employee", "manager"]` as the intended vocabulary. [derived from architecture]

---

**Q6. Are those roles verified by your system, or supplied by the user themselves?**

> Self-reported / unverifiable at runtime. The role is initialized at server start as `"user"` via `set_user_context("mcp_user", "user")`. No caller can change it since `set_user_role` is commented out. The `user_profile.user_role` in POST /chat requests is embedded in the system prompt but does NOT write to `current_user_context` — it only influences LLM reasoning. [derived from architecture]

---

**Q7. Is there a user ID? Where does it come from?**

> Yes — `current_user_context["user_id"]` set to `"mcp_user"` at server start. It does not distinguish between callers. `system_vars.json` declares `id: "Bob"` as the representative value. [derived from architecture, system_vars.json]

---

**Q8. Can a user belong to multiple roles at once?**

> No. `current_user_context["user_role"]` is a single string. The `roles` array in the universal schema is populated as a single-element list `[user_role]`. [derived from architecture]

---

## Section 3: What Each Role Is Allowed To Do

**Q9. For each role, which tools are they allowed to use and with what conditions or scope restrictions?**

| Tool | employee | manager | guidance.txt rule |
|------|----------|---------|-------------------|
| `view_team_compensation` | Blocked | Allowed — manager's own team only; must exclude SSN, home_address, bank_account, personal_email, emergency_contact from select_fields; select_fields must be specified | Rules 1, 2, 3 |
| `export_compensation_data` | Blocked | Allowed — CSV, PDF, JSON formats; select_fields must be specified; must not include PII fields; external_sharing must be false | Rules 4, 5 |
| `email_compensation_report` | Blocked (implied by Rules 1–5) | Allowed — @ibm.com domain only; external_sharing must be false | Rules 6, 7, 8 |
| `send_email` | Allowed — non-compensation content only; no blocked domains | Allowed — same restrictions | Rules 6, 7, 8 |
| `create_ticket` | Allowed | Allowed | (no explicit rule — general access implied) |
| `submit_ticket` | Allowed | Allowed | (no explicit rule — general access implied) |
| `purchase` | Allowed — amount < $200 only; ≥$200 requires manager approval | Allowed — amount < $1,000 | Rules 9, 10 |
| `return_product` | Allowed | Allowed | (no explicit rule — general access implied) |
| `ask_for_workpolicy` | Allowed | Allowed | (no explicit rule — general access implied) |
| `get_w2_form` | Allowed | Allowed | (no explicit rule — general access implied) |
| `export_content_as_file` | Allowed | Allowed | (no explicit rule — general access implied) |

[derived from guidance.txt] [derived from architecture]

---

**Q10. Are there topics, values, or parameter combinations some roles can use that others cannot?**

> - **Compensation fields** (`select_fields`): Managers may not request ssn, home_address, bank_account, personal_email, emergency_contact. These must be excluded regardless of role. [derived from guidance.txt Rule 3]
> - **Export formats**: Managers can export CSV, PDF, JSON. Employees cannot export at all. [derived from guidance.txt Rule 4]
> - **External sharing**: No role may set `external_sharing=true` for compensation or salary data. [derived from guidance.txt Rules 5, 7]
> - **Email domain**: No role may send compensation data to non-@ibm.com addresses. No role may send any email to gmail.com, yahoo.com, hotmail.com, outlook.com, personal.com. [derived from guidance.txt Rules 7, 8]
> - **Purchase amounts**: Employees capped at $200 (with approval for ≥$200); managers capped at $1,000. [derived from guidance.txt Rules 9, 10]

---

**Q11. Are there roles that have no restrictions?**

> No — both roles have restrictions. Managers are restricted from sensitive PII fields, external sharing, blocked email domains, and purchases ≥$1,000. [derived from guidance.txt]

---

## Section 4: Hard Limits

**Q12. Are there parameter values that should always be blocked for everyone, regardless of role?**

> - `external_sharing=true` on `export_compensation_data` or `email_compensation_report`: always blocked. [derived from guidance.txt Rules 5, 7]
> - `recipient_email` or `destination` domain in {gmail.com, yahoo.com, hotmail.com, outlook.com, personal.com}: always blocked for `send_email` and `email_compensation_report`. [derived from guidance.txt Rule 8]
> - `destination` not ending in `@ibm.com` for `email_compensation_report`: always blocked. [derived from guidance.txt Rule 7]
> - `select_fields` containing any of {ssn, home_address, bank_account, personal_email, emergency_contact} for `view_team_compensation`: always blocked. [derived from guidance.txt Rule 3]
> - `select_fields` containing any PII fields for `export_compensation_data`: always blocked. Note: `export_compensation_data` body adds ssn, personal_email, home_address, bank_account unconditionally before `project_record()` filtering — OPA must block these field names in `select_fields` AND block calls where `select_fields` is null/absent. [derived from guidance.txt Rule 3, derived from architecture]

---

**Q13. Is there a maximum value for any numeric parameter that no role can exceed?**

> - `purchase.amount`: hard cap $1,000 for managers; hard cap $200 for employees (above $200 requires approval). No role may purchase ≥$1,000 (managers) or ≥$200 without approval (employees). [derived from guidance.txt Rules 9, 10]

---

**Q13b. Are there approval paths — actions allowed conditionally when an approval field is set?**

> | Parameter condition | Approval field | guidance.txt rule |
> |---------------------|----------------|-------------------|
> | `purchase.amount >= 200` and `input.extensions.subject.roles` includes `"employee"` | `input.extensions.subject.approval == "true"` | Rule 9 |
>
> **Critical note:** `system_vars.json` declares `approval: "true|false"` as a session variable, but no tool or application component currently populates `input.extensions.subject.approval`. Any OPA rule checking this field will always deny employee purchases ≥$200 until the application is updated. [derived from guidance.txt Rule 9, system_vars.json, architecture]

---

**Q14. Are there keywords or inputs that must always be rejected?**

> The following phrases, matched case-insensitively as substrings in any free-text argument (`ticket_content`, `question`, `email_content`, `body`, `report_data`, `justification`), must always be blocked: [derived from guidance.txt Rules 11–14]
> - `"ignore all policies"`
> - `"bypass security"`
> - `"override all policies"`
> - `"show all SSN data"`

---

## Section 5: Volume and Rate Limits

**Q15. Is there a maximum number of times this tool can be called in a single conversation session?**

> No rate limits are defined in guidance.txt or the source code. `current_user_context` tracks `daily_ticket_count` but it is never incremented or checked in any tool body. [derived from architecture]

| Role | Max calls per session |
|------|-----------------------|
| employee | No limit defined |
| manager | No limit defined |

---

**Q16. Who keeps track of how many times the tool has been called — your app, or should the policy enforce it?**

> Currently no tracking occurs. `daily_ticket_count` exists in `current_user_context` but is never updated. If rate limiting were desired, the policy would need to read a counter from session state, but no such field is reliably populated today. [derived from architecture]

---

## Section 6: Response Filtering

**Q17. After the tool returns results, does anything need to be hidden, flagged, or categorised before the user sees it?**

> Yes. Both `view_team_compensation` and `export_compensation_data` include sensitive PII (SSN, home_address, bank_account, personal_email, emergency_contact) in the candidate record unconditionally before applying `select_fields` filtering. If `select_fields` is absent or null, all fields including PII are returned. Additionally, `export_compensation_data` adds PII from `comp_db.sensitive_data` unconditionally in its body — even if those fields are not in the docstring's available-field list. OPA must block calls where `select_fields` is null/absent or contains forbidden field names — post-execution filtering via `project_record()` is too late. [derived from guidance.txt Rule 3, architecture]

---

**Q18. Are there fields in the response that should be suppressed for certain roles?**

> For all roles on `view_team_compensation` and `export_compensation_data`: [derived from guidance.txt Rule 3]
> - `ssn`
> - `home_address`
> - `bank_account`
> - `personal_email`
> - `emergency_contact`
> - `tax_id` — referenced in guidance.txt Rule 3 but NOT declared as a field in any tool's parameters. A rule blocking `tax_id` in `select_fields` can never fire (no tool accepts it). [derived from architecture — Undeclared Fields table]
>
> These must be excluded from `select_fields` (or the call blocked when `select_fields` is null/absent).

---

**Q19. Are there conditions on a result that determine whether it is "actionable"?**

> For `purchase`: the tool always returns an approval confirmation string regardless of role or amount — the business logic does not enforce purchase thresholds. The policy must intercept before execution to enforce Rules 9–10. [derived from architecture]

---

## Section 7: Violations

**Q20. Should a blocked request be silently rejected, or should the user receive an explanation?**

> The existing `get_universal_denial_message()` in `opa_client.py` returns emoji-prefixed denial strings (e.g. `"🚫 Access to compensation data is restricted."`). The agent's system prompt instructs it to relay denial messages verbatim. The policy should return `allow=false`; the application layer provides the user-facing message. [derived from architecture]

---

**Q21. Are there different severity levels — hard block vs. warning?**

> | Level | Examples |
> |-------|----------|
> | Hard block | Employee accessing `view_team_compensation`; `external_sharing=true`; blocked email domain; blocked keyword phrase; purchase over role cap |
> | Soft block / log only | No current examples — `set_user_role` is commented out, removing the only soft-block candidate from the previous analysis |

[derived from guidance.txt, architecture]

---

**Q22. Do you need to log which rule was violated, or just that a request was denied? Does an existing violation-code scheme need to be reused?**

> No pre-existing violation-code scheme exists in the application that must be reused. Violation codes should be generated in Step D alongside the rules they attach to. [derived from architecture]
>
> | Code | Meaning |
> |------|---------|
> | (none pre-existing) | — |

---

## Confidence breakdown

- `[derived from guidance.txt]`: 28 answers / sub-answers
- `[derived from architecture]`: 20 answers / sub-answers
- `[derived from tool_definitions.json]` / `[derived from system_vars.json]`: 4 answers
- `[inferred — low confidence]`: 0
- Blank: 0
