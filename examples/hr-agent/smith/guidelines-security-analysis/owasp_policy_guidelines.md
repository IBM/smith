# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines

## Architecture Summary

Single-agent HR system (agent.py) driving a mock MCP tool server (server.py) over direct HTTP (MCP_PROXY empty in the local/Smith-run configuration). Six tools: get_compensation, display_compensation, get_directory, send_email, search_repos, adjust_compensation — all declared in tool_definitions.json. server.py performs zero pre-execution authorization/content checks in this tree; the only existing enforcement is the offline policy.rego (7 deny rules) evaluated by Smith's own policy-testing harness, not wired into the live request path. Runtime subject fields (input.extensions.subject.roles, .permissions, .has_approval, .user_name) are declared in system_vars.json but have no producing implementation observed in agent.py/server.py — their documented provenance (Keycloak JWT via an authbridge-cpex sidecar) is out of scope for this tree. Per Phase C, applicable OWASP categories are ASI02 (Yes), ASI01 and ASI06 (Partial); all others No.

## Threat Disposition

| Threat ID | Field / surface | Owner | Reason |
|---|---|---|---|
| T01 | input.args.employee_id, input.args.include_ssn (get_compensation) | OPA | Passes the eligibility gate: get_compensation declares both input.args.employee_id and input.args.include_ssn; the deny condition (include_ssn == true without input.extensions.subject.permissions containing view_ssn, or caller lacking hr role) is a complete Rego-translatable predicate with no prompt reasoning or output inspection needed. Already encoded in policy.rego as SSN_VIEW_PERM and COMP_HR_ONLY. |
| T02 | input.args.employee_id (get_compensation, display_compensation) | OPA | Non-HR caller access to compensation tools is a complete predicate on input.extensions.subject.roles alone (no args needed beyond tool name). Already encoded in policy.rego as COMP_HR_ONLY. |
| T03 | input.args.include_ssn (get_compensation), SYSTEM_PROMPT | Agent | The failure mode is the LLM being induced by prompt phrasing to set include_ssn=true when the request was not an explicit SSN ask. No structured, pre-execution signal distinguishes an 'explicit ask' from an induced one — deciding this requires prompt/intent reasoning, which the eligibility gate excludes (check 6). The resulting include_ssn=true value is itself still gated by the OPA-eligible T01 rule, so this threat's own remediation is agent-side prompt/behavior hardening, not a new OPA predicate. |
| T04 | input.args.to (send_email) | Agent | No guidance rule, system_vars.json field, or tool schema names a recipient allowlist/domain restriction; inventing one would violate the rule against fabricating fields/values to make a candidate pass. Recorded in the Gap Register rather than emitted as a candidate. |
| T05 | input.args.subject, input.args.body (send_email); conversation history | Agent | The threat's core claim is the broader 'sensitive data accessed earlier in-session' carry-over (salary figures, internal_notes) which has no structured/OPA-visible signal in input.args or input.extensions.subject — fails eligibility check 6 (would require inspecting conversation history / prior tool outputs, not declared tool arguments). The narrower SSN-regex slice of this concern is separately already OPA-covered by the existing EMAIL_SSN_BLOCK rule (guidance rule 7), which is unaffected by this disposition. |
| T06 | send_email call volume (no declared field) | Infrastructure | No per-session call-count field, counter, or rate-limit value is declared anywhere in guidance.txt, system_vars.json, or tool_definitions.json (Phase B Q15/Q16 open gap); rate limiting of this kind is conventionally an infrastructure/gateway concern and there is no declared structured input to ground a Rego predicate on. Recorded in the Gap Register. |
| T07 | input.extensions.subject.roles (search_repos) | OPA | Complete predicate on caller role membership vs. the fixed engineer/security set; no args needed. Already encoded in policy.rego as REPO_ROLE_GATE. |
| T08 | input.args.visibility (search_repos) | OPA | Complete predicate: input.args.visibility != "internal" (declared enum field on search_repos). Already encoded in policy.rego as REPO_INTERNAL_ONLY. |
| T09 | input.args.amount, input.extensions.subject.has_approval (adjust_compensation) | OPA | Complete predicate: input.args.amount > 10000 AND input.extensions.subject.has_approval != "true". Already encoded in policy.rego as ADJ_APPROVAL_THRESHOLD. That has_approval currently has no producing implementation (see T11) does not disqualify the rule — existing/future OPA wiring and runtime population are not required for OPA-policy-expressibility per the shared rule. |
| T10 | input.args.amount (adjust_compensation) | OPA | Complete predicate: input.args.amount < 0 (declared, required, integer field on adjust_compensation, which acts on it via `employee['salary'] += amount`). No subject field, prompt reasoning, or output inspection needed. Passes all 7 eligibility checks; this is the one new (Novel) candidate identified in this phase — see Rules/Input Schema/Candidate Reconciliation. |
| T11 | input.extensions.subject.roles, input.extensions.subject.permissions | Infrastructure | Fails eligibility check 4: runtime conditions must use authoritative, pre-execution subject fields, and these fields have no producing implementation anywhere in this tree — there is no authoritative value to ground a predicate on, only an unpopulated placeholder. This is an identity-provisioning gap (populating roles/permissions from a verified source), not an OPA rule to author; recorded in the Gap Register, not emitted as a candidate. |
| T12 | user_text, conversation history | Agent | Fails eligibility checks 1 and 6: detecting induced goal/tool selection requires prompt/intent reasoning over untrusted natural-language input, not a structured tool-argument or subject-field predicate. Mitigation is agent-side (prompt hardening, intent validation before dispatch), consistent with ASI01 mitigations. |
| T13 | LLM tool_calls JSON (function.arguments) | Agent | The failure is agent.py's own error-handling behavior (silently substituting {} on JSON decode failure instead of rejecting the call) — this is application logic prior to any policy-input construction, not a condition expressible over input.args/input.extensions.subject values themselves. |
| T14 | get_compensation response body (internal_notes) | Tool implementation | This is response content returned by the tool, not an input.args.* field the caller supplies or a subject field — the shared OPA-policy-expressibility rule requires declared structured inputs to a pre-execution decision, and response content is a distinct boundary (Phase A: 'not OPA-interceptable ... it is response content, a different boundary than input.args'). Remediation is removing/redacting the field in server.py's tool implementation, not an OPA rule. |

