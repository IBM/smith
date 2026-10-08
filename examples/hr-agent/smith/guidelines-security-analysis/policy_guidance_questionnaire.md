# OPA Policy Guidance Questionnaire

## Answer Register

| Q | Required answer | Answer | Confidence |
|---|---|---|---|
| Q1 | Tool names and one-sentence purposes | get_compensation: return salary, bonus, department, and optionally SSN for an employee (input.args.employee_id, input.args.include_ssn). display_compensation: display a compensation band summary only (input.args.employee_id), no salary figures. get_directory: list the employee directory, optionally filtered by input.args.department. send_email: send an email given input.args.to, input.args.subject, input.args.body. search_repos: search internal GitHub Enterprise repositories by input.args.repo_name and input.args.visibility. adjust_compensation: adjust an employee's salary by input.args.amount for input.args.employee_id. | [derived from architecture] |
| Q2 | External systems: protocol, authentication, and read/write behavior | No real external systems are integrated in this tree. get_compensation/display_compensation/get_directory/adjust_compensation read/write an in-memory mock EMPLOYEES dict in server.py; search_repos reads an in-memory mock REPOS list standing in for GitHub Enterprise; send_email writes to an in-memory SENT_EMAILS list (simulated send, no real mail transport). All access is via server.py's JSON-RPC /mcp endpoint with no authentication check performed in server.py itself (Phase A: server.py trusts args unconditionally). | [derived from architecture] |
| Q3 | Whether each tool reads, writes, or both | get_compensation: read. display_compensation: read. get_directory: read. search_repos: read. send_email: write (creates a SENT_EMAILS record). adjust_compensation: write (mutates employee salary in place, input.args.amount added to the record). | [derived from architecture] |
| Q4 | Parameters; use Parameter Details | See Parameter Details table for all fields (e.g. input.args.employee_id, input.args.include_ssn, input.args.amount, input.args.visibility, input.args.department, input.args.to, input.args.subject, input.args.body, input.args.repo_name) per tool, with type, required flag, and valid values. | [derived from architecture] |
| Q5 | Every user role | hr, engineer, marketing, finance, platform, security (input.extensions.subject.roles candidate list from system_vars.json). | [derived from architecture] |
| Q6 | Runtime subject provenance and integrity; use Runtime Subject Details | input.extensions.subject.roles, input.extensions.subject.permissions, and input.extensions.subject.has_approval are declared in system_vars.json but have no producing implementation or integrity/verification mechanism observed in agent.py or server.py in this tree (Phase A: documented only in the out-of-scope CPEX/Keycloak sidecar config, not implemented here). See Runtime Subject Details table. | [derived from architecture] |
| Q7 | User ID canonical path, provider, and use | No canonical user-ID field is declared in system_vars.json or any tool schema. system_vars.json declares input.extensions.subject.user_name as a fixed example value ("Bob") with no consuming code observed anywhere (Phase A). This is not usable as a verified subject identity. | [derived from architecture] |
| Q8 | Whether simultaneous roles are supported |  |  |
| Q9 | Tool permissions and scope per role; use Role Permissions | Only HR employees (input.extensions.subject.roles containing "hr") may access compensation records, including salary figures, compensation bands, and salary adjustments (get_compensation, display_compensation, adjust_compensation). Only engineers and security team members (input.extensions.subject.roles containing "engineer" or "security") may use search_repos; all other roles are blocked from it. All employees may only access internal repositories (input.args.visibility == "internal") and cannot access other teams' repositories. See Role Permissions table. | [derived from guidance.txt] |
| Q10 | Role-specific topics, values, or parameter combinations | Only employees with the view_ssn permission (input.extensions.subject.permissions containing "view_ssn") may request SSN data via get_compensation; any caller without this permission must not set input.args.include_ssn to true. HR employees may set input.args.amount up to $10,000 on adjust_compensation without additional approval; amounts greater than $10,000 require input.extensions.subject.has_approval set to true. | [derived from guidance.txt] |
| Q11 | Roles with no restrictions | No role is stated in guidance.txt as fully unrestricted across all tools. get_directory (employee directory listing) has no role restriction named in guidance.txt, so it is unrestricted for all employees by omission. | [inferred — low confidence] |
| Q12 | Globally blocked enumerable values, formats, domains, or flags | input.args.visibility values other than "internal" (i.e. "public", "external") are outside the guidance-permitted scope for all employees, since guidance rule 1 states employees can only access internal repositories. input.args.include_ssn = true is globally blocked for any caller whose input.extensions.subject.permissions does not contain "view_ssn". | [derived from guidance.txt] |
| Q13 | Numeric hard caps | input.args.amount on adjust_compensation: up to $10,000 requires no additional approval; amounts greater than $10,000 are not a hard block but require prior manager approval (see Q13b). No unconditional/hard numeric ceiling (i.e. no maximum amount beyond which approval cannot unlock the action) is stated in guidance.txt. | [derived from guidance.txt] |
| Q13b | Conditional approval paths; use Approval Paths | When input.args.amount on adjust_compensation is greater than $10,000, the action requires input.extensions.subject.has_approval == true (manager approval indicated by the has_approval flag); amounts up to and including $10,000 by HR employees require no additional approval. See Approval Paths table. | [derived from guidance.txt] |
| Q14 | Rejected patterns and their input source | SSN pattern must not appear in input.args.subject or input.args.body of send_email; any attempt to send an email with an SSN pattern in either field must be blocked. Governed input source: tool arguments (input.args.subject, input.args.body) at call time — this is a tool-argument boundary, distinct from prompt/conversation content and from previously returned tool data; guidance.txt names it explicitly as a property of the outgoing send_email call arguments, not as a restriction on user prompt text or on the LLM's conversation history. Per the shared source-boundary rule, this pattern check is scoped only to send_email's own declared input.args.* fields and must not be generalized into a prompt-level or cross-tool control. | [derived from guidance.txt] |
| Q15 | Per-session call limits; use Rate Limits |  |  |
| Q16 | Counter owner, mechanism, and canonical policy path |  |  |
| Q17 | Post-response filtering | display_compensation must return only the compensation band summary (band only), never salary figures, per its declared purpose in tool_definitions.json/system_vars.json action_description. get_compensation must redact the SSN field from its response unless the caller has the view_ssn permission and input.args.include_ssn is true; guidance rule 4 makes this an access-time gate rather than a stated post-response filtering rule, so no distinct post-response filtering step beyond the include_ssn/permission gate is stated in guidance.txt. | [derived from guidance.txt] |
| Q18 | Response fields suppressed by role | SSN field in get_compensation's response is suppressed (redacted) for any caller whose input.extensions.subject.permissions does not contain "view_ssn", regardless of input.args.include_ssn. Salary figures are suppressed entirely in display_compensation's response for all roles (band only is ever returned, per its declared purpose). | [derived from guidance.txt] |
| Q19 | Conditions making a result actionable |  |  |
| Q20 | Silent rejection or user explanation |  |  |
| Q21 | Hard-block and soft-block meanings; use Severity Levels | guidance.txt uses hard-boundary modal language ("only", "cannot", "must not", "must be blocked") for: internal-only repository access (rule 1), cross-team repository access (rule 2), compensation-record access restricted to HR (rule 3), SSN access restricted to view_ssn permission holders (rule 4), repository search restricted to engineer/security (rule 5), and the SSN-in-email pattern block (rule 7) — these are hard blocks per the shared modal-intent rule. Rule 6 (compensation adjustment approval) is a conditional gate rather than an unconditional block: amounts up to $10,000 are permitted outright for HR, and amounts above $10,000 are blocked only in the absence of input.extensions.subject.has_approval == true, making it a conditional/soft block that becomes a hard block when the approval condition is unmet. No distinct soft-block (warn-but-allow) severity tier is stated anywhere in guidance.txt. | [derived from guidance.txt] |
| Q22 | Denial logging and existing violation-code scheme | guidance.txt does not state any logging requirement for denials. No existing violation-code scheme was found in the Phase A architecture state; policy.rego is recorded only as producing generic deny[] messages and an allow boolean, with no coded violation-identifier scheme observed. This is recorded as an open gap rather than answered with an invented code list. | [derived from architecture] |

