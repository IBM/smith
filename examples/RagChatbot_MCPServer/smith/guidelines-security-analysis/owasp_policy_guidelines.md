# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines

## Architecture Summary

Single MCP server (mcp_server.py, FastMCP over SSE) registering 11 tools, invoked by two alternate client orchestrators (run_llm_with_mcp.py Streamlit, fast_server.py FastAPI). No live @mcp.tool function performs a pre-execution authorization check: opa_client.py's OPAClient/UniversalOPAClient is fully built but unreachable (dead code), and LLMGuard is wired only into run_llm_with_mcp.py's chat() loop, not into fast_server.py or mcp_server.py's tool-dispatch boundary. Runtime subject fields (input.extensions.subject.id/roles/teams/approval) have no authenticated per-request provenance: roles is a self-selected UI dropdown value, id/teams are hard-coded process-wide globals, and approval is an unpopulated system_vars.json placeholder with no runtime producer. data_sources/hr_database.py unconditionally merges sensitive_data (ssn, personal_email, home_address, bank_account, tax_id, emergency_contact, healthcare fields) into view_team_compensation/export_compensation_data results before any select_fields projection. external_sharing and destination/recipient_email arguments on the compensation-sharing tools are declared but never enforced against guidance rules 6-8/17-18. purchase.amount is never compared against any role-based ceiling, and no declared field or populated subject field carries manager-approval status for rule 9's >=$200 branch. Phase C (threat_model.md) is authoritative for all 13 threat instances (T01-T13) and the ASI01/02/03/06/08/09-applicable, ASI04/05/07/10-inapplicable category assessment; this phase reuses that data rather than re-deriving it.

## Threat Disposition