## OWASP Top 10 for Agentic AI Security — Scope Assessment

| OWASP | Scope | OPA threat IDs | Other-layer threat IDs | Reason / owner |
|---|---|---|---|---|
| ASI01 | Other-layer |  | T12 | Phase C rated ASI01 Partial (narrow prompt-injection/goal-selection surface only). Its sole grounded threat instance, T12, fails the eligibility gate (requires prompt/intent reasoning) and is owned by Agent; no OPA-eligible threat exists under this category, so Scope is Other-layer rather than Partial (the guide reserves Partial for categories with both OPA and other-layer threats). |
| ASI02 | Partial | T01, T02, T07, T08, T09, T10 | T03, T04, T05, T06, T11, T13, T14 | Phase C rated ASI02 Yes (the dominant category: every tool executes with zero pre-execution authorization). Six of its threat instances are OPA-eligible (role/permission/visibility/amount gates, including the new T10 sign check); seven are owned by Agent, Infrastructure, or Tool implementation (prompt-level reliability, unnamed recipient control, session-content reuse, rate limiting, unpopulated subject provenance, JSON error handling, and response-content leakage). Both OPA and other-layer threats exist, so Scope is Partial. |
| ASI03 | Not applicable |  |  | Phase C rated ASI03 No — no delegation chain, agent-to-agent trust, or credential caching/reuse exists in this tree; no threat instances were grounded under this category. |
| ASI04 | Not applicable |  |  | Phase C rated ASI04 No — no dynamically loaded third-party tools, plugins, or registries exist; TOOLS/server.py are hardcoded local code. No threat instances grounded. |
| ASI05 | Not applicable |  |  | Phase C rated ASI05 No — no tool generates or executes code, shell commands, or deserializes objects. No threat instances grounded. |
| ASI06 | Other-layer |  | T05 | Phase C rated ASI06 Partial (narrow in-session carry-over slice only, not persistent/cross-session memory poisoning). Its sole grounded threat instance under this ASI, T05, is owned by Agent for the reasons in Threat Disposition (no structured signal for the broader carry-over claim); the narrow SSN-regex slice is already covered by the existing EMAIL_SSN_BLOCK rule but that coverage is recorded under guidance rule 7 / T01 family, not as a distinct OPA threat instance filed under ASI06. No OPA threat instance is filed under ASI06 itself, so Scope is Other-layer rather than Partial. |
| ASI07 | Not applicable |  |  | Phase C rated ASI07 No — single agent, single mock MCP server, no peer agents or message bus. No threat instances grounded. |
| ASI08 | Not applicable |  |  | Phase C rated ASI08 No — single agent, no downstream agents/workflows for a fault to cascade into. No threat instances grounded. |
| ASI09 | Not applicable |  |  | Phase C rated ASI09 No — backend HR agent with no separate human reviewer being persuaded and no agent-initiated persuasive interaction pattern. No threat instances grounded. |
| ASI10 | Not applicable |  |  | Phase C rated ASI10 No — single-agent system, no peer agents or multi-agent ecosystem. No threat instances grounded. |

