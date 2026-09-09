# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines
# Tool: RagChatbot_MCPServer

---

## Architecture Summary

`RagChatbot_MCPServer` is an HR assistant that exposes 11 tools over SSE (FastMCP, port 8000), dispatched by a `max_turns=10` LLM agent loop in `fast_server.py`. All tool arguments arrive as caller-supplied, LLM-generated structured fields at the MCP Tool Layer; role state comes from a process-global `current_user_context` initialized at server start and unmodifiable at runtime. No OPA enforcement is currently active — all `@policy_check` decorators are commented out — but the MCP Tool Layer is the sole viable pre-execution interception point.

---

## OWASP Top 10 for Agentic AI Security — Scope Assessment

### ASI01 — Agent Goal Hijack
**Risk:** Attackers redirect agent goals through prompt injection, deceptive tool outputs, or poisoned external data.
**Verdict:** Partial — OPA can enforce substring-match denials on free-text arguments (`ticket_content`, `question`, `body`, `email_content`, `report_data`) that carry known goal-hijacking phrases. The broader goal-hijack vectors — injection into the system prompt via `user_profile`, fabricated `history`, LLM-internal plan injection, and RAG content poisoning — are not visible as structured fields at tool-invocation time and are out of OPA scope.

### ASI02 — Tool Misuse and Exploitation
**Risk:** Agents apply legitimate tools in unsafe or unintended ways, leading to data exfiltration, unauthorized purchases, or domain-policy bypass.
**Verdict:** Partial — OPA can enforce: (a) role-based blocking of `view_team_compensation` and `export_compensation_data` for non-manager callers; (b) blocking of forbidden PII field names in `select_fields` on `view_team_compensation`; (c) blocking of `select_fields=null/absent` on both compensation tools; (d) blocking of `external_sharing=true` on `export_compensation_data` and `email_compensation_report`; (e) blocking of disallowed email domains on `send_email` and `email_compensation_report`; (f) purchase amount caps per role on `purchase`. HR database data-integrity risks are tool-implementation concerns outside OPA scope.

### ASI03 — Identity and Privilege Abuse
**Risk:** Attackers escalate access by manipulating role state, injecting user persona, or exploiting vocabulary mismatches.
**Verdict:** Partial — OPA can gate `view_team_compensation`, `export_compensation_data`, and `email_compensation_report` on `input.extensions.subject.roles` from `current_user_context`. Role-vocabulary enforcement (checking that the runtime value is a declared role) is also OPA-enforceable. Injection into the system prompt via `user_profile` and `history` are agent-layer concerns outside OPA scope.

### ASI04 — Agentic Supply Chain Vulnerabilities
**Risk:** Compromised or tampered third-party components (model weights, PyPI packages) inject unsafe behavior at startup or runtime.
**Verdict:** Out of scope — all supply chain risks manifest at startup time (HuggingFace model load, PyPI install) or at the library level, not as structured fields at tool-invocation time.

### ASI05 — Unexpected Code Execution (RCE)
**Risk:** Prompt injection or unsafe tool access escalates into remote code execution.
**Verdict:** Out of scope — no code generation or execution surface exists in the 11 active tools.

### ASI06 — Memory & Context Poisoning
**Risk:** Adversaries corrupt stored or retrievable context, biasing future reasoning or tool use.
**Verdict:** Partial — free-text arguments (`ticket_content`, `question`, `body`, `email_content`, `report_data`) carrying known injecting phrases can be blocked at tool-invocation time. The RAG vector store poisoning and `history` re-injection are not structured fields at invocation time and are out of OPA scope.

### ASI07 — Insecure Inter-Agent Communication
**Risk:** Weak inter-agent controls allow interception, spoofing, or manipulation of agent messages.
**Verdict:** Out of scope — single-agent system with no multi-agent communication channel.

