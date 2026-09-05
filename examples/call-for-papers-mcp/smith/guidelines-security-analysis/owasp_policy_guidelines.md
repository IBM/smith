# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines
# Tool: get_events (call-for-papers-mcp)

---

## Architecture Summary

The call-for-papers-mcp system is a five-layer architecture: an HTTP API layer accepts caller-supplied `question` and `user_profile` fields and embeds them verbatim into the LLM agent's system prompt; the agent (LangGraph ReAct) generates tool call arguments (`keywords`, `topic`, `limit`) which are intercepted by OPA before execution; the MCP tool layer forwards the call to a WikiCFP scraper, dropping the `topic` argument before it reaches the implementation. The trust model is dominated by self-reported identity — `user_role`, `dissertation_area`, and `queries_this_session` are all caller-supplied with no external verification, and the sole OPA enforcement boundary sits between the MCP tool declaration and the tool implementation call.

---

## OWASP Top 10 for Agentic AI Security — Scope Assessment

### ASI01 — Agent Goal Hijack
**Risk:** Attackers inject instructions via `user_profile` fields or WikiCFP response content to redirect the LLM's goal and cause it to call `get_events` with unapproved topics or blocked keywords.
**Verdict:** Partial — In scope for the observable outputs of goal hijacking (`topic` and `keywords` at invocation time); the prompt injection vectors themselves (user_profile embedding, WikiCFP response content) are not OPA-interceptable.

### ASI02 — Tool Misuse and Exploitation
**Risk:** Callers or the LLM supply out-of-range `limit` values or defeat the session cap by setting `queries_this_session` to 0, causing excessive WikiCFP scraping or bypassing rate controls.
**Verdict:** In scope — `limit` and `queries_this_session` are both present as structured fields at invocation time.

### ASI03 — Identity and Privilege Abuse
**Risk:** Callers forge `user_role` (e.g. claiming `faculty` instead of `guest`) or set `dissertation_area` to a different approved area to bypass role gating and the PhD narrowing rule.
**Verdict:** Partial — Role-based access and dissertation_area match are OPA-enforceable (self-reported but structurally checkable); `user_name` impersonation has no access-control effect and is not OPA-scope.

### ASI04 — Agentic Supply Chain Vulnerabilities
**Risk:** Unpinned third-party dependencies (`requests`, `beautifulsoup4`, `mcp`) could be replaced with compromised versions.
**Verdict:** Out of scope — Library trust cannot be evaluated at tool invocation time; this is an infrastructure/deployment concern.

### ASI05 — Unexpected Code Execution (RCE)
**Risk:** No code generation or execution capability exists in this tool.
**Verdict:** Out of scope — Not applicable.

### ASI06 — Memory & Context Poisoning
**Risk:** No persistent memory or retrieval mechanism exists.
**Verdict:** Out of scope — Not applicable.

### ASI07 — Insecure Inter-Agent Communication
**Risk:** Single-agent system; no inter-agent communication.
**Verdict:** Out of scope — Not applicable.

### ASI08 — Cascading Failures
**Risk:** Single agent and tool; no multi-agent propagation path.
**Verdict:** Out of scope — Not applicable.

### ASI09 — Human-Agent Trust Exploitation
**Risk:** WikiCFP returns misleading event data that the agent presents as authoritative without provenance signals.
**Verdict:** Out of scope — Response content is not visible to OPA at invocation time; tool-implementation concern.

### ASI10 — Rogue Agents
**Risk:** Single-agent system; no multi-agent architecture.
**Verdict:** Out of scope — Not applicable.

---

## Summary Table

| OWASP Category | In OPA scope? | Out-of-scope owner |
|---|---|---|
| ASI01 Agent Goal Hijack | Partial | Agent layer (prompt injection filtering); Tool-implementation (response sanitisation) |
| ASI02 Tool Misuse and Exploitation | Yes | — |
| ASI03 Identity and Privilege Abuse | Partial | Audit/identity layer (user_name attribution) |
| ASI04 Agentic Supply Chain Vulnerabilities | No | Infrastructure/deployment |
| ASI05 Unexpected Code Execution (RCE) | No | N/A |
| ASI06 Memory & Context Poisoning | No | N/A |
| ASI07 Insecure Inter-Agent Communication | No | N/A |
| ASI08 Cascading Failures | No | N/A |
| ASI09 Human-Agent Trust Exploitation | No | Tool-implementation (response content filtering) |
| ASI10 Rogue Agents | No | N/A |

Categories flowing into the OPA policy: ASI01 (Partial), ASI02, ASI03 (Partial)

---

## Gap Register

| Threat | Layer | Recommended action |
|---|---|---|
| ASI01: Prompt injection via user_profile keys (user_role, user_name, research_area, dissertation_area) embedded verbatim into system prompt | Agent layer | Apply prompt injection filtering to user_profile values before building the system prompt; consider allowlisting accepted keys and sanitising values |
| ASI01: user question field may contain direct goal-override instructions | Agent layer | Apply input validation or prompt injection detection to the question field before passing it to the LLM |
| ASI01: WikiCFP response content may contain hidden instructions embedded in conference names/descriptions | Tool-implementation | Sanitise HTML-extracted text fields to strip or neutralise prompt-injection patterns before returning data to the agent |
| ASI03: user_name impersonation (audit risk — user_name has no access-control effect but appears in logs) | Infrastructure/audit | Add server-side user identity verification; treat user_name as a display field and correlate logs with a verified identifier |
| ASI04: Unpinned third-party dependencies (requests, beautifulsoup4, mcp, langchain-openai, langchain-mcp-adapters, fastapi, pydantic) | Infrastructure | Pin all package versions in requirements.txt; integrate dependency scanning (pip-audit, safety) into CI |
| ASI09: WikiCFP returns untrusted event content with no provenance signal | Tool-implementation | Attach a provenance label to returned events; consider schema-validating expected fields before returning data to the agent |
| Session cap self-reporting: queries_this_session is caller-supplied; a dishonest caller can set it to 0 to bypass the cap entirely | Agent/Infrastructure | Move session call counting to a server-side session store so the count cannot be forged by the caller; this would make SESSION_LIMIT_EXCEEDED unconditionally enforceable |

