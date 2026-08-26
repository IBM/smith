# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines
# Tool: RagChatbot_MCPServer

---

## Architecture Summary

The RagChatbot_MCPServer is a three-layer HR agent: a FastAPI HTTP API layer (`fast_server.py`) that embeds a caller-supplied, unverified `user_profile` into the LLM system prompt; an LLM agent layer that selects and constructs MCP tool calls; and an MCP tool layer (`mcp_server.py`) hosting 12 tools that execute business logic against an in-memory HR/compensation database and a local RAG pipeline. Role and approval fields are entirely self-reported by the caller with no cryptographic verification, and the tool implementations return sensitive data (SSN, home address, bank account) without field-level filtering, deferring that responsibility to the policy layer.

---

## OWASP Top 10 for Agentic AI Security — Scope Assessment

### ASI01 — Agent Goal Hijack
**Risk:** Attackers redirect the agent's goals or tool-call decisions through prompt injection in user input, free-text arguments, or RAG-retrieved PDF content.
**Verdict:** Partial — direct prompt injection via free-text tool arguments (`question`, `ticket_content`, `email_content`, `report_data`) is OPA-interceptable via keyword blocking; injection via RAG PDF content and LLM argument fabrication is out of OPA scope.

### ASI02 — Tool Misuse and Exploitation
**Risk:** The LLM or caller misuses legitimate tools to exfiltrate compensation data, bypass role restrictions, or send data to blocked external destinations.
**Verdict:** Partial — role-based tool blocking, forbidden-field checks in `select_fields`, blocked email domains, `external_sharing` blocking, and purchase amount/approval enforcement are all OPA-interceptable; `set_user_role` misuse is only partially addressable via OPA; raw sensitive-data return from tool bodies is out of OPA scope.

### ASI03 — Identity and Privilege Abuse
**Risk:** Callers self-report elevated roles or approval flags to bypass access controls.
**Verdict:** Partial — OPA can enforce role-based rules and the approval condition as a structural gate, but cannot verify the authenticity of the self-reported role; authentication infrastructure is out of OPA scope.

### ASI04 — Agentic Supply Chain Vulnerabilities
**Risk:** Compromised third-party dependencies or poisoned local PDF files introduce malicious behavior.
**Verdict:** Out of scope — dependency integrity and PDF file verification are infrastructure and deployment concerns; OPA cannot inspect library code or file hashes at tool invocation time.

### ASI05 — Unexpected Code Execution (RCE)
**Risk:** Attackers exploit code generation or shell tool access to achieve RCE.
**Verdict:** Out of scope — no code interpreter or shell tool is exposed; not applicable to the current tool set.

### ASI06 — Memory & Context Poisoning
**Risk:** Adversarial PDF content or within-session context injection causes the agent to act on poisoned data.
**Verdict:** Out of scope — RAG content sanitization and session memory management occur at the agent layer, not at tool invocation time.

### ASI07 — Insecure Inter-Agent Communication
**Risk:** Insecure inter-agent messaging enables interception or spoofing.
**Verdict:** Out of scope — single-agent system; not applicable.

### ASI08 — Cascading Failures
**Risk:** A single `set_user_role` escalation cascades across all subsequent tool calls in the same session.
**Verdict:** Partial — prevented by the same OPA rules that block `set_user_role` misuse (ASI02/ASI03). No separate rule needed.

### ASI09 — Human-Agent Trust Exploitation
**Risk:** Unfiltered sensitive fields in tool responses are presented to users; policy opacity enables probing.
**Verdict:** Out of scope — OPA cannot filter tool return values; both instances require tool-implementation and agent-layer changes.

### ASI10 — Rogue Agents
**Risk:** Malicious agents deviate from intended behavior in a multi-agent system.
**Verdict:** Out of scope — single-agent system; not applicable.

---

## Summary Table

