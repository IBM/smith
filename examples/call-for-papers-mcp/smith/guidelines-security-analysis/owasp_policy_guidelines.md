# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines
# Tool: call-for-papers-mcp / get_events

---

## Architecture Summary

The `call-for-papers-mcp` system is a two-layer stack: a FastAPI agent layer (`agent.py`) that accepts caller-supplied `user_profile` context and constructs an LLM-backed ReAct agent, which invokes a single MCP tool (`get_events` in `server.py`) over a local stdio transport. All identity and session fields (`user_role`, `dissertation_area`, `queries_this_session`) are self-reported by the caller with no cryptographic verification, and `topic` — the primary policy-scoping parameter — is accepted by `server.py` but silently discarded before the WikiCFP HTTP call in `app.py`, making OPA enforcement at the MCP invocation boundary the only structural control point.

---

## OWASP Top 10 for Agentic AI Security — Scope Assessment

### ASI01 — Agent Goal Hijack
**Risk:** Caller-controlled `user_profile` fields are injected verbatim into the system prompt, enabling prompt injection that redirects the LLM's tool-argument decisions.
**Verdict:** Partial — The downstream effect (LLM selects a bad `topic` or `keywords` value) is OPA-enforceable at invocation time; the injection mechanism itself (inside LLM reasoning) is not.

### ASI02 — Tool Misuse and Exploitation
**Risk:** LLM-generated arguments (`topic`, `limit`, `keywords`) are not validated server-side, enabling out-of-scope topic use, excessive result limits, and blocked keyword searches.
**Verdict:** In scope — `input.args.topic`, `input.args.limit`, and `input.args.keywords` are all present as structured fields at tool invocation time and can be checked by OPA.

### ASI03 — Identity and Privilege Abuse
**Risk:** `user_role` and `dissertation_area` are self-reported, enabling role escalation and PhD-scope bypass; `queries_this_session` is self-reported, enabling rate-limit defeat.
**Verdict:** Partial — OPA can enforce the rules that depend on these fields; it cannot verify their authenticity. Self-reporting integrity is an application-layer concern.

### ASI04 — Agentic Supply Chain Vulnerabilities
**Risk:** Third-party libraries (`requests`, `beautifulsoup4`) could be compromised to tamper with WikiCFP responses.
**Verdict:** Out of scope — library loading occurs at import time, not at tool invocation; no structured field is available at interception that reflects library integrity.

### ASI05 — Unexpected Code Execution (RCE)
**Risk:** Not applicable — the tool has no code-generation, eval, or shell execution capability.
**Verdict:** Out of scope — N/A.

### ASI06 — Memory & Context Poisoning
**Risk:** Not applicable — the agent is stateless with no persistent memory store.
**Verdict:** Out of scope — N/A.

### ASI07 — Insecure Inter-Agent Communication
**Risk:** Not applicable — single-agent, single-tool system with local stdio transport only.
**Verdict:** Out of scope — N/A.

### ASI08 — Cascading Failures
**Risk:** Not applicable — single tool, no delegation chain, no multi-session propagation.
**Verdict:** Out of scope — N/A.

### ASI09 — Human-Agent Trust Exploitation
**Risk:** LLM may fabricate conference entries; no source attribution in responses.
**Verdict:** Out of scope — hallucination occurs post-tool-call during response generation, not at a structured tool-invocation intercept point.

### ASI10 — Rogue Agents
**Risk:** Not applicable — single-agent system with no multi-agent coordination.
**Verdict:** Out of scope — N/A.

---

## Summary Table

| OWASP Category | In OPA scope? | Out-of-scope owner |
|---|---|---|
| ASI01 — Agent Goal Hijack | Partial | Agent layer (prompt sanitization, input validation) |
| ASI02 — Tool Misuse and Exploitation | Yes | — |
| ASI03 — Identity and Privilege Abuse | Partial | Application layer (authenticated identity provider) |
| ASI04 — Agentic Supply Chain Vulnerabilities | No | Infrastructure/deployment (dependency pinning, SBOM) |
| ASI05 — Unexpected Code Execution (RCE) | No | N/A |
| ASI06 — Memory & Context Poisoning | No | N/A |
| ASI07 — Insecure Inter-Agent Communication | No | N/A |
| ASI08 — Cascading Failures | No | N/A |
| ASI09 — Human-Agent Trust Exploitation | No | Agent layer (response attribution, confidence markers) |
| ASI10 — Rogue Agents | No | N/A |