### ASI08 — Cascading Failures
**Risk:** A single fault propagates across agents, tools, and workflows, compounding into system-wide harm.
**Verdict:** Partial — OPA can break individual links in a cascading chain by enforcing pre-execution denials on `view_team_compensation`, `export_compensation_data`, and `email_compensation_report` (the primary exfiltration tools). The `_fail_secure_decision` fail-open bug for `purchase`/`return_product` is a code-level issue in `opa_client.py` that must be fixed in the application before OPA is re-activated; it cannot be remedied from outside the function. The multi-step loop cap and history-drift cascade are agent-layer concerns.

### ASI09 — Human-Agent Trust Exploitation
**Risk:** Attackers exploit user trust in agent responses to influence harmful decisions.
**Verdict:** Out of scope — manifests in the agent's output text and user interface layer; no structured field at tool-invocation time.

### ASI10 — Rogue Agents
**Risk:** Malicious or compromised agents deviate from intended function within multi-agent ecosystems.
**Verdict:** Out of scope — single-agent system; no multi-agent infrastructure.

---

## Summary Table

| OWASP Category | In OPA scope? | Out-of-scope owner |
|---|---|---|
| ASI01 — Agent Goal Hijack | Partial | Agent layer (system prompt construction, input validation), Infrastructure (RAG source integrity) |
| ASI02 — Tool Misuse and Exploitation | Partial | Tool implementation (`export_compensation_data` body PII exposure, HR DB integrity) |
| ASI03 — Identity and Privilege Abuse | Partial | Agent layer (system-prompt role injection via `user_profile`, history fabrication), Application (role vocabulary normalization) |
| ASI04 — Agentic Supply Chain | No | Infrastructure/deployment (dependency pinning, model attestation) |
| ASI05 — Unexpected RCE | No | N/A — surface does not exist |
| ASI06 — Memory & Context Poisoning | Partial | Infrastructure (RAG PDF provenance), Agent layer (history re-injection isolation) |
| ASI07 — Insecure Inter-Agent Communication | No | N/A — single-agent |
| ASI08 — Cascading Failures | Partial | Application (fix `_fail_secure_decision` `safe_actions` list), Agent layer (multi-step loop confirmation) |
| ASI09 — Human-Agent Trust Exploitation | No | Agent layer / UI |
| ASI10 — Rogue Agents | No | N/A — single-agent |

**Categories flowing into the OPA policy:** ASI01 (partial), ASI02 (partial), ASI03 (partial), ASI06 (partial), ASI08 (partial)

---

## Gap Register