| OWASP Category | In OPA scope? | Out-of-scope owner |
|---|---|---|
| ASI01 — Agent Goal Hijack | Partial | Agent layer: RAG content filtering; LLMGuard enhancement |
| ASI02 — Tool Misuse and Exploitation | Partial | Tool Implementation layer: field-level response filtering; Agent layer: MCP authentication for `set_user_role` |
| ASI03 — Identity and Privilege Abuse | Partial | Infrastructure: authentication system for role verification |
| ASI04 — Agentic Supply Chain Vulnerabilities | No | Infrastructure/deployment: SBOM, dependency pinning, PDF integrity |
| ASI05 — Unexpected Code Execution (RCE) | No | N/A — not applicable |
| ASI06 — Memory & Context Poisoning | No | Agent layer: RAG content sanitization, session memory management |
| ASI07 — Insecure Inter-Agent Communication | No | N/A — not applicable |
| ASI08 — Cascading Failures | Partial | Prevented by ASI02/ASI03 `set_user_role` rules |
| ASI09 — Human-Agent Trust Exploitation | No | Tool Implementation layer: field-level filtering; Agent layer: output explanation policy |
| ASI10 — Rogue Agents | No | N/A — not applicable |

Categories flowing into the OPA policy: ASI01 (partial), ASI02 (partial), ASI03 (partial)

---

## Gap Register

| Threat | Layer | Recommended action |
|---|---|---|
| ASI01: RAG PDF content injection (hidden instructions in indexed PDFs) | Agent layer | Sanitize content retrieved from the RAG pipeline before passing it to the LLM; apply prompt-carrier detection to retrieved chunks |
| ASI01: LLMGuard business-keyword override allows bypass phrases | Agent layer | Require bypass phrase to be absent even when business keywords are present; do not override on keyword co-presence alone |
| ASI02: Tool implementations return SSN, home_address, bank_account unconditionally | Tool Implementation layer | Remove sensitive fields from `view_team_compensation` and `export_compensation_data` response construction unconditionally |
| ASI02: `set_user_role` tool accessible without authentication | Calling application / MCP layer | Require authenticated session context before accepting `set_user_role` calls; restrict or remove in production |
| ASI03: Self-reported `user_role` accepted without verification | Infrastructure | Integrate with an identity provider (OAuth/OIDC) to supply cryptographically verified role claims |
| ASI03: Self-reported `approval` field not validated by an authority | Calling application | Populate `input.extensions.subject.approval` from an authoritative approval workflow, not from caller input |
| ASI04: Third-party dependency versions not hash-pinned | Infrastructure/deployment | Pin all dependencies by content hash; verify hashes in CI before deployment |
| ASI04: Preloaded PDFs lack integrity verification | Infrastructure | Store and verify SHA-256 hashes of PDF files on server startup |
| ASI06: RAG pipeline does not sanitize retrieved text | Agent layer | Apply content filtering (CDR/prompt-carrier detection) to all text retrieved from the RAG index |
| ASI06: Within-session context injection (approval assertion in early turns) | Agent layer | Enforce authorization via structured fields only; do not rely on LLM-recalled free-text from prior turns |
| ASI09: `view_team_compensation` and `export_compensation_data` return raw sensitive data | Tool Implementation layer | Remove SSN, home_address, bank_account, emergency_contact, tax_id from all tool responses unconditionally |
| ASI09: Denial messages are opaque (🚫 relay-only) enabling oracle-attack probing | Agent layer | Include a violation code or category in denial messages so legitimate users can understand the reason |

---

## Policy Rules (OPA scope only)

### Input Schema
| Field | Source |
|---|---|
| `input.name` | Tool name (string) |
| `input.arguments.amount` | integer — purchase, return_product |
| `input.arguments.external_sharing` | boolean — export_compensation_data, email_compensation_report |
| `input.arguments.recipient_email` | string — send_email |
| `input.arguments.destination` | string — email_compensation_report |
| `input.arguments.select_fields` | array of strings or null — view_team_compensation, export_compensation_data |
| `input.arguments.question` | string — ask_for_workpolicy |
| `input.arguments.ticket_content` | string — create_ticket, submit_ticket |
| `input.arguments.email_content` | string — send_email |
| `input.arguments.report_data` | string — email_compensation_report |
| `input.arguments.user_role` | string — set_user_role |
| `input.extensions.subject.roles` | string — caller role ("employee" or "manager") |
| `input.extensions.subject.approval` | string — "true" or "false" |

### Known values
- **Blocked email domains:** gmail.com, yahoo.com, hotmail.com, outlook.com, personal.com
- **Sensitive field names (blocked in select_fields for all roles):** ssn, home_address, bank_account, tax_id, emergency_contact
- **Policy-bypass keywords (case-insensitive substrings):** "ignore all policies", "bypass security", "override all policies", "show all SSN data"
- **Employee purchase threshold requiring approval:** $200
- **Manager purchase hard cap:** $1,000
- **Compensation tools blocked for employee role:** view_team_compensation, export_compensation_data, email_compensation_report

