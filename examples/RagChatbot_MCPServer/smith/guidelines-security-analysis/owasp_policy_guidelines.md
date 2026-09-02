# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines
# Tool: RagChatbot_MCPServer

---

## Architecture Summary

RagChatbot_MCPServer is a single LLM-driven HR assistant that dispatches 12 MCP tools over SSE (`mcp_server.py`), with role/identity carried as self-reported, unauthenticated, process-global state (`set_user_role`) and no live OPA enforcement wired into the tool-dispatch path today. The MCP Tool Layer is the only point where tool name and full structured arguments are simultaneously visible before any side effect occurs, making it the sole viable OPA interception point — but the caller-identity signal it would gate role-based rules on currently carries no integrity guarantee.

---

## OWASP Top 10 for Agentic AI Security — Scope Assessment

### ASI01 — Agent Goal Hijack
**Risk:** Attackers manipulate the agent's objectives or tool-call decisions by embedding instructions in free-text arguments or exploiting the LLM's unverified trust in caller-supplied role claims.
**Verdict:** Partial — OPA can literal-match a known set of blocked phrases in free-text arguments, but cannot address the LLM's reasoning-level trust in an unverified role claim or the absence of input scanning on the FastAPI path.

### ASI02 — Tool Misuse and Exploitation
**Risk:** A caller or the LLM misuses a legitimately-available tool (default field exposure, external-sharing flags, unenforced email domains) to exfiltrate compensation data or bypass intended scope limits.
**Verdict:** In scope — every threat instance here reduces to a structured-field check (`select_fields` presence/absence, `external_sharing`, `destination` domain) visible at tool-invocation time.

### ASI03 — Identity and Privilege Abuse
**Risk:** Any caller can set their own role via an unauthenticated `set_user_role` call, or via a self-reported `user_profile.user_role` field, and then invoke role-gated tools with no verification.
**Verdict:** Partial — OPA can gate the `set_user_role` call itself and check `input.extensions.subject.role` on every other tool, but cannot add real authentication behind the role value or fix the underlying process-global state-sharing bug.

### ASI04 — Agentic Supply Chain Vulnerabilities
**Risk:** The unpinned HuggingFace embedding model revision could be swapped upstream with no local detection.
**Verdict:** Out of scope — model/dependency pinning is a build-time, not invocation-time, concern; no structured field exists at tool-call time to check.

### ASI05 — Unexpected Code Execution (RCE)
**Risk:** N/A for this tool.
**Verdict:** Out of scope — no code-generation or code-execution capability exists in any of the 12 tools.

### ASI06 — Memory & Context Poisoning
**Risk:** The RAG-retrieved PDF content and the rolling 10-message chat history are trusted by the LLM with no provenance check or per-turn re-validation.
**Verdict:** Out of scope — both are content-trust concerns evaluated during LLM reasoning, not structured fields visible at tool-invocation time.

### ASI07 — Insecure Inter-Agent Communication
**Risk:** N/A for this tool.
**Verdict:** Out of scope — no multi-agent substrate exists; a single agent calls a single tool server directly.

### ASI08 — Cascading Failures
**Risk:** A hallucinated or misread tool result early in a `max_turns`-bounded session can shape every subsequent tool call in the same session with no reconciliation step.
**Verdict:** Out of scope — this is an LLM-reasoning propagation concern with no structured field OPA could check to interrupt it.

### ASI09 — Human-Agent Trust Exploitation
**Risk:** Users cannot independently verify the role actually in effect (UI/backend desync), the OPA-unreachable fallback silently diverges from guidance.txt's real thresholds, and no durable audit trail exists for disputed transactions.
**Verdict:** Partial — the underlying `set_user_role` call is already gated under ASI03; the remaining threat instances here (UI desync, fallback divergence, missing audit trail) are response-side or infra concerns with no invocation-time field to check.

### ASI10 — Rogue Agents
**Risk:** N/A for this tool.
**Verdict:** Out of scope — no multi-agent substrate exists.

---

## Summary Table