| Threat | Layer | Recommended action |
|---|---|---|
| ASI01-T1: Caller injects `user_profile.user_role = "manager"` into system prompt | Agent layer | Validate `user_profile` fields server-side before embedding in system prompt; normalize or strip `user_role` to a declared value; do not embed arbitrary caller keys verbatim |
| ASI01-T4: Fabricated `history` items assert prior permissions | Agent layer | Validate and sanitize the `history` field; enforce a maximum context age; do not re-inject caller-supplied history verbatim; tag history entries with provenance |
| ASI01-T5: LLM chains sensitive tools without human confirmation gate | Agent layer | Require explicit user confirmation before high-impact tool chains (export → email); implement an intent-gate between `export_compensation_data` and outbound email tools |
| ASI02-T7: In-memory `hr_database.py` returns records with no authentication | Tool implementation / Infrastructure | Consider replacing with a real authenticated DB backend; at minimum, hash the module at startup and verify integrity on each load |
| ASI02-T2 (body): `export_compensation_data` body adds PII from `comp_db.sensitive_data` unconditionally before `project_record()` filtering | Tool implementation | Fix tool body to exclude ssn, personal_email, home_address, bank_account from the candidate dict unless those fields are explicitly in select_fields — OPA cannot intercept the tool's internal dict construction |
| ASI03-T3 / ASI06-T2 / ASI08-T3: `history` re-injected verbatim without provenance or expiry | Agent layer | Validate and sanitize history; enforce session expiry; do not persist across requests without provenance tagging |
| ASI04-T1: HuggingFace BAAI/bge-small-en-v1.5 loaded from external registry without attestation | Infrastructure | Pin the model to a specific commit hash or digest; verify provenance before loading; consider vendoring the model weights |
| ASI04-T2: PyPI dependencies not pinned by hash | Infrastructure | Add `--require-hashes` to install requirements; lock with a verified hash manifest; scan for typosquats |
| ASI06-T1: RAG PDF source file could be replaced on disk | Infrastructure | Hash the PDF at startup and verify hash on each `ask_for_workpolicy` call; restrict filesystem write access to the PDF path |
| ASI08-T1: `max_turns=10` loop allows multi-step exfiltration chain without human gate | Agent layer | Require human confirmation between `export_compensation_data` and any outbound email/file tool call |
| ASI08-T2: `_fail_secure_decision` lists `purchase` and `return_product` in `safe_actions` — fail-open when OPA unreachable | Application (opa_client.py line 113) | Remove `purchase` and `return_product` from the `safe_actions` list; these must fail-closed when OPA is unreachable, consistent with guidance.txt Rules 9–10 |
| ASI09-T1: LLM produces hallucinated policy rationale with high apparent authority | Agent layer | Add source attribution to `ask_for_workpolicy` responses (cite PDF section, confidence level) |
| ASI09-T2: Multi-step chain presented as natural workflow conceals aggregate exfiltration | Agent layer / UI | Surface intermediate tool-call summaries; require step-by-step confirmation for sequences involving compensation data |
| Role vocabulary mismatch (`"user"` in runtime vs `"employee"` in `system_vars.json`) | Application | Normalize `set_user_context` initialization to use `"employee"` rather than `"user"`; align `opa_client.py` `USER_ROLES` with `system_vars.json` `roles` |
| `input.extensions.subject.approval` never populated — approval gate permanently blocked | Application | Implement application-layer population of `approval` in `current_user_context` before OPA evaluation; add manager-confirmation flow for purchases ≥$200 |
| Rate limiting absent (`daily_ticket_count` never incremented) | Application | Implement ticket-count tracking in `current_user_context`; consider adding rate-limit rules once the counter is reliably populated |

---

## Policy Rules (OPA scope only)

### Input Schema

| Field | Source | Notes |
|---|---|---|
| `input.name` | MCP protocol — tool name | Always present; routes dispatch |
| `input.args.ticket_content` | Caller via LLM | Free text; `create_ticket`, `submit_ticket` |
| `input.args.question` | Caller via LLM | Free text; `ask_for_workpolicy` |
| `input.args.body` | Caller via LLM | Free text; `send_email` |
| `input.args.email_content` | Caller via LLM | Free text; `send_email` |
| `input.args.report_data` | Caller via LLM | Free text; `email_compensation_report` |
| `input.args.select_fields` | Caller via LLM | List of strings or null; `view_team_compensation`, `export_compensation_data` |
| `input.args.external_sharing` | Caller via LLM | Boolean; `export_compensation_data`, `email_compensation_report` |
| `input.args.recipient_email` | Caller via LLM | Email address string; `send_email` |
| `input.args.destination` | Caller via LLM | Email address string; `email_compensation_report` |
| `input.args.amount` | Caller via LLM | Integer; `purchase`, `return_product` |
| `input.extensions.subject.roles` | Process-global session state | Single-element list; current runtime value `["user"]` — correct value once bug fixed: `["employee"]` or `["manager"]` |
| `input.extensions.subject.approval` | Process-global session state | String `"true"` or `"false"`; NOT currently populated at runtime |

### Known values

- **Declared roles** (from `system_vars.json`): `"employee"`, `"manager"`
  Note: current runtime value is `"user"` (vocabulary mismatch — see Gap Register). OPA rules must be written against the declared vocabulary.
