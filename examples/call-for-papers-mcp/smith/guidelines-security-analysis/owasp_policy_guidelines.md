# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines

## Architecture Summary

Single declared tool get_events(keywords, topic, limit) with no OPA/policy enforcement anywhere in agent.py, server.py, or app.py (Phase A E1). The only viable pre-execution enforcement point is the MCP tool boundary in server.py, where keywords, topic, and limit are structured and fully visible before app.getEvents is called. All five system_vars.json subject fields (user_role, dissertation_area, research_area, queries_this_session, user_name) are declared but not read by any code path and are not placed into input.extensions.subject.* at runtime (E3) — they are effectively undeclared-at-runtime today. server.py additionally drops the topic argument before calling app.getEvents (E2), so a pre-execution topic check at the MCP boundary would be sound in isolation but nothing downstream re-derives it. No session counter, no post-response filtering, and no violation-code/logging scheme exist (E8, E9). Given this, only argument-only predicates over input.args.keywords, input.args.topic, and input.args.limit that do not depend on subject/role data are OPA-policy-expressible today; every rule that requires user_role, dissertation_area, or queries_this_session as an authoritative pre-execution field is recorded in the Gap Register rather than encoded as a candidate.

## Threat Disposition

| Threat ID | Field / surface | Owner | Reason |
|---|---|---|---|
| T1 | input.args.keywords (get_events) | OPA | Global keyword denylist is a pre-execution, role-independent predicate over a declared tool argument (guidance.txt lines 31-36); all eligibility criteria pass. |
| T2 | input.args.topic (get_events) | OPA | Global topic allowlist is a pre-execution, role-independent predicate over a declared tool argument (guidance.txt line 16); the rule denies the submitted value directly, so the tool need not act on topic for the predicate to hold (eligibility criterion 7). |
| T3 | input.args.topic (get_events, downstream of server.py) | Tool implementation | server.py never forwards topic to app.getEvents (E2); this is an implementation defect (topic-drop blind spot), not a deniable predicate — fixing it requires changing server.py to actually pass topic through, not an OPA rule. |
| T4 | input.args.limit (get_events) | OPA | The role-independent absolute bound (1 to 15 inclusive) is a pre-execution predicate over a declared argument and passes all eligibility criteria. The role-conditional portion of this same guidance rule (15 faculty / 10 phd_student caps) is not OPA-eligible today because it requires input.extensions.subject.user_role, which has no authoritative runtime source (see T5); that portion is recorded in the Gap Register, not assigned to OPA. |
| T5 | input.extensions.subject.user_role | Infrastructure | No canonical, authenticated user-identity or role-resolution mechanism exists anywhere in the system (E4); the only delivery path is an unvalidated, caller-supplied user_profile dict folded into LLM prompt text (E3), which fails eligibility criterion 4 (authoritative, pre-execution subject field). Fixing this requires an identity/authentication layer upstream of the MCP boundary, not a Rego rule. |
| T6 | input.extensions.subject.dissertation_area | Infrastructure | The PhD Student Narrow-Scope Rule depends on a per-user dissertation_area field with no verified runtime source distinct from the same untrusted user_profile path as T5 (E3, E7); fails eligibility criterion 4. Requires an authoritative subject-data pipeline before this can become a Rego predicate. |
| T7 | input.extensions.subject.queries_this_session | Infrastructure | No code path increments or supplies a genuine running per-session counter (E8); guidance.txt itself conditions this rule on the agent supplying that counter. Fails eligibility criteria 4 and 6 (no authoritative pre-execution field; a stateless policy cannot compute session history it is never given). |
| T8 | WikiCFP search-result content (tool output) | Tool implementation | Mitigating unauthenticated/unverified scraped HTML requires output inspection or content-integrity verification at or after the external-call boundary (app.py), not a pre-execution argument predicate; fails eligibility criterion 6 (no output inspection or post-processing may be required of an OPA candidate). |
| T9 | Denial/violation behavior (no logging, no violation codes) | Agent | Traceability and explanation of denials is an application/agent-layer logging concern, not a pre-execution allow/deny predicate; guidance.txt defines no actionability or denial-explanation behavior to encode (Q17-Q20, Q22 open gaps), so there is no rule content for OPA to express. |

## OWASP Top 10 for Agentic AI Security — Scope Assessment

| OWASP | Scope | OPA threat IDs | Other-layer threat IDs | Reason / owner |
|---|---|---|---|---|
| ASI01 | Partial |  | T8 | The caller-controlled question field drives LLM tool-argument construction, but the only OWASP-relevant surface for this category (T8, indirect content injection via unauthenticated WikiCFP output) requires output inspection, which is not OPA-eligible (Tool implementation). No OPA-expressible predicate exists for this category. |
| ASI02 | Partial | T1, T2, T4 | T3, T7 | Keyword denylist (T1), topic allowlist (T2), and the role-independent absolute limit bound (T4) are OPA-eligible argument predicates at the get_events boundary. The topic-drop blind spot (T3, Tool implementation) and the session-cap gap (T7, Infrastructure, no counter) are not OPA-eligible, giving this category mixed ownership. |
| ASI03 | No |  | T5, T6 | Both identity/privilege-abuse threats (role spoofing T5; PhD narrow-scope bypass via forged/misapplied subject data T6) require an authoritative, pre-execution subject field that does not exist (Infrastructure). No OPA-expressible predicate exists for this category today. |
| ASI09 | No |  | T9 | The denial-traceability gap (T9) is a logging/explanation concern owned by the Agent layer, not a pre-execution allow/deny predicate; no rule content exists for OPA to express. |