Categories flowing into the OPA policy: ASI01 (partial), ASI02, ASI03 (partial)

---

## Gap Register

| Threat | Layer | Recommended action |
|---|---|---|
| ASI01: Prompt injection via `user_profile` fields injected into system prompt | Agent layer | Sanitize and validate `user_profile` values before inserting them into the system prompt; strip or escape natural-language instruction patterns |
| ASI03: `user_role` and `dissertation_area` are self-reported with no verification | Application layer | Integrate an authenticated identity provider that issues verified role and profile claims; do not rely solely on OPA for role-based controls when the role value is caller-supplied |
| ASI03: `queries_this_session` is self-reported, making the session rate limit bypassable | Application layer | Maintain the session query counter server-side (e.g. in a session store) rather than trusting the caller-supplied value |
| ASI04: `requests` and `beautifulsoup4` supply chain — compromised library could tamper WikiCFP responses | Infrastructure/deployment | Pin library versions, use a lockfile, scan with a vulnerability scanner, and verify hashes at install time |
| ASI09: LLM may fabricate conference entries with no source attribution | Agent layer | Attach source attribution (WikiCFP result IDs or URLs) to agent responses; add a disclaimer when the LLM supplements results beyond what WikiCFP returned |

---

## Policy Rules (OPA scope only)

### Input Schema
| Field | Source |
|---|---|
| `input.name` | Tool name (`get_events`) |
| `input.args.keywords` | `tool_definitions.json` — free-text string |
| `input.args.topic` | `tool_definitions.json` — string, one of three approved values |
| `input.args.limit` | `tool_definitions.json` — integer, default 10 |
| `input.extensions.subject.user_role` | `system_vars.json` — string (or array), one of: faculty, phd_student, guest |
| `input.extensions.subject.dissertation_area` | `system_vars.json` — string, one of three approved areas |
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

allowed_roles = { "faculty", "phd_student" }

faculty_limit_cap = 15
phd_limit_cap = 10
absolute_limit_min = 1
absolute_limit_max = 15
session_cap = 5
```

### Rule: CFP-ROLE-001
- OWASP: ASI03 / ASI02
- Severity: Hard block
- Condition: Deny `get_events` when `input.extensions.subject.user_role` is not in `allowed_roles` (i.e. role is `guest` or any unknown value)
- Matching: Set membership (exact)

### Rule: CFP-TOPIC-001
- OWASP: ASI01 / ASI02
- Severity: Hard block
- Condition: Deny `get_events` when `input.args.topic` is not in `approved_topics`
- Matching: Exact equality (case-sensitive, verbatim match required per tool description)

### Rule: CFP-TOPIC-002
- OWASP: ASI03
- Severity: Hard block
- Condition: Deny `get_events` when `input.extensions.subject.user_role` is `phd_student` and `input.args.topic` does not equal `input.extensions.subject.dissertation_area`
- Matching: Exact equality

### Rule: CFP-LIMIT-001
- OWASP: ASI02
- Severity: Hard block
- Condition: Deny `get_events` when `input.args.limit` is below `absolute_limit_min` (< 1) or above `absolute_limit_max` (> 15)
- Matching: Numeric comparison

### Rule: CFP-LIMIT-002
- OWASP: ASI02 / ASI03
- Severity: Hard block
- Condition: Deny `get_events` when `input.extensions.subject.user_role` is `phd_student` and `input.args.limit` exceeds `phd_limit_cap` (> 10)
- Matching: Numeric comparison

### Rule: CFP-KW-001
- OWASP: ASI01 / ASI02
- Severity: Hard block
- Condition: Deny `get_events` when `input.args.keywords` contains any term from `blocked_keywords` (case-insensitive substring match)
- Matching: Case-insensitive substring — each blocked term is checked as a substring of the `keywords` value

### Rule: CFP-RATE-001
- OWASP: ASI03
- Severity: Hard block
- Condition: Deny `get_events` when `input.extensions.subject.queries_this_session` is greater than or equal to `session_cap` (≥ 5). Note: this rule is only as reliable as the caller-supplied counter; see gap register for server-side counter recommendation.
- Matching: Numeric comparison

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
