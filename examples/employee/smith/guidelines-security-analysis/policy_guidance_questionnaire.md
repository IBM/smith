# OPA Policy Guidance Questionnaire
# Tool: employee (Enterprise Employee Hub — 29 tools)

---

## Section 1: Tool Identity

**Q1. What is the tool name and what does it do in one sentence?**

> Tool name: `enterprise-employee-hub` — 29 tools across 6 domains managing employee records, org chart, departments, sensitive personal records (passport, visa, emergency contact, bank account), country holidays, and time-off (allotments, requests, and balances) against a shared SQLite database. [derived from architecture]

---

**Q2. What external systems does it call?**

> - **SQLite database** (`employee_hub.db`) — read/write; all employee, personal, leave, and holiday data. [derived from architecture]
> - **LLM inference** (OpenAI-compatible endpoint, default local Ollama): read-only, no external auth relevant to policy. [derived from architecture]
> - No external APIs or network services beyond the LLM. [derived from architecture]

---

**Q3. Does it read data, write data, or both?**

> Both. Read tools: `get_employee`, `list_employees`, `get_manager`, `get_direct_reports`, `get_reporting_chain`, `get_department`, `list_departments`, `get_passport`, `get_visa`, `get_emergency_contact`, `get_bank_account`, `get_leave_allotments`, `get_time_off_request`, `list_time_off_requests`, `get_leave_balance`, `list_holidays`. Write/mutate tools: `add_employee`, `update_employee`, `add_department`, `update_department`, `set_passport`, `update_passport`, `set_visa`, `update_visa`, `set_emergency_contact`, `update_emergency_contact`, `set_bank_account`, `update_bank_account`, `set_leave_allotment`, `create_time_off_request`, `update_time_off_status`, `add_holiday`, `delete_holiday`. [derived from architecture]

---

**Q4. What are its parameters? (key parameters only — see `tool_definitions.json` for full list)**

| Parameter | Tools | Type | Required | Valid values |
|-----------|-------|------|----------|--------------|
| `user_id` | most tools | int | varies | target employee numeric ID |
| `salary` | `add_employee`, `update_employee` | float | No | must be > 0 |
| `email` | `add_employee`, `update_employee` | string | varies | must match org domain |
| `organization` | `add_employee`, `update_employee` | string | No | `IBM Corporation`, `Red Hat`, `Kyndryl` |
| `department_id` | `add_employee`, `update_employee`, `list_employees` | int | No | valid dept id |
| `manager_id` | `add_employee`, `update_employee`, `list_employees` | int | No | valid employee id |
| `home_address`, `country_code` | `add_employee`, `update_employee` | string | varies | — |
| `expiry_date`, `issue_date` | passport/visa tools | string | No | YYYY-MM-DD |
| `start_date`, `end_date` | `create_time_off_request` | string | Yes | YYYY-MM-DD |
| `leave_type` | `create_time_off_request`, `set_leave_allotment` | string | Yes | `Vacation`, `Sick Leave`, `Maternity`, `Paternity`, `Jury Duty`, `Unpaid` |
| `status` | `update_time_off_status` | string | Yes | `Pending`, `Approved`, `Denied` |
| `annual_days` | `set_leave_allotment` | int | No | null = untracked |
| `country_code` | holiday tools | string | Yes | ISO country code |
| `holiday_id` | `delete_holiday` | int | Yes | — |
| `request_id` | `update_time_off_status`, `get_time_off_request` | int | Yes | — |

> [derived from architecture] — confirmed against `tool_definitions.json` and `server.py`

---

## Section 2: Who Uses It

**Q5. What are the types of users? List every role.**

