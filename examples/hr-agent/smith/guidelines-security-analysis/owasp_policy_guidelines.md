# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines
# Tool: hr-agent (HR Copilot — 6 tools)

---

## Architecture Summary

The HR Copilot is an A2A agent (`agent.py` :8001) that runs an LLM tool-calling loop over 6 HR tools (`get_compensation`, `display_compensation`, `get_directory`, `send_email`, `search_repos`, `adjust_compensation`). All outbound tool calls flow through an authbridge-cpex sidecar forward proxy (:8081) that resolves caller identity from JWTs, runs Cedar PDP, redacts SSNs, and enforces session taint; the MCP tool server (`server.py` :9100) has no enforcement of its own. OPA can intercept at the agent → sidecar boundary where `input.name`, `input.arguments.*`, and `input.extensions.subject.*` (roles, permissions, has_approval) are all present as structured fields.

---

## OWASP Top 10 for Agentic AI Security — Scope Assessment

### ASI01 — Agent Goal Hijack
**Risk:** Crafted user messages or poisoned tool responses redirect the LLM to call tools with arguments it should not supply (e.g., `include_ssn=true`, excessive `amount`).
**Verdict:** Partial — OPA can block the downstream tool call after the LLM has decided to make it (structured field checks on `include_ssn`, `amount`, `has_approval`); OPA cannot intercept the LLM's reasoning or the goal-shifting itself (Agent layer).

### ASI02 — Tool Misuse and Exploitation
**Risk:** The LLM or a crafted user prompt assembles a tool call (wrong `visibility`, excessive `amount`, exfiltration via `send_email`) that abuses a legitimate tool within granted permissions.
**Verdict:** Partial — OPA can enforce parameter-level rules (`visibility`, `amount`, SSN-in-email body) at invocation time; tool-chain exfiltration without an SSN (e.g., full directory in email body) is out of OPA scope (Agent layer).

### ASI03 — Identity and Privilege Abuse
**Risk:** Callers attempt to access tools or data beyond their role (`hr`-only compensation tools, `security`-only external repos) or exceed their permission (SSN without `view_ssn`) or approval threshold (`adjust_compensation > $10,000` without `has_approval`).
**Verdict:** In scope — `input.extensions.subject.roles`, `permissions`, and `has_approval` are Verified (JWT-derived) and present at tool invocation time; OPA can enforce all role/permission/approval checks.

### ASI04 — Agentic Supply Chain Vulnerabilities
**Risk:** Compromised third-party packages (`litellm`, `a2a-sdk`, `httpx`) or an unpinned LLM model alter tool argument construction or identity header forwarding.
**Verdict:** Out of scope — OPA cannot verify the integrity of packages that constructed the invocation. Ownership: Infrastructure/Deployment.

### ASI05 — Unexpected Code Execution (RCE)
**Risk:** Agents that generate and execute code create RCE pathways.
**Verdict:** Out of scope — this agent has no code-generation or code-execution tools. Not applicable.

### ASI06 — Memory & Context Poisoning
**Risk:** Poisoned tool responses (e.g., `internal_notes` with injected instructions, or SSN data) enter the in-memory conversation history and bias subsequent LLM decisions.
**Verdict:** Out of scope — OPA intercepts before tool execution; it cannot inspect or filter tool responses. Ownership: Agent layer (output filtering).

### ASI07 — Insecure Inter-Agent Communication
**Risk:** Session ID hijacking via a forged `X-Session-Id`/`contextId`, or a compromised sidecar injecting malicious MCP responses.
**Verdict:** Out of scope — `X-Session-Id` is not OPA-enforceable; sidecar integrity is an infrastructure concern. Ownership: Sidecar / Infrastructure.

### ASI08 — Cascading Failures
**Risk:** A single intra-session cascade (e.g., `get_compensation(include_ssn=true)` → `send_email` with SSN in body) executes within a single turn without a policy gate between calls.
**Verdict:** Partial — OPA can block the final `send_email` call if it detects an SSN-pattern in `input.arguments.body` or `input.arguments.subject`; it cannot see the cross-call data flow, only the individual invocation.

### ASI09 — Human-Agent Trust Exploitation
**Risk:** Prompt injection causes the agent to fabricate justifications for data disclosure, or cognitive overload causes reviewers to approve denied requests.
**Verdict:** Out of scope — LLM reasoning and UX layers; OPA cannot detect fabricated rationales. Ownership: Agent layer.