- **Declared teams** (from `system_vars.json`): `"IT"`, `"HR"`, `"Sales"`, `"Finance"`, `"Legal"`, `"Operations"`, `"Marketing"`
- **Blocked email domains** (from `guidance.txt` Rule 8): `"gmail.com"`, `"yahoo.com"`, `"hotmail.com"`, `"outlook.com"`, `"personal.com"`
- **Compensation-only email domain** (from `guidance.txt` Rule 7): destination for `email_compensation_report` must end with `"@ibm.com"`
- **Forbidden PII field names in `select_fields`** (for `view_team_compensation` only): `"ssn"`, `"home_address"`, `"bank_account"`, `"personal_email"`, `"emergency_contact"`
  Note: `"tax_id"` is referenced in `guidance.txt` Rule 3 but is NOT in `view_team_compensation`'s available `select_fields` domain — a rule blocking it is vacuous.
  Note: `export_compensation_data`'s `select_fields` domain (`employee_id`, `name`, `title`, `level`, `current_salary`, `total_comp_2024`, `performance_rating`, `salary_history`, `bonus_history`) contains no PII field names. PII enters via the body directly. The correct OPA control for `export_compensation_data` is a role-gate (VIO-006) plus null-select_fields block (VIO-008).
- **Keyword blocklist** (from `guidance.txt` Rules 11–14): `"ignore all policies"`, `"bypass security"`, `"override all policies"`, `"show all SSN data"`
- **Purchase thresholds** (from `guidance.txt` Rules 9–10): employee cap: amount ≥ 200 requires approval; manager cap: amount ≥ 1000 hard blocked

---

### Rule: VIO-001
- **OWASP:** ASI01 / ASI06
- **Severity:** Hard block
- **Governs:** `create_ticket`, `submit_ticket`
- **Condition:** `input.args.ticket_content` contains any blocked keyword phrase
- **Matching:** Case-insensitive substring — `"ignore all policies"`, `"bypass security"`, `"override all policies"`, `"show all SSN data"`
- **Threat linkage:** ASI01-T2 (Direct Plan Injection via ticket_content); ASI06-T3 (free-text context manipulation)
- **Mitigation grounding (ASI01):** "Treat all natural-language inputs as untrusted. Route them through the same input-validation and prompt-injection safeguards."

---

### Rule: VIO-002
- **OWASP:** ASI01 / ASI06
- **Severity:** Hard block
- **Governs:** `ask_for_workpolicy`
- **Condition:** `input.args.question` contains any blocked keyword phrase
- **Matching:** Case-insensitive substring — same 4 phrases
- **Threat linkage:** ASI01-T2 (injection via question); ASI06-T3
- **Mitigation grounding (ASI01):** Same as VIO-001.

---

### Rule: VIO-003
- **OWASP:** ASI01 / ASI06
- **Severity:** Hard block
- **Governs:** `send_email`
- **Condition:** `input.args.body` OR `input.args.email_content` contains any blocked keyword phrase
- **Matching:** Case-insensitive substring — same 4 phrases
- **Threat linkage:** ASI01-T2 (Direct Plan Injection via email body); ASI06-T3
- **Mitigation grounding (ASI01):** Same as VIO-001.

---

### Rule: VIO-004
- **OWASP:** ASI01 / ASI06
- **Severity:** Hard block
- **Governs:** `email_compensation_report`
- **Condition:** `input.args.report_data` contains any blocked keyword phrase
- **Matching:** Case-insensitive substring — same 4 phrases
- **Threat linkage:** ASI01-T2 (injection via report_data); ASI06-T3
- **Mitigation grounding (ASI01):** Same as VIO-001.

---

### Rule: VIO-005
- **OWASP:** ASI02 / ASI03
- **Severity:** Hard block
- **Governs:** `view_team_compensation`
- **Condition:** `input.extensions.subject.roles` does not contain `"manager"`
- **Matching:** Set membership — deny when `"manager"` is absent from the roles list
- **Threat linkage:** ASI02-T1 (employee-role session calls view_team_compensation, returning PII); ASI03-T1 (role impersonation via system prompt — OPA uses runtime `current_user_context`, not LLM persona)
- **Mitigation grounding (ASI02):** "Least Agency and Least Privilege for Tools. Define per-tool least-privilege profiles and restrict agentic tool functionality and each tool's data scope to those profiles."

---