## Gap Register

| Finding ID | Layer | Recommended action |
|---|---|---|
| G1 | Infrastructure | Establish a canonical, authenticated user-identity and role-resolution mechanism (no such path exists per Phase B Q7/Q8) and thread the resolved role into input.extensions.subject.user_role as a trustworthy, pre-execution field distinct from the caller-supplied, unvalidated user_profile dict. Until this exists, guest-exclusion and the differential faculty/phd_student limit caps (T5, T4's role-conditional portion) cannot be expressed as an OPA predicate. |
| G2 | Infrastructure | Provide a per-user, authoritative dissertation_area field distinct from the shared research_area list and from the untrusted user_profile path, so the PhD Student Narrow-Scope Rule (T6) can be expressed as an OPA predicate on input.extensions.subject.dissertation_area. Never substitute research_area for dissertation_area — guidance.txt explicitly warns this would silently defeat the narrowing. |
| G3 | Infrastructure | Implement a genuine, agent-maintained running per-session call counter and supply it as input.extensions.subject.queries_this_session (T7). Guidance.txt itself states the 5-calls-per-session cap is enforceable only once this exists; a stateless policy cannot enforce it today. |
| G4 | Tool implementation | Fix server.py so that the topic argument is actually forwarded to app.getEvents (T3); today it is silently dropped, so even a future OPA gate on input.args.topic checks a value that has no downstream effect at all. This is an enforcement-mapping precondition, not a Rego change. |
| G5 | Tool implementation | Consider content-integrity verification or sanitization of WikiCFP scraped HTML before it is returned as tool output (T8), since the source is unauthenticated plain HTTP with no TLS/signature/checksum. This is an output-inspection concern outside OPA's pre-execution scope. |
| G6 | Agent | Define a denial-logging and violation-code scheme, and an actionability/explanation policy for rejected calls (T9), to close the traceability gap. No violation codes exist today to reference, and guidance.txt defines no actionability criteria (Q17-Q20, Q22 open gaps) — none are invented here. |
| G7 | Infrastructure | Resolve whether simultaneous roles are supported (Phase B Q8 open gap: user_role in system_vars.json is an enumerated list of possibilities, not a resolved single role). Until this human decision is made, no policy can assume a single-valued role even if G1 is addressed. |

## Policy Rules (OPA scope only)

Four argument-only rules (CFP-001 through CFP-004) are eligible for OPA expression at the get_events MCP boundary. All four make an existing guidance.txt requirement concrete against the declared tool schema (enforcement mapping, not novel guidance): (1) a global topic allowlist restricting input.args.topic to exactly one of the three approved values; (2) a global keyword denylist blocking 19 case-insensitive substrings in input.args.keywords; (3)-(4) a role-independent absolute bound on input.args.limit (integer, 1 to 15 inclusive). guidance.txt has no numbered rules (only prose/bullets), so no Existing Guidance Normalization or Candidate Reconciliation rows are produced — each Rule instead cites its own source line and threat ID directly. All role-conditional behavior — guest exclusion, the faculty/phd_student differential limit caps (15 vs 10), and the PhD Student Narrow-Scope Rule tying topic to dissertation_area — requires input.extensions.subject.user_role or input.extensions.subject.dissertation_area as an authoritative, pre-execution subject field. Per Phase A/B/C (E3, E4, T5, T6), no such authoritative field exists today: the only delivery path is an unvalidated, caller-supplied user_profile dict folded into LLM prompt text, which is self-asserted and not structured input.extensions.subject data. These role-conditional rules therefore fail eligibility criterion 4 and are recorded in the Gap Register (G1, G2, G7), not encoded as OPA rules. The 5-calls-per-session cap (T7) similarly fails eligibility because no genuine queries_this_session counter is maintained by any code path; guidance.txt itself states this (Gap G3). Topic's downstream drop (T3, G4), WikiCFP content trust (T8, G5), and denial-traceability (T9, G6) are non-argument, non-pre-execution concerns and are recorded as gaps owned by other layers.

### Input Schema

| Field | Source |
|---|---|
| input.args.keywords | get_events tool argument (tool_definitions.json: string, required) |
| input.args.topic | get_events tool argument (tool_definitions.json: string, required) |
| input.args.limit | get_events tool argument (tool_definitions.json: integer, optional, default 10) |

### Known values

Approved topic values (verbatim, case-sensitive): "Artificial intelligence", "Cybersecurity and privacy", "Software engineering". Disallowed keyword substrings (case-insensitive): bioinformatics, genomics, clinical trials, drug discovery, quantum physics, materials science, renewable energy, economics, finance, marketing, supply chain, education, psychology, sociology, political science, trade show, career fair, startup expo, hackathon. Absolute limit bound: integer, 1 to 15 inclusive (role-independent floor/ceiling within which the unenforceable role caps of 15 faculty / 10 phd_student would further narrow if user_role were ever authoritative).

### Rules

| Code | OWASP | Threat IDs | Severity | Tool(s) / field | Condition | Matching |
|---|---|---|---|---|---|---|
| CFP-001 | ASI02 | T2 | High | get_events / input.args.topic | Deny when topic is not exactly one of: "Artificial intelligence", "Cybersecurity and privacy", "Software engineering". | Case-sensitive exact string match against the enumerated set (not_in); no default applied since topic is required and has no default; missing/null/empty topic also denies (required field). |
| CFP-002 | ASI02 | T1 | High | get_events / input.args.keywords | Deny when keywords contains, case-insensitively, any of the 19 disallowed substrings (bioinformatics, genomics, clinical trials, drug discovery, quantum physics, materials science, renewable energy, economics, finance, marketing, supply chain, education, psychology, sociology, political science, trade show, career fair, startup expo, hackathon). | Case-insensitive substring containment (contains_any) over the fixed term list; keywords is required with no default, so missing/null/empty keywords is out of scope for this rule (no substring can match empty input) and is not itself a denial condition under this rule. |
| CFP-003 | ASI02 | T4 | Medium | get_events / input.args.limit | Deny when limit is less than 1. | Numeric comparison (lt) against 1, the role-independent absolute floor; limit defaults to 10 when omitted, and the default value (10) always satisfies this bound, so a missing limit does not trigger this rule. |
| CFP-004 | ASI02 | T4 | Medium | get_events / input.args.limit | Deny when limit is greater than 15. | Numeric comparison (gt) against 15, the role-independent absolute ceiling; limit defaults to 10 when omitted, and the default value (10) always satisfies this bound, so a missing limit does not trigger this rule. |

## Candidate Reconciliation

| Candidate ID | Tool | Subject scope | Field expression | Operator | Values | Action | Sources | Related rule | Guidance group | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|

## Existing Guidance Normalization

| Existing ID | Rule number | Tool | Subject scope | Field expression | Operator | Values | Action |
|---|---|---|---|---|---|---|---|

## Prior Proposal Reconciliation

| Prior ID | Original number | Normalized rule | Disposition | Candidate / reason |
|---|---|---|---|---|

## Phase Handoff

- Status: PASS
- Artifact schema: enforcement-mapping-v8
- Summary: 9 threats mapped: 3 assigned to OPA (T1, T2, and the role-independent portion of T4 — keyword denylist, topic allowlist, absolute limit bound 1-15, all pre-execution predicates over declared get_events arguments); 6 assigned to other layers (T3, T8 to Tool implementation; T5, T6, T7 to Infrastructure — no authoritative subject field/counter exists; T9 to Agent — no logging/violation-code scheme exists). ASI scope: ASI02 = Partial (OPA: T1,T2,T4; other-layer: T3,T7); ASI01 = Partial (other-layer: T8 only, no OPA content); ASI03 = No (T5,T6 both require an authoritative subject field that does not exist); ASI09 = No (T9 is a logging concern, not a predicate). 4 new Rules emitted (CFP-001 through CFP-004: topic allowlist, keyword denylist, limit floor, limit ceiling) — all four make an existing guidance.txt requirement concrete against the declared get_events schema (enforcement mapping), not novel guidance. guidance.txt uses no numbered rules (prose/bullets only), so Candidate Reconciliation and Existing Guidance Normalization are intentionally empty per the guide's rule that numbered-rule reconciliation applies only when the source guidance uses numbered rules; each Rule instead cites its guidance.txt source line and threat ID directly. Every role- or counter-conditional behavior already stated by guidance.txt (guest exclusion, faculty/phd_student differential limit caps of 15/10, the PhD Student Narrow-Scope Rule, and the 5-calls-per-session cap) fails OPA eligibility criterion 4 (and criterion 6 for the session cap) because input.extensions.subject.user_role, dissertation_area, and queries_this_session all lack an authoritative, pre-execution runtime source (Phase A/B/C E3, E4, T5, T6, T7); each is recorded in the Gap Register rather than invented as a candidate. Zero Novel or Additive guidance is proposed — every OPA-eligible behavior was already stated by guidance.txt, so nothing new is added. 7 Gap Register findings (G1-G7) cover the identity/subject-data infrastructure gap (G1, G2, G7), the session-counter gap (G3), the topic-drop implementation defect (G4), WikiCFP content-integrity (G5), and the denial-logging/violation-code gap (G6). No prior addendum existed (GUIDANCE_UPDATE_FILE was ABSENT), so Prior Proposal Reconciliation is empty and no guidance_updated.txt is produced — there is no consolidated Novel or uncovered Additive decision to write. No blocking Overlap/Conflict/Contradictory-correction relationships exist. Open gaps remain exactly as carried forward from Phase B/C: no canonical user-ID/role-resolution path, unresolved simultaneous-role support, no genuine session counter, the server.py topic-forwarding defect, unauthenticated WikiCFP content, and no denial-logging/violation-code scheme.