### ASI10 — Rogue Agents
**Risk:** Malicious or compromised peer agents deviate from intended scope.
**Verdict:** Out of scope — single-agent deployment; no multi-agent trust graph. Not applicable.

---

## Summary Table

| OWASP Category | In OPA scope? | Out-of-scope owner |
|---|---|---|
| ASI01 Agent Goal Hijack | Partial | Agent layer (LLM reasoning, context filtering) |
| ASI02 Tool Misuse and Exploitation | Partial | Agent layer (non-SSN tool-chain exfiltration, rate limits) |
| ASI03 Identity and Privilege Abuse | Yes | — |
| ASI04 Agentic Supply Chain Vulnerabilities | No | Infrastructure/Deployment |
| ASI05 Unexpected Code Execution (RCE) | No | N/A — not applicable |
| ASI06 Memory & Context Poisoning | No | Agent layer (output filtering) |
| ASI07 Insecure Inter-Agent Communication | No | Sidecar / Infrastructure |
| ASI08 Cascading Failures | Partial | Agent layer (cross-call data flow) |
| ASI09 Human-Agent Trust Exploitation | No | Agent layer / UX |
| ASI10 Rogue Agents | No | N/A — not applicable |

Categories flowing into the OPA policy: ASI01 (partial), ASI02 (partial), ASI03, ASI08 (partial)

---

## Gap Register

| Threat | Layer | Recommended action |
|---|---|---|
| ASI01 T3 — Poisoned `internal_notes` in tool response enters conversation history, directing LLM to call `send_email` with sensitive data | Agent layer | Filter or sanitise tool response content before appending to message history; strip `internal_notes` from `get_compensation` results before feeding to LLM |
| ASI01 T4 — Gradual prompt injection via free-text `send_email` body/subject steers LLM goal | Agent layer | Apply prompt-injection detection on incoming user messages before they enter the LLM context |
| ASI02 T4 — LLM chains `get_directory` → `send_email` to exfiltrate full directory roster | Agent layer | Implement output-pattern monitoring or require confirmation before `send_email` when body contains bulk employee data |
| ASI03 T2 — Forged/replayed `X-Session-Id` hijacks another user's taint session bucket | Sidecar / Infrastructure | Bind `X-Session-Id` cryptographically to the resolved JWT subject in the cpex sidecar; reject mismatched sessions |
| ASI04 T1 — Compromised third-party packages alter tool argument construction | Infrastructure/Deployment | Pin all Python dependencies by hash; maintain SBOM; use reproducible container builds |
| ASI04 T2 — Unpinned Ollama model — poisoned update alters LLM tool-selection behaviour | Infrastructure/Deployment | Pin the model by digest; gate model updates through a test suite |
| ASI06 T1 — Crafted `internal_notes` in `get_compensation` response poisons conversation history | Agent layer | Strip or redact `internal_notes` from tool results before they enter LLM context |
| ASI06 T2 — User builds false context across turns to manipulate LLM decisions | Agent layer | Bound conversation history window; do not allow user messages to persist security-relevant claims without re-validation from JWT claims |
| ASI07 T1 — Crafted A2A `contextId` to hijack existing session | Sidecar / Infrastructure | Validate that `X-Session-Id`/`contextId` corresponds to the authenticated JWT subject; reject mismatches |
| ASI07 T2 — Compromised sidecar forward proxy injects malicious MCP response payloads | Infrastructure/Deployment | Enforce mTLS between agent and sidecar; verify certificate pinning; monitor sidecar for anomalous response payloads |
| ASI08 T2 — Poisoned adjust_compensation in turn poisons session context for later calls | Agent layer | Clear or quarantine session history after a denied tool call |
| ASI09 T1 — LLM fabricates justification for sensitive data disclosure | Agent layer | Strengthen SYSTEM_PROMPT with explicit prohibitions on self-justifying data disclosure |
| ASI09 T2 — Cognitive overload of human reviewers via high-frequency denial summaries | Agent layer / UX | Implement rate limiting on `message/send` per session; alert on anomalous denial rates |

---

## Policy Rules (OPA scope only)