### Rule: VIO-006
- **OWASP:** ASI02 / ASI03
- **Severity:** Hard block
- **Governs:** `export_compensation_data`
- **Condition:** `input.extensions.subject.roles` does not contain `"manager"`
- **Matching:** Set membership — deny when `"manager"` is absent
- **Threat linkage:** ASI02-T2 (employee session exports compensation; body adds PII unconditionally); ASI03-T1
- **Mitigation grounding (ASI02):** Same as VIO-005.

---

### Rule: VIO-007
- **OWASP:** ASI02
- **Severity:** Hard block
- **Governs:** `view_team_compensation`
- **Condition:** `input.args.select_fields` is null, absent, or an empty list
- **Matching:** Null / absent / empty-list check
- **Threat linkage:** ASI02-T1 (select_fields=null causes all fields including PII to be returned by `project_record()`)
- **Mitigation grounding (ASI02):** "Policy Enforcement Middleware ('Intent Gate'). A pre-execution PEP/PDP validates intent and arguments, enforces schemas."

---

### Rule: VIO-008
- **OWASP:** ASI02
- **Severity:** Hard block
- **Governs:** `export_compensation_data`
- **Condition:** `input.args.select_fields` is null, absent, or an empty list
- **Matching:** Null / absent / empty-list check
- **Threat linkage:** ASI02-T2 (select_fields=null causes full-record return including PII added unconditionally by body)
- **Mitigation grounding (ASI02):** Same as VIO-007.

---

### Rule: VIO-009
- **OWASP:** ASI02 / ASI03
- **Severity:** Hard block
- **Governs:** `view_team_compensation` (NARROWED — `export_compensation_data` dropped; its select_fields domain does not include PII field names per criterion 1d)
- **Condition:** `input.args.select_fields` contains any of: `"ssn"`, `"home_address"`, `"bank_account"`, `"personal_email"`, `"emergency_contact"`
- **Matching:** Set membership — deny when any forbidden field name is present in the list
- **Threat linkage:** ASI02-T5 (caller injects PII field names in select_fields; project_record() returns them); ASI03-T4
- **Mitigation grounding (ASI02):** "Least Agency and Least Privilege for Tools. Restrict agentic tool functionality and each tool's data scope."

---

### Rule: VIO-010
- **OWASP:** ASI02
- **Severity:** Hard block
- **Governs:** `export_compensation_data`
- **Condition:** `input.args.external_sharing` is `true`
- **Matching:** Exact boolean equality
- **Threat linkage:** ASI02-T6 (external_sharing is echoed only; OPA denial stops the call before any data is returned)
- **Mitigation grounding (ASI02):** "Policy Enforcement Middleware. A pre-execution PEP/PDP validates intent and arguments."
- **Note:** `external_sharing` is echoed only on this tool. This is a sound deny-path rule — the denial is the enforcement regardless of what the tool would have done.

---

### Rule: VIO-011
- **OWASP:** ASI02
- **Severity:** Hard block
- **Governs:** `email_compensation_report`
- **Condition:** `input.args.external_sharing` is `true`
- **Matching:** Exact boolean equality
- **Threat linkage:** ASI02-T6; ASI08-T1 (breaking a link in the exfiltration chain)
- **Mitigation grounding (ASI02):** Same as VIO-010.
- **Note:** Same echoed-only caveat — deny-path rule is sound.

---

### Rule: VIO-012
- **OWASP:** ASI02 / ASI03
- **Severity:** Hard block
- **Governs:** `email_compensation_report`
- **Condition:** The domain of `input.args.destination` is not `"ibm.com"` (i.e., destination does not end with `"@ibm.com"`)
- **Matching:** Suffix/domain check on the destination email address
- **Threat linkage:** ASI02-T3 (non-@ibm.com destination injected by caller or LLM)
- **Mitigation grounding (ASI02):** "Execution Sandboxes and Egress Controls. Enforce outbound allowlists and deny all non-approved network destinations."

---

