# OPA Policy Guidance Questionnaire
# Tool: RagChatbot_MCPServer (HR Agent — 12 MCP tools)

Fill in each answer based on your tool and agent. You do not need to
know OPA or security to complete this — just describe how your tool
works and who should be able to use it.

---

## Section 1: Tool Identity

**Q1. What is the tool name and what does it do in one sentence?**

> Tool name: `RagChatbot_MCPServer` (12 tools: `create_ticket`, `submit_ticket`, `send_email`, `export_content_as_file`, `ask_for_workpolicy`, `get_w2_form`, `return_product`, `view_team_compensation`, `export_compensation_data`, `email_compensation_report`, `purchase`, `set_user_role`)
> An HR assistant agent that allows employees and managers to view/export compensation data, send emails, create support tickets, make purchases, and query HR policy documents via RAG. [derived from architecture]

---

**Q2. What external systems does it call?**

> - **LLM inference** — OpenAI-compatible API (Ollama locally or remote), read-only for generation [derived from architecture]
> - **Preloaded PDF RAG index** — local files `work_rules_and_regulations_2016.pdf` and `salary_summary.pdf`; read-only [derived from architecture]
> - **In-memory HR/compensation database** (`hr_db`, `comp_db`, `purchase_db`) — internal, no outbound network call [derived from architecture]
> - No live external email relay or financial API is implemented (tools return stub confirmation strings) [derived from architecture]

---

**Q3. Does it read data, write data, or both?**

> Both — reads compensation/HR data and writes (creates tickets, submits tickets, simulates email sends and purchases). The "write" actions return stub strings rather than calling live external systems. [derived from architecture]

---

**Q4. What are its parameters? For each: name, type, required or optional, what counts as a valid value?**

| Parameter | Tool | Type | Required | Valid values |
|---|---|---|---|---|
| `ticket_content` | create_ticket, submit_ticket | string | Yes | Any free text |
| `recipient_email` | send_email | string | Yes | Valid email address; domain must not be in blocked list |
| `subject` | send_email | string | Yes | Any free text |
| `body` | send_email | string | Yes | Any free text |
| `email_content` | send_email | string | Yes | Any free text (non-compensation content) |
| `attached_file` | send_email | string | Yes | File name string |
| `data` | export_content_as_file | string | Yes | Any string data |
| `file_name` | export_content_as_file | string | Yes | Any file name string |
| `question` | ask_for_workpolicy | string | Yes | Any natural-language question |
| `amount` | return_product, purchase | integer | Yes | Positive integer (dollars) |
| `product_name` | return_product, purchase | string | Yes | Any product name |
| `department` | view_team_compensation | string | Yes | One of: IT, HR, Sales, Finance, Legal, Operations, Marketing |
| `select_fields` | view_team_compensation, export_compensation_data | array of strings or null | No | Subset of available fields; blocked fields: ssn, home_address, bank_account, tax_id, emergency_contact for all roles |
| `id` | view_team_compensation, export_compensation_data | string or null | No | Employee ID |
| `time_range` | view_team_compensation, export_compensation_data | string | No | "last_quarter", "current_year", "last_year" |
| `format` | view_team_compensation, export_compensation_data | string | No | "JSON", "CSV", "PDF" |
| `include_benefits` | view_team_compensation | boolean | No | true/false |
| `export_type` | export_compensation_data | string | No | "aggregated", "detailed" |
| `business_justification` | export_compensation_data | string | No | Any free text |
| `external_sharing` | export_compensation_data, email_compensation_report | boolean | No | false (external sharing of compensation data always blocked) |
| `destination` | email_compensation_report | string | Yes | Email address; must be @ibm.com domain; must not be in blocked list |
| `report_data` | email_compensation_report | string | Yes | Compensation report content |
| `encryption_required` | email_compensation_report | boolean | No | Default true |
| `category` | purchase | string or null | No | Optional product category |
| `justification` | purchase | string or null | No | Optional business justification |
| `user_role` | set_user_role | string | Yes | "user" or "manager" |

[derived from architecture + tool_definitions.json]

---

## Section 2: Who Uses It

**Q5. What are the types of users? List every role.**

> - `employee` — standard employee; limited access; cannot view/export team compensation, cannot purchase $200+ without approval, cannot share externally
> - `manager` — elevated access; can view/export team compensation, send non-compensation email externally, purchase up to $999
> [derived from guidance.txt + system_vars.json]