| OWASP Category | In OPA scope? | Out-of-scope owner |
|---|---|---|
| ASI01 | Partial | Agent layer |
| ASI02 | Yes | — |
| ASI03 | Partial | Tool implementation / Infra |
| ASI04 | No | Infra/deployment |
| ASI05 | No | N/A |
| ASI06 | No | Tool implementation / Agent |
| ASI07 | No | N/A |
| ASI08 | No | Agent layer |
| ASI09 | Partial | Agent layer / Infra |
| ASI10 | No | N/A |

Categories flowing into the OPA policy: ASI01, ASI02, ASI03

---

## Gap Register

| Threat | Layer | Recommended action |
|---|---|---|
| LLM trusts unverified `user_role` embedded directly in the system prompt | Agent | Do not embed self-reported role claims into the LLM's context as if authoritative; resolve role via policy evaluation, not by prompt inclusion |
| FastAPI `/chat` and `/extract_tool_call` have no input/output scanning at all | Agent | Add the same LLMGuard-equivalent scanning that exists on the Streamlit path |
| LLM may mis-route compensation content through `send_email` instead of `email_compensation_report` | Agent | Add a system-prompt instruction and/or output-side classifier flagging compensation-shaped content in non-compensation tool calls |
| Process-global `current_user_context` causes cross-request identity bleed between concurrent callers | Tool implementation / Infra | Replace global mutable role state with per-session/per-request context |
| No real authentication behind role assignment | Infra | Introduce an identity provider or credential check before any role value is trusted; OPA can only gate on the field once it is trustworthy |
| `employee` vs `user` role-naming mismatch between `system_vars.json` and `set_user_role`/`USER_ROLES` | Tool implementation | Align the declared role vocabulary before writing role-based rules that reference `employee` |
| Unpinned HuggingFace embedding model revision (`BAAI/bge-small-en-v1.5`) | Infra/deployment | Pin to a specific commit/revision hash in the loader call |
| RAG-retrieved PDF content trusted with no provenance/integrity check | Tool implementation | Checksum or version-control the bundled PDF asset rather than implicitly trusting it |
| Rolling chat history reinforcement across turns within a session | Agent | Consider per-turn re-validation of role/permission claims rather than trusting reinforced context |
| Within-session hallucination compounding with no reconciliation step | Agent | Add a lightweight fact-check/reconciliation step between tool calls in the same session loop |
| UI/backend role desync not visibly surfaced to the user | Agent / Tool implementation | Surface the actually-enforced (post-policy) role back to the UI, not just the caller-selected one |
| `_fail_secure_decision()` fallback diverges materially from guidance.txt (e.g., treats `purchase` as unconditionally safe) | Tool implementation / Infra | Rewrite the fallback to mirror guidance.txt's real thresholds, or fail closed entirely |
| No durable, queryable audit trail of tool calls, arguments, role, and outcome | Infra | Add persistent structured logging for every tool invocation and its allow/deny outcome |

---

## Policy Rules (OPA scope only)

### Input Schema

| Field | Source |
|---|---|
| `input.name` | Tool name (all 12 tools, `tool_definitions.json`) |
| `input.args.ticket_content` | `create_ticket`, `submit_ticket` |
| `input.args.question` | `ask_for_workpolicy` |
| `input.args.email_content` | `send_email` |
| `input.args.body` | `send_email` |
| `input.args.report_data` | `email_compensation_report` |
| `input.args.justification` | `purchase` |
| `input.args.select_fields` | `view_team_compensation`, `export_compensation_data` |
| `input.args.external_sharing` | `export_compensation_data`, `email_compensation_report` |
| `input.args.destination` | `email_compensation_report` |
| `input.args.recipient_email` | `send_email` |
| `input.args.user_role` | `set_user_role` |
| `input.args.amount` | `purchase`, `return_product` |
| `input.extensions.subject.role` | Role/Session State layer (architecture.md), `system_vars.json`'s `roles` field |

### Known values