### Rule: VIO-013
- **OWASP:** ASI02
- **Severity:** Hard block
- **Governs:** `send_email` (on `input.args.recipient_email`), `email_compensation_report` (on `input.args.destination`)
- **Condition:** The domain portion of the email address is in the blocked domain list: `"gmail.com"`, `"yahoo.com"`, `"hotmail.com"`, `"outlook.com"`, `"personal.com"`
- **Matching:** Domain set membership
- **Threat linkage:** ASI02-T3 (data exfiltration to personal email domains)
- **Mitigation grounding (ASI02):** "Execution Sandboxes and Egress Controls."

---

### Rule: VIO-014
- **OWASP:** ASI02 / ASI08
- **Severity:** Hard block
- **Governs:** `purchase`
- **Condition:** `input.extensions.subject.roles` contains `"manager"` AND `input.args.amount` >= 1000
- **Matching:** Set membership + numeric comparison (deny when manager AND amount ≥ 1000)
- **Threat linkage:** ASI02-T4 (purchase body has no threshold check; OPA must intercept before execution); ASI08-T2
- **Mitigation grounding (ASI02):** "Least Agency and Least Privilege for Tools. Define per-tool least-privilege profiles — restrict maximum rate and scope."

---

### Rule: VIO-015
- **OWASP:** ASI02 / ASI08
- **Severity:** Hard block
- **Governs:** `purchase`
- **Condition:** `input.extensions.subject.roles` does NOT contain `"manager"` AND `input.args.amount` >= 200 AND `input.extensions.subject.approval` != `"true"`
- **Matching:** Set membership + numeric comparison + exact string equality
- **Threat linkage:** ASI02-T4 (employee purchases ≥$200 without approval); ASI08-T2 (fail-open bypass)
- **Mitigation grounding (ASI02):** "Action-Level Authentication and Approval. Require explicit authentication for each tool invocation and human confirmation for high-impact actions."
- **Critical note:** `input.extensions.subject.approval` is currently never populated (see Gap Register). This rule will deny all non-manager purchases ≥$200 until the application is updated to populate the field — which is the correct fail-closed behavior.

---

### Rule: VIO-016
- **OWASP:** ASI03
- **Severity:** Hard block
- **Governs:** `email_compensation_report`
- **Condition:** `input.extensions.subject.roles` does not contain `"manager"`
- **Matching:** Set membership — deny when `"manager"` is absent
- **Threat linkage:** ASI03-T1 (non-manager calls email_compensation_report; no existing guidance.txt rule explicitly gates this tool by role)
- **Mitigation grounding (ASI03):** "Enforce Task-Scoped, Time-Bound Permissions. Bind permissions to subject, resource, purpose, and duration."

---

## Violation Code Reference

| Code | OWASP | Governs | Severity |
|---|---|---|---|
| VIO-001 | ASI01 / ASI06 | Keyword phrase in `ticket_content` (`create_ticket`, `submit_ticket`) | Hard block |
| VIO-002 | ASI01 / ASI06 | Keyword phrase in `question` (`ask_for_workpolicy`) | Hard block |
| VIO-003 | ASI01 / ASI06 | Keyword phrase in `body` / `email_content` (`send_email`) | Hard block |
| VIO-004 | ASI01 / ASI06 | Keyword phrase in `report_data` (`email_compensation_report`) | Hard block |
| VIO-005 | ASI02 / ASI03 | Non-manager calls `view_team_compensation` | Hard block |
| VIO-006 | ASI02 / ASI03 | Non-manager calls `export_compensation_data` | Hard block |
| VIO-007 | ASI02 | `select_fields` null/absent/empty on `view_team_compensation` | Hard block |
| VIO-008 | ASI02 | `select_fields` null/absent/empty on `export_compensation_data` | Hard block |
| VIO-009 | ASI02 / ASI03 | Forbidden PII field in `select_fields` on `view_team_compensation` (narrowed) | Hard block |
| VIO-010 | ASI02 | `external_sharing=true` on `export_compensation_data` | Hard block |
| VIO-011 | ASI02 | `external_sharing=true` on `email_compensation_report` | Hard block |
| VIO-012 | ASI02 / ASI03 | Non-@ibm.com destination on `email_compensation_report` | Hard block |
| VIO-013 | ASI02 | Blocked email domain on `send_email` or `email_compensation_report` | Hard block |
| VIO-014 | ASI02 / ASI08 | Manager purchase amount ≥ $1,000 | Hard block |
| VIO-015 | ASI02 / ASI08 | Non-manager purchase ≥ $200 without approval | Hard block |
| VIO-016 | ASI03 | Non-manager calls `email_compensation_report` | Hard block |

