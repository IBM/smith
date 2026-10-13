# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines

## Architecture Summary

Enterprise Employee Hub is a single-agent, single MCP server (stdio FastMCP) system fronting a SQLite employee directory. The server performs no authorization of its own; guidance.txt is the only enforcement layer contemplated. Subject identity (department, organization, user_name, user_id) arrives via system_vars.json / input.extensions.subject.*; tool arguments arrive via input.args.* per tool_definitions.json. No manager_id/direct-report relationship, blacklist flag, or emergency-contact 'area' granularity is declared as a subject or tool-argument field anywhere, so any guidance rule keyed on those relationships cannot be decided pre-execution from declared structured inputs alone.

## Threat Disposition

| Threat ID | Field / surface | Owner | Reason |
|---|---|---|---|
| T1 | get_bank_account/get_passport/get_visa/get_employee args.user_id (surface #1) | Tool implementation | The own-data slice requires comparing args.user_id to the acting subject's own user_id -- a dynamic field-to-field comparison, not a field-to-static-literal comparison, so it cannot be represented in this candidate schema's Values column (operator arity/domain checks require a literal). The Manager/direct-reports broadening also cannot be decided pre-execution because manager_id/direct-report status is not a declared subject field. Only the HR-only broadening (subject.department == HR) is OPA-decidable, but HR already has full access with no restriction to deny, so no OPA candidate arises from this threat -- see Gap Register. |
| T2 | update_employee/update_passport/update_visa/update_bank_account/set_leave_allotment/create_time_off_request/update_time_off_status args.user_id, args.status (surface #1, #2, #11) | OPA | Partial: the HR-only gates on add_department/update_department/add_holiday/delete_holiday/set_leave_allotment/add_employee (subject.department == HR, a field-to-literal comparison) are OPA-decidable. The create_time_off_request self-only rule and the direct-manager slice of the salary-update and time-off-status rules are not: self-only requires a field-to-field comparison (args.user_id vs subject.user_id) this schema cannot represent as a literal Values comparison, the manager slice needs an undeclared manager_id relationship, and update_time_off_status has no requester argument at all -- see Gap Register. |
| T3 | agent.py user_profile / system prompt identity claim (surface #4) | Agent | The threat is that a caller-supplied identity claim is interpolated into the prompt without being cross-checked against system_vars.json before being trusted as input.extensions.subject.*; OPA already assumes subject fields it receives are authoritative, so the fix belongs in how the agent/session layer populates the subject, not in policy content. |
| T4 | add_employee/update_employee args.role (surface #5) | Tool implementation | No enum constrains this field in the implementation; this is a data-integrity/type constraint on a single argument's value set, not an access-control decision, so it belongs in tool-level input validation. |
| T5 | add_employee/update_employee args.organization, args.email (surface #6, #7) | Tool implementation | Requires cross-field validation (email domain must match organization's mapping) and reconciling two independently-declared enums (tool-argument organization vs subject organization) that do not have a 1:1 declared correspondence; not a role/ownership access decision. |
| T6 | add_employee/update_employee args.salary (surface #8) | OPA | A direct, static comparison of a single declared tool argument (args.salary <= 0) with no subject dependency; fully decidable pre-execution. |
| T7 | update_time_off_status args.status (surface #11) | Tool implementation | update_time_off_status declares only request_id and status -- no requester/user_id or manager-relationship argument exists on this tool at all, so no role or ownership condition can be expressed against its declared arguments; the tool itself must be extended with an authoritative requester/relationship input before any pre-execution gate becomes possible. |
| T8 | set_passport/update_passport/set_visa/update_visa args.issue_date, args.expiry_date (surface #9) | Tool implementation | The six-month-minimum rule is relative to the current date at call time (not a static Values comparison) and the issue-before-expiry rule requires derived date-arithmetic across two arguments; neither is expressible as a static field/operator/value candidate. |
| T9 | create_time_off_request args.start_date, args.end_date (surface #10) | Tool implementation | The 90-day cap requires computing a derived duration (end_date minus start_date) rather than comparing a single declared field against a static value; not expressible under the candidate normalization form. |
| T10 | agent-narrated write confirmation (surface #14, #16) | Agent | Confirmation-integrity (verifying the summarized action matches the real input.args.* about to execute) is a prompt/response-structuring concern with no structured pre-execution argument to gate on; belongs to the agent orchestration layer. |
| T11 | set_emergency_contact/update_emergency_contact args.country, args.city (surface #13) | Tool implementation | Requires a cross-field, cross-record check against the employee's own country_code, and 'area' has no declared granularity anywhere; not an access-control condition on a single declared field. |
| T12 | free-text chat instruction to skip confirmation (surface #14) | Agent | The confirm-before-write control is itself a prompt-level behavioral instruction with no structured input.args.* gate; a code-level backstop for this belongs to agent orchestration, not a per-tool argument policy. |
| T13 | web.py process-wide shared conversation list (surface #15) | Infrastructure | Session/context isolation across concurrent callers is a deployment/infrastructure design property (per-session memory segmentation), not a tool-argument or subject-field decision. |

## OWASP Top 10 for Agentic AI Security — Scope Assessment

| OWASP | Scope | OPA threat IDs | Other-layer threat IDs | Reason / owner |
|---|---|---|---|---|
| ASI01 | Partial | — | T12 | Agent Goal Hijack here is a prompt-injection bypass of a purely conversational confirmation control (T12); no structured pre-execution argument exists to gate, so enforcement is entirely Agent-layer. |
| ASI02 | Partial | T2, T6 | T1, T4, T5, T7, T8, T9, T11 | Tool Misuse and Exploitation spans both layers: the HR-only role slice of T2 (a field-to-literal subject.department comparison) and the salary floor (T6) are OPA-decidable from declared subject/argument fields; T1's own-data/self-only slice and T2's create_time_off_request self-only slice require a field-to-field comparison this candidate schema cannot represent as a literal Values comparison, and the remaining ASI02 threats require cross-field validation, derived arithmetic, undeclared fields, or a tool argument that does not exist (T7), so they remain Tool implementation responsibilities. |
| ASI03 | No | — | T3 | Identity and Privilege Abuse here is about the caller-supplied identity claim never being cross-checked before being trusted as subject data; OPA can only consume input.extensions.subject.* as given, so this is entirely an Agent/session-construction responsibility, upstream of any policy decision. |
| ASI04 | No | — | — | Phase C marked this category not applicable: one locally-defined MCP server with no dynamic tool loading, external registry, or third-party server; no supply-chain component to enforce against. |
| ASI05 | No | — | — | Phase C marked this category not applicable: no code-generation, eval, shell, deserialization, or template-execution path exists in the traced architecture. |
| ASI06 | No | — | T13 | Memory & Context Poisoning is scoped to a process-wide shared in-memory conversation list; session isolation is an infrastructure/deployment property, not a per-call argument or subject condition OPA can evaluate. |
| ASI07 | No | — | — | Phase C marked this category not applicable: single-agent system, no peer agent or inter-agent message channel exists. |
| ASI08 | No | — | — | Phase C marked this category not applicable: no multi-agent fan-out or downstream consumer; the data-integrity gaps that exist (T6, T8, T9) are direct-effect and already scoped under ASI02, not a propagating cascade. |
| ASI09 | No | — | T10 | Human-Agent Trust Exploitation here concerns the same LLM narrating and verifying its own confirmation summary; there is no structured pre-execution argument that captures 'the summary matched the real action', so enforcement is entirely Agent-layer. |
| ASI10 | No | — | — | Phase C marked this category not applicable: single-agent process, no peer agents to diverge from or collude with. |

## Gap Register

| Finding ID | Layer | Recommended action |
|---|---|---|
| G1 | Tool implementation / Agent | Declare an authoritative manager_id (or direct-report) relationship as either a subject field or a tool-returned, policy-consumable input before the Manager broadening in the Data Access, salary-update, and leave-viewing rules (T1, T2) can be expressed pre-execution; until then, only the self-only and HR-only slices are OPA-enforceable and the Manager slice must be enforced in the tool implementation. |
| G2 | Tool implementation | Add a role/enum constraint on add_employee/update_employee args.role so only recognized role values are persisted (T4). |
| G3 | Tool implementation | Reconcile the tool-argument organization enum with system_vars.json's organization enum and add a corporate-email-domain cross-check on add_employee/update_employee when organization is provided (T5); clarify with guidance owners whether the two organization enumerations are meant to be identical. |
| G4 | Tool implementation | update_time_off_status has no requester/manager-relationship argument; add one (e.g. an authoritative requester_id or manager_id-of-target) so the HR-any-status / direct-manager-Approved-or-Denied / requester-Pending-only rule (T7) becomes expressible at any enforcement layer; today it cannot be enforced anywhere from declared arguments. |
| G5 | Tool implementation | Add issue-before-expiry ordering and a six-month-minimum-from-today validity check on set_passport/update_passport/set_visa/update_visa (T8); the six-month check requires a runtime current-date reference, which is not a static policy value. |
| G6 | Tool implementation | Add a 90-consecutive-calendar-day span cap (end_date minus start_date) on create_time_off_request (T9); this is a derived-duration check, not a static field comparison. |
| G7 | Tool implementation | Declare 'area' at a specific granularity (e.g. country_code or city) for both employees and emergency contacts, then add a same-area cross-check on set_emergency_contact/update_emergency_contact (T11); currently undeclared and unenforceable at any layer. |
| G8 | Agent | Verify the caller-supplied identity claim (department/organization/user_id) against an authoritative source before it is trusted as input.extensions.subject.* (T3); OPA cannot detect a forged subject value it is handed as ground truth. |
| G9 | Agent | Add an independent, structured diff between the write-confirmation summary shown to the user and the actual input.args.* about to execute, and validate the deletion confirmation phrase programmatically rather than relying on the narrating LLM (T10); enforce the confirm-before-write step and the exact-phrase deletion check as a code-level gate the LLM cannot narrate around (T12). |
| G10 | Infrastructure | Replace the process-wide shared conversation list with per-session/per-caller memory isolation (T13). |
| G11 | Tool implementation | An employee on the blacklist (persona non grata) may not update passport information, but no 'blacklist' field is declared on any tool or subject schema; declare this field before the rule can be enforced at any layer. |
| G12 | Tool implementation | The home-address same-country-only update rule requires comparing a new address's country against the employee's own current country_code, a cross-field/cross-record check on update_employee's home_address argument; the current country_code is not available as a static comparison value at candidate-authoring time, so this remains a tool-implementation check. |
| G13 | Tool implementation | Self/ownership rules that require args.user_id to equal the acting subject's own user_id (T1's own-data read rules on get_bank_account/get_passport/get_visa/get_employee, and T2's create_time_off_request self-only rule) compare two dynamic fields rather than a field against a static literal; this candidate schema's operator+Values form (arity and domain checks assume a literal comparison value) cannot represent a field-to-field comparison, so these self-only checks must be enforced in the tool implementation until the schema or policy engine supports comparing two declared fields directly. |

## Policy Rules (OPA scope only)

Eight tool/condition pairs are within OPA scope: HR-only gates on add_employee, add_department, update_department, add_holiday, delete_holiday, and set_leave_allotment (input.extensions.subject.department != HR => deny); and a data-integrity floor on add_employee/update_employee salary (input.args.salary <= 0 => deny, when salary is provided). Self/ownership comparisons (an argument's user_id must equal the acting subject's own user_id, e.g. the create_time_off_request self-only rule and the own-data read rules) compare two dynamic fields rather than a field against a static literal, which this candidate schema's Values column cannot represent (operator arity/domain checks require a literal comparison value); these remain Tool implementation responsibilities and are recorded in the Gap Register. All other guidance.txt rules identified in Phase A-C either require a Manager/direct-report relationship not present in declared subject fields, require derived/relative-date arithmetic not expressible as a static Values comparison, reference undeclared fields (blacklist, area), or are conversational/behavioral controls outside tool-argument or subject scope; these are also recorded in the Gap Register rather than encoded as candidates.

### Input Schema

| Field | Source |
|---|---|
| input.extensions.subject.department | system_vars.json |
| input.args.salary | tool_definitions.json (add_employee, update_employee) |

### Known values

department: Corporate Leadership | Engineering | Product | HR | Finance (system_vars.json). organization: IBM Corporation | Red Hat | Kyndryl (system_vars.json). Tool argument names and enums per tool_definitions.json (32 tools). No manager_id, blacklist, or area field is declared on any tool or in system_vars.json.

### Rules

| Code | OWASP | Threat IDs | Severity | Tool(s) / field | Condition | Matching |
|---|---|---|---|---|---|---|
| ENF-001 | ASI02 | T2, T3 | Medium | add_employee | Deny add_employee unless the acting subject's department is HR. | Guidance group GG-HR-ADMIN |
| ENF-002 | ASI02 | T2, T3 | Medium | add_department | Deny add_department unless the acting subject's department is HR. | Guidance group GG-HR-ADMIN |
| ENF-003 | ASI02 | T2, T3 | Medium | update_department | Deny update_department unless the acting subject's department is HR. | Guidance group GG-HR-ADMIN |
| ENF-004 | ASI02 | T2, T3 | Medium | add_holiday | Deny add_holiday unless the acting subject's department is HR. | Guidance group GG-HR-ADMIN |
| ENF-005 | ASI02 | T2, T3 | Medium | delete_holiday | Deny delete_holiday unless the acting subject's department is HR. | Guidance group GG-HR-ADMIN |
| ENF-006 | ASI02 | T2, T3 | Medium | set_leave_allotment | Deny set_leave_allotment unless the acting subject's department is HR. | Guidance group GG-HR-ADMIN |
| ENF-007 | ASI02 | T6 | Medium | add_employee, update_employee / args.salary | Deny add_employee/update_employee when args.salary is provided and is less than or equal to zero. | Guidance group GG-SALARY-POSITIVE |

## Candidate Reconciliation

| Candidate ID | Tool | Subject scope | Field expression | Operator | Values | Action | Sources | Related rule | Guidance group | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| C1 | add_employee | all | input.extensions.subject.department | neq | HR | deny | T2, T3, Q4 | Only HR may add a new employee. | GG-HR-ADMIN | Novel |
| C2 | add_department | all | input.extensions.subject.department | neq | HR | deny | T2, T3, Q4 | Only HR may add or update a department, add or delete a country holiday, or set a leave allotment. | GG-HR-ADMIN | Novel |
| C3 | update_department | all | input.extensions.subject.department | neq | HR | deny | T2, T3, Q4 | Only HR may add or update a department, add or delete a country holiday, or set a leave allotment. | GG-HR-ADMIN | Novel |
| C4 | add_holiday | all | input.extensions.subject.department | neq | HR | deny | T2, T3, Q4 | Only HR may add or update a department, add or delete a country holiday, or set a leave allotment. | GG-HR-ADMIN | Novel |
| C5 | delete_holiday | all | input.extensions.subject.department | neq | HR | deny | T2, T3, Q4 | Only HR may add or update a department, add or delete a country holiday, or set a leave allotment. | GG-HR-ADMIN | Novel |
| C6 | set_leave_allotment | all | input.extensions.subject.department | neq | HR | deny | T2, T3, Q4 | Only HR may add or update a department, add or delete a country holiday, or set a leave allotment. | GG-HR-ADMIN | Novel |
| C8 | add_employee | all | input.args.salary | lte | 0 | deny | T6, Q10 | When an employee's salary is set or updated, it must be a positive amount (greater than zero). | GG-SALARY-POSITIVE | Novel |
| C9 | update_employee | all | input.args.salary | lte | 0 | deny | T6, Q10 | When an employee's salary is set or updated, it must be a positive amount (greater than zero). | GG-SALARY-POSITIVE | Novel |

## Existing Guidance Normalization

| Existing ID | Rule number | Tool | Subject scope | Field expression | Operator | Values | Action |
|---|---|---|---|---|---|---|---|

## Prior Proposal Reconciliation

| Prior ID | Original number | Normalized rule | Disposition | Candidate / reason |
|---|---|---|---|---|

## Phase Handoff

- Status: PASS
- Artifact schema: enforcement-mapping-v8