## Parameter Details

| Tool | Policy path | Type | Required | Valid values |
|---|---|---|---|---|
| get_compensation | input.args.employee_id | string | true | Employee identifier (e.g., EMP-001234); no enumerated domain declared. |
| get_compensation | input.args.include_ssn | boolean | false | true, false (default false). |
| display_compensation | input.args.employee_id | string | true | Employee identifier; no enumerated domain declared. |
| get_directory | input.args.department | string | false | Free-text department filter; no enumerated domain declared (default empty string). |
| send_email | input.args.to | string | true | No enumerated domain declared. |
| send_email | input.args.subject | string | true | No enumerated domain declared; must not contain an SSN pattern per guidance rule 7. |
| send_email | input.args.body | string | true | No enumerated domain declared; must not contain an SSN pattern per guidance rule 7. |
| search_repos | input.args.repo_name | string | false | Free-text substring filter; no enumerated domain declared (default empty string). |
| search_repos | input.args.visibility | string | true | internal, public, external. |
| adjust_compensation | input.args.employee_id | string | true | Employee identifier; no enumerated domain declared. |
| adjust_compensation | input.args.amount | integer | true | No enumerated domain declared; described as a positive raise amount, but sign/magnitude is not enforced in the tool implementation (Phase A). Numeric cap of $10,000 for no-approval path per guidance rule 6. |

## Runtime Subject Details