| Threat ID | Field / surface | Owner | Reason |
|---|---|---|---|
| T01 | Free-text prompt content (surface #1); guidance rules 11-14 blocked phrases | Agent | Blocked phrases exist only in the free-text end-user prompt, a source distinct from input.args.* and input.extensions.subject.*; per the shared source-boundary rule a prompt-only control cannot be re-expressed as a tool-argument or subject-field predicate without a declared field carrying that text, and none exists. Fails eligibility gate #4/#6. |
| T02 | Retrieved PDF context (surface #4), work_rules_and_regulations_2016.pdf | Infrastructure | No declared tool argument or subject field carries PDF provenance/integrity; a future control (checksum/signature validation on ingestion) sits outside OPA's declared-input boundary entirely. Fails eligibility gate #2/#3. |
| T03 | user_profile (surface #2), self-declared role/department/name | Agent | user_profile is interpolated as free prompt text only; no registered tool declares it as an argument and no tool re-reads it for an authorization decision. Fails eligibility gate #2/#4. |
| T04 | Conversation history / memory_text (surface #3) | Agent | Replayed conversation memory is prompt-layer content with no declared tool argument or subject field to bind a Rego predicate to. Fails eligibility gate #2/#6. |
| T05 | MCP tool dispatch (surface #6); OPA/LLMGuard wiring (surface #7) | Infrastructure | T05 is the absence of the pre-execution enforcement point itself (OPA/LLMGuard never invoked from a live @mcp.tool function). Per the shared analysis rules, missing future OPA wiring is not itself a gap or an OPA rule to add — it is the infrastructure precondition every other OPA candidate in this phase depends on. |
| T06 | input.extensions.subject.id/roles/teams (surface #8) | Infrastructure | Subject fields have no authenticated per-request provenance (self-selected UI dropdown for roles; hard-coded process-wide globals for id/teams). Fails eligibility gate #4 (runtime conditions must use authoritative, pre-execution subject fields); this is why no candidate in this phase conditions on subject.roles. |
| T07 | view_team_compensation.select_fields, export_compensation_data.select_fields (surfaces #11, #12) | OPA | select_fields is declared by both governing tools, optional/defaults null, marked Acts on by Phase A, and rule 15 requires blocking a null/empty request. Complete missing/null/empty predicate, no prompt or output reasoning required. Passes all 7 eligibility checks. |
| T08 | view_team_compensation.select_fields (surface #11) | OPA | select_fields is declared, Acts on, and its documented enum includes ssn/personal_email/home_address/bank_account/emergency_contact; rules 3 and 16 require these never appear in the response. A contains_any deny on the submitted values is a complete, structured predicate that rejects the submitted argument directly (eligibility gate #7 carve-out) without requiring the tool to act further on it. |
| T09 | export_compensation_data.external_sharing, email_compensation_report.external_sharing (surface #13); email_compensation_report.destination, send_email.recipient_email (surfaces #14, #15) | OPA | external_sharing (boolean) and destination/recipient_email (string) are declared by their exact governing tools and available pre-execution. Although Phase A marks external_sharing/destination as Echoed and recipient_email as Ignored (never read by the implementation), gate #7's carve-out applies: a rule that directly rejects a submitted value does not require the tool to act on it. Deny-on-submitted-value predicates for external_sharing=true (rules 17-18) and blocked-domain substrings (rule 8) are complete and structured. |
| T10 | send_email.email_content (surface #16) | Tool implementation | Distinguishing compensation/salary/payroll content from general content (rule 6) requires semantic interpretation of free text, not an operator-based predicate over a declared field value. Fails eligibility gate #5/#6 (no complete Rego-translatable predicate without content/prompt reasoning). |
| T11 | purchase.amount (surface #18); no declared/populated approval field | Infrastructure | Both branches of rules 9-10 are role-conditioned, and subject.roles is non-authoritative (T06), so no role-scoped ceiling passes gate #4 today. Separately, rule 9's >=$200-with-approval branch has no declared purchase argument or populated subject field carrying approval status (Phase A/B carried-forward gap); inventing one is prohibited. Fails eligibility gate #2/#3/#4; no candidate emitted. |
| T12 | return_product.amount (surface #20) | Tool implementation | Validating a refund amount against an actual prior purchase requires a purchase-record lookup that is not a declared tool argument or subject field on return_product. Fails eligibility gate #2/#3. |
| T13 | Denial-message 🚫 prefix convention (surface #21) | Agent | The bypass is triggered by inspecting LLM-generated output text (actor = LLM, not Caller) for a leading character; output inspection is explicitly excluded by eligibility gate #6, and no declared tool argument carries this text pre-execution. |

## OWASP Top 10 for Agentic AI Security — Scope Assessment

| OWASP | Scope | OPA threat IDs | Other-layer threat IDs | Reason / owner |
|---|---|---|---|---|
| ASI01 | Other-layer |  | T01, T02, T03, T04 | All four ASI01 threats are prompt-layer manipulations (blocked phrases, indirect PDF injection, self-declared user_profile, conversation-memory replay) with no declared tool-argument or subject-field source; owned by Agent/Infrastructure per Threat Disposition, not OPA. |
| ASI02 | Partial | T07, T08, T09 | T05, T10, T11, T12 | Sensitive-field/select_fields and external-sharing/domain threats (T07-T09) bind to declared, pre-execution, Acts-on tool arguments and are OPA-eligible. The missing dispatch-level enforcement point (T05), content-type judgment (T10), role-conditioned purchase ceiling/approval (T11), and refund-record validation (T12) each fail one or more eligibility checks and remain with Infrastructure/Tool implementation. |
| ASI03 | Other-layer |  | T06 | Identity/privilege abuse is bounded to unauthenticated, non-session-bound subject fields (T06); no authoritative pre-execution subject field exists for a Rego predicate to use, so this category has no OPA-eligible candidate today — it is the infrastructure precondition (authenticated identity) every role-conditioned rule in ASI02/ASI08 would need. |
| ASI06 | Other-layer |  | T04 | Session-scoped conversation-history replay (T04) is prompt-layer content with no declared field; owned by Agent, not OPA. |
| ASI08 | Other-layer |  | T04 | The single-agent hallucination-propagation boundary reuses T04's evidence and disposition; no distinct OPA-eligible surface exists beyond what ASI06 already covers. |
| ASI09 | Other-layer |  | T13 | The denial-message-prefix output-scanning bypass (T13) requires inspecting LLM-generated output text; owned by Agent, excluded from OPA by the no-output-inspection eligibility check. |

## Gap Register

| Finding ID | Layer | Recommended action |
|---|---|---|
| G1 | Agent / prompt boundary | Rules 11-14's blocked phrases (T01) have no declared tool-argument or subject-field carrier; enforcement must remain at the prompt/LLMGuard layer in both client entry points (fast_server.py currently has none) rather than as an OPA predicate, unless a future architecture copies the raw prompt text into a declared tool argument. |
| G2 | Infrastructure / external data | T02's PDF-injection risk needs a content-integrity control (checksum/signature validation, CDR) at PDF ingestion in rag_pipeline.py; no declared field exists for OPA to gate on. |
| G3 | Infrastructure / identity | T06 (and by extension every role-conditioned branch of T07/T08/T09/T11) needs an authenticated, session-bound mechanism to populate input.extensions.subject.roles/id/teams before any role-scoped Rego predicate can be trustworthy. Until then, only unconditional (all-role) argument-value denials are OPA-eligible. |
| G4 | Tool implementation | T10 needs a content-classification step (or a required content_type argument) on send_email before a compensation-content restriction (rule 6) could become structured and OPA-expressible; today it requires semantic judgment over free text. |
| G5 | Tool implementation / data model | T11's approval branch (rule 9, >=$200) has no declared purchase.approval argument and no populated subject.approval field (system_vars.json's placeholder is never set at runtime); a structured field must be added to the tool/data model before this branch is OPA-expressible. The manager/employee amount ceilings themselves also cannot be gated today because subject.roles is non-authoritative (see G3). |
| G6 | Tool implementation | T12 needs return_product to declare a reference to an actual purchase/order record (e.g. an order_id argument validated against purchase history) before a refund-amount check becomes structured and OPA-expressible. |
| G7 | Agent / output boundary | T13's 🚫-prefix output-scan bypass is an output-inspection concern on LLM-generated text, categorically excluded from OPA candidacy; fix by removing the bypass condition in run_llm_with_mcp.py's enforce_output rather than adding a policy rule. |
| G8 | Tool implementation / policy | Rule 7's positive requirement ("compensation data may only be shared externally to @ibm.com addresses") is not expressible with the available deny-only operator set (no not_contains/domain-suffix operator); only the overlapping blocked-domain-list portion (rule 8) is emitted as an OPA candidate (T09). A future policy engine extension supporting a domain-suffix allowlist operator would be needed to fully encode rule 7. |

## Policy Rules (OPA scope only)

Five threats (T07, T08, T09) yield OPA-eligible deny candidates against declared, pre-execution tool arguments on view_team_compensation, export_compensation_data, email_compensation_report, and send_email. No candidate depends on input.extensions.subject.roles (or any other runtime subject field), because Phase A/C establish that field as unauthenticated and non-authoritative (T06) — the eligibility gate's requirement for authoritative, pre-execution subject fields is not met for any role-conditioned rule (this is why T11's purchase-ceiling/approval threat, and any role-scoped variant of T07/T08/T09, is excluded from OPA scope and recorded in the Gap Register instead). All emitted rules are unconditional (apply to every caller/role) argument-value denials, which the eligibility gate's outcome-claim carve-out permits without requiring the tool to act further on the rejected value.

### Input Schema

| Field | Source |
|---|---|
| input.args.select_fields | view_team_compensation, export_compensation_data (tool_definitions.json; optional, default null, array[string]) |
| input.args.external_sharing | export_compensation_data, email_compensation_report (tool_definitions.json; optional, default false, boolean) |
| input.args.destination | email_compensation_report (tool_definitions.json; required, string) |
| input.args.recipient_email | send_email (tool_definitions.json; required, string) |

### Known values

Tools (tool_definitions.json): create_ticket, submit_ticket, send_email, export_content_as_file, ask_for_workpolicy, get_w2_form, return_product, view_team_compensation, export_compensation_data, email_compensation_report, purchase. Sensitive select_fields values referenced by rules 3/16: ssn, personal_email, home_address, bank_account, emergency_contact (all declared in view_team_compensation's documented Available fields; tax_id is named in guidance rule 3 but is not a declared select_fields value on any tool, so it cannot be bound to an argument-level predicate). Blocked domains referenced by rule 8: gmail.com, yahoo.com, hotmail.com, outlook.com, personal.com. No existing violation-code scheme exists (Phase B Violation Codes table is empty); this phase originates the first codes (OPA-D01 through OPA-D04).

### Rules

| Code | OWASP | Threat IDs | Severity | Tool(s) / field | Condition | Matching |
|---|---|---|---|---|---|---|
| OPA-D01 | ASI02 | T07 | Critical | view_team_compensation.select_fields, export_compensation_data.select_fields | select_fields is missing, null, or an empty array | missing/null/empty; applies to every caller/role (no subject scope) |
| OPA-D02 | ASI02 | T08 | Critical | view_team_compensation.select_fields | select_fields contains any of: ssn, personal_email, home_address, bank_account, emergency_contact | contains_any {ssn, personal_email, home_address, bank_account, emergency_contact}; applies to every caller/role (no subject scope) |
| OPA-D03 | ASI02 | T09 | High | export_compensation_data.external_sharing, email_compensation_report.external_sharing | external_sharing equals true | eq true; applies to every caller/role (no subject scope) |
| OPA-D04 | ASI02 | T09 | High | email_compensation_report.destination, send_email.recipient_email | destination or recipient_email contains any of: gmail.com, yahoo.com, hotmail.com, outlook.com, personal.com | contains_any {gmail.com, yahoo.com, hotmail.com, outlook.com, personal.com}; applies to every caller/role (no subject scope) |

## Candidate Reconciliation

| Candidate ID | Tool | Subject scope | Field expression | Operator | Values | Action | Sources | Related rule | Guidance group | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| C1 | view_team_compensation | all | input.args.select_fields | missing/null/empty |  | deny | T07, Q1 | 15 | G-select-fields-required | Covered |
| C2 | export_compensation_data | all | input.args.select_fields | missing/null/empty |  | deny | T07, Q1 | 15 | G-select-fields-required | Covered |
| C3 | view_team_compensation | all | input.args.select_fields | contains_any | ssn, personal_email, home_address, bank_account, emergency_contact | deny | T08, Q1 | 3, 16 | G-sensitive-fields-blocked | Covered |
| C4 | export_compensation_data | all | input.args.external_sharing | eq | true | deny | T09, Q1 | 17 | G-external-sharing-blocked | Covered |
| C5 | email_compensation_report | all | input.args.external_sharing | eq | true | deny | T09, Q1 | 18 | G-external-sharing-blocked | Covered |
| C6 | email_compensation_report | all | input.args.destination | contains_any | gmail.com, yahoo.com, hotmail.com, outlook.com, personal.com | deny | T09, Q1 | 8 | G-blocked-domains | Covered |
| C7 | send_email | all | input.args.recipient_email | contains_any | gmail.com, yahoo.com, hotmail.com, outlook.com, personal.com | deny | T09, Q1 | 8 | G-blocked-domains | Additive |

## Existing Guidance Normalization

| Existing ID | Rule number | Tool | Subject scope | Field expression | Operator | Values | Action |
|---|---|---|---|---|---|---|---|
| E-15 | 15 | view_team_compensation | all | input.args.select_fields | missing/null/empty |  | deny |
| E-15b | 15 | export_compensation_data | all | input.args.select_fields | missing/null/empty |  | deny |
| E-3-16 | 3 | view_team_compensation | all | input.args.select_fields | contains_any | ssn, home_address, bank_account, emergency_contact, personal_email | deny |
| E-17 | 17 | export_compensation_data | all | input.args.external_sharing | eq | true | deny |
| E-18 | 18 | email_compensation_report | all | input.args.external_sharing | eq | true | deny |
| E-8a | 8 | email_compensation_report | all | input.args.destination | contains_any | gmail.com, hotmail.com, outlook.com, personal.com, yahoo.com | deny |

## Prior Proposal Reconciliation

| Prior ID | Original number | Normalized rule | Disposition | Candidate / reason |
|---|---|---|---|---|

## Phase Handoff

- Status: PASS
- Artifact schema: enforcement-mapping-v8
- Summary: All 13 Phase C threats (T01-T13) mapped exactly once in Threat Disposition: 3 to OPA (T07, T08, T09), 4 to Agent (T01, T03, T04, T13), 3 to Infrastructure (T02, T05, T06), 1 split Infrastructure (T11, both role-authoritativeness and approval-field gaps), 2 to Tool implementation (T10, T12). ASI category scope: ASI02 Partial (OPA + other-layer), ASI01/ASI03/ASI06/ASI08/ASI09 Other-layer only (no OPA-eligible surface survived their eligibility checks). 7 candidates emitted (C1-C7) after normalizing existing guidance (rules 3, 8, 15, 16, 17, 18) into the Existing Guidance Normalization table: C1-C6 (select_fields-required, sensitive-fields-blocked, external-sharing-blocked, and blocked-domains-on-email_compensation_report groups) are Enforcement-mapping realizations of already-closed guidance rules -> Covered, emit nothing (in particular, rules 3+16 read together already cover C3's full sensitive-field set, and rule 8's normalized form (E-8a) already names email_compensation_report.destination exactly, so C6 is a duplicate, not an addition). Only C7 (blocked-domain list applied to send_email.recipient_email) is Additive: guidance.txt's rule 8 states the blocked-domain rule at the request level without naming send_email specifically, and Phase A confirms recipient_email is a distinct tool argument declared on a different tool (send_email) that is not read at all today; per the guide's rule that a new request-level hard block is not automatically covered by wording elsewhere, applying the same blocked-domain deny to send_email.recipient_email is an independently expressible uncovered set for that tool. C6 and C7 share Guidance group G-blocked-domains, but since C6 is Covered (not emitted) and only C7 is Additive (emitted), exactly one addendum rule is produced for that group, describing only the send_email.recipient_email extension. No Overlap/Conflict/Contradictory correction relationship exists. Gap Register: G1-G8 (blocked phrases T01, PDF integrity T02, subject-field authoritativeness T06/T11, send_email content classification T10, purchase approval field T11, return_product purchase-record reference T12, output-scan bypass T13, rule-7 positive-domain operator gap). guidance_updated.txt written with 1 Additive rule (numbered 20) applying the rule-8 blocked-domain list to send_email's recipient_email argument. No Rego was written and no merge occurred; only owasp_policy_guidelines.json/.md were produced.
