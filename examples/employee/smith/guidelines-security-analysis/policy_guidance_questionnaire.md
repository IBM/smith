# Policy Guidance Questionnaire — Enterprise Employee Hub

**Target agent path:** `examples/employee/`
**Generated:** 2026-09-04
**Workflow step:** B — Policy Guidance Questionnaire

---

## Section 1 — System Identity and Scope

**Q1. What is the name and purpose of this MCP server?**
Enterprise Employee Hub. It exposes an SQLite-backed employee directory through 33 MCP tools covering employee records, org chart, departments, personal records (passport, visa, emergency contact, bank account), country holidays, and time-off (allotments, requests, balances).

**Q2. What deployment model is used?**
Single agent (LangGraph ReAct) served over FastAPI at `:9000`. No multi-agent orchestration. The MCP server runs as a subprocess (stdio transport).

**Q3. What is the primary trust boundary at which the OPA policy is enforced?**
Agent → MCP server boundary (pre-execution). The policy intercepts every tool call before the MCP server executes it. This is the **only** access-control enforcement layer; the MCP server performs no authorization.

---

## Section 2 — Actor Identity and Trust Model

**Q4. How is the acting user's identity established?**
Via `user_profile` JSON in the `/chat` and `/extract_tool_call` request bodies. `build_system_prompt()` in `agent.py` embeds these key/values verbatim into the system prompt. There is no cryptographic authentication; all identity claims are self-reported by the caller.

Available subject fields (`input.extensions.subject.*`):
- `user_id` (integer) — maps to `employees.user_id` in DB
- `user_name` (string) — display name
- `department` (one of: Corporate Leadership, Engineering, Product, HR, Finance)
- `organization` (one of: IBM Corporation, Red Hat, Kyndryl)

**Q5. What roles or groups are defined, and how are they determined?**
- **HR** — `input.extensions.subject.department == "HR"`. The only role that gates privileged write operations.
- **Manager** — *not* a declared field in `system_vars.json`. Manager status is inferred from the DB (`employees.manager_id`); it is not available as an OPA-enforceable subject field at invocation time. [inferred — low confidence: manager exception for direct-reports view cannot be enforced at OPA layer]
- **IBM employee** — determined by `input.extensions.subject.organization == "IBM Corporation"`. Cross-user org check (blocking non-IBM from viewing IBM records) requires the target employee's org from the DB — not available in OPA input.

**Q6. What is the threat model for identity claims?**
Since all `input.extensions.subject.*` values are self-reported, any caller can claim any department or organization. A policy relying on these must account for the possibility that a malicious caller claims `department = HR` or `organization = IBM Corporation` falsely. No additional authentication layer exists in the current architecture.

---

## Section 3 — Tool Access Rules

**Q7. Which tools require HR department?**
The following tools may only be invoked by users with `department = HR`:
- `add_employee` — add new employee record
- `add_department` — add department
- `update_department` — update department name/description
- `add_holiday` — add country holiday
- `delete_holiday` — delete holiday
- `set_leave_allotment` — set annual leave allotment

Source: guidance.txt §Administrative Actions.

**Q8. Which tools are read-only and open to any user?**
- `list_employees`, `get_manager`, `get_direct_reports`, `get_reporting_chain`
- `get_department`, `list_departments`
- `list_holidays`

Source: guidance.txt §Administrative Actions ("org chart, department listings, and country holidays may be viewed by any user").

**Q9. Which tools require ownership (target user_id == acting user_id)?**
Ownership check required for:
- Personal-record tools: `get_passport`, `set_passport`, `update_passport`, `get_visa`, `set_visa`, `update_visa`, `get_emergency_contact`, `set_emergency_contact`, `update_emergency_contact`, `get_bank_account`, `set_bank_account`, `update_bank_account`
- Employee-record tools: `get_employee`, `update_employee`
- Leave-view tools: `get_leave_allotments`, `list_time_off_requests`, `get_leave_balance`, `get_time_off_request`
- Time-off creation: `create_time_off_request`

Exception: HR bypasses ownership checks for all of the above.
Exception (blind spot): Direct manager may view direct reports' data — requires DB lookup, not enforceable at OPA.

**Q10. What ownership field is used in tool arguments?**
`input.args.user_id` for all employee/personal/leave tools. The exception is `update_time_off_status` and `get_time_off_request` / `list_time_off_requests` — these use `request_id`, not `user_id` directly.

---

## Section 4 — Data Integrity Rules

**Q11. What constraints apply to salary?**
Salary must be a positive number (greater than zero) when set via `add_employee` or `update_employee`. The constraint applies only when the `salary` argument is present in the call; it is optional.

**Q12. What constraints apply to employee email?**
When `add_employee` or `update_employee` is called with both `email` and `organization` in the same call, the email domain must match the organization's corporate domain:
- `IBM Corporation` → `@ibm.com`
- `Red Hat` → `@redhat.com`
- `Kyndryl` → `@kyndryl.com`

**Q13. What constraints apply to passport and visa dates?**
When both `issue_date` and `expiry_date` are provided in the same call to any of `set_passport`, `update_passport`, `set_visa`, `update_visa`, the issue date must be strictly earlier than the expiry date.

Note: The 6-month expiry rule (expiry must be >6 months from current date) is a blind spot — the current date is not in OPA input. [inferred — low confidence: not enforceable at OPA layer without adding `current_date` to system_vars.json]

---

## Section 5 — Time-Off and Leave Rules

**Q14. Who may create a time-off request?**
Only the acting user for themselves: `input.args.user_id` must equal `input.extensions.subject.user_id`.

**Q15. What is the maximum time-off span?**
A single request may not span more than 90 consecutive calendar days (`end_date` minus `start_date` ≤ 90 days).

