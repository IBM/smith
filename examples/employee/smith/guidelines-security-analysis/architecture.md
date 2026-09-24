# Architecture Analysis

## Layers

| Layer | File | Role | Inputs | Outputs | Current enforcement |
|---|---|---|---|---|---|
| Client / UI | ui/index.html | Static browser UI; posts user chat text to web.py and calls /reset. No tool selection, no subject-field injection observed. | User-typed chat text | Rendered reply text and step timeline from web.py's JSON response | None |
| Agent / HTTP entrypoint (chat server) | web.py | Starlette app wrapping the LangGraph ReAct agent; maintains one in-memory conversation; exposes POST /chat and POST /reset; reseeds the DB on boot via seed.py. | JSON body {message: str} | JSON {reply: str, steps: [...]} | None |
| Agent / HTTP entrypoint (alt FastAPI app) | agent.py | Builds the same ReAct agent plus a non-executing tool-bound LLM; exposes POST /chat, POST /extract_tool_call, GET /health, and a REPL main(). Interpolates an optional user_profile/system_variables dict into the system prompt. | JSON body {question: str, user_profile: dict\|None} | JSON {response: str} or {tool_name: str, arguments: dict} | None |
| MCP transport / registration | server.py | FastMCP('enterprise-employee-hub') server; registers 32 @mcp.tool() functions over stdio transport; opens one shared sqlite3 connection at import time; wraps every tool body in _safe() which converts ValueError to {'error': msg}. | Tool name + keyword arguments from the MCP client | dict/list tool results or {'error': str} | None (no authorization; only input-shape/domain validation inside api/*.py, e.g. enum checks, date parsing, FK existence checks) |
| Tool implementation (business logic) | api/employees.py, api/org.py, api/departments.py, api/personal.py, api/leave.py, api/holidays_api.py | Implements each tool's actual read/write logic against the SQLite schema; the only place where argument values are actually consumed to build SQL and business rules (enum validation, date parsing, business-day counting). | Parameters forwarded from server.py wrappers | dicts/lists mirroring table rows, or raised ValueError | Data-integrity validation only (validate_enum, parse_date, FK existence via get_employee/get_department/get_time_off_request); no identity/authorization checks anywhere in this layer |
| Persistence | db.py, schema.sql, employee_hub.db | SQLite connection factory and row-dict helpers; schema defines employees, departments, passports, visas, emergency_contacts, bank_accounts, leave_allotments, time_off_requests, holidays. | Parameterized SQL from api/*.py | sqlite3.Row results | SQL-level constraints only (UNIQUE, NOT NULL, FK with ON DELETE CASCADE); no row-level security |
| Runtime context / enforcement (absent) | N/A (not implemented anywhere in this tree) | No policy/OPA interception point, middleware, or decorator exists between the MCP transport and the tool implementation, or between the HTTP entrypoints and the agent loop. | N/A | N/A | None -- confirmed absent by inspection; matches guidance.txt's explicit statement that 'the server performs no authorization of its own' |

### Runtime Subject Context

| Field | Provider | Provenance | Verification / integrity | OPA-visible? |
|---|---|---|---|---|
| input.extensions.subject.user_id | system_vars.json ("user_id": 1) | Static demo value in the authoritative system_vars.json; not observed to be read or injected by any Python file in this tree (agent.py/web.py accept an arbitrary caller-supplied user_profile dict at runtime, which is a distinct, unvalidated channel -- see Prompt Inputs) | None observed. No signature, session lookup, or auth-header binding found in agent.py, web.py, or server.py. | Yes, as input.extensions.subject.user_id, if the caller supplies it through whatever channel a future enforcement point uses -- but no current code path plumbs system_vars.json's static value into a tool call or policy decision. |
| input.extensions.subject.user_name | system_vars.json ("user_name": "Bob") | Static demo value; same caveat as user_id -- not observed wired into any request path. | None observed. | Yes, as input.extensions.subject.user_name, once wired. |
| input.extensions.subject.department | system_vars.json (enum: Corporate Leadership, Engineering, Product, HR, Finance) | Static demo value; guidance.txt's 'HR' role predicate depends on this field equaling 'HR'. | None observed. | Yes, as input.extensions.subject.department, once wired. |
| input.extensions.subject.organization | system_vars.json (enum: IBM Corporation, Red Hat, Kyndryl) | Static demo value. Note: this enum's spelling ('IBM Corporation', 'Kyndryl') differs from the tool-argument organization enum validated in api/util.py (ORGANIZATIONS = {'IBM', 'IBM partner', 'Red Hat'}) and from guidance.txt's own domain-mapping list (IBM Corporation, Red Hat, Kyndryl). The subject-context organization and the tool-argument organization are declared by different schemas with different allowed values and must not be treated as the same field despite the shared name. | None observed. | Yes, as input.extensions.subject.organization, once wired -- but any policy must not conflate it with the employees.organization tool argument (see Tool Arguments and Undeclared Fields). |

### Tool Arguments

| Field | Tool | Origin / influence | Disposition |
|---|---|---|---|
| input.args.first_name | add_employee | LLM-chosen string | Acts on (inserted into employees.first_name) |
| input.args.last_name | add_employee | LLM-chosen string | Acts on (inserted into employees.last_name) |
| input.args.email | add_employee | LLM-chosen string | Acts on (inserted; UNIQUE constraint enforced; no corporate-domain check performed in code despite guidance.txt's email-domain rule) |
| input.args.role | add_employee | LLM-chosen string | Acts on (inserted, no enum validation) |
| input.args.title | add_employee | LLM-chosen string | Acts on (inserted, no validation) |
| input.args.home_address | add_employee | LLM-chosen string | Acts on (inserted, no validation) |
| input.args.country_code | add_employee | LLM-chosen string | Acts on (inserted, no validation) |
| input.args.organization | add_employee | LLM-chosen string | Acts on (validated against ORGANIZATIONS = {IBM, IBM partner, Red Hat} in api/util.py; raises ValueError otherwise) |
| input.args.department_id | add_employee | LLM-chosen integer | Acts on (inserted; FK enforced by SQLite) |
| input.args.manager_id | add_employee | LLM-chosen integer | Acts on (inserted; FK enforced by SQLite; self-referencing employees.user_id) |
| input.args.salary | add_employee | LLM-chosen number | Acts on (inserted verbatim; no positive-amount check in code despite guidance.txt's positivity rule) |
| input.args.salary_currency | add_employee | LLM-chosen string | Acts on (inserted, no validation) |
| input.args.start_date | add_employee | LLM-chosen string | Acts on (inserted verbatim; no date-format validation, unlike leave/holiday dates) |
| input.args.user_id | update_employee | LLM-chosen integer | Acts on (identifies row to update; existence-checked via get_employee) |
| input.args.first_name | update_employee | LLM-chosen string | Acts on (partial update if not None) |
| input.args.last_name | update_employee | LLM-chosen string | Acts on (partial update if not None) |
| input.args.email | update_employee | LLM-chosen string | Acts on (partial update if not None; no domain re-check) |
| input.args.role | update_employee | LLM-chosen string | Acts on (partial update if not None) |
| input.args.organization | update_employee | LLM-chosen string | Acts on (validated against ORGANIZATIONS if provided) |
| input.args.title | update_employee | LLM-chosen string | Acts on (partial update if not None) |
| input.args.department_id | update_employee | LLM-chosen integer | Acts on (partial update if not None; FK enforced) |
| input.args.home_address | update_employee | LLM-chosen string | Acts on (partial update if not None; no country-match check in code despite guidance.txt's same-country rule) |
| input.args.manager_id | update_employee | LLM-chosen integer | Acts on (partial update if not None; FK enforced) |
| input.args.country_code | update_employee | LLM-chosen string | Acts on (partial update if not None) |
| input.args.salary | update_employee | LLM-chosen number | Acts on (partial update if not None; no positivity check in code) |
| input.args.salary_currency | update_employee | LLM-chosen string | Acts on (partial update if not None) |
| input.args.start_date | update_employee | LLM-chosen string | Acts on (partial update if not None; no date validation) |
| input.args.user_id | get_employee | LLM-chosen integer | Acts on (selects the row; no ownership check) |
| input.args.department_id | list_employees | LLM-chosen integer, optional | Acts on (SQL filter if not None) |
| input.args.manager_id | list_employees | LLM-chosen integer, optional | Acts on (SQL filter if not None) |
| input.args.country_code | list_employees | LLM-chosen string, optional | Acts on (SQL filter if not None) |
| input.args.user_id | get_manager | LLM-chosen integer | Acts on (looks up employee then its manager) |
| input.args.user_id | get_direct_reports | LLM-chosen integer | Acts on (filters list_employees by manager_id=user_id) |
| input.args.user_id | get_reporting_chain | LLM-chosen integer | Acts on (walks manager_id chain) |
| input.args.name | add_department | LLM-chosen string | Acts on (inserted; UNIQUE constraint) |
| input.args.description | add_department | LLM-chosen string, optional | Acts on (inserted) |
| input.args.department_id | update_department | LLM-chosen integer | Acts on (identifies row; existence-checked) |
| input.args.name | update_department | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.description | update_department | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.department_id | get_department | LLM-chosen integer | Acts on (selects the row) |
| input.args.user_id | set_passport | LLM-chosen integer | Acts on (upsert key; existence-checked) |
| input.args.passport_number | set_passport | LLM-chosen string | Acts on (upserted) |
| input.args.issuing_country | set_passport | LLM-chosen string | Acts on (upserted) |
| input.args.issue_date | set_passport | LLM-chosen string, optional | Acts on (upserted verbatim; no format validation; no issue<expiry cross-check in code despite guidance.txt's rule) |
| input.args.expiry_date | set_passport | LLM-chosen string, optional | Acts on (upserted verbatim; no 6-month-minimum check in code despite guidance.txt's rule) |
| input.args.user_id | update_passport | LLM-chosen integer | Acts on (identifies row; existence-checked) |
| input.args.passport_number | update_passport | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.issuing_country | update_passport | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.issue_date | update_passport | LLM-chosen string, optional | Acts on (partial update if not None; no validation) |
| input.args.expiry_date | update_passport | LLM-chosen string, optional | Acts on (partial update if not None; no validation) |
| input.args.user_id | get_passport | LLM-chosen integer | Acts on (selects the row) |
| input.args.user_id | set_visa | LLM-chosen integer | Acts on (upsert key; existence-checked) |
| input.args.visa_number | set_visa | LLM-chosen string | Acts on (upserted) |
| input.args.issuing_country | set_visa | LLM-chosen string | Acts on (upserted) |
| input.args.visa_type | set_visa | LLM-chosen string, optional | Acts on (upserted, no validation) |
| input.args.issue_date | set_visa | LLM-chosen string, optional | Acts on (upserted verbatim; no validation) |
| input.args.expiry_date | set_visa | LLM-chosen string, optional | Acts on (upserted verbatim; no validation) |
| input.args.user_id | update_visa | LLM-chosen integer | Acts on (identifies row; existence-checked) |
| input.args.visa_number | update_visa | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.visa_type | update_visa | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.issuing_country | update_visa | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.issue_date | update_visa | LLM-chosen string, optional | Acts on (partial update if not None; no validation) |
| input.args.expiry_date | update_visa | LLM-chosen string, optional | Acts on (partial update if not None; no validation) |
| input.args.user_id | get_visa | LLM-chosen integer | Acts on (selects the row) |
| input.args.user_id | set_emergency_contact | LLM-chosen integer | Acts on (upsert key; existence-checked) |
| input.args.name | set_emergency_contact | LLM-chosen string | Acts on (upserted) |
| input.args.relationship | set_emergency_contact | LLM-chosen string | Acts on (validated against RELATIONSHIPS enum) |
| input.args.phone | set_emergency_contact | LLM-chosen string | Acts on (upserted, no format validation) |
| input.args.email | set_emergency_contact | LLM-chosen string, optional | Acts on (upserted, no validation) |
| input.args.street_address | set_emergency_contact | LLM-chosen string, optional | Acts on (upserted; no same-area-as-employee check in code despite guidance.txt's rule, and no 'area' field exists to check against) |
| input.args.city | set_emergency_contact | LLM-chosen string, optional | Acts on (upserted, no cross-check) |
| input.args.country | set_emergency_contact | LLM-chosen string, optional | Acts on (upserted, no cross-check against employee.country_code) |
| input.args.postal_code | set_emergency_contact | LLM-chosen string, optional | Acts on (upserted, no validation) |
| input.args.user_id | update_emergency_contact | LLM-chosen integer | Acts on (identifies row; existence-checked) |
| input.args.name | update_emergency_contact | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.relationship | update_emergency_contact | LLM-chosen string, optional | Acts on (validated if provided) |
| input.args.phone | update_emergency_contact | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.email | update_emergency_contact | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.street_address | update_emergency_contact | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.city | update_emergency_contact | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.country | update_emergency_contact | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.postal_code | update_emergency_contact | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.user_id | get_emergency_contact | LLM-chosen integer | Acts on (selects the row) |
| input.args.user_id | set_bank_account | LLM-chosen integer | Acts on (upsert key; existence-checked) |
| input.args.bank_name | set_bank_account | LLM-chosen string | Acts on (upserted) |
| input.args.account_number | set_bank_account | LLM-chosen string | Acts on (upserted, no format validation) |
| input.args.routing_number | set_bank_account | LLM-chosen string, optional | Acts on (upserted) |
| input.args.iban | set_bank_account | LLM-chosen string, optional | Acts on (upserted) |
| input.args.currency | set_bank_account | LLM-chosen string, optional | Acts on (upserted) |
| input.args.user_id | update_bank_account | LLM-chosen integer | Acts on (identifies row; existence-checked) |
| input.args.bank_name | update_bank_account | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.account_number | update_bank_account | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.routing_number | update_bank_account | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.iban | update_bank_account | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.currency | update_bank_account | LLM-chosen string, optional | Acts on (partial update if not None) |
| input.args.user_id | get_bank_account | LLM-chosen integer | Acts on (selects the row) |
| input.args.user_id | set_leave_allotment | LLM-chosen integer | Acts on (existence-checked; upsert key) |
| input.args.leave_type | set_leave_allotment | LLM-chosen string | Acts on (validated against LEAVE_TYPES enum) |
| input.args.annual_days | set_leave_allotment | LLM-chosen integer, optional | Acts on (upserted verbatim, no bound checking) |
| input.args.user_id | get_leave_allotments | LLM-chosen integer | Acts on (existence-checked; filters the query) |
| input.args.user_id | create_time_off_request | LLM-chosen integer | Acts on (existence-checked; inserted as the request owner -- no cross-check that this equals the acting subject's user_id, despite guidance.txt's 'only for themselves' rule) |
| input.args.leave_type | create_time_off_request | LLM-chosen string | Acts on (validated against LEAVE_TYPES enum) |
| input.args.start_date | create_time_off_request | LLM-chosen string | Acts on (parsed; end_date>=start_date enforced; no 90-day-span check in code despite guidance.txt's rule) |
| input.args.end_date | create_time_off_request | LLM-chosen string | Acts on (parsed; end_date>=start_date enforced; no 90-day-span check in code) |
| input.args.reason | create_time_off_request | LLM-chosen string, optional | Acts on (inserted verbatim, not re-parsed elsewhere) |
| input.args.request_id | update_time_off_status | LLM-chosen integer | Acts on (identifies row; existence-checked) |
| input.args.status | update_time_off_status | LLM-chosen string | Acts on (validated against STATUSES enum; no role-based restriction on which status values a caller may set, despite guidance.txt's HR/manager/requester status rule) |
| input.args.request_id | get_time_off_request | LLM-chosen integer | Acts on (selects the row) |
| input.args.user_id | list_time_off_requests | LLM-chosen integer, optional | Acts on (SQL filter if not None) |
| input.args.status | list_time_off_requests | LLM-chosen string, optional | Acts on (SQL filter if not None) |
| input.args.user_id | get_leave_balance | LLM-chosen integer | Acts on (looks up employee and country_code, drives allotment/usage query) |
| input.args.year | get_leave_balance | LLM-chosen integer | Acts on (bounds the date range of the balance calculation) |
| input.args.country_code | add_holiday | LLM-chosen string | Acts on (inserted) |
| input.args.holiday_date | add_holiday | LLM-chosen string | Acts on (parsed via parse_date; inserted; UNIQUE with country_code) |
| input.args.name | add_holiday | LLM-chosen string | Acts on (inserted) |
| input.args.country_code | list_holidays | LLM-chosen string | Acts on (SQL filter) |
| input.args.year | list_holidays | LLM-chosen integer, optional | Acts on (SQL range filter if not None) |
| input.args.holiday_id | delete_holiday | LLM-chosen integer | Acts on (deletes the row; no confirmation-state argument exists despite guidance.txt's confirm-before-write rule) |

### Prompt Inputs

| Field or data | Source | Consumer | Trust / influence |
|---|---|---|---|
| SYSTEM_PROMPT (fixed constant) | agent.py source code | LangGraph ReAct agent (both /chat paths) and llm_with_tools | Trusted, static; defines tool-call conventions and leave-type/status enums but contains no access-control instructions |
| user_profile (agent.py) / system_variables | Caller-supplied JSON field on the /chat and /extract_tool_call request bodies in agent.py; arbitrary keys, not restricted to system_vars.json's schema | build_system_prompt(), which appends every key/value pair verbatim as prompt text consumed by the LLM | Untrusted and unvalidated -- any caller of agent.py's HTTP API can inject arbitrary claimed 'system variables' (e.g. a fabricated department: HR) into the prompt with no cross-check against an authoritative identity source; this is a prompt-boundary control, not a tool-argument or verified subject-context control, and must not be treated as equivalent to system_vars.json |
| message / question (free text) | HTTP request body (web.py's /chat, agent.py's /chat and /extract_tool_call) | LLM as the user turn; may include guidance-relevant facts such as a baby's birth date/name for Paternity leave approval (per guidance.txt) or a delete-confirmation phrase | Untrusted; the LLM alone decides how conversational content maps to tool arguments -- no code path extracts or independently verifies these facts |
| Conversation history (_messages / result['messages']) | Accumulated prior turns held in-memory by web.py (single shared list) or passed by the caller (agent.py's REPL) | LLM on every subsequent turn | Untrusted, cumulative; web.py's single-conversation state model means all callers of one running instance share the same history |

### External Data

| Data | Source | Verification / integrity | Consumer |
|---|---|---|---|
| None found | N/A | N/A | N/A |

## Enforcement Points

| Layer | Current | Available (OPA-interceptable) | Blind spots |
|---|---|---|---|
| MCP transport (server.py, before dispatch to the api/* implementation) | None | Every tool call's exact tool name plus its declared input.args.* (all captured above) are structured and available before the api/* call executes; a pre-execution Rego decision could gate on any combination of these plus input.extensions.subject.* once subject context is reliably plumbed in | Ownership/role predicates that guidance.txt expresses in terms of returned data (e.g. 'direct reports', 'their manager') require a prior read (get_employee/get_direct_reports) whose result is not itself a declared input.args or subject field at decision time for a later call -- a pre-execution policy cannot see it unless the caller re-supplies it as an argument |
| HTTP entrypoint (agent.py's user_profile / system_variables interpolation) | None | None -- this channel feeds free text into the prompt rather than a structured, declared field, so it is not itself OPA-policy-expressible as a subject-context source; a fix would be to stop treating caller-supplied profile data as authoritative and instead source input.extensions.subject.* from a verified channel | A caller can claim any department/organization/user_id via user_profile with no verification; this is a genuine blind spot distinct from the (currently also unwired) system_vars.json path |
| Conversation-derived facts (Paternity birth date/name; delete-confirmation phrase; write confirmation generally) | None | None as currently structured -- guidance.txt explicitly ties these to 'conversation history' / an exact confirmation phrase, which is prompt/conversation content, not a declared tool argument or subject field | True blind spot: no tool argument or subject field captures confirmation state, the birth-date/name pair, or the delete-confirmation phrase; a pre-execution policy has no structured signal for these rules unless the tool schemas are extended to accept them as explicit arguments |
| Data-integrity rules already implemented in api/*.py (enum validation, date parsing, FK existence) | Input-shape/domain validation inside the tool implementation (validate_enum, parse_date, require) | The same input.args.* used by this validation (e.g. organization, leave_type, status, relationship, the date fields) are fully declared and could equally be checked pre-execution by policy, but today the check lives inside the implementation, not at a policy layer | None for the fields actually validated in code; but several guidance.txt data-integrity rules (salary > 0, email domain matches organization, issue_date < expiry_date, 6-month expiry minimum, home-address same-country, 90-day request span, same-area emergency contact) have no corresponding validation anywhere in api/*.py despite being declared purely in terms of already-declared tool arguments -- these are enforceable pre-execution today but are currently enforced nowhere |

## Undeclared Fields

| Field | Referenced by guidance rule # | Declared by | Consequence |
|---|---|---|---|
| blacklist / persona-non-grata status | Personal-Record Update Rules: 'An employee who is on the blacklist (persona non grata list) may not update their passport information.' | Declared nowhere -- no such column exists in schema.sql, no such tool argument exists in tool_definitions.json, and no such field exists in system_vars.json | This rule cannot be expressed as a pre-execution OPA decision against any currently declared structured input; it would require a new tool argument or subject field to be added before it is enforceable |
| manager_id / 'direct report' and 'direct manager' relationship | Data Access ('A Manager may view only their direct reports'), Data Access ('salary may be updated ... by that employee's direct manager'), Time Off and Leave (direct-manager viewing and approval rules) | Declared as a tool-returned data field (employees.manager_id, returned by get_employee/list_employees/get_direct_reports/get_manager) and as an input.args.* field only on add_employee/update_employee (where it sets the value, not queries it) -- it is not a runtime subject-context field (system_vars.json has no manager_id or reports list for the acting user) | A pre-execution policy deciding a call against, say, get_bank_account or update_time_off_status cannot determine 'is the acting user the target's direct manager' from input.args.* or input.extensions.subject.* alone; the relationship exists only as data returned by a separate prior tool call. This is 'declared by another tool's output', not by the acting subject's own declared context, and is a structural gap between guidance intent and enforceable inputs. |
| employee 'area' (for emergency-contact same-area matching) | Personal-Record Update Rules: 'An employee's emergency contact must reside in the same area as the employee.' | Declared nowhere as 'area' -- the closest declared fields are employees.country_code (tool argument on add_employee/update_employee) and employees.home_address (free-text string); emergency_contacts has its own separate country/city/postal_code/street_address fields with no schema-level link enforcing equality to the employee's | The rule is ambiguous against the current schema (no defined 'area' granularity) and not enforced anywhere in api/personal.py; a policy could only approximate it (e.g. country match) without a guidance clarification of what 'area' means |
| write-confirmation state ('yes' / exact delete-confirmation phrase) | Database Writes and Confirmation (both bullets) | Declared nowhere as a structured field -- guidance.txt itself frames this as conversational behavior ('the agent must first list the details... and obtain the user's explicit confirmation'), and no tool argument or subject field carries a confirmation flag | Not pre-execution-OPA-expressible against any current declared input; enforcing it would require either a new confirmed:bool-style tool argument or treating it as a prompt/agent-behavior control outside this workflow's structured-input scope |
| Paternity leave birth-date and baby's-name conversation facts | Time Off and Leave: 'A Paternity leave request may be approved only if the requester has provided both the baby's birth date and the baby's name in their chat messages to the agent.' | Declared nowhere as a structured field -- guidance.txt explicitly scopes this to conversation history, and no tool argument on create_time_off_request or update_time_off_status carries these values | Not expressible as a pre-execution structured-input decision without a schema change (e.g. adding these as explicit arguments); currently a true blind spot consistent with the shared workflow's rule to keep conversation-derived controls distinct from tool-argument controls |
| Booking / flight passenger count / frequent-flyer points / 'regular' membership | Booking: 'A customer with a regular membership may not book a flight for more than three passengers unless they own at least 200 frequent flyer points.' | Declared nowhere in this agent's tool_definitions.json, system_vars.json, or schema.sql -- there is no booking, flight, passenger, membership, or frequent-flyer concept anywhere in the employee-hub source tree | This guidance.txt rule appears to be out-of-domain content unrelated to the Enterprise Employee Hub (possibly carried over from a different example's guidance file); it cannot be mapped to any tool or subject field in this agent and should be flagged as a guidance-file inconsistency rather than encoded |
| organization (subject-context enum) vs organization (tool-argument enum) | Actors and Identity ('organization -- one of IBM Corporation, Red Hat, Kyndryl') and Data Integrity ('IBM Corporation -> @ibm.com, Red Hat -> @redhat.com, Kyndryl -> @kyndryl.com') | Declared twice with incompatible value sets: system_vars.json declares {IBM Corporation, Red Hat, Kyndryl}; api/util.py's ORGANIZATIONS enum (enforced on add_employee/update_employee's organization tool argument) declares {IBM, IBM partner, Red Hat} -- Kyndryl is not a valid tool-argument value and 'IBM partner' is not a valid subject-context value | Any guidance rule that assumes these two 'organization' notions are interchangeable (e.g. the email-domain rule, which is phrased using the subject-context enum's spelling) cannot be mechanically applied to the employees.organization tool argument without a value-mapping decision; this is a genuine schema mismatch between the two declared sources, not a missing field, and should be called out explicitly rather than silently reconciled |

## Phase Handoff

- Status: PASS
- Artifact schema: architecture-v2
- Summary: Inspected 13 implementation files (agent.py, server.py, web.py, db.py, schema.sql, api/__init__.py [empty], api/util.py, api/employees.py, api/org.py, api/departments.py, api/personal.py, api/leave.py, api/holidays_api.py) plus a UI-only skim of ui/index.html, within the 20-file budget and at most two hops from any tool. All 32 tools declared in tool_definitions.json have a confirmed one-to-one @mcp.tool() registration in server.py with matching signatures and a traced implementation in api/*.py -- no missing, extra, or incompatible tool declarations found (no Unknown/dynamic wrappers either). 7 layers recorded (client/UI, two HTTP entrypoints, MCP transport, tool implementation, persistence, and the confirmed-absent enforcement layer). 4 runtime subject fields from system_vars.json recorded, all currently unwired into any actual request path (a separate, unvalidated user_profile channel exists in agent.py). Tool Arguments table enumerates all 97 input.args.* occurrences across the 32 tools with disposition determined from the api/*.py function bodies (all resolve to 'Acts on'; none found Echoed/Ignored/Unclear). 4 Prompt Inputs and an empty External Data table (no outbound HTTP/external-service calls found anywhere in the tree). Enforcement Points records the current total absence of authorization, the OPA-interceptable structured surface (tool name + input.args.*, and input.extensions.subject.* once wired), and three categories of true blind spot (returned-data relationships, conversation-only facts, and confirmation state). Undeclared Fields records 7 guidance-visibility gaps from a full sweep of guidance.txt against the declared tool/subject schema: blacklist status (declared nowhere), manager/direct-report relationship (declared only as tool-returned data, not subject context), employee 'area' (undefined/nowhere), write-confirmation state (nowhere, conversational by design), Paternity birth-date/name facts (nowhere, conversational by design), an out-of-domain Booking/flight rule unrelated to any tool in this agent, and a value-set mismatch between the subject-context 'organization' enum and the tool-argument 'organization' enum. No proven tool mismatch was found, so status is PASS; the recorded gaps are guidance-visibility and cross-schema findings for later phases, not architecture-phase failures.