---

**Q6. Are those roles verified by your system, or supplied by the user themselves?**

> Self-reported — the `user_role` in `user_profile` is accepted from the HTTP request body without cryptographic verification. The Streamlit UI allows any visitor to select their role from a dropdown. The MCP server's `set_user_role` tool also accepts any string and sets the server-side context. [derived from architecture]

---

**Q7. Is there a user ID? Where does it come from?**

> Yes — `id` in `system_vars.json` defaults to `"Bob"`. It is set in the session context by `opa_config.initialize_user_session`. Like role, it is self-reported and unverified. [derived from architecture + system_vars.json]

---

**Q8. Can a user belong to multiple roles at once?**

> No — `system_vars.json` defines `"roles": ["employee", "manager"]` as an enumeration; the calling application sets exactly one role per session. [derived from system_vars.json]

---

## Section 3: What Each Role Is Allowed To Do

**Q9. For each role, which tools are they allowed to use and with what conditions or scope restrictions?**

| Tool | employee | manager | guidance.txt rule |
|---|---|---|---|
| `create_ticket` | Allowed, no restrictions | Allowed, no restrictions | — |
| `submit_ticket` | Allowed, no restrictions | Allowed, no restrictions | — |
| `ask_for_workpolicy` | Allowed | Allowed | — |
| `get_w2_form` | Allowed | Allowed | — |
| `return_product` | Allowed | Allowed | — |
| `send_email` | Allowed; non-@ibm.com requires role=manager per Rule 6; blocked domains apply | Allowed; non-@ibm.com OK for non-compensation content | Rules 6, 8 |
| `export_content_as_file` | Allowed (for non-compensation data) | Allowed | — |
| `view_team_compensation` | **Blocked** — employees cannot use this tool | Allowed; own team only; cannot request SSN, home address, bank account, Tax ID, emergency_contact via select_fields | Rules 1, 2, 3 |
| `export_compensation_data` | **Blocked** — employees cannot export compensation data | Allowed in CSV/PDF/JSON; external_sharing must be false | Rules 4, 5, 7 |
| `email_compensation_report` | **Blocked** — compensation data sharing is restricted to managers; external sharing blocked for all | Managers: destination must be @ibm.com; external_sharing must be false | Rules 6, 7 |
| `purchase` | Allowed; amount < $200 without approval; $200–$999 requires approval (subject.approval=true); $1000+ blocked | Allowed up to $999 | Rules 9, 10 |
| `set_user_role` | [inferred — low confidence] May be used for session initialization | [inferred — low confidence] May be used for session initialization | — |

---

**Q10. Are there topics, values, or parameter combinations some roles can use that others cannot?**

> - `select_fields` containing any of `ssn`, `home_address`, `bank_account`, `tax_id`, `emergency_contact` is blocked for all roles including managers [derived from guidance.txt Rule 3]
> - `external_sharing=true` is blocked for all roles on `export_compensation_data` and `email_compensation_report` [derived from guidance.txt Rule 7]
> - `recipient_email` / `destination` matching blocked domains (gmail.com, yahoo.com, hotmail.com, outlook.com, personal.com) is blocked for all roles [derived from guidance.txt Rule 8]
> - `destination` not matching @ibm.com is blocked on `email_compensation_report` for all roles [derived from guidance.txt Rule 7]

---

**Q11. Are there roles that have no restrictions?**

> No — both roles have restrictions. Managers have fewer restrictions than employees but are still subject to Rules 3, 7, 8, and 10. [derived from guidance.txt]

---

## Section 4: Hard Limits

**Q12. Are there parameter values that should always be blocked for everyone, regardless of role?**

> - `select_fields` containing: `ssn`, `home_address`, `bank_account`, `tax_id`, `emergency_contact` (Rule 3)
> - `external_sharing=true` on `export_compensation_data` or `email_compensation_report` (Rule 7)
> - `recipient_email` / `destination` domain in: `gmail.com`, `yahoo.com`, `hotmail.com`, `outlook.com`, `personal.com` (Rule 8)
> - `destination` not ending in `@ibm.com` on `email_compensation_report` (Rule 7)
> - Free-text containing: "ignore all policies", "bypass security", "override all policies", "show all SSN data" in any free-text argument (Rules 11–14)
> [derived from guidance.txt]