**Q16. Who may view leave data?**
Leave allotments, time-off requests, and leave balance may be viewed only by:
- HR (any leave data for any user)
- The employee themselves (`input.args.user_id == input.extensions.subject.user_id`)
- [blind spot] The employee's direct manager — requires DB lookup, not enforceable at OPA

**Q17. Who may change time-off request status?**
- HR may set any status (Pending, Approved, Denied)
- Direct manager may set Approved or Denied [blind spot — DB lookup required; safe default: block all non-HR from Approved/Denied]
- Requesting employee may set only Pending [blind spot — requires mapping request_id to requester user_id; not enforceable at OPA]

OPA-enforceable rule: if `department != HR` and `status` is `Approved` or `Denied`, deny.

**Q18. What leave balance check applies?**
An employee may not create a time-off request unless they have sufficient available balance. [blind spot — balance requires computing annual_days minus used_days from DB; not enforceable at OPA layer without pre-computation]

---

## Section 6 — Administrative and Org-Chart Rules

**Q19. Who may modify departments and holidays?**
Only HR (see Q7). Read access is open to all users.

**Q20. Who may delete employees?**
Not covered by any tool in the current tool_definitions.json — there is no `delete_employee` tool. The guidance.txt mentions explicit confirmation phrasing for user deletion, but this is an agent-layer control, not OPA-enforceable.

**Q21. What cross-organization data restrictions apply?**
Users outside IBM Corporation are prohibited from viewing IBM employee data. [blind spot — the target employee's organization is in the DB, not in input.args.*; requires pre-fetch or DB-layer enforcement]

---

## Section 7 — Agent Behavior Rules

**Q22. Are there agent behavior rules beyond tool access?**
Yes, from guidance.txt:
- DB write confirmation: before any write, agent must list the action and get explicit "yes". [agent-layer gate; not OPA-enforceable]
- Agent makes one tool call at a time. [agent-layer / structured output; not OPA-enforceable]
- Paternity leave approved only if baby details in conversation. [agent-layer gate; not OPA-enforceable]

---

## Section 8 — Full Tool Role-Permission Matrix

| Tool | HR | Own (self) | Direct Manager | Any user |
|---|---|---|---|---|
| `add_employee` | ✓ write | — | — | ✗ |
| `update_employee` | ✓ write | ✓ self only | ✗ (blind spot) | ✗ |
| `get_employee` | ✓ read | ✓ self only | ✗ (blind spot) | ✗ |
| `list_employees` | ✓ | ✓ | ✓ | ✓ (filtered) |
| `get_manager` | ✓ | ✓ | ✓ | ✓ |
| `get_direct_reports` | ✓ | ✓ | ✓ | ✓ |
| `get_reporting_chain` | ✓ | ✓ | ✓ | ✓ |
| `add_department` | ✓ write | — | — | ✗ |
| `update_department` | ✓ write | — | — | ✗ |
| `get_department` | ✓ | ✓ | ✓ | ✓ |
| `list_departments` | ✓ | ✓ | ✓ | ✓ |
| `set_passport` | ✓ write | ✓ self only | ✗ | ✗ |
| `update_passport` | ✓ write | ✓ self only | ✗ | ✗ |
| `get_passport` | ✓ read | ✓ self only | ✗ | ✗ |
| `set_visa` | ✓ write | ✓ self only | ✗ | ✗ |
| `update_visa` | ✓ write | ✓ self only | ✗ | ✗ |
| `get_visa` | ✓ read | ✓ self only | ✗ | ✗ |
| `set_emergency_contact` | ✓ write | ✓ self only | ✗ | ✗ |
| `update_emergency_contact` | ✓ write | ✓ self only | ✗ | ✗ |
| `get_emergency_contact` | ✓ read | ✓ self only | ✗ | ✗ |
| `set_bank_account` | ✓ write | ✓ self only | ✗ | ✗ |
| `update_bank_account` | ✓ write | ✓ self only | ✗ | ✗ |
| `get_bank_account` | ✓ read | ✓ self only | ✗ | ✗ |
| `set_leave_allotment` | ✓ write | — | — | ✗ |
| `get_leave_allotments` | ✓ read | ✓ self only | ✗ (blind spot) | ✗ |
| `create_time_off_request` | ✓ | ✓ self only | ✗ | ✗ |
| `update_time_off_status` | ✓ any status | ✗ (blind spot) | ✗ (blind spot) | ✗ |
| `get_time_off_request` | ✓ read | ✓ self only (blind spot) | ✗ (blind spot) | ✗ |
| `list_time_off_requests` | ✓ read | ✓ self only | ✗ (blind spot) | ✗ |
| `get_leave_balance` | ✓ read | ✓ self only | ✗ (blind spot) | ✗ |
| `add_holiday` | ✓ write | — | — | ✗ |
| `list_holidays` | ✓ | ✓ | ✓ | ✓ |
| `delete_holiday` | ✓ write | — | — | ✗ |

---

## Section 9 — Violation Code Convention

All denial messages use the format: `UPPER_SNAKE_CASE: description`.

| Code | Applies to |
|---|---|
| `HR_ONLY` | Tool restricted to HR department |
| `OWNERSHIP` | Personal or employee record access requires own user_id or HR |
| `SALARY_INVALID` | Salary must be positive |
| `EMAIL_DOMAIN` | Email domain does not match organization |
| `TIMEOFF_OWNERSHIP` | Time-off request must be for the requesting user |
| `TIMEOFF_SPAN` | Time-off span exceeds 90 days |
| `DATE_ORDER` | Issue date must be before expiry date |
| `LEAVE_OWNERSHIP` | Leave records restricted to employee or HR |
| `TIMEOFF_STATUS` | Non-HR user cannot set Approved or Denied status |