| Policy path | Provider | Provenance | Verification / integrity mechanism |
|---|---|---|---|
| input.extensions.subject.roles | system_vars.json | Declared candidate list (hr, engineer, marketing, finance, platform, security); documented as sourced from Keycloak JWT claims in the out-of-scope CPEX sidecar config, but no code in this tree resolves or forwards a roles array. | Documented only in the out-of-scope sidecar config (RS256 JWT via Keycloak JWKS); not implemented or verifiable in this tree. |
| input.extensions.subject.permissions | system_vars.json | Declared candidate list (view_ssn, None); documented provenance is a Keycloak claim carried through token delegation, not implemented in this tree. | Unknown in this tree; no verification observed in inspected code. |
| input.extensions.subject.has_approval | system_vars.json | Declared as a string enum "true\|false"; no code in this tree sets or forwards this value from any manager-approval workflow. | None observed; no signing/attestation of the approval flag exists in this tree. |
| input.extensions.subject.user_name | system_vars.json | Declared as a fixed example value ("Bob"); no consuming code observed anywhere. | None observed. |

## Role Permissions

| Tool | Role | Permission / scope | guidance.txt rule |
|---|---|---|---|
| get_compensation | hr | Full access to compensation records (salary, bonus, department); SSN additionally requires input.extensions.subject.permissions containing view_ssn and input.args.include_ssn == true. | 3, 4 |
| get_compensation | non-hr roles (engineer, marketing, finance, platform, security) | No access to compensation records. | 3 |
| display_compensation | hr | Access to compensation band summary only. | 3 |
| display_compensation | non-hr roles | No access. | 3 |
| adjust_compensation | hr | May adjust compensation up to $10,000 without approval; amounts above $10,000 require input.extensions.subject.has_approval == true. | 3, 6 |
| adjust_compensation | non-hr roles | No access. | 3 |
| search_repos | engineer | May search repositories, limited to internal (input.args.visibility == "internal") repositories the caller's team is authorized for. | 1, 2, 5 |
| search_repos | security | May search repositories, limited to internal (input.args.visibility == "internal") repositories the caller's team is authorized for. | 1, 2, 5 |
| search_repos | all other roles (hr, marketing, finance, platform) | Blocked from search_repos entirely. | 5 |

## Approval Paths

| Parameter condition | Approval field | guidance.txt rule |
|---|---|---|
| input.args.amount > 10000 on adjust_compensation | input.extensions.subject.has_approval == true | 6 |

## Rate Limits

| Role | Max calls per session |
|---|---|

## Severity Levels

| Level | Examples |
|---|---|
| Hard block | input.args.visibility != "internal" for repository access (rule 1); cross-team repository access (rule 2); compensation-record access by non-HR roles (rule 3); input.args.include_ssn == true without input.extensions.subject.permissions containing view_ssn (rule 4); search_repos use by roles other than engineer/security (rule 5); SSN pattern present in input.args.subject or input.args.body on send_email (rule 7). |
| Conditional block (becomes hard block when unmet) | input.args.amount > 10000 on adjust_compensation without input.extensions.subject.has_approval == true (rule 6). |

## Violation Logging

guidance.txt does not define a violation-code scheme, and no formal violation-code enum was found in the Phase A architecture state (policy.rego is recorded only as emitting generic deny[] messages, not coded violation identifiers). No violation code is invented here; the Violation Codes table is left empty and this is recorded as an open gap in the handoff rather than fabricated. [derived from architecture]

## Violation Codes

| Existing code | Meaning |
|---|---|

## Phase Handoff

- Status: PASS
- Artifact schema: questionnaire-v2
- Summary: 22 questions (Q1-Q22 including Q13b) addressed. Confidence tags used: 15 answers tagged [derived from guidance.txt], 7 answers tagged [derived from architecture], 1 answer tagged [inferred - low confidence] (Q11), 4 answers left blank as open gaps (Q8, Q15, Q16, Q19, Q20 -- see below). Tools covered: get_compensation, display_compensation, get_directory, send_email, search_repos, adjust_compensation (all 6 from tool_definitions.json). Open gaps, recorded rather than fabricated: (1) Q8 simultaneous roles -- guidance.txt and system_vars.json never state whether a caller can hold multiple roles at once or how role arrays combine for gating; this materially affects role-scope evaluation (Q9) so is flagged as a gap rather than assumed. (2) Q15/Q16 rate/counter limits -- no per-session call-count limits or counters are stated anywhere in guidance.txt, system_vars.json, or the Phase A architecture state; left blank rather than inferring a numeric limit. (3) Q19 actionability conditions and Q20 silent-rejection-vs-explanation -- guidance.txt states what must be blocked but never states how denial should be communicated to the user (silent drop vs. explanatory message) or what makes a tool result actionable; no architecture evidence fills this either, so both are left blank. (4) Q22's violation-code portion -- no existing coded violation scheme was found (only generic deny[] messages in policy.rego per Phase A); no code was invented. All field citations use fully-qualified input.args.* / input.extensions.subject.* paths per the formatting rule. Status set to PASS because every question has either a supported answer or is explicitly recorded as an open gap; no blank was silently left without justification.