---

## STEP 7 — Combined Candidate Rule List

All Source 2 (questionnaire) candidates deduplicated against Source 1 (OWASP-derived). Final 16 unique candidates:

1. [ASI01/ASI06 / VIO-001] [from Q13] — Block keyword phrases in `create_ticket`/`submit_ticket`.`ticket_content`
2. [ASI01/ASI06 / VIO-002] [from Q13] — Block keyword phrases in `ask_for_workpolicy`.`question`
3. [ASI01/ASI06 / VIO-003] [from Q13] — Block keyword phrases in `send_email`.`body`/`email_content`
4. [ASI01/ASI06 / VIO-004] [from Q13] — Block keyword phrases in `email_compensation_report`.`report_data`
5. [ASI02/ASI03 / VIO-005] [from Q9] — Non-manager blocked from `view_team_compensation` on `subject.roles`
6. [ASI02/ASI03 / VIO-006] [from Q9] — Non-manager blocked from `export_compensation_data` on `subject.roles`
7. [ASI02 / VIO-007] [from Q12, Q17] — Null/absent `select_fields` denied on `view_team_compensation`
8. [ASI02 / VIO-008] [from Q12, Q17] — Null/absent `select_fields` denied on `export_compensation_data`
9. [ASI02/ASI03 / VIO-009] [from Q10, Q18] — PII field names in `select_fields` denied on `view_team_compensation` (narrowed from both compensation tools — `export_compensation_data` dropped per criterion 1d)
10. [ASI02 / VIO-010] [from Q10] — `external_sharing=true` denied on `export_compensation_data`
11. [ASI02 / VIO-011] [from Q10] — `external_sharing=true` denied on `email_compensation_report`
12. [ASI02/ASI03 / VIO-012] [from Q10] — Non-@ibm.com destination denied on `email_compensation_report`
13. [ASI02 / VIO-013] [from Q10] — Blocked email domain denied on `send_email` and `email_compensation_report`
14. [ASI02/ASI08 / VIO-014] [from Q9, Q13] — Manager purchase ≥ $1,000 denied
15. [ASI02/ASI08 / VIO-015] [from Q9, Q13b] — Non-manager purchase ≥ $200 without approval denied
16. [ASI03 / VIO-016] [from Q9] — Non-manager blocked from `email_compensation_report` on `subject.roles`

---

## STEP 8 — Coverage Scratch Table

Prior `guidance_updated.txt`: Empty (no prior-run rules to capture).