### Input Schema
| Field | Source |
|---|---|
| `input.name` | Tool name (LLM-chosen string) |
| `input.arguments.employee_id` | Tool argument (string) |
| `input.arguments.include_ssn` | Tool argument (boolean) |
| `input.arguments.amount` | Tool argument (integer) |
| `input.arguments.visibility` | Tool argument (enum: `internal`, `public`, `external`) |
| `input.arguments.repo_name` | Tool argument (string, optional) |
| `input.arguments.to` | Tool argument (string) |
| `input.arguments.subject` | Tool argument (string) |
| `input.arguments.body` | Tool argument (string) |
| `input.arguments.department` | Tool argument (string, optional) |
| `input.extensions.subject.roles` | Verified — JWT claim resolved by cpex sidecar (array of strings) |
| `input.extensions.subject.permissions` | Verified — JWT claim resolved by cpex sidecar (array of strings) |
| `input.extensions.subject.has_approval` | Verified — JWT claim resolved by cpex sidecar (string: `"true"` or `"false"`) |

### Known values
- Compensation tools: `get_compensation`, `display_compensation`, `adjust_compensation`
- Repo tool: `search_repos`
- Email tool: `send_email`
- Roles: `hr`, `engineer`, `marketing`, `finance`, `platform`, `security`
- Permissions: `view_ssn`, `None`
- Visibility values: `internal`, `public`, `external`
- SSN pattern: `\d{3}-\d{2}-\d{4}` (US Social Security Number format)

---

### Rule: ROLE_COMP_BLOCK
- OWASP: ASI03 (Identity and Privilege Abuse) — catalog mitigation: "Mandate Per-Action Authorization: Re-verify each privileged step with a centralized policy engine"
- Severity: Hard block
- Condition: `input.name` is one of `get_compensation`, `display_compensation`, `adjust_compensation` AND `"hr"` is not a member of `input.extensions.subject.roles`
- Matching: Exact set-membership for tool name; set-membership (not-contains) for roles array

### Rule: PERM_SSN_BLOCK
- OWASP: ASI03 (Identity and Privilege Abuse) — catalog mitigation: "Enforce Task-Scoped, Time-Bound Permissions"
- Severity: Hard block
- Condition: `input.name == "get_compensation"` AND `input.arguments.include_ssn == true` AND `"view_ssn"` is not a member of `input.extensions.subject.permissions`
- Matching: Exact equality for tool name and boolean argument; set-membership (not-contains) for permissions array

### Rule: REPO_ACCESS_BLOCK
- OWASP: ASI02 (Tool Misuse) + ASI03 (Identity and Privilege Abuse) — catalog mitigations: "Least Agency and Least Privilege for Tools"; "Mandate Per-Action Authorization"
- Severity: Hard block
- Condition: `input.name == "search_repos"` AND `"engineer"` is not a member of `input.extensions.subject.roles` AND `"security"` is not a member of `input.extensions.subject.roles`
- Matching: Exact equality for tool name; set-membership (not-contains) for roles array (caller must hold at least one of `engineer` or `security`)

### Rule: REPO_EXTERNAL_BLOCK
- OWASP: ASI02 (Tool Misuse) + ASI03 (Identity and Privilege Abuse) — catalog mitigation: "Policy Enforcement Middleware ('Intent Gate')"
- Severity: Hard block
- Condition: `input.name == "search_repos"` AND `input.arguments.visibility == "external"` AND `"security"` is not a member of `input.extensions.subject.roles`
- Matching: Exact equality for tool name and visibility value; set-membership (not-contains) for roles array

### Rule: ADJUST_APPROVAL_BLOCK
- OWASP: ASI03 (Identity and Privilege Abuse) + ASI01 (Agent Goal Hijack) — catalog mitigations: "Apply Human-in-the-Loop for Privilege Escalation"; "Minimize the impact of goal hijacking by requiring human approval for high-impact actions"
- Severity: Hard block
- Condition: `input.name == "adjust_compensation"` AND `input.arguments.amount > 10000` AND `input.extensions.subject.has_approval != "true"`
- Matching: Exact equality for tool name; numeric comparison (greater-than) for amount; exact equality for has_approval string

### Rule: EMAIL_SSN_BLOCK
- OWASP: ASI01 (Agent Goal Hijack) + ASI02 (Tool Misuse) + ASI08 (Cascading Failures) — catalog mitigations: "Treat all natural-language inputs as untrusted"; "Policy Enforcement Middleware ('Intent Gate')"
- Severity: Hard block
- Condition: `input.name == "send_email"` AND (`input.arguments.body` matches SSN pattern `\d{3}-\d{2}-\d{4}` OR `input.arguments.subject` matches SSN pattern `\d{3}-\d{2}-\d{4}`)
- Matching: Regex match on string arguments; OR semantics across body and subject fields

---

## Violation Code Reference

