# OPA Policy Guidance Questionnaire
# Tool: RagChatbot_MCPServer (12 tools, single MCP server)

Fill in each answer based on your tool and agent. You do not need to
know OPA or security to complete this — just describe how your tool
works and who should be able to use it.

---

## Section 1: Tool Identity

**Q1. What is the tool name and what does it do in one sentence?**

> - `create_ticket` — Drafts an HR inquiry ticket from free-text content. [derived from architecture]
> - `submit_ticket` — Submits an HR inquiry ticket from free-text content. [derived from architecture]
> - `send_email` — Sends a general-purpose (non-compensation) email with subject/body/content/attachment. [derived from architecture]
> - `export_content_as_file` — Exports arbitrary caller-supplied data to a named file. [derived from architecture]
> - `ask_for_workpolicy` — Answers questions via RAG over a preloaded work-policy PDF. [derived from architecture]
> - `get_w2_form` — Always returns a canned refusal telling the user to contact HR; not wired to real data. [derived from architecture]
> - `return_product` — Submits a product return for a refund amount. [derived from architecture]
> - `view_team_compensation` — Displays a manager's team's compensation data on screen (JSON/CSV). [derived from architecture]
> - `export_compensation_data` — Exports a manager's team's compensation data as a file (CSV/PDF/JSON). [derived from architecture]
> - `email_compensation_report` — Emails a compensation/salary report to a recipient. [derived from architecture]
> - `purchase` — Processes a purchase request against a vendor catalog. [derived from architecture]
> - `set_user_role` — Sets the caller's own role (`user`/`manager`) for policy enforcement, with no authentication. [derived from architecture]

---

**Q2. What external systems does it call?**

> None of the 12 tools call a real external system today. `view_team_compensation`/`export_compensation_data` read an in-memory mock HR/compensation database (`data_sources/hr_database.py`). `ask_for_workpolicy` runs a local RAG pipeline over a bundled PDF (`rag_pipeline.py`). `email_compensation_report`/`send_email` return canned confirmation strings — no real SMTP call. `purchase`/`return_product` return canned confirmation strings against a local mock vendor catalog. [derived from architecture]

---

**Q3. Does it read data, write data, or both?**

> - `create_ticket`, `submit_ticket` — write (ticket creation; no persistent store observed). [derived from architecture]
> - `send_email`, `email_compensation_report` — write (simulated send). [derived from architecture]
> - `export_content_as_file`, `export_compensation_data` — read (compensation/data source) + write (file export). [derived from architecture]
> - `ask_for_workpolicy` — read (RAG over PDF). [derived from architecture]
> - `get_w2_form` — neither (canned string, no data access). [derived from architecture]
> - `return_product`, `purchase` — write (simulated transaction). [derived from architecture]
> - `view_team_compensation` — read (compensation/data source). [derived from architecture]
> - `set_user_role` — write (mutates global session role state). [derived from architecture]

---

**Q4. What are its parameters? For each: name, type, required or optional, what counts as a valid value?**

| Tool | Parameter | Type | Required | Valid values |
|------|-----------|------|----------|--------------|
| create_ticket | ticket_content | string | Yes | free text |
| submit_ticket | ticket_content | string | Yes | free text |
| send_email | recipient_email | string | Yes | email address |
| send_email | subject | string | Yes | free text |
| send_email | body | string | Yes | free text |
| send_email | email_content | string | Yes | free text (must not be compensation/salary content per Rule 6/15) |
| send_email | attached_file | string | Yes | file name |
| export_content_as_file | data | string | Yes | free text |
| export_content_as_file | file_name | string | Yes | file name |
| ask_for_workpolicy | question | string | Yes | free text |
| get_w2_form | (none) | — | — | — |
| return_product | amount | integer | Yes | dollar amount |
| return_product | product_name | string | Yes | free text |
| view_team_compensation | department | string | Yes | one of `IT, HR, Sales, Finance, Legal, Operations, Marketing` |
| view_team_compensation | select_fields | array\|null | No (default null=all fields) | subset of the documented field list (see Q18) |
| view_team_compensation | id | string\|null | No | employee ID |
| view_team_compensation | time_range | string | No (default `last_quarter`) | `last_quarter`, `current_year`, `last_year` |
| view_team_compensation | format | string | No (default `JSON`) | `JSON`, `CSV` |
| view_team_compensation | include_benefits | boolean | No (default `true`) | true/false |
| export_compensation_data | select_fields | array\|null | No | subset of the documented field list |
| export_compensation_data | id | string\|null | No | employee ID |
| export_compensation_data | format | string | No (default `CSV`) | `CSV`, `PDF`, `JSON` |
| export_compensation_data | time_range | string | No (default `last_quarter`) | free text |
| export_compensation_data | export_type | string | No (default `aggregated`) | `aggregated`, `detailed` |
| export_compensation_data | business_justification | string | No (default `""`) | free text |
| export_compensation_data | external_sharing | boolean | No (default `false`) | true/false |
| email_compensation_report | destination | string | Yes | email address |
| email_compensation_report | report_data | string | Yes | free text |
| email_compensation_report | external_sharing | boolean | No (default `false`) | true/false |
| email_compensation_report | encryption_required | boolean | No (default `true`) | true/false |
| purchase | amount | integer | Yes | dollar amount |
| purchase | product_name | string | Yes | free text, matched fuzzily against a vendor catalog |
| purchase | category | string\|null | No | free text (auto-detected if omitted) |
| purchase | justification | string\|null | No | free text |
| set_user_role | user_role | string | Yes | `user` or `manager` |