| Candidate | Verified (tool, field) | Operator | Value set | Matching guidance.txt rule # | Covered? |
|---|---|---|---|---|---|
| 1. Keyword phrases in ticket_content | create_ticket/ticket_content, submit_ticket/ticket_content | case-insensitive substring | {"ignore all policies","bypass security","override all policies","show all SSN data"} | Rules 11, 12, 13, 14 (same phrases) | Yes |
| 2. Keyword phrases in question | ask_for_workpolicy/question | case-insensitive substring | same 4 phrases | Rules 11–14 | Yes |
| 3. Keyword phrases in body/email_content | send_email/body, send_email/email_content | case-insensitive substring | same 4 phrases | Rules 11–14 | Yes |
| 4. Keyword phrases in report_data | email_compensation_report/report_data | case-insensitive substring | same 4 phrases | Rules 11–14 | Yes |
| 5. Non-manager blocked from view_team_compensation | view_team_compensation/subject.roles | set membership (not-manager) | deny when manager absent | Rule 2 blocks employees — subsumption test: Rule 2 covers {employee}; candidate covers {anything ≠ manager} = {employee} ∪ {unrecognized roles}. Rule 2 does NOT cover unrecognized roles (e.g., runtime "user"). Not covered by subsumption; three-criteria test: same field (subject.roles), same operator (role restriction) but different value scope (employee-only vs not-manager). Not covered. | **No** |
| 6. Non-manager blocked from export_compensation_data | export_compensation_data/subject.roles | set membership (not-manager) | deny when manager absent | Rule 5 blocks employees — same analysis as #5. | **No** |
| 7. Null/absent select_fields on view_team_compensation | view_team_compensation/select_fields | null/absent/empty | deny | No matching rule | **No** |
| 8. Null/absent select_fields on export_compensation_data | export_compensation_data/select_fields | null/absent/empty | deny | No matching rule | **No** |
| 9. PII field names in select_fields on view_team_compensation (narrowed) | view_team_compensation/select_fields | set membership | {"ssn","home_address","bank_account","personal_email","emergency_contact"} | Rule 3 ("Managers cannot see SSN, Home addresses, Bank account numbers, Tax ID numbers, emergency_contact") — same field, same operator (field exclusion), overlapping value set. Covered. | Yes |
| 10. external_sharing=true on export_compensation_data | export_compensation_data/external_sharing | exact boolean | true | Rule 5 ("Employees cannot export") addresses role, not external_sharing. Rule 7 addresses destination email domain, not external_sharing flag. No rule covers this field. | **No** |
| 11. external_sharing=true on email_compensation_report | email_compensation_report/external_sharing | exact boolean | true | Same analysis — Rule 7 addresses destination domain; no rule covers external_sharing. | **No** |
| 12. Non-@ibm.com destination on email_compensation_report | email_compensation_report/destination | domain suffix ≠ ibm.com | ibm.com | Rule 7 ("No one can share compensation data externally to non @ibm.com email addresses") — same field, same domain check, same value (ibm.com). Covered. | Yes |
| 13. Blocked domains on send_email + email_compensation_report | send_email/recipient_email, email_compensation_report/destination | domain set membership | {"gmail.com","yahoo.com","hotmail.com","outlook.com","personal.com"} | Rule 8 (same domains). Covered. | Yes |
| 14. Manager purchase ≥ $1,000 | purchase/amount, subject.roles | numeric + set | ≥1000, manager | Rule 10 ("Managers can buy products under $1,000"). Same field, same threshold, same role scope. Covered. | Yes |
| 15. Non-manager purchase ≥ $200 without approval | purchase/amount, subject.roles, subject.approval | numeric + set + exact | ≥200, not-manager, approval≠"true" | Rule 9 ("Employees cannot buy products $200+ without manager approval"). Same field, same threshold. Covered. | Yes |
| 16. Non-manager blocked from email_compensation_report | email_compensation_report/subject.roles | set membership (not-manager) | deny when manager absent | No existing rule explicitly blocks non-managers from email_compensation_report. Rules 1–5 cover compensation data viewing/exporting; Rule 6 grants managers external send rights for non-compensation data. No rule gates email_compensation_report by role. | **No** |

**Missing candidates: #5, #6, #7, #8, #10, #11, #16** (7 new rules needed)

---

## STEP 8b — Redundancy Self-check

Post-merge state: guidance.txt rules 1–14, new rules 15–21.

| Rule i | Rule j | Verdict | Notes |
|---|---|---|---|
| Rule 2 (employees cannot view compensation) | New Rule 15 (non-manager blocked from view_team_compensation) | Overlap (additive) — Rule 15 is broader (any non-manager), Rule 2 is narrower (employees). Compatible: both deny, same tool, no contradiction. | Rule 15 adds coverage for unrecognized roles; both can coexist |
| Rule 5 (employees cannot export) | New Rule 16 (non-manager blocked from export_compensation_data) | Overlap (additive) — same analysis as above. Compatible. | |
| All other pairs | — | No overlap, conflict, or correction found | — |

`Redundancy self-check: 2 additive overlaps (Rules 2/15, Rules 5/16) — compatible, no action required; 0 conflicts; 0 contradictory corrections`

---

## STEP 8c — Regression Check

`Regression check: no prior run to compare against (guidance_updated.txt was empty before this run)`