| Code | OWASP | Severity |
|---|---|---|
| ROLE_COMP_BLOCK | ASI03 | Hard block |
| PERM_SSN_BLOCK | ASI03 | Hard block |
| REPO_ACCESS_BLOCK | ASI02, ASI03 | Hard block |
| REPO_EXTERNAL_BLOCK | ASI02, ASI03 | Hard block |
| ADJUST_APPROVAL_BLOCK | ASI01, ASI03 | Hard block |
| EMAIL_SSN_BLOCK | ASI01, ASI02, ASI08 | Hard block |

Citations verified: 6/6 — all `input.arguments.*` fields confirmed in `tool_definitions.json`; all `input.extensions.subject.*` fields confirmed in `system_vars.json`; all mitigation citations confirmed in `owasp_10_ai_catalog.json`; all rules trace to threat instances in `threat_model.md`.

---

## STEP 7 — Combined Candidate-Rule List (for review)

1. [ASI03/ROLE_COMP_BLOCK + Q9] `input.name` ∈ {`get_compensation`, `display_compensation`, `adjust_compensation`}; operator: set-membership; value: `hr` not in `subject.roles` → deny
2. [ASI03/PERM_SSN_BLOCK + Q10] `input.name == "get_compensation"` AND `input.arguments.include_ssn == true`; operator: exact + set-membership; value: `view_ssn` not in `subject.permissions` → deny
3. [ASI02+ASI03/REPO_ACCESS_BLOCK + Q9] `input.name == "search_repos"`; operator: set-membership; value: neither `engineer` nor `security` in `subject.roles` → deny
4. [ASI02+ASI03/REPO_EXTERNAL_BLOCK + Q10] `input.name == "search_repos"` AND `input.arguments.visibility == "external"`; operator: exact + set-membership; value: `security` not in `subject.roles` → deny
5. [ASI01+ASI03/ADJUST_APPROVAL_BLOCK + Q13b] `input.name == "adjust_compensation"` AND `input.arguments.amount > 10000`; operator: numeric comparison + exact; value: `subject.has_approval != "true"` → deny
6. [ASI01+ASI02+ASI08/EMAIL_SSN_BLOCK + Q14] `input.name == "send_email"` AND `body` or `subject` matches `\d{3}-\d{2}-\d{4}`; operator: regex; value: SSN pattern → deny

## STEP 8 — Coverage Scratch Table

| Candidate | Field | Operator | Value set | Matching guidance.txt rule # | Covered? |
|---|---|---|---|---|---|
| #1 hr-only for comp tools | `input.name` + `subject.roles` | set-membership | `get_compensation`, `display_compensation`, `adjust_compensation`; role `hr` | — | No |
| #2 view_ssn for include_ssn | `input.arguments.include_ssn` + `subject.permissions` | exact + set-membership | `true`; `view_ssn` | — | No |
| #3 search_repos engineer/security only | `input.name` + `subject.roles` | exact + set-membership | `search_repos`; `engineer`, `security` | Rule 1 (partial — about visibility only, not role gate) | No |
| #4 no external repos for non-security | `input.arguments.visibility` + `subject.roles` | exact + set-membership | `external`; `security` | Rule 1 ("internal only") — same field, same polarity, but security exception absent | No |
| #5 adjust comp approval threshold | `input.arguments.amount` + `subject.has_approval` | numeric + exact | `> 10000`; `"true"` | — | No |
| #6 SSN in email body/subject | `input.arguments.body/subject` | regex | `\d{3}-\d{2}-\d{4}` | — | No |

All 6 candidates are missing from `guidance.txt`. All 6 are appended to `guidance_updated.txt`.

## STEP 8b — Redundancy Self-Check

Pairwise comparison of all 8 rules in `guidance_updated.txt` (existing rules 1–2 + new rules 3–8):

- Rules 1 ("internal only") and 4 ("external blocked for non-security"): Same field (`input.arguments.visibility`), same polarity (block non-internal), but Rule 4 is scoped to `security` exception — not present in Rule 1. Rule 1 is broader (all employees, all external); Rule 4 is a subset condition. They overlap on the `visibility` field but Rule 4's security-exception polarity distinguishes them. **Not a redundant pair** — Rule 1 becomes partially superseded by Rules 3+4 combined but they are not pairwise redundant.
- Rules 3 (role gate for `search_repos`) and 4 (visibility gate for `search_repos`): Different fields — Rule 3 checks role for tool access; Rule 4 checks `visibility` value. **Not a redundant pair.**
- All other pairs: distinct fields, distinct tools, or distinct operators.

**Redundancy self-check: no overlapping pairs found.**