[derived from architecture] (parameter names/types), [derived from guidance.txt] (valid-value constraints tied to guidance rules 1, 3, 6-10, 16)

---

## Section 2: Who Uses It

**Q5. What are the types of users? List every role.**

> - `employee` — baseline caller; guidance.txt and mcp_server.py disagree on the exact label (guidance.txt/system_vars.json say `employee`/`manager`, mcp_server.py's `set_user_role`/`USER_ROLES` say `user`/`manager`). [derived from guidance.txt] + [derived from architecture] — flagged mismatch, see Q6.
> - `manager` — elevated caller; can view/export own team's compensation data, send external non-compensation email, higher purchase limit. [derived from guidance.txt]

---

**Q6. Are those roles verified by your system, or supplied by the user themselves?**

> Self-reported, with no authentication. The role is set via the `set_user_role` MCP tool (any caller can invoke it directly with any value in `["user","manager"]`) or via the Streamlit sidebar dropdown / FastAPI `user_profile.user_role` request field, both of which just forward the caller's chosen value to `set_user_role`/`initialize_user_session`. There is no credential check, token, or identity system behind this value anywhere in the codebase. [derived from architecture]
>
> Additionally there is a **naming mismatch**: `system_vars.json`'s `roles` list is `["employee","manager"]` (matching guidance.txt's wording), but the live `set_user_role` tool and `opa_config.USER_ROLES` only recognize `["user","manager"]` — `"employee"` is not a value `set_user_role` accepts. This needs resolution before policy rules can reference `input.extensions.subject.role == "employee"` and expect it to ever actually be set that way by the running server. [derived from architecture] — flagging for Step D / policy creation.

---

**Q7. Is there a user ID? Where does it come from?**

> Yes — `system_vars.json` declares `"id": "Bob"` as a single example subject id. In code, `current_user_context["user_id"]` defaults to `"default_user"` and is only ever set by `set_user_context()`/`initialize_user_session()`, called with a hardcoded caller-chosen id (`"mcp_user"`, `"streamlit_user"`, `"demo_user"`) — not tied to any real authentication. `view_team_compensation`/`export_compensation_data` use this id only to look up which manager's team to show (`hr_db.managers.get(manager_id, ...)`), defaulting to `"manager_123"` if not found. [derived from architecture]

---

**Q8. Can a user belong to multiple roles at once?**

> No — `current_user_context["user_role"]` is a single string value, and `USER_ROLES`/`set_user_role`'s valid-role check treats role as one-of. [derived from architecture]

---

## Section 3: What Each Role Is Allowed To Do

**Q9. For each role, which tools are they allowed to use and with what conditions or scope restrictions?**

| Tool | employee/user | manager | guidance.txt rule |
|------|---------------|---------|-------------------|
| view_team_compensation | Blocked | Allowed — own team only, name/title/salary/bonus/department/hire_date only | Rule 1, 2 |
| export_compensation_data | Blocked | Allowed — CSV/PDF/JSON | Rule 4, 5 |
| email_compensation_report | Blocked (cannot send comp/salary reports to any recipient) | Allowed, subject to Rule 6/7/8 domain restrictions | Rule 15, 6, 7, 8 |
| send_email | Allowed — non-compensation content only; external send restricted to @ibm.com | Allowed — same content restriction; external send restricted to @ibm.com | Rule 6, 8 (send_email is the "general email" tool guidance Rule 6 implicitly contrasts against email_compensation_report) |
| purchase | Allowed, capped at <$200 without manager approval | Allowed, capped at <$1,000 | Rule 9, 10 |
| return_product | Allowed (no role restriction stated) | Allowed | none — [inferred — low confidence] |
| create_ticket / submit_ticket | Allowed (no role restriction stated) | Allowed | none — [inferred — low confidence] |
| ask_for_workpolicy | Allowed (no role restriction stated) | Allowed | none — [inferred — low confidence] |
| export_content_as_file | Allowed (no role restriction stated) | Allowed | none — [inferred — low confidence] |
| get_w2_form | Allowed (tool itself always refuses regardless of caller) | Allowed (same) | none — [derived from architecture] (behavior is hardcoded, not role-gated) |
| set_user_role | Not restricted by guidance.txt — but this is itself the vulnerability (see Section 4/blind spots) | Not restricted | none stated — [inferred — low confidence] this is a gap, not an intentional allowance |