---

## Policy Rules (OPA scope only)

### Input Schema
| Field | Source |
|---|---|
| `input.name` | Tool name, always `"get_events"` for this tool |
| `input.args.keywords` | LLM-generated string; passed to WikiCFP `q=` param |
| `input.args.topic` | LLM-generated string; **Echoed** — not forwarded to WikiCFP; deny-path rules are sound, permit-path rules are not |
| `input.args.limit` | LLM-generated integer; slices result list in app.py |
| `input.extensions.subject.user_role` | Caller-supplied list of strings (self-reported) |
| `input.extensions.subject.dissertation_area` | Caller-supplied string (self-reported) |
| `input.extensions.subject.queries_this_session` | Caller-supplied integer (self-reported) |

### Known values
- Approved topics (verbatim, case-sensitive): `"Artificial intelligence"`, `"Cybersecurity and privacy"`, `"Software engineering"`
- Permitted roles for `get_events`: `"faculty"`, `"phd_student"`
- Blocked roles: `"guest"` and any unrecognised value
- Per-role limit caps: `faculty` → 15, `phd_student` → 10
- Absolute limit bounds: minimum 1, maximum 15
- Session cap: 5 calls per session (enforced via `queries_this_session`)
- Blocked keyword substrings (case-insensitive): `bioinformatics`, `genomics`, `clinical trials`, `drug discovery`, `quantum physics`, `materials science`, `renewable energy`, `economics`, `finance`, `marketing`, `supply chain`, `education`, `psychology`, `sociology`, `political science`, `trade show`, `career fair`, `startup expo`, `hackathon`
- `user_role` is a list; role checks must test for membership in the list, not equality to a string
- A caller with multiple roles is evaluated against all roles simultaneously; a phd_student who also holds faculty is evaluated as faculty for limit purposes [inferred — low confidence: guidance.txt does not address multi-role precedence explicitly]

### Rule: ROLE_BLOCKED
- OWASP: ASI03 (Identity and Privilege Abuse)
- Severity: Hard block
- Condition: `input.extensions.subject.user_role` does not contain any of `{"faculty", "phd_student"}` — i.e. the caller holds no permitted role for `get_events`
- Matching: Set membership (check whether the role list contains at least one permitted role)

### Rule: TOPIC_BLOCKED
- OWASP: ASI01 (Agent Goal Hijack) + ASI03 (Identity and Privilege Abuse)
- Severity: Hard block
- Condition: `input.args.topic` is not exactly one of `{"Artificial intelligence", "Cybersecurity and privacy", "Software engineering"}`
- Matching: Exact string equality (set membership); case-sensitive

### Rule: TOPIC_ROLE_BLOCKED
- OWASP: ASI03 (Identity and Privilege Abuse)
- Severity: Hard block
- Condition: `input.extensions.subject.user_role` contains `"phd_student"` AND `input.args.topic` does not equal `input.extensions.subject.dissertation_area`
- Matching: Set membership for role check; exact string equality for topic-vs-dissertation_area comparison

### Rule: LIMIT_EXCEEDED
- OWASP: ASI02 (Tool Misuse and Exploitation)
- Severity: Hard block
- Condition: `input.args.limit` < 1 OR `input.args.limit` > 15
- Matching: Numeric comparison

### Rule: LIMIT_ROLE_EXCEEDED
- OWASP: ASI02 (Tool Misuse and Exploitation)
- Severity: Hard block
- Condition: `input.extensions.subject.user_role` contains `"phd_student"` AND `input.args.limit` > 10
- Matching: Set membership for role check; numeric comparison for limit

### Rule: SESSION_LIMIT_EXCEEDED
- OWASP: ASI02 (Tool Misuse and Exploitation)
- Severity: Hard block
- Condition: `input.extensions.subject.queries_this_session` >= 5
- Matching: Numeric comparison
- Note: Enforcement depends on caller-supplied count; effectiveness is conditional on caller honesty or server-side session tracking (see Gap Register)

### Rule: KEYWORD_BLOCKED
- OWASP: ASI01 (Agent Goal Hijack)
- Severity: Hard block
- Condition: `input.args.keywords` contains any blocked substring (case-insensitive): `bioinformatics`, `genomics`, `clinical trials`, `drug discovery`, `quantum physics`, `materials science`, `renewable energy`, `economics`, `finance`, `marketing`, `supply chain`, `education`, `psychology`, `sociology`, `political science`, `trade show`, `career fair`, `startup expo`, `hackathon`
- Matching: Case-insensitive substring (each blocked term checked as a substring of `input.args.keywords`)

---

## Violation Code Reference

| Code | OWASP | Severity |
|---|---|---|
| ROLE_BLOCKED | ASI03 | Hard block |
| TOPIC_BLOCKED | ASI01, ASI03 | Hard block |
| TOPIC_ROLE_BLOCKED | ASI03 | Hard block |
| LIMIT_EXCEEDED | ASI02 | Hard block |
| LIMIT_ROLE_EXCEEDED | ASI02 | Hard block |
| SESSION_LIMIT_EXCEEDED | ASI02 | Hard block |
| KEYWORD_BLOCKED | ASI01 | Hard block |
