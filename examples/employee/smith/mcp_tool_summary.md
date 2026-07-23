# Enterprise Employee Hub MCP Server: Tool Summary and Capability Analysis

## Overview

This MCP server (`server.py`, FastMCP over stdio) exposes an SQLite-backed
employee hub as a set of tools. Each tool is a thin wrapper over a pure-Python
`api.*` function. The data model covers employees, the org chart, departments,
personal records (passport, visa, emergency contact, bank account), country
holidays, and time-off (allotments, requests, and per-type balances).

The server itself performs **no authorization** — any caller can invoke any
tool with any arguments. Access control is exactly what the Smith-managed
policy is expected to add.

## System Variables Available to the Policy

From `system_vars.json`, mapped to `input.extensions.subject.*`:

- `department` — one of `Corporate Leadership`, `Engineering`, `Product`, `HR`,
  `Finance`.
- `organization` — one of `IBM Corporation`, `Red Hat`, `Kyndryl`. Employees also
  carry an `organization` field, so the policy can compare the acting user's
  organization against a target employee's (e.g. a user whose organization is not
  `IBM Corporation` — a `Red Hat` or `Kyndryl` user — may not view `IBM
  Corporation` employee data).
- `user_name` — the acting user's display name.
- `user_id` — the acting user's numeric id (matches `employees.user_id`), so
  the policy can distinguish self-service (`arguments.user_id == subject.user_id`)
  from acting on another employee.

There is **no acting-user `role` system variable**: authority derives from
`department` (e.g. HR) and the reporting relationship (`manager_id` /
`get_direct_reports`), not from a role. `role` exists only as a field on employee
**records** — i.e. a tool argument (`input.arguments.*`), not a policy subject
attribute.

## Exposed MCP Tools

Tool arguments map to `input.arguments.*` in the policy.

### Employees

| Tool | Args | Notes |
|------|------|-------|
| `add_employee` | first_name, last_name, email, role, title, home_address, country_code, [organization, department_id, manager_id, salary, salary_currency, start_date] | Creates records; can set `salary`, `role`, and `organization`. |
| `update_employee` | user_id, [any employee field] | Can change `role`, `organization`, `salary`, `manager_id`, `department_id` — privilege-sensitive. |
| `get_employee` | user_id | Returns `salary` and `home_address`. |
| `list_employees` | [department_id, manager_id, country_code] | Bulk read; returns salary per row. |

### Org

| Tool | Args |
|------|------|
| `get_manager` | user_id |
| `get_direct_reports` | user_id |
| `get_reporting_chain` | user_id |

### Departments

| Tool | Args |
|------|------|
| `add_department` | name, [description] |
| `update_department` | department_id, [name, description] |
| `get_department` | department_id |
| `list_departments` | — |

### Personal records (sensitive PII)

Each entity has `set_*` (upsert), `update_*`, and `get_*` tools keyed by `user_id`.

| Entity | Tools | Sensitivity |
|--------|-------|-------------|
| Passport | `set_passport`, `update_passport`, `get_passport` | Passport number, issuing country — sensitive PII. |
| Visa | `set_visa`, `update_visa`, `get_visa` | Visa number, type — sensitive PII. |
| Emergency contact | `set_emergency_contact`, `update_emergency_contact`, `get_emergency_contact` | Personal contact details. `relationship` restricted to a fixed set. |
| Bank account | `set_bank_account`, `update_bank_account`, `get_bank_account` | Account number, routing number, IBAN — highly sensitive financial PII. |

### Leave and time-off

| Tool | Args | Notes |
|------|------|-------|
| `set_leave_allotment` | user_id, leave_type, [annual_days] | `leave_type` ∈ Vacation, Sick Leave, Maternity, Paternity, Jury Duty, Unpaid. |
| `get_leave_allotments` | user_id | |
| `create_time_off_request` | user_id, leave_type, start_date, end_date, [reason] | Creates a `Pending` request. |
| `update_time_off_status` | request_id, status | **Approval action** — status ∈ Pending, Approved, Denied. |
| `get_time_off_request` | request_id | |
| `list_time_off_requests` | [user_id, status] | |
| `get_leave_balance` | user_id, year | |

### Holidays

| Tool | Args |
|------|------|
| `add_holiday` | country_code, holiday_date, name |
| `list_holidays` | country_code, [year] |
| `delete_holiday` | holiday_id |

## Security-Sensitive Surfaces

1. **Financial / identity PII reads** — `get_bank_account`, `get_passport`,
   `get_visa`, and the salary fields returned by `get_employee` / `list_employees`
   are the highest-value data. Natural candidates for restriction to HR and/or
   self-service only.
2. **Privilege-changing writes** — `update_employee` can change a person's
   `role`, `manager_id`, `department_id`, or `salary`; `add_employee` can set
   `salary`. These are the mutation tools most worth constraining.
3. **Approval authority** — `update_time_off_status` (Approve/Deny) is an
   authority action distinct from `create_time_off_request` (which any employee
   might do for themselves).
4. **Self vs. others** — most read/write tools are keyed by `user_id`, so the
   policy can allow employees to act on their own record (`arguments.user_id ==
   subject.user_id`) while denying access to other employees' data.
5. **Bulk / structural changes** — `add_department`, `update_department`,
   `delete_holiday` change shared org structure rather than one person's data.

## Architecture Notes

- FastMCP (Python), stdio transport; ~33 tools over one shared SQLite connection.
- ValueError from the API layer is surfaced as `{"error": <message>}`.
- No authentication, rate limiting, or per-caller state in the server — the
  policy is the only enforcement layer.