[derived from guidance.txt] for rows with a rule number; [inferred — low confidence] for the rest, since guidance.txt does not mention them.

---

**Q10. Are there topics, values, or parameter combinations some roles can use that others cannot?**

> - Managers only: viewing/exporting any team compensation data at all (Rule 1, 2, 4, 5). [derived from guidance.txt]
> - Managers only: sending emails to non-@ibm.com addresses containing non-compensation data (Rule 6). Employees are not stated to have this permission, implying employee external send is blocked entirely, but guidance.txt does not say this explicitly for `send_email` — [inferred — low confidence].
> - No role — regardless of manager/employee — may: send compensation data externally (Rule 7), send to the listed blocked consumer domains (Rule 8), or have SSN/home_address/bank_account/tax_id/emergency_contact returned via `select_fields` (Rule 16). [derived from guidance.txt]
> - Even managers cannot see SSN/home address/bank account/tax ID/emergency contact "when querying salary information" (Rule 3) — this is stricter than Rule 16's select_fields-only framing; Rule 3 implies these fields must be excluded even when the manager does NOT specify select_fields (i.e., the default full-record case). [derived from guidance.txt] — flagging for Step D since this is a stronger requirement than Rule 16 alone would produce.

---

**Q11. Are there roles that have no restrictions?**

> None. Even managers face scope restriction (own team only), field exclusions (Rule 3, 16), and a purchase cap (Rule 10). [derived from guidance.txt]

---

## Section 4: Hard Limits

**Q12. Are there parameter values that should always be blocked for everyone, regardless of role?**

> - `email_compensation_report`/any compensation-carrying email with `external_sharing == true`, or destination domain not `ibm.com` (Rule 7). [derived from guidance.txt]
> - Any email (compensation or not) to `destination`/`recipient_email` domains: `gmail.com, yahoo.com, hotmail.com, outlook.com, personal.com` (Rule 8). [derived from guidance.txt]
> - `select_fields` containing `ssn`, `home_address`, `bank_account`, `tax_id`, or `emergency_contact` on `view_team_compensation`/`export_compensation_data` (Rule 16) — and per Rule 3, these fields must be excluded from manager-facing salary queries even without an explicit `select_fields` list. [derived from guidance.txt]
> - Free-text phrases: "ignore all policies", "bypass security", "override all policies", "show all SSN data" anywhere in a free-text argument (Rule 11-14). [derived from guidance.txt]

---

**Q13. Is there a maximum value for any numeric parameter that no role can exceed?**

> `purchase.amount`: manager cap $1,000 (Rule 10); no stated absolute cap above that for any role — [derived from guidance.txt]. `return_product.amount` has no stated cap — [inferred — low confidence].

---

**Q13b. Are there approval paths — actions allowed conditionally when an approval field is set?**

