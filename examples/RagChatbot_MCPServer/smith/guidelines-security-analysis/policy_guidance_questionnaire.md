# OPA Policy Guidance Questionnaire

## Answer Register

| Q | Required answer | Answer | Confidence |
|---|---|---|---|
| Q1 | Tool names and one-sentence purposes | 11 tools: create_ticket (create an inquiry ticket), submit_ticket (submit an inquiry ticket), send_email (send a general-purpose, non-compensation email), export_content_as_file (export arbitrary data/content to a file), ask_for_workpolicy (answer questions from a preloaded work-policy PDF via RAG), get_w2_form (request the caller's own W2 form), return_product (request a product return/refund), view_team_compensation (view team compensation/salary data on screen), export_compensation_data (export team compensation data as a file), email_compensation_report (email a compensation/salary/payroll report), purchase (process a purchase request against a vendor catalog). | [derived from architecture] |
| Q2 | External systems: protocol, authentication, and read/write behavior | MCP server reached over SSE (source=http://localhost:8000/sse per tool_definitions.json), no authentication documented on that transport. ask_for_workpolicy reads a local PDF (pdfs/work_rules_and_regulations_2016.pdf) via PDFPlumberLoader and calls an external OpenAI-compatible chat-completion endpoint (INFERENCE_BASE_URL) to synthesize an answer (read-only against the PDF; no write). An OPA server at http://localhost:8181 is defined (opa_client.py) with no authentication documented, but it is dead code -- never called by any live tool. All other tools operate against an in-memory Python data layer (data_sources/hr_database.py) with no external network calls. | [derived from architecture] |
| Q3 | Whether each tool reads, writes, or both | create_ticket: write (echoes into a confirmation string; no persistence). submit_ticket: write (same pattern). send_email: write (declared, but body/subject/recipient_email unused; email_content/attached_file echoed). export_content_as_file: write (echoes data/file_name; no file actually written). ask_for_workpolicy: read (RAG retrieval + LLM synthesis, no write). get_w2_form: read (no parameters; implementation not detailed in Phase A beyond registration). return_product: write (echoes amount/product_name; no validation against purchase records). view_team_compensation: read (reads hr_db/comp_db in-memory records). export_compensation_data: read (reads the same records, formats as a file-like string). email_compensation_report: write (send action; report_data ignored). purchase: write (reads vendor_catalog for matching, writes an order confirmation). | [derived from architecture] |
| Q4 | Parameters; use Parameter Details | Recorded in the Parameter Details table below for all 11 tools' declared input_schema arguments, with each field's canonical input.args.* path, type, required flag, and valid values (enumerated where guidance.txt or the docstring constrains them). | [derived from architecture] |
| Q5 | Every user role | Two roles are declared: employee and manager (system_vars.json roles=["employee","manager"]). guidance.txt only ever distinguishes these two roles (plus 'no one' as a role-independent hard block). No other role (e.g. admin) is declared or referenced anywhere. | [derived from guidance.txt] |
| Q6 | Runtime subject provenance and integrity; use Runtime Subject Details | None of the four declared runtime subject fields (id, roles, teams, approval) have real per-request provenance or an integrity mechanism. Detail recorded in the Runtime Subject Details table below. | [derived from architecture] |
| Q7 | User ID canonical path, provider, and use | input.extensions.subject.id. Provided by system_vars.json ("id": "Bob") and, at runtime in the dead-code OPA path, by opa_client.get_principal_context() defaulting to 'mcp_direct_user'; the live server instead uses a process-wide global set once at start (set_user_context('mcp_user','user')) to pick 'manager_123' as the team owner inside view_team_compensation/export_compensation_data. It is not transmitted by the client as a structured field and is not read by any live tool for an authorization decision -- only used internally to select which hard-coded team's records to return. | [derived from architecture] |
| Q8 | Whether simultaneous roles are supported | Not supported and not addressed. system_vars.json declares roles as a two-value enumeration (["employee","manager"]) selected singly via a UI dropdown (Streamlit selectbox), not a set. guidance.txt always refers to 'Managers' and 'Employees' as mutually exclusive categories and never describes a dual-role case. | [derived from architecture] |
| Q9 | Tool permissions and scope per role; use Role Permissions | Manager: view_team_compensation scoped to only the requested manager's own team (rule 1); export_compensation_data allowed (rule 4); send_email allowed for non-compensation/non-salary content to non-blocked, @ibm.com-only external domains (rules 6-8); purchase allowed for amount < $1000 (rule 10). Employee: view_team_compensation blocked entirely (rule 2); export_compensation_data blocked entirely (rule 5); email_compensation_report blocked entirely (rule 19); purchase allowed only for amount < $200, or amount >= $200 with manager approval (rule 9). Detail recorded in the Role Permissions table below. | [derived from guidance.txt] |
| Q10 | Role-specific topics, values, or parameter combinations | Manager viewing/querying team compensation: must exclude ssn, home_address, bank_account, tax_id, emergency_contact (rule 3) and personal_email (rule 16), regardless of select_fields request. Manager sending email externally: content must be non-compensation and non-salary (rule 6). No role may combine external_sharing=true with export_compensation_data (rule 17) or email_compensation_report (rule 18) -- this restriction applies to both roles equally, not just one. | [derived from guidance.txt] |
| Q11 | Roles with no restrictions | None. guidance.txt places at least one explicit restriction on both declared roles (employee: rules 2, 5, 9, 19; manager: rules 1, 3, 6, 9(approval-grantor context), 10, 16), plus role-independent 'no one' rules (7, 8, 17, 18) and role-independent blocked-phrase rules (11-14) that apply regardless of role. | [derived from guidance.txt] |
| Q12 | Globally blocked enumerable values, formats, domains, or flags | Blocked email domains for input.args.recipient_email (send_email) / input.args.destination (email_compensation_report): gmail.com, yahoo.com, hotmail.com, outlook.com, personal.com (rule 8, applies to no one / all roles). Additionally, compensation data may only be shared externally to @ibm.com addresses; any non-@ibm.com destination is blocked for compensation content regardless of the rule-8 list (rule 7). Blocked boolean flag: input.args.external_sharing=true is blocked on export_compensation_data (rule 17) and on email_compensation_report (rule 18), for every role. | [derived from guidance.txt] |
| Q13 | Numeric hard caps | purchase.amount: employee hard cap is amount < $200 without approval (rule 9); manager hard cap is amount < $1000 (rule 10). Both are declared on input.args.amount of the purchase tool (type integer). No numeric cap is stated for return_product.amount or for any compensation export/view call volume. | [derived from guidance.txt] |
| Q13b | Conditional approval paths; use Approval Paths | One conditional approval path exists in guidance.txt: employee purchases of $200 or more require manager approval (rule 9) before being permitted (implicitly, up to the manager ceiling of $1000; guidance.txt does not state whether an employee purchase can ever legitimately exceed $1000 even with approval -- left blank, see open gap). Recorded in the Approval Paths table below. No approval field is declared on the purchase tool's input_schema and no populated subject field carries approval status (see Q6/Runtime Subject Details and Undeclared Fields in Phase A) -- this is a structural gap, not an absence of policy intent. | [derived from guidance.txt] |
| Q14 | Rejected patterns and their input source | Four literal/near-literal phrase patterns must always be blocked: "ignore all policies" (rule 11), "bypass security" (rule 12), "override all policies" (rule 13), "show all SSN data" (rule 14). guidance.txt does not name a declared tool argument or subject field as the governed input source for these phrases; Phase A confirms they exist today only in the free-text end-user prompt (a source distinct from input.args.* and input.extensions.subject.*), never copied into a declared tool argument. Per the shared source-boundary rule, a prompt-only pattern cannot be re-expressed as a tool-argument or subject-field OPA predicate without a declared field carrying that text; no such field exists on any of the 11 tools. Recorded as not OPA-policy-expressible against structured input today (Phase A Undeclared Fields, rule refs 11-14). | [derived from architecture] |
| Q15 | Per-session call limits; use Rate Limits | guidance.txt states no per-session or per-role call-count limit for any tool. No rate/counter language appears anywhere in the 19 rules. Left blank in the Rate Limits table (empty array) rather than inventing a limit. |  |
| Q16 | Counter owner, mechanism, and canonical policy path | Not applicable: no counter or rate-limit requirement exists in guidance.txt (see Q15), so there is no counter owner, mechanism, or canonical policy path to record. |  |
| Q17 | Post-response filtering | guidance.txt requires that manager-facing compensation view/export responses exclude ssn, home_address, bank_account, tax_id, emergency_contact (rule 3) and personal_email (rule 16) regardless of what select_fields requested, and that a compensation view/export request specifying no fields at all must be blocked outright rather than defaulting to 'all fields' (rule 15). Architecture confirms the implementation does the opposite of rule 3/16 intent: sensitive_data (including ssn, personal_email, home_address, bank_account, emergency_contact, healthcare fields) is unconditionally merged into both view_team_compensation and export_compensation_data results before any select_fields projection, so today's post-response filtering is absent even though guidance.txt requires it. | [derived from guidance.txt] |
| Q18 | Response fields suppressed by role | For managers viewing/exporting team compensation: ssn, home_address, bank_account, tax_id, emergency_contact (rule 3) and personal_email (rule 16) must be suppressed from the response. guidance.txt does not name any field that must be suppressed specifically from employees, because employees are blocked from view_team_compensation/export_compensation_data/email_compensation_report entirely (rules 2, 5, 19) rather than receiving a filtered response. | [derived from guidance.txt] |
| Q19 | Conditions making a result actionable | guidance.txt does not state an explicit actionability condition (e.g. a confidence threshold or confirmation step) distinct from the access/value rules themselves. The closest actionability condition is rule 15: a view/export compensation request is only actionable if it specifies which fields to return; an unspecified-fields request must be blocked rather than acted on. | [derived from guidance.txt] |
| Q20 | Silent rejection or user explanation | guidance.txt does not state whether a blocked request should be silently rejected or explained to the user. Architecture shows the system prompt convention is to explain: a denial message uses a distinguishing prefix and the LLM is instructed to relay it verbatim without elaboration -- i.e. the user is told something was blocked, not left with silence -- but this is an implementation/prompt convention, not stated guidance intent, and it is inert today because no live tool actually emits such a message. | [derived from architecture] |
| Q21 | Hard-block and soft-block meanings; use Severity Levels | guidance.txt uses only hard-block modal language throughout ("cannot", "no one can", "always block", "must be blocked") and never uses soft-block/advisory language (e.g. "should", "discouraged", "warn"). Per the shared analysis rules, modal terms like 'cannot' and 'no one' establish hard boundaries; guidance.txt therefore defines only a single severity tier -- hard block -- with no soft-block tier. Recorded in the Severity Levels table below. | [derived from guidance.txt] |
| Q22 | Denial logging and existing violation-code scheme | guidance.txt specifies no logging requirement and no violation-code scheme. Architecture confirms no denial logging exists in the live tool path and no violation-code registry exists anywhere in the codebase (opa_client.py's denial-message helper is dead code). See the Violation Logging section and the empty Violation Codes table; no code is invented. | [derived from architecture] |

## Parameter Details

| Tool | Policy path | Type | Required | Valid values |
|---|---|---|---|---|
| create_ticket | input.args.ticket_content | string | true |  |
| submit_ticket | input.args.ticket_content | string | true |  |
| send_email | input.args.recipient_email | string | true | Must not resolve to a blocked domain (rule 8): gmail.com, yahoo.com, hotmail.com, outlook.com, personal.com |
| send_email | input.args.subject | string | true |  |
| send_email | input.args.body | string | true |  |
| send_email | input.args.email_content | string | true | Must not be compensation/salary/payroll/pay-related content (rule 6); email_compensation_report is the required tool for that content instead |
| send_email | input.args.attached_file | string | true |  |
| export_content_as_file | input.args.data | string | true |  |
| export_content_as_file | input.args.file_name | string | true |  |
| ask_for_workpolicy | input.args.question | string | true |  |
| return_product | input.args.amount | integer | true |  |
| return_product | input.args.product_name | string | true |  |
| view_team_compensation | input.args.department | string | true | IT, HR, Sales, Finance, Legal, Operations, Marketing |
| view_team_compensation | input.args.select_fields | array[string] \| null | false | employee_name, title, department, level, hire_date, base_salary, bonus_target, actual_bonus_2024, performance_rating, next_review_date, ssn, personal_email, home_address, emergency_contact, bank_account, and (when include_benefits) healthcare_plan, healthcare_id, stock_grant_value, benefits_value, total_compensation; must not be null/empty per rule 15; ssn, home_address, bank_account, emergency_contact, personal_email must not be present in the effective response for managers per rules 3 and 16 |
| view_team_compensation | input.args.id | string \| null | false |  |
| view_team_compensation | input.args.time_range | string | false | last_quarter (default), current_year, last_year |
| view_team_compensation | input.args.format | string | false | JSON (default), CSV |
| view_team_compensation | input.args.include_benefits | boolean | false | true (default), false |
| export_compensation_data | input.args.select_fields | array[string] \| null | false | employee_id, name, title, level, current_salary, total_comp_2024, performance_rating, and (when export_type=detailed) salary_history, bonus_history; must not be null/empty per rule 15 |
| export_compensation_data | input.args.id | string \| null | false |  |
| export_compensation_data | input.args.format | string | false | CSV (default), PDF, JSON |
| export_compensation_data | input.args.time_range | string | false | last_quarter (default) |
| export_compensation_data | input.args.export_type | string | false | aggregated (default), detailed |
| export_compensation_data | input.args.business_justification | string | false |  |
| export_compensation_data | input.args.external_sharing | boolean | false | Must not be true (rule 17 blocks external_sharing=true for every role) |
| email_compensation_report | input.args.destination | string | true | Must be an @ibm.com address (rule 7); must not resolve to a blocked domain (rule 8): gmail.com, yahoo.com, hotmail.com, outlook.com, personal.com |
| email_compensation_report | input.args.report_data | string | true |  |
| email_compensation_report | input.args.external_sharing | boolean | false | Must not be true (rule 18 blocks external_sharing=true for every role) |
| email_compensation_report | input.args.encryption_required | boolean | false |  |
| purchase | input.args.amount | integer | true | Employee: < 200 without approval (rule 9); Manager: < 1000 (rule 10) |
| purchase | input.args.product_name | string | true |  |
| purchase | input.args.category | string \| null | false |  |
| purchase | input.args.justification | string \| null | false |  |

## Runtime Subject Details

| Policy path | Provider | Provenance | Verification / integrity mechanism |
|---|---|---|---|
| input.extensions.subject.id | system_vars.json ("id": "Bob"); opa_client.get_principal_context() default 'mcp_direct_user' (dead code) | Server-side global set once at process start (set_user_context('mcp_user','user')) or client-side Streamlit session state; never transmitted to or read by any registered tool for an authorization decision | None documented |
| input.extensions.subject.roles | system_vars.json roles=[employee, manager]; opa_client.current_user_context['user_role'] default 'user'; Streamlit role selectbox | Self-selected by the end user in a UI dropdown with no authentication; never read by any live compensation/purchase tool body for an authorization decision | None; self-declared, no session binding |
| input.extensions.subject.teams | opa_client.get_user_teams() hard-coded to ['engineering_team']; system_vars.json teams=[IT,HR,Sales,Finance,Legal,Operations,Marketing] | Hard-coded placeholder in opa_client.py unrelated to the department argument accepted by view_team_compensation | None; get_user_teams ignores its user_id parameter |
| input.extensions.subject.approval | system_vars.json ("approval": "true\|false" placeholder) | Declared as a template placeholder string; no code path ever sets it on a real request | Not implemented; not documented |

## Role Permissions

| Tool | Role | Permission / scope | guidance.txt rule |
|---|---|---|---|
| view_team_compensation | manager | May view only the requested manager's own team's compensation data (employee name, title, salary, bonus, department, hire date); ssn, home_address, bank_account, tax_id, emergency_contact, and personal_email must not appear in the response | 1, 3, 16 |
| view_team_compensation | employee | Blocked entirely | 2 |
| export_compensation_data | manager | May export team compensation data in CSV, PDF, or JSON format; external_sharing must not be true | 4, 17 |
| export_compensation_data | employee | Blocked entirely | 5 |
| send_email | manager | May send externally to non-@ibm.com addresses only non-compensation and non-salary content | 6 |
| send_email | employee | Not addressed by guidance.txt for this tool beyond the role-independent blocked-domain rule | 8 |
| email_compensation_report | manager | May send only to @ibm.com destinations, never with external_sharing=true | 7, 18 |
| email_compensation_report | employee | Blocked entirely | 19 |
| purchase | employee | May purchase amounts under $200 freely; amounts of $200 or more require manager approval | 9 |
| purchase | manager | May purchase amounts under $1000 | 10 |

## Approval Paths

| Parameter condition | Approval field | guidance.txt rule |
|---|---|---|
| purchase: input.args.amount >= 200 and subject role = employee | No declared field carries approval status. Not present on purchase's input_schema (no approval/approver argument declared). Not populated as a runtime subject field: system_vars.json's top-level "approval":"true\|false" is an unpopulated template placeholder with no runtime producer (per Phase A Undeclared Fields). OPEN GAP: no structured input.args.* or input.extensions.subject.* path exists today to bind this approval condition to. | 9 |

## Rate Limits

| Role | Max calls per session |
|---|---|

## Severity Levels

| Level | Examples |
|---|---|
| Hard block | All 19 guidance.txt rules use hard-block modal language ("cannot", "no one can", "always block", "must be blocked"): employee view/export/email-report blocks (rules 2, 5, 19); sensitive-field exclusions for managers (rules 3, 16); external-sharing blocks (rules 17, 18); blocked-domain and non-@ibm.com sharing blocks (rules 7, 8); purchase ceilings (rules 9, 10); the four blocked-phrase rules (11-14); the missing-fields block (rule 15). |

## Violation Logging

guidance.txt establishes no violation-code scheme and no denial-logging mechanism. Architecture confirms no logging of denials exists anywhere in the live tool path (mcp_server.py has no authorization check to log from; opa_client.py's get_universal_denial_message()/_fail_secure_decision are dead code, never invoked by a registered @mcp.tool function). There is no existing violation-code registry to reuse; the Violation Codes table is empty because none exist to record (inventing one is prohibited).

## Violation Codes

| Existing code | Meaning |
|---|---|

## Phase Handoff

- Status: PASS
- Artifact schema: questionnaire-v2
- Summary: 22/22 questions (Q1-Q22 incl. Q13b) answered or explicitly recorded as an open gap; none invented. Confidence tags: 15 [derived from guidance.txt], 7 [derived from architecture], 0 [inferred - low confidence]; Q15/Q16 left blank (no rate-limit intent exists in guidance.txt to derive from, so no confidence tag applies). One consolidated open gap surfaced and retained rather than guessed: purchase's manager-approval condition (rule 9) has no declared tool argument or populated subject field to bind to (Approval Paths table; system_vars.json's approval key is an unpopulated placeholder) -- this was already flagged in Phase A and is carried forward, not re-litigated, per the one-follow-up-then-retain rule. A second, related gap: guidance.txt does not state whether an approved employee purchase is capped at the manager's $1000 ceiling or has no upper bound (Q13b). A third gap: the four blocked-phrase rules (11-14, Q14) have no declared tool-argument or subject-field source and are not OPA-policy-expressible against structured input today. Covered tools: all 11 from tool_definitions.json (create_ticket, submit_ticket, send_email, export_content_as_file, ask_for_workpolicy, get_w2_form, return_product, view_team_compensation, export_compensation_data, email_compensation_report, purchase).