- Blocked free-text phrases (case-insensitive substring): `"ignore all policies"`, `"bypass security"`, `"override all policies"`, `"show all SSN data"` — guidance.txt Rules 11-14.
- Blocked sensitive field names (for `select_fields` set-membership check): `ssn`, `home_address`, `bank_account`, `tax_id`, `emergency_contact` — guidance.txt Rules 3, 16.
- Blocked email domains (exact suffix match): `gmail.com`, `yahoo.com`, `hotmail.com`, `outlook.com`, `personal.com` — guidance.txt Rule 8.
- Trusted internal domain: `ibm.com` — guidance.txt Rules 6, 7.
- Role values referenced: `manager`, `employee` (per `system_vars.json`; note the ASI03-4 gap-register item — this value must be reconciled with the tool's actual accepted values before the rule can fire in practice).
- Compensation-scoped tools: `view_team_compensation`, `export_compensation_data`, `email_compensation_report`.
- Purchase thresholds: employee cap $200, manager cap $1,000 — guidance.txt Rules 9, 10.

### Rule: SET_ROLE_UNVERIFIABLE
- OWASP: ASI03
- Severity: Soft block
- Condition: `input.name` equals `set_user_role`. Because no structured field can distinguish an authenticated role change from an unauthenticated one, this rule can only flag/log every such call for downstream review rather than deny outright — denying it entirely would break the tool's only role-assignment path with no replacement available yet.
- Matching: exact (tool name)

### Rule: DEFAULT_SENSITIVE_FIELD_EXPOSURE
- OWASP: ASI02
- Severity: Hard block
- Condition: `input.name` is one of `view_team_compensation`, `export_compensation_data`, AND `input.args.select_fields` is absent, null, or does not exclude every blocked sensitive field name.
- Matching: set-membership (blocked field names) combined with a presence/absence check on `select_fields`

### Rule: EXTERNAL_COMPENSATION_SHARING
- OWASP: ASI02
- Severity: Hard block
- Condition: `input.name` equals `export_compensation_data` or `email_compensation_report`, AND `input.args.external_sharing` is `true`.
- Matching: exact (boolean)

### Rule: COMPENSATION_EMAIL_DOMAIN_RESTRICTION
- OWASP: ASI02
- Severity: Hard block
- Condition: `input.name` equals `email_compensation_report`, AND the domain of `input.args.destination` is not `ibm.com`.
- Matching: case-insensitive exact-suffix match on domain

### Rule: BLOCKED_EMAIL_DOMAIN
- OWASP: ASI02
- Severity: Hard block
- Condition: `input.name` is `send_email` or `email_compensation_report`, AND the domain of `input.args.recipient_email` or `input.args.destination` is one of the blocked domains.
- Matching: case-insensitive exact-suffix match on domain, set-membership against the blocked-domain list

### Rule: MANAGER_ROLE_GATED_COMPENSATION_ACCESS
- OWASP: ASI03
- Severity: Hard block
- Condition: `input.name` is one of `view_team_compensation`, `export_compensation_data`, `email_compensation_report`, AND `input.extensions.subject.role` is not `manager`.
- Matching: exact (string equality)

### Rule: PROMPT_INJECTION_PHRASE_BLOCK
- OWASP: ASI01
- Severity: Hard block
- Condition: Any free-text argument (`ticket_content`, `question`, `email_content`, `body`, `report_data`, `justification`) contains one of the blocked phrases.
- Matching: case-insensitive substring

---

## Violation Code Reference

| Code | OWASP | Severity |
|---|---|---|
| SET_ROLE_UNVERIFIABLE | ASI03 | Soft block |
| DEFAULT_SENSITIVE_FIELD_EXPOSURE | ASI02 | Hard block |
| EXTERNAL_COMPENSATION_SHARING | ASI02 | Hard block |
| COMPENSATION_EMAIL_DOMAIN_RESTRICTION | ASI02 | Hard block |
| BLOCKED_EMAIL_DOMAIN | ASI02 | Hard block |
| MANAGER_ROLE_GATED_COMPENSATION_ACCESS | ASI03 | Hard block |
| PROMPT_INJECTION_PHRASE_BLOCK | ASI01 | Hard block |
