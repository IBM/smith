# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines
# Tool: get_events

---

## Architecture Summary
`get_events` flows through five layers — HTTP API → Agent (LLM reasoning) → MCP Tool → Tool Implementation → the external WikiCFP scrape — and the Agent layer is the only point where the proposed tool call and the caller's self-reported identity (`user_profile`) are simultaneously visible as structured data. Every subject-identifying field (`user_role`, `dissertation_area`) and every tool argument (`keywords`, `topic`, `limit`) is self-reported or LLM-generated with no authentication or validation at any layer today, and the external WikiCFP response is classified untrusted with no integrity guarantee.

---

## OWASP Top 10 for Agentic AI Security — Scope Assessment

### ASI01 — Agent Goal Hijack
**Risk:** Poisoned WikiCFP listing content re-entering the Agent layer's context could attempt to redirect a subsequent `get_events` call toward a disallowed `topic` or `keywords` value.
**Verdict:** Out of scope — the exploit acts on tool-output content and LLM reasoning after the call executes, not on a structured field visible before execution.

### ASI02 — Tool Misuse and Exploitation
**Risk:** Unconstrained `limit` and `keywords` arguments let the agent request more results than a role's cap allows, or submit search terms the department has explicitly disallowed.
**Verdict:** In scope — `input.arguments.limit` and `input.arguments.keywords` are structured fields visible before execution and can be denied by a rule.

### ASI03 — Identity and Privilege Abuse
**Risk:** A self-reported `user_role` or `dissertation_area` lets a caller claim a wider scope (faculty-level access, or a different research area) than they actually hold.
**Verdict:** Partial — OPA can enforce role/attribute-conditioned restrictions once those fields reach the interception point, but cannot verify the fields are truthful; that verification gap is a separate, non-OPA concern (see Gap Register).

### ASI04 — Agentic Supply Chain Vulnerabilities
**Risk:** None identified — the tool schema is defined locally in `server.py`, not sourced from a dynamic registry, peer agent, or externally-fetched template.
**Verdict:** Out of scope — not applicable to this tool's architecture.

### ASI05 — Unexpected Code Execution (RCE)
**Risk:** None identified — no code-generation, `eval`, or shell-invocation surface exists anywhere in the documented layers.
**Verdict:** Out of scope — not applicable.

### ASI06 — Memory & Context Poisoning
**Risk:** None identified — no persistent memory store, vector database, or retrievable context is documented between requests.
**Verdict:** Out of scope — not applicable.

### ASI07 — Insecure Inter-Agent Communication
**Risk:** None identified — a single agent and a single MCP tool server, with no peer agents or inter-agent protocol.
**Verdict:** Out of scope — not applicable.

### ASI08 — Cascading Failures
**Risk:** None identified — no downstream agent, workflow, or persisted session exists for a fault to propagate into.
**Verdict:** Out of scope — not applicable.

### ASI09 — Human-Agent Trust Exploitation
**Risk:** Untrusted WikiCFP content is presented to the user with no provenance indication, and the user has no basis to distinguish it from a verified source.
**Verdict:** Out of scope — the concern is response-content presentation after tool execution, not a pre-execution structured-field check.

### ASI10 — Rogue Agents
**Risk:** None identified — a single-agent architecture with no multi-agent ecosystem for behavioral divergence to occur within.
**Verdict:** Out of scope — not applicable.

---

## Summary Table

| OWASP Category | In OPA scope? | Out-of-scope owner |
|---|---|---|
| ASI01 | No | Tool implementation (sanitize scraped content) / Agent layer (output validation) |
| ASI02 | Yes | — |
| ASI03 | Partial | Agent layer / Infra (identity verification upstream of OPA) |
| ASI04 | No | N/A |
| ASI05 | No | N/A |
| ASI06 | No | N/A |
| ASI07 | No | N/A |
| ASI08 | No | N/A |
| ASI09 | No | Agent layer (provenance/risk indicator on response) |
| ASI10 | No | N/A |

Categories flowing into the OPA policy: ASI02, ASI03

---

## Gap Register

| Threat | Layer | Recommended action |
|---|---|---|
| Poisoned WikiCFP listing content could redirect subsequent tool calls (ASI01) | Tool implementation | Sanitize or strip instruction-like text from scraped event descriptions/links before returning them to the Agent layer. |
| `user_role` and `dissertation_area` are self-reported with no verification mechanism (ASI03) | Agent layer / Infra | Add a real authentication step upstream of the Agent layer so the values OPA reads from `input.extensions.subject.*` are trustworthy, not just structurally present. |
| Untrusted WikiCFP content shown to the user without a provenance indicator (ASI09) | Agent layer | Display a risk/provenance indicator when composing results derived from `getEvents()`, since the source is classified External/untrusted. |
| Max-5-calls-per-session rule cannot be enforced — `queries_this_session` is a static value, never incremented (guidance.txt) | Tool implementation / Infra | Implement real per-session call counting and pass it as a live `input.extensions.subject.queries_this_session` value before this rule can become OPA-enforceable. |

---

## Policy Rules (OPA scope only)

### Input Schema
| Field | Source |
|---|---|
| input.arguments.keywords | tool_definitions.json |
| input.arguments.topic | tool_definitions.json |
| input.arguments.limit | tool_definitions.json |
| input.extensions.subject.user_role | system_vars.json |
| input.extensions.subject.dissertation_area | system_vars.json |

### Known values
- Approved roles: `faculty`, `phd_student` (`guest` is explicitly denied)
- Role limit caps: `faculty` ≤ 15, `phd_student` ≤ 10; absolute floor 1
- Disallowed `keywords` terms (case-insensitive substring): `bioinformatics`, `genomics`, `clinical trials`, `drug discovery`, `quantum physics`, `materials science`, `renewable energy`, `economics`, `finance`, `marketing`, `supply chain`, `education`, `psychology`, `sociology`, `political science`, `trade show`, `career fair`, `startup expo`, `hackathon`

### Rule: CFP_LIMIT_EXCEEDED
- OWASP: ASI02
- Severity: Hard block
- Condition: `input.arguments.limit` is less than 1, or exceeds the cap for the role in `input.extensions.subject.user_role` (15 for `faculty`, 10 for `phd_student`)
- Matching: numeric comparison, role-conditioned threshold

### Rule: CFP_KEYWORD_BLOCKED
- OWASP: ASI02
- Severity: Hard block
- Condition: `input.arguments.keywords` contains any term from the disallowed list above
- Matching: case-insensitive substring

### Rule: CFP_ROLE_DENIED
- OWASP: ASI03
- Severity: Hard block
- Condition: `input.extensions.subject.user_role` does not include `faculty` or `phd_student` (i.e. the caller is `guest` or has no recognized role)
- Matching: set-membership, exact match against the approved role set

### Rule: CFP_PHD_SCOPE_VIOLATION
- OWASP: ASI03
- Severity: Hard block
- Condition: `input.extensions.subject.user_role` is `phd_student` and `input.arguments.topic` does not equal `input.extensions.subject.dissertation_area`
- Matching: exact equality, role-conditioned

---

## Violation Code Reference

| Code | OWASP | Severity |
|---|---|---|
| CFP_LIMIT_EXCEEDED | ASI02 | Hard block |
| CFP_KEYWORD_BLOCKED | ASI02 | Hard block |
| CFP_ROLE_DENIED | ASI03 | Hard block |
| CFP_PHD_SCOPE_VIOLATION | ASI03 | Hard block |