---

### Rule: ROLE_COMP_VIEW
- OWASP: ASI02, ASI03
- Severity: Hard block
- Condition: `input.name` is `view_team_compensation` AND `input.extensions.subject.roles` is `"employee"`
- Matching: exact equality on both fields

### Rule: ROLE_COMP_EXPORT
- OWASP: ASI02, ASI03
- Severity: Hard block
- Condition: `input.name` is `export_compensation_data` AND `input.extensions.subject.roles` is `"employee"`
- Matching: exact equality on both fields

### Rule: ROLE_COMP_EMAIL
- OWASP: ASI02, ASI03
- Severity: Hard block
- Condition: `input.name` is `email_compensation_report` AND `input.extensions.subject.roles` is `"employee"`
- Matching: exact equality on both fields

### Rule: FIELD_SENSITIVE_BLOCK
- OWASP: ASI02
- Severity: Hard block
- Condition: `input.name` is `view_team_compensation` or `export_compensation_data` AND `input.arguments.select_fields` contains any element from {ssn, home_address, bank_account, tax_id, emergency_contact}
- Matching: set-membership check; each element of `select_fields` checked case-insensitively against the blocked set

### Rule: EXT_SHARING_COMP
- OWASP: ASI02, ASI01
- Severity: Hard block
- Condition: `input.name` is `export_compensation_data` or `email_compensation_report` AND `input.arguments.external_sharing` is `true`
- Matching: exact boolean equality

### Rule: EMAIL_DOMAIN_BLOCK
- OWASP: ASI02
- Severity: Hard block
- Condition: `input.name` is `send_email` or `email_compensation_report` AND the domain portion of `input.arguments.recipient_email` (send_email) or `input.arguments.destination` (email_compensation_report) is a member of {gmail.com, yahoo.com, hotmail.com, outlook.com, personal.com}
- Matching: extract substring after `@`; exact-equality set-membership

### Rule: COMP_EMAIL_INTERNAL_ONLY
- OWASP: ASI02, ASI03
- Severity: Hard block
- Condition: `input.name` is `email_compensation_report` AND the domain portion of `input.arguments.destination` does not equal `"ibm.com"`
- Matching: extract substring after `@`; exact equality negation

### Rule: PURCHASE_EMPLOYEE_APPROVAL
- OWASP: ASI02, ASI03
- Severity: Hard block
- Condition: `input.name` is `purchase` AND `input.extensions.subject.roles` is `"employee"` AND `input.arguments.amount` >= 200 AND `input.extensions.subject.approval` is not `"true"`
- Matching: exact equality on roles and approval; numeric comparison (>=) on amount

### Rule: PURCHASE_MANAGER_CAP
- OWASP: ASI02, ASI03
- Severity: Hard block
- Condition: `input.name` is `purchase` AND `input.extensions.subject.roles` is `"manager"` AND `input.arguments.amount` >= 1000
- Matching: exact equality on roles; numeric comparison (>=) on amount

### Rule: KEYWORD_BYPASS_BLOCK
- OWASP: ASI01
- Severity: Hard block
- Condition: any of `input.arguments.question`, `input.arguments.ticket_content`, `input.arguments.email_content`, or `input.arguments.report_data` contains any of: "ignore all policies", "bypass security", "override all policies", "show all SSN data"
- Matching: case-insensitive substring match across all listed free-text fields

---

## Violation Code Reference

| Code | OWASP | Severity |
|---|---|---|
| ROLE_COMP_VIEW | ASI02, ASI03 | Hard block |
| ROLE_COMP_EXPORT | ASI02, ASI03 | Hard block |
| ROLE_COMP_EMAIL | ASI02, ASI03 | Hard block |
| FIELD_SENSITIVE_BLOCK | ASI02 | Hard block |
| EXT_SHARING_COMP | ASI02, ASI01 | Hard block |
| EMAIL_DOMAIN_BLOCK | ASI02 | Hard block |
| COMP_EMAIL_INTERNAL_ONLY | ASI02, ASI03 | Hard block |
| PURCHASE_EMPLOYEE_APPROVAL | ASI02, ASI03 | Hard block |
| PURCHASE_MANAGER_CAP | ASI02, ASI03 | Hard block |
| KEYWORD_BYPASS_BLOCK | ASI01 | Hard block |