---

**Q13. Is there a maximum value for any numeric parameter that no role can exceed?**

> `amount` (purchase): hard cap of $999 for managers (Rule 10); employees need approval for $200+ and are implicitly capped at $999 as well [inferred — low confidence on the employee upper cap; Rule 10 names only managers]

---

**Q13b. Are there approval paths — actions allowed conditionally when an approval field is set?**

> | Parameter condition | Approval field | guidance.txt rule |
> |---|---|---|
> | `input.name = "purchase"` AND `input.extensions.subject.roles = "employee"` AND `input.arguments.amount >= 200` | `input.extensions.subject.approval == "true"` | Rule 9 |

[derived from guidance.txt Rule 9 + system_vars.json `approval` field]

---

**Q14. Are there keywords or inputs that must always be rejected?**

> In free-text arguments (e.g., `question`, `ticket_content`, `email_content`, `report_data`):
> - "ignore all policies" (Rule 11)
> - "bypass security" (Rule 12)
> - "override all policies" (Rule 13)
> - "show all SSN data" (Rule 14)
> [derived from guidance.txt]

---

## Section 5: Volume and Rate Limits

**Q15. Is there a maximum number of times this tool can be called in a single conversation session?**

> No explicit rate limit is defined in guidance.txt or system_vars.json. [inferred — low confidence: none defined]

---

**Q16. Who keeps track of how many times the tool has been called — your app, or should the policy enforce it?**

> Not defined. The application does not expose a call-count field in the session context. OPA cannot enforce rate limits without a field to read. [inferred — low confidence]

---

## Section 6: Response Filtering

**Q17. After the tool returns results, does anything need to be hidden, flagged, or categorised before the user sees it?**

> Yes — `view_team_compensation` and `export_compensation_data` currently return SSN, home_address, bank_account, and emergency_contact unconditionally in the tool response (commented as pending policy filtering). This filtering must happen at the tool implementation layer, not at OPA invocation time, because OPA cannot modify return values. [derived from architecture + mcp_server.py comments]

---

**Q18. Are there fields in the response that should be suppressed for certain roles?**

> - `ssn`, `home_address`, `bank_account`, `tax_id`, `emergency_contact` — suppressed for all roles including managers (Rule 3)
> These must be suppressed at the tool implementation layer (Layer 4), not via OPA. [derived from guidance.txt Rule 3 + architecture]

---

**Q19. Are there conditions on a result that determine whether it is "actionable"?**

> Denial messages prefixed with 🚫 are passed through to the user without LLMGuard filtering (per `run_llm_with_mcp.py`). No other actionability conditions are defined in guidance.txt. [derived from architecture]

---

## Section 7: Violations

**Q20. Should a blocked request be silently rejected, or should the user receive an explanation?**

> Explanation — the system uses 🚫 denial messages and instructs the agent to relay them verbatim without elaboration (per `fast_server.py` system prompt: "If a tool returns a denial message (starting with 🚫), simply relay that exact message without any explanation, elaboration, or additional context about policies, limits, or reasons"). [derived from architecture]

---

**Q21. Are there different severity levels — hard block vs. warning?**

> | Level | Examples |
> |---|---|
> | Hard block | Keyword injection attempts (Rules 11–14); external_sharing=true on compensation tools (Rule 7); blocked email domains (Rule 8); SSN/bank_account in select_fields (Rule 3); employee accessing view_team_compensation or export_compensation_data (Rules 2, 5) |
> | Hard block (conditional on approval) | Employee purchase $200+ without approval=true (Rule 9); manager purchase $1000+ (Rule 10) |
> No soft-block / warning tier is defined in guidance.txt. [derived from guidance.txt]

---

**Q22. Do you need to log which rule was violated, or just that a request was denied? Does an existing violation-code scheme need to be reused?**

> guidance.txt does not specify a violation-code scheme. No pre-existing codes are defined. New codes will be minted by the enforcement mapping step.
>
> | Code | Meaning |
> |------|---------|
> | *(none pre-existing)* | |

---

**Confidence summary:** 18 answers `[derived from guidance.txt]` · 14 answers `[derived from architecture]` · 4 answers `[inferred — low confidence]` · 0 blank