> Users are identified by `department` (their organizational unit):
> - `Corporate Leadership` — executives; general access implied.
> - `Engineering` — engineers; general access.
> - `Product` — product staff; general access.
> - `HR` — HR staff; privileged — may view/edit all employee data, add employees, manage departments, holidays, and leave allotments.
> - `Finance` — finance staff; general access.
>
> Functional roles derived from `guidance.txt`:
> - **Employee** (any department) — may view/edit only their own data; may create time-off for themselves.
> - **Manager** — an employee whose `user_id` appears as another employee's `manager_id` in the DB; may view direct reports' data.
> - **HR** — `department == "HR"`.
>
> [derived from guidance.txt + architecture]

---

**Q6. Are those roles verified by your system, or supplied by the user themselves?**

> **Self-reported** — `department`, `organization`, `user_id`, and `user_name` all come from the caller's `user_profile` JSON body field, which is injected into the system prompt verbatim. There is no authentication or cryptographic verification anywhere in this system. OPA enforces what the caller claims. [derived from architecture]

---

**Q7. Is there a user ID? Where does it come from?**

> Yes — `input.extensions.subject.user_id` (integer). Comes from the caller's `user_profile.user_id`. Self-reported; not verified. Used by OPA to check self-service ownership (`args.user_id == subject.user_id`). [derived from architecture]

---

**Q8. Can a user belong to multiple roles at once?**

> `department` is a single string (not an array) per `system_vars.json`. A user has exactly one department. The Manager role is structural (DB-derived), not a `department` value. OPA cannot enforce the Manager role directly; it would need a DB lookup. [derived from architecture]

---

## Section 3: What Each Role Is Allowed To Do

**Q9. For each role, which tools are they allowed to use and with what conditions?**

| Tool group | Employee (own data) | HR | Manager (direct reports) | guidance.txt rule |
|---|---|---|---|---|
| `get_employee`, `list_employees` | Allowed (own `user_id` only) | Allowed (all) | Allowed (direct reports) | Data Access |
| `update_employee` (non-salary fields) | Allowed (own record) | Allowed (all) | Allowed (direct reports) | Data Access |
| `update_employee` (salary) | Blocked | Allowed | Allowed (direct reports only) | Data Access |
| `add_employee` | Blocked | Allowed | Blocked | Data Access |
| `get_passport`, `get_visa`, `get_emergency_contact`, `get_bank_account` | Allowed (own) | Allowed (all) | Allowed (direct reports) | Data Access |
| `set_passport`, `update_passport`, `set_visa`, `update_visa`, `set_emergency_contact`, `update_emergency_contact`, `set_bank_account`, `update_bank_account` | Allowed (own) | Allowed (all) | [inferred — low confidence; guidance says manager views but is silent on edits] | Data Access |
| `get_manager`, `get_direct_reports`, `get_reporting_chain` | Allowed | Allowed | Allowed | Administrative Actions |
| `get_department`, `list_departments` | Allowed | Allowed | Allowed | Administrative Actions |
| `add_department`, `update_department` | Blocked | Allowed | Blocked | Administrative Actions |
| `add_holiday`, `delete_holiday` | Blocked | Allowed | Blocked | Administrative Actions |
| `list_holidays` | Allowed | Allowed | Allowed | Administrative Actions |
| `set_leave_allotment` | Blocked | Allowed | Blocked | Administrative Actions |
| `get_leave_allotments`, `get_leave_balance`, `get_time_off_request`, `list_time_off_requests` | Allowed (own) | Allowed (all) | Allowed (direct reports) | Time Off and Leave |
| `create_time_off_request` | Allowed (own `user_id` only) | [inferred — low confidence] | [inferred — low confidence] | Time Off and Leave |
| `update_time_off_status` | Allowed (set to `Pending` only) | Allowed (any status) | Allowed (`Approved` or `Denied` for direct reports) | Time Off and Leave |

---

**Q10. Are there topics, values, or parameter combinations some roles can use that others cannot?**