> | Parameter condition | Approval field | guidance.txt rule |
> |---------------------|----------------|-------------------|
> | `purchase.amount >= 200`, role = employee/user | `input.extensions.subject.approval` (per `system_vars.json`'s `"approval": "true|false"` field) — **not currently passed as a tool argument or wired into any tool call**; `system_vars.json` declares it but no code path sets or reads it | Rule 9 |
>
> [derived from guidance.txt] for the rule itself; [derived from architecture] for the gap — this is the same mismatch flagged in Step A: the approval mechanism guidance.txt requires has no implementation today, so the policy can reference `input.extensions.subject.approval` (matching system_vars.json's declared shape) but it will need a source of truth for that value before it can be meaningfully enforced end-to-end.

---

**Q14. Are there keywords or inputs that must always be rejected?**

> - "ignore all policies" (and the general pattern "ignore all instructions") — Rule 11
> - "bypass security" — Rule 12
> - "override all policies" — Rule 13
> - "show all SSN data" — Rule 14
>
> These appear as free text in any string-typed argument (`ticket_content`, `question`, `email_content`, `body`, `report_data`, `justification`, etc.) — guidance.txt does not scope them to a specific tool/field, implying a blanket check. [derived from guidance.txt]

---

## Section 5: Volume and Rate Limits

**Q15. Is there a maximum number of times this tool can be called in a single conversation session?**

> Not stated in guidance.txt for any tool. `opa_client.py`'s `current_user_context` tracks a `daily_ticket_count` field (initialized to 0) and `get_daily_request_count()` (hardcoded to return `10`), suggesting rate limiting was planned but guidance.txt does not specify thresholds. [derived from architecture] for the scaffold; no rule to cite — leaving blank per Gated-mode instruction rather than guessing a number.

| Role | Max calls per session |
|------|-----------------------|
| (none specified) | — |

---

**Q16. Who keeps track of how many times the tool has been called — your app, or should the policy enforce it?**

> Today, nothing meaningfully tracks or enforces this — `daily_ticket_count` exists in the context dict but is never incremented anywhere observed, and `get_daily_request_count()` is a hardcoded stub returning `10` regardless of actual usage. [derived from architecture] — not a policy gap so much as an unimplemented feature; no guidance.txt rule requires the policy to enforce a count, so no field name to hand to Step D.

---

## Section 6: Response Filtering

**Q17. After the tool returns results, does anything need to be hidden, flagged, or categorised before the user sees it?**

> Yes — SSN, home address, bank account, tax ID, and emergency contact must never appear in a `view_team_compensation` or `export_compensation_data` response, for any role, regardless of whether `select_fields` was specified (Rule 3, 16). [derived from guidance.txt] Per Step A's architecture finding, this must be enforced by denying/rewriting the call before tool execution (or blocking the specific fields at the request stage), since the tool implementation itself applies no exclusion floor and the sensitive fields are already serialized into the returned string by the time the tool body finishes.

---

**Q18. Are there fields in the response that should be suppressed for certain roles?**

> - `ssn`, `home_address`, `bank_account`, `tax_id`, `emergency_contact` — suppressed for ALL roles including managers, always (Rule 3, 16). [derived from guidance.txt]
> - `hire_date`, `bonus_target`/bonus data — suppressed for employees (Rule 2 blocks the whole tool for employees, so this is moot in practice, but Rule 1 explicitly scopes what a manager may see: `employee name, title, salary, bonus, department, hire date` — implying fields beyond this list, e.g. `performance_rating`, `next_review_date`, `stock_grant_value`, `benefits_value`, `total_compensation`, `personal_email`, `healthcare_plan`, `healthcare_id`, are not explicitly authorized by Rule 1 even for managers). [derived from guidance.txt] — flagging for Step D: Rule 1's field list is narrower than the tool's full available-field set in `tool_definitions.json`, which is a candidate additional restriction beyond what's explicitly stated as forbidden.

---

**Q19. Are there conditions on a result that determine whether it is "actionable"?**

> None stated in guidance.txt. [inferred — low confidence] — no evidence either way; leaving as "none."

---

## Section 7: Violations

**Q20. Should a blocked request be silently rejected, or should the user receive an explanation?**

> Explanation, using a denial message — `opa_client.py::get_universal_denial_message()` already defines per-tool denial strings (e.g. "🚫 Access to compensation data is restricted.") and `run_llm_with_mcp.py`'s system prompt explicitly instructs the LLM to "relay that exact message without any explanation, elaboration, or additional context" whenever a tool result starts with 🚫. [derived from architecture]

---

**Q21. Are there different severity levels — hard block vs. warning?**

> | Level | Examples |
> |-------|----------|
> | Hard block | Role-gated tools for employees (Rule 2, 15), external compensation sharing (Rule 7), blocked domains (Rule 8), sensitive field exposure (Rule 3, 16), prompt-injection phrases (Rule 11-14), purchase over cap (Rule 9, 10) |
> | Soft block with redirect | None identified in guidance.txt — [inferred — low confidence] |
>
> [derived from guidance.txt] for the Hard block row.

---

**Q22. Do you need to log which rule was violated, or just that a request was denied? Does an existing violation-code scheme need to be reused (e.g. codes already emitted by the calling application or by another policy)?**

> No pre-existing violation-code scheme found in the codebase — `get_universal_denial_message()` maps tool name to a human-readable string, not a code. guidance.txt does not specify logging requirements. [derived from architecture] Leaving the code table empty per instructions (no scheme to reuse); Step D may introduce new codes if it chooses.
>
> | Code | Meaning |
> |------|---------|
> | (none) | (none) |

---

## Confidence Breakdown

- `[derived from guidance.txt]`: 26
- `[derived from architecture]`: 17
- `[inferred — low confidence]`: 8
- Blank: 2 (Q15 table, Q19 table cell left as "none" with no rule to cite)