## Gap Register

| Finding ID | Layer | Recommended action |
|---|---|---|
| G01 | Runtime subject provenance (Agent / Infrastructure) | The 'team' field needed by guidance rule 2 (cross-team repository access restriction) is declared nowhere in system_vars.json or any tool schema (Phase A Undeclared Fields; corroborated by smith/extension_suggestions.json). Guidance rule 2 cannot be encoded as an OPA predicate until a caller-team field and a repo-team-ownership field are both declared and populated. Recommended action: a human decision to add and populate these fields is required before this rule can be enforced at the OPA boundary; do not invent the field. |
| G02 | Infrastructure / gateway | No per-session call-count limits or counters for any tool (including send_email, T06) are stated in guidance.txt, system_vars.json, or tool_definitions.json (Phase B Q15/Q16 open gap). Recommended action: a human decision on whether and how to define rate limits (and whether they belong in OPA via a declared counter field, or purely at an infrastructure/gateway layer) is required; none is assumed here. |
| G03 | Runtime subject provenance (Infrastructure) | input.extensions.subject.roles, .permissions, and .has_approval (T11) are declared in system_vars.json but have no producing implementation in agent.py/server.py in this tree; their documented provenance (Keycloak JWT via an out-of-scope CPEX sidecar) is not implemented here. Recommended action: wiring an authoritative identity/approval source into the live request path is an infrastructure task, not an OPA rule; existing policy.rego rules that reference these fields (COMP_HR_ONLY's fallback, SSN_VIEW_PERM, ADJ_APPROVAL_THRESHOLD) remain correctly OPA-expressible but will receive Unknown/unpopulated values until this is resolved. Not treated as missing OPA wiring (excluded from Gap Register scope by the guide) — filed here specifically because it is a provenance/identity gap, not an OPA-wiring gap. |
| G04 | Tool implementation | get_compensation's response includes the internal_notes field to any successful caller (T14); no guidance rule or policy.rego rule addresses it, and it is response content — a different boundary than input.args, so it is not OPA-interceptable. Recommended action: a human decision to either remove internal_notes from the tool's response or add an explicit guidance rule governing it (enforceable via response filtering, not OPA) is required. |
| G05 | Agent | send_email has no recipient allowlist/domain restriction in guidance.txt or any declared field (T04); a caller can direct the agent to relay legitimately retrieved data to an arbitrary address. Recommended action: a human decision on whether to add a recipient-domain guidance rule (and a corresponding declared field) is required before this can become an OPA candidate; none is invented here. |
| G06 | Agent / conversation memory | The broader in-session sensitive-data carry-over concern named in system_vars.json's send_email description ('data the caller accessed earlier as sensitive in the same session', T05) has no structured/OPA-visible signal (no session-taint field is declared anywhere). Recommended action: a human decision on whether to introduce a session-taint or provenance-tagging mechanism (and declare it as a structured field) is required; the existing SSN-regex check (EMAIL_SSN_BLOCK) already covers the narrower pattern-matchable slice and is unaffected. |
| G07 | Agent | Phase B Q19 (conditions making a tool result actionable) and Q20 (silent rejection vs. user-facing explanation on denial) are open gaps — guidance.txt never states how a denial should be communicated to the user, and no architecture evidence fills this either. Recommended action: a human decision on denial UX/messaging is required; not assumed here and not something an OPA predicate itself determines. |
| G08 | Agent | agent.py silently substitutes {} for tool_calls arguments on JSON-decode failure (T13, Phase A Trust Boundary #2) instead of rejecting the call; this is an agent-side error-handling defect, not an OPA-expressible condition (there is no malformed-arguments signal reaching a structured input.args.* field distinguishably from a legitimately-empty call). Recommended action: a human decision to change agent.py's error handling (fail closed on decode failure) is required at the agent-implementation layer. |

## Policy Rules (OPA scope only)

This phase records only whether a rule is OPA-policy-expressible per the shared rule and the 7-point eligibility gate; no Rego is written here. One new eligible candidate was found beyond the seven rules already in smith/smith_outputs/policy.rego: a sign/negative-value check on input.args.amount (adjust_compensation), grounded in T10 (Critical, financial-integrity break) and not covered by guidance.txt rule 6 (which only gates amounts above $10,000, not negative amounts) or by any existing policy.rego rule.

### Input Schema

| Field | Source |
|---|---|
| input.args.employee_id | get_compensation, display_compensation, adjust_compensation (tool_definitions.json; string, required) |
| input.args.include_ssn | get_compensation (tool_definitions.json; boolean, optional, default false) |
| input.args.visibility | search_repos (tool_definitions.json; string, required, enum internal/public/external) |
| input.args.amount | adjust_compensation (tool_definitions.json; integer, required, no declared sign/magnitude constraint) |
| input.args.subject | send_email (tool_definitions.json; string, required) |
| input.args.body | send_email (tool_definitions.json; string, required) |
| input.extensions.subject.roles | system_vars.json (declared candidate list: hr, engineer, marketing, finance, platform, security) |
| input.extensions.subject.permissions | system_vars.json (declared candidate list: view_ssn, None) |
| input.extensions.subject.has_approval | system_vars.json (declared string enum "true"\|"false") |

### Known values

Existing violation codes reused from smith/smith_outputs/policy.rego: REPO_INTERNAL_ONLY, COMP_HR_ONLY, SSN_VIEW_PERM, REPO_ROLE_GATE, ADJ_APPROVAL_THRESHOLD, EMAIL_SSN_BLOCK. New code created for the one genuinely novel candidate: ADJ_NO_NEGATIVE (consistent with the existing ADJ_* prefix used for adjust_compensation rules).

### Rules

| Code | OWASP | Threat IDs | Severity | Tool(s) / field | Condition | Matching |
|---|---|---|---|---|---|---|
| COMP_HR_ONLY | ASI02 | T02 | High | get_compensation, display_compensation, adjust_compensation / input.extensions.subject.roles | deny when the tool is one of {get_compensation, display_compensation, adjust_compensation} and "hr" is not in input.extensions.subject.roles | in / not_in (set membership on roles); exact string match on tool name |
| SSN_VIEW_PERM | ASI02 | T01 | Critical | get_compensation / input.args.include_ssn, input.extensions.subject.permissions | deny when tool == get_compensation and input.args.include_ssn == true and "view_ssn" is not in input.extensions.subject.permissions | eq on include_ssn (boolean true); not_in (set membership) on permissions |
| REPO_ROLE_GATE | ASI02 | T07 | High | search_repos / input.extensions.subject.roles | deny when tool == search_repos and none of {"engineer", "security"} is in input.extensions.subject.roles | not_in (set intersection empty) on roles |
| REPO_INTERNAL_ONLY | ASI02 | T08 | High | search_repos / input.args.visibility | deny when tool == search_repos and input.args.visibility != "internal" | neq (case-insensitive per Phase A tool behavior) on visibility |
| ADJ_APPROVAL_THRESHOLD | ASI02 | T09 | High | adjust_compensation / input.args.amount, input.extensions.subject.has_approval | deny when tool == adjust_compensation and input.args.amount > 10000 and input.extensions.subject.has_approval != "true" | gt on amount (integer 10000); neq on has_approval (string "true") |
| EMAIL_SSN_BLOCK | ASI02 | T01 (narrow slice referenced by T05's covered portion) | Critical | send_email / input.args.subject, input.args.body | deny when tool == send_email and (input.args.subject or input.args.body) matches an SSN pattern (\d{3}-\d{2}-\d{4} or 9 bare digits) | contains_any (regex match) on subject/body |
| ADJ_NO_NEGATIVE | ASI02 | T10 | Critical | adjust_compensation / input.args.amount | deny when tool == adjust_compensation and input.args.amount < 0 | lt on amount (integer 0); no subject dependency; no default/missing-value ambiguity since amount is a required field with no declared default |

## Candidate Reconciliation

| Candidate ID | Tool | Subject scope | Field expression | Operator | Values | Action | Sources | Related rule | Guidance group | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| C01a | get_compensation | input.extensions.subject.permissions | input.args.include_ssn | eq | true | deny | T01 | SSN_VIEW_PERM (policy.rego) | SSN-permission gate | Duplicate |
| C01b | get_compensation | input.extensions.subject.permissions | input.extensions.subject.permissions | not_in | view_ssn | deny | T01 | SSN_VIEW_PERM (policy.rego) | SSN-permission gate | Duplicate |
| C02a | get_compensation | input.extensions.subject.roles | input.extensions.subject.roles (gates tool call itself) | not_in | hr | deny | T02 | COMP_HR_ONLY (policy.rego) | HR-only compensation access | Duplicate |
| C02b | display_compensation | input.extensions.subject.roles | input.extensions.subject.roles (gates tool call itself) | not_in | hr | deny | T02 | COMP_HR_ONLY (policy.rego) | HR-only compensation access | Duplicate |
| C02c | adjust_compensation | input.extensions.subject.roles | input.extensions.subject.roles (gates tool call itself) | not_in | hr | deny | T02 | COMP_HR_ONLY (policy.rego) | HR-only compensation access | Duplicate |
| C03 | search_repos | input.extensions.subject.roles | input.extensions.subject.roles (gates tool call itself) | not_in | engineer, security | deny | T07 | REPO_ROLE_GATE (policy.rego) | Repo search role gate | Duplicate |
| C04 | search_repos | none | input.args.visibility | neq | internal | deny | T08 | REPO_INTERNAL_ONLY (policy.rego) | Internal-only repository access | Duplicate |
| C05a | adjust_compensation | none | input.args.amount | gt | 10000 | deny | T09 | ADJ_APPROVAL_THRESHOLD (policy.rego) | Compensation-adjustment approval threshold | Duplicate |
| C05b | adjust_compensation | input.extensions.subject.has_approval | input.extensions.subject.has_approval | neq | true | deny | T09 | ADJ_APPROVAL_THRESHOLD (policy.rego) | Compensation-adjustment approval threshold | Duplicate |
| C06 | send_email | none | input.args.subject, input.args.body | contains_any | SSN pattern (regex) | deny | T01, T05 | EMAIL_SSN_BLOCK (policy.rego) | SSN-in-email content block | Duplicate |
| C07 | adjust_compensation | none | input.args.amount | lt | 0 | deny | T10 | none (no existing policy.rego rule or guidance.txt rule addresses sign; guidance.txt rule 6 only gates amounts > 10000, silent on negative values) | Compensation-adjustment sign integrity | Novel |

## Existing Guidance Normalization

| Existing ID | Rule number | Tool | Subject scope | Field expression | Operator | Values | Action |
|---|---|---|---|---|---|---|---|
| EG1 | 1 | search_repos | none | input.args.visibility | neq | internal | deny |
| EG3a | 3 | get_compensation | input.extensions.subject.roles | input.extensions.subject.roles (gates tool call itself) | not_in | hr | deny |
| EG3b | 3 | display_compensation | input.extensions.subject.roles | input.extensions.subject.roles (gates tool call itself) | not_in | hr | deny |
| EG3c | 3 | adjust_compensation | input.extensions.subject.roles | input.extensions.subject.roles (gates tool call itself) | not_in | hr | deny |
| EG4a | 4 | get_compensation | input.extensions.subject.permissions | input.args.include_ssn | eq | true | deny |
| EG4b | 4 | get_compensation | input.extensions.subject.permissions | input.extensions.subject.permissions | not_in | view_ssn | deny |
| EG5 | 5 | search_repos | input.extensions.subject.roles | input.extensions.subject.roles (gates tool call itself) | not_in | engineer, security | deny |
| EG6a | 6 | adjust_compensation | none | input.args.amount | gt | 10000 | deny |
| EG6b | 6 | adjust_compensation | input.extensions.subject.has_approval | input.extensions.subject.has_approval | neq | true | deny |
| EG7 | 7 | send_email | none | input.args.subject, input.args.body | contains_any | SSN pattern (regex) | deny |

## Prior Proposal Reconciliation

| Prior ID | Original number | Normalized rule | Disposition | Candidate / reason |
|---|---|---|---|---|

## Phase Handoff

- Status: PASS
- Artifact schema: enforcement-mapping-v8
- Summary: 14 threats (T01-T14) mapped: OPA=6 (T01, T02, T07, T08, T09, T10), Agent=5 (T03, T04, T05, T12, T13), Infrastructure=2 (T06, T11), Tool implementation=1 (T14). OWASP scope: ASI02=Partial (6 OPA + 7 other-layer threats), ASI01 and ASI06=Other-layer (each has exactly one grounded threat instance, owned outside OPA, so Partial does not apply per the guide's definition), ASI03/04/05/07/08/09/10=Not applicable (Phase C: No, zero grounded threat instances). 8 gap-register findings (G01-G08) covering the 'team' field, rate limiting, unpopulated subject provenance, the internal_notes response leak, the unaddressed send_email recipient control, the broader session-content-reuse concern, the Q19/Q20 denial-UX open questions, and agent.py's malformed-JSON silent-{} substitution. 7 OPA candidates reconciled against the 7 existing policy.rego/guidance.txt rules: 6 are Duplicate (C01-C06, restating SSN_VIEW_PERM, COMP_HR_ONLY, REPO_ROLE_GATE, REPO_INTERNAL_ONLY, ADJ_APPROVAL_THRESHOLD, EMAIL_SSN_BLOCK — identical deny behavior to existing coverage); 1 is Novel (C07: a negative/sign check on input.args.amount for adjust_compensation, grounded in T10, not addressed by guidance.txt rule 6 which only gates amounts above $10,000, and not present in policy.rego). No Clarification, Overlap, Conflict, or Contradictory correction found, so no blocking relationship exists. Prior Proposal Reconciliation is empty (GUIDANCE_UPDATE_FILE was ABSENT). Addendum written to guidance_updated.txt with one plain line for the C07/ADJ_NO_NEGATIVE Novel finding, matching guidance.txt's flat one-rule-per-line style. Status: PASS.
