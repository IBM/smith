# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines
# Tool: call-for-papers-mcp / get_events

---

## Architecture Summary

The `call-for-papers-mcp` system is a linear four-layer stack: a FastAPI HTTP layer (`agent.py`) accepts caller-supplied `question` and `user_profile`, an Agent/LLM layer builds a system prompt with `user_profile` values injected verbatim and drives a ReAct planner, a single MCP tool (`get_events` in `server.py`) accepts three LLM-generated arguments, and the tool implementation (`app.py`) issues an unencrypted HTTP GET to WikiCFP. All identity and session fields (`user_role`, `dissertation_area`, `queries_this_session`) are self-reported by the caller with no cryptographic verification, and `topic` — the primary policy-scoping parameter — is silently discarded by `app.py` before the external call, making OPA enforcement at the MCP invocation boundary the only structural control point over what actually reaches WikiCFP.

---

## OWASP Top 10 for Agentic AI Security — Scope Assessment

### ASI01 — Agent Goal Hijack
**Risk:** Caller-controlled `user_profile.*` fields and `question` are injected verbatim into the system prompt or fed to the LLM; a prompt-injection payload redirects the LLM to pick out-of-scope `topic`, blocked `keywords`, or oversized `limit`. Adversarial content in the WikiCFP HTML response can also re-enter the LLM on subsequent turns.
**Verdict:** Partial — the downstream effect (LLM emits a bad structured argument) is checkable at `input.args.*`; the injection mechanism itself (arbitrary text inside the LLM's context window) and the LLM's re-reading of the WikiCFP HTML response are outside OPA's interception surface.

### ASI02 — Tool Misuse and Exploitation
**Risk:** All three LLM-generated arguments (`keywords`, `topic`, `limit`) reach the external WikiCFP call with no server-side validation in `server.py` or `app.py`; further, `topic` is silently discarded by `app.py`, so scope enforcement depends entirely on the policy at invocation time.
**Verdict:** In scope — `input.args.keywords`, `input.args.topic`, and `input.args.limit` are all present as structured fields at the MCP interception boundary and can be checked by OPA.

### ASI03 — Identity and Privilege Abuse
**Risk:** `user_role`, `dissertation_area`, `user_name`, and `queries_this_session` are all caller-self-reported with no verification; a caller can escalate their role, misrepresent their dissertation area to defeat PhD scope, under-report the session counter to defeat the rate limit, or impersonate another user. Multi-role `user_role` arrays add ambiguity to policy evaluation.
**Verdict:** Partial — OPA can enforce every rule that depends on these fields as structured attributes; it cannot verify their authenticity. Field-integrity is an Application-layer concern.

### ASI04 — Agentic Supply Chain Vulnerabilities
**Risk:** Third-party libraries (`requests`, `beautifulsoup4`, `fastmcp`) are unpinned per `architecture.md`; the WikiCFP request uses unencrypted HTTP (network MITM feasible); the agent's system prompt and blocked-keyword list live in a source repo with no attestation or content-hash pinning cited.
**Verdict:** Out of scope — dependency loading, TLS to external services, and repo/source-code integrity all occur outside the tool invocation moment; no structured field carries this evidence.

### ASI05 — Unexpected Code Execution (RCE)
**Risk:** Not applicable — no `eval`, `exec`, subprocess call, code-generation, template-engine execution, or unsafe deserialisation exists in the stack.
**Verdict:** Out of scope — N/A.

### ASI06 — Memory & Context Poisoning
**Risk:** Not applicable — the agent is stateless with no persistent memory store, no vector DB, no session store.
**Verdict:** Out of scope — N/A.

### ASI07 — Insecure Inter-Agent Communication
**Risk:** Not applicable — single-agent system with a local stdio MCP transport; no A2A, no message bus, no shared registry.
**Verdict:** Out of scope — N/A.

### ASI08 — Cascading Failures
**Risk:** Not applicable — linear call chain, no delegation, no fan-out, no persistent state.
**Verdict:** Out of scope — N/A.

### ASI09 — Human-Agent Trust Exploitation
**Risk:** The `/chat` natural-language response is composed from LLM reasoning over WikiCFP results with no source attribution, no confidence marker, no logging; the LLM may fabricate plausible conference entries, and adversarial WikiCFP entries can surface malicious links to the caller.
**Verdict:** Out of scope — response-content integrity, source attribution, and audit logging live post-tool-call in the Agent / Tool-implementation layer; nothing about the response is a structured field at invocation time.

### ASI10 — Rogue Agents
**Risk:** Not applicable — single-agent system with no orchestration layer, no peer agents, no delegation chains.
**Verdict:** Out of scope — N/A.

---

## Summary Table

| OWASP Category | In OPA scope? | Out-of-scope owner |
|---|---|---|
| ASI01 — Agent Goal Hijack | Partial | Agent layer (prompt sanitization, WikiCFP-response filtering) |
| ASI02 — Tool Misuse and Exploitation | Yes | — |
| ASI03 — Identity and Privilege Abuse | Partial | Application layer (authenticated identity provider, server-side session store) |
| ASI04 — Agentic Supply Chain Vulnerabilities | No | Infrastructure / deployment (dependency pinning, TLS, repo attestation) |
| ASI05 — Unexpected Code Execution (RCE) | No | N/A |
| ASI06 — Memory & Context Poisoning | No | N/A |
| ASI07 — Insecure Inter-Agent Communication | No | N/A |
| ASI08 — Cascading Failures | No | N/A |
| ASI09 — Human-Agent Trust Exploitation | No | Agent layer (source attribution, URL scanning) + Tool implementation (audit logging) |
| ASI10 — Rogue Agents | No | N/A |

Categories flowing into the OPA policy: ASI01 (partial), ASI02, ASI03 (partial)

---

## Gap Register

| Threat | Layer | Recommended action |
|---|---|---|
| ASI01: Prompt injection via `user_profile.*` fields (`user_name`, `research_area`, `dissertation_area`, any key) injected verbatim into the system prompt | Agent layer | Sanitize and validate `user_profile` values before splicing them into the system prompt; strip or escape natural-language instruction patterns; consider using a fixed template with escaped placeholders rather than free-form key/value concatenation. |
| ASI01: Prompt injection via caller-supplied `question` field | Agent layer | Apply prompt-injection detection / classifier over the `question` field before it reaches the LLM's instruction context; consider intent-capsule binding of goal + scope per LLM call. |
| ASI01: Adversarial WikiCFP HTML response (event descriptions, links) re-read by the LLM as tool output | Tool implementation / Agent layer | Sanitize the tool return payload before it re-enters the LLM (strip HTML, drop control characters, cap string lengths); apply prompt-injection detection over event descriptions. |
| ASI03: `user_role` is self-reported with no verification | Application layer | Integrate an authenticated identity provider that issues verified role claims; do not rely solely on OPA when the role value is caller-supplied. |
| ASI03: `dissertation_area` is self-reported with no verification | Application layer | Bind `dissertation_area` to an authenticated user record on the server side (not to a caller-supplied `user_profile` value); source it from the identity provider or a curated departmental directory. |
| ASI03: `queries_this_session` is self-reported, making the session rate limit bypassable | Application layer | Maintain the session query counter server-side (e.g. in a session store keyed by an authenticated session identifier) rather than accepting the caller-supplied value. |
| ASI03: `user_name` self-reporting allows attribution to another user (Incriminating Another User) | Application layer | Bind `user_name` to the authenticated identity; never accept it from the request body. |
| ASI04: `requests`, `beautifulsoup4`, `fastmcp`, and transitive dependencies are unpinned and unverified | Infrastructure / deployment | Pin dependency versions in a lockfile, verify hashes at install time, generate and publish an SBOM/AIBOM, and run a supply-chain scanner in CI. |
| ASI04: WikiCFP request uses unencrypted HTTP; on-path attacker can substitute response | Infrastructure / Tool implementation | Switch to HTTPS; if WikiCFP's TLS endpoint is unavailable, add a response-integrity check (hash pinning of expected response structure) or accept the risk explicitly with monitoring. |
| ASI04: Agent source (system prompt, blocked-keyword list) is not attested; a compromised commit propagates unchecked | Infrastructure / deployment | Content-hash pin the system prompt and rule tables; require signed commits and staged rollout with differential tests on prompt / rule changes. |
| ASI09: LLM may fabricate conference entries with no source attribution | Agent layer | Attach source attribution (WikiCFP result URLs / IDs) to every entry in the `/chat` response; add a disclaimer whenever the LLM produces content not directly sourced from the WikiCFP tool result. |
| ASI09: Adversarial `event_link` from WikiCFP is surfaced to the caller without scanning | Tool implementation / Agent layer | Scan outbound URLs against a threat-intel feed before including them in the response; render links with domain-warning UI cues. |
| ASI09: No forensic logging of tool invocations, policy denials, or violation attribution | Tool implementation / observability | Emit immutable, structured audit logs of every `get_events` invocation with the input arguments, subject attributes, policy decision, and violation code; retain per compliance policy. |

---

## Policy Rules (OPA scope only)

### Input Schema

| Field | Source |
|---|---|
| `input.name` | Tool name (`get_events`) — `tool_definitions.json` |
| `input.arguments.keywords` | `tool_definitions.json` — string, free-text search terms |
| `input.arguments.topic` | `tool_definitions.json` — string, expected to be one of three approved values |
| `input.arguments.limit` | `tool_definitions.json` — integer, default 10 |
| `input.extensions.subject.user_role` | `system_vars.json` — string OR array of strings; values drawn from `{faculty, phd_student, guest}` |
| `input.extensions.subject.dissertation_area` | `system_vars.json` — string, one of the three approved research areas |
| `input.extensions.subject.queries_this_session` | `system_vars.json` — integer, self-reported session counter |

### Known values

```
approved_topics = {
  "Artificial intelligence",
  "Cybersecurity and privacy",
  "Software engineering"
}

blocked_keywords = {
  "bioinformatics", "genomics", "clinical trials", "drug discovery",
  "quantum physics", "materials science", "renewable energy",
  "economics", "finance", "marketing", "supply chain",
  "education", "psychology", "sociology", "political science",
  "trade show", "career fair", "startup expo", "hackathon"
}

allowed_roles         = { "faculty", "phd_student" }
faculty_limit_cap     = 15
phd_limit_cap         = 10
absolute_limit_min    = 1
absolute_limit_max    = 15
session_cap           = 5
```

**Multi-role semantics.** Per `system_vars.json` and questionnaire Q8, `user_role` may be an array. Rule evaluation treats a multi-role array as the strictest (least-permissive) role present: if any element is `guest`, the request is denied by CFP-ROLE-001; if any element is `phd_student`, PhD-scope constraints (CFP-TOPIC-002, CFP-LIMIT-002) apply.

### Rule: CFP-ROLE-001
- OWASP: ASI03 / ASI02
- Mitigation grounding: ASI03 catalog `mitigations` — "Enforce Task-Scoped, Time-Bound Permissions" (least-privilege on tool invocation) and "Bind permissions to subject, resource, purpose, and duration."
- Threat linkage: ASI03 threat instances (caller self-reports `user_role`) and ASI03 multi-role edge case.
- Severity: Hard block
- Condition: Deny `get_events` when `input.extensions.subject.user_role` is not in `allowed_roles`; if `user_role` is an array, deny when any element is outside `allowed_roles` (`guest` present → deny).
- Matching: Set membership (exact string match, case-sensitive), applied element-wise for arrays.

### Rule: CFP-TOPIC-001
- OWASP: ASI01 / ASI02
- Mitigation grounding: ASI02 catalog `mitigations` — "Policy Enforcement Middleware ('Intent Gate')" and "Semantic and Identity Validation" (validate intended semantics of tool calls, fail closed on ambiguity).
- Threat linkage: ASI02 LLM-emits-out-of-scope-topic threat instance; ASI01 prompt-injection-shifts-topic threat instances.
- Severity: Hard block
- Condition: Deny `get_events` when `input.arguments.topic` is not in `approved_topics`.
- Matching: Exact equality, case-sensitive (verbatim match required per the `tool_definitions.json` description).

### Rule: CFP-TOPIC-002
- OWASP: ASI03
- Mitigation grounding: ASI03 catalog `mitigations` — "Bind permissions to subject, resource, purpose, and duration" (subject `dissertation_area` bound to resource `topic`).
- Threat linkage: ASI03 threat instance (PhD self-reports `dissertation_area` to bypass narrow-scope rule).
- Severity: Hard block
- Condition: Deny `get_events` when `input.extensions.subject.user_role` includes `phd_student` and `input.arguments.topic` does not equal `input.extensions.subject.dissertation_area`.
- Matching: Exact equality (string) between `topic` and `dissertation_area`; set-membership (`phd_student` in the role value or array) for the guard.

### Rule: CFP-LIMIT-001
- OWASP: ASI02
- Mitigation grounding: ASI02 catalog `mitigations` — "Adaptive Tool Budgeting" (usage ceilings on parameters that map to cost / rate).
- Threat linkage: ASI02 LLM-emits-oversized-limit threat instance; ASI01 prompt-injection-forces-oversized-limit threat instance.
- Severity: Hard block
- Condition: Deny `get_events` when `input.arguments.limit` < `absolute_limit_min` (< 1) OR > `absolute_limit_max` (> 15).
- Matching: Numeric comparison.

### Rule: CFP-LIMIT-002
- OWASP: ASI02 / ASI03
- Mitigation grounding: ASI02 catalog `mitigations` — "Least Agency and Least Privilege for Tools" (per-role scope on the `limit` argument).
- Threat linkage: ASI02 LLM-emits-oversized-limit threat instance (PhD-role sub-case) + ASI03 role-scope threat.
- Severity: Hard block
- Condition: Deny `get_events` when `input.extensions.subject.user_role` includes `phd_student` and `input.arguments.limit` > `phd_limit_cap` (> 10).
- Matching: Numeric comparison guarded by set-membership on `user_role`.

### Rule: CFP-KW-001
- OWASP: ASI01 / ASI02
- Mitigation grounding: ASI02 catalog `mitigations` — "Policy Enforcement Middleware ('Intent Gate')" (schema and value validation of LLM/planner outputs before execution).
- Threat linkage: ASI02 LLM-emits-blocked-keyword threat instance; ASI01 prompt-injection-shifts-keywords threat instances.
- Severity: Hard block
- Condition: Deny `get_events` when `input.arguments.keywords` contains any term from `blocked_keywords`.
- Matching: Case-insensitive substring match — each blocked term is checked as a substring of `keywords`.

### Rule: CFP-RATE-001
- OWASP: ASI03
- Mitigation grounding: ASI03 catalog `mitigations` — "Enforce Task-Scoped, Time-Bound Permissions" (per-session ceiling); also aligns with ASI02 "Adaptive Tool Budgeting" (usage ceilings with throttling).
- Threat linkage: ASI03 threat instance (caller under-reports `queries_this_session` to defeat rate limit). Note: the rule enforces the ceiling but cannot verify the counter's integrity — see gap register for the server-side counter recommendation.
- Severity: Hard block
- Condition: Deny `get_events` when `input.extensions.subject.queries_this_session` >= `session_cap` (>= 5).
- Matching: Numeric comparison.

---

## Violation Code Reference

| Code | OWASP | Severity |
|---|---|---|
| CFP-ROLE-001 | ASI03 / ASI02 | Hard block |
| CFP-TOPIC-001 | ASI01 / ASI02 | Hard block |
| CFP-TOPIC-002 | ASI03 | Hard block |
| CFP-LIMIT-001 | ASI02 | Hard block |
| CFP-LIMIT-002 | ASI02 / ASI03 | Hard block |
| CFP-KW-001 | ASI01 / ASI02 | Hard block |
| CFP-RATE-001 | ASI03 | Hard block |

---

## Citation Verification Log

Citations verified: 7/7 — every `input.arguments.*` field referenced by a rule is present in `tool_definitions.json` (`keywords`, `topic`, `limit`); every `input.extensions.subject.*` field is present in `system_vars.json` (`user_role`, `dissertation_area`, `queries_this_session`) and appears in the `architecture.md` Enforcement Points table; every mitigation cited from the OWASP catalog is a verbatim phrase or clear paraphrase from the corresponding ASI category's `mitigations` array in `owasp_10_ai_catalog.json`; every rule traces back to at least one threat instance in `threat_model.md`. No rule cites a questionnaire answer tagged `[inferred — low confidence]` (Q20/Q21/Q22 are unused as rule sources; questionnaire Q9-Q16 which are the sourcing basis are `[derived from guidance.txt]` or `[derived from architecture]`). No rule dropped.