> - `salary` update: HR or direct manager only. [derived from guidance.txt]
> - `include_ssn` equivalent: passport, visa, bank account — sensitive PII; same ownership rules as above.
> - `email` field: must match organization's corporate domain when `organization` is also provided. [derived from guidance.txt]
> - `salary` value: must be > 0 for all roles. [derived from guidance.txt]
> - `expiry_date` must be > `issue_date` when both provided in the same call. [derived from guidance.txt]
> - `start_date`/`end_date` span: ≤ 90 calendar days. [derived from guidance.txt]
> - `leave_type` for `create_time_off_request`: must be from fixed enum. [derived from architecture]
> - `status` for `update_time_off_status`: employee → `Pending` only; manager → `Approved`/`Denied`; HR → any. [derived from guidance.txt]

---

**Q11. Are there roles that have no restrictions?**

> HR has the fewest restrictions — may view/edit all employee data, add employees, manage departments/holidays/leave allotments, and set any time-off status. However, HR is still subject to data integrity rules (positive salary, email domain, date ordering). [derived from guidance.txt]

---

## Section 4: Hard Limits

**Q12. Are there parameter values that should always be blocked for everyone, regardless of role?**

> - `salary ≤ 0` — blocked for all (must be positive). [derived from guidance.txt]
> - Email domain mismatch: `args.email` not matching `args.organization`'s domain when both provided in the same call. [derived from guidance.txt]
> - `issue_date >= expiry_date` when both provided in the same call (passport/visa). [derived from guidance.txt]
> - `end_date - start_date > 90 days` for `create_time_off_request`. [derived from guidance.txt]

---

**Q13. Is there a maximum value for any numeric parameter that no role can exceed?**

> `create_time_off_request`: `end_date` − `start_date` ≤ 90 calendar days (computed, not a single integer field). [derived from guidance.txt]

---

**Q13b. Are there approval paths?**

> `update_time_off_status`: the allowed values for `status` depend on who is calling (HR / manager / employee). This is a role-conditional rule, not a simple approval flag. [derived from guidance.txt]

---

**Q14. Are there keywords or inputs that must always be rejected?**

> No free-text keyword blocks identified. The booking / frequent-flyer rule in `guidance.txt` does not apply to any of the 29 Employee Hub tools — it is out of scope. [derived from guidance.txt]

---

## Section 5: Volume and Rate Limits

**Q15. Is there a maximum number of times this tool can be called in a single session?**

> No rate limits defined. [inferred — low confidence]

---

**Q16. Who keeps track of call counts?**

> No call-count field in `system_vars.json`. [inferred — low confidence]

---

## Section 6: Response Filtering

**Q17. After the tool returns results, does anything need to be hidden?**

> All personal record data (passport, visa, bank account, emergency contact, home address, salary) should only be returned for the acting user's own records or, for HR/managers, for records they are authorized to view. However, response-side filtering is out of OPA scope — OPA blocks the tool call pre-execution. [derived from architecture]

---

**Q18. Are there fields in the response that should be suppressed for certain roles?**

> Not OPA-enforceable (response filtering is post-execution). [derived from architecture]

---

**Q19. Are there conditions on a result that determine whether it is "actionable"?**

> No post-execution actionability checks needed — OPA blocks pre-execution. [derived from architecture]

---

## Section 7: Violations

**Q20. Should a blocked request be silently rejected or explained?**

> The agent is instructed: "if a tool returns an 'error' key, explain it to the user." OPA denials return an error envelope. [derived from architecture]

---

**Q21. Are there different severity levels — hard block vs. warning?**

> | Level | Examples |
> |-------|----------|
> | Hard block | All identified policy violations — no soft-block paths. |
> | Soft block | None identified. |

---

**Q22. Does an existing violation-code scheme need to be reused?**

> No pre-existing OPA violation-code scheme for this agent. New codes minted in Step D.
>
> | Code | Meaning |
> |------|---------|
> | (none pre-existing) | — |

---

**Confidence breakdown:** `[derived from guidance.txt]`: 18 | `[derived from architecture]`: 14 | `[inferred — low confidence]`: 4 | blank: 0
