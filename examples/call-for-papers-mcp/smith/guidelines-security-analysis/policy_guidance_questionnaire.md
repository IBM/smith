# OPA Policy Guidance Questionnaire

## Answer Register

| Q | Required answer | Answer | Confidence |
|---|---|---|---|
| Q1 | Tool names and one-sentence purposes | get_events: searches WikiCFP for academic conferences matching given keywords/topic, returning event name, description, dates, location, deadline, and link. | [derived from architecture] |
| Q2 | External systems: protocol, authentication, and read/write behavior | WikiCFP (http://www.wikicfp.com/cfp/servlet/tool.search), plain HTTP GET, no authentication, read-only (scraped HTML response, no writes). | [derived from architecture] |
| Q3 | Whether each tool reads, writes, or both | get_events is read-only: it issues an outbound GET to WikiCFP and returns parsed results; it performs no writes to any system. | [derived from architecture] |
| Q4 | Parameters; use Parameter Details | get_events declares three parameters: keywords (string, required), topic (string, required), limit (integer, optional, default 10). See Parameter Details. | [derived from architecture] |
| Q5 | Every user role | faculty, phd_student, guest. | [derived from guidance.txt] |
| Q6 | Runtime subject provenance and integrity; use Runtime Subject Details | All five system_vars.json subject fields (user_role, dissertation_area, research_area, queries_this_session, user_name) are declared but not read by any code path at runtime; none are placed into a structured input.extensions.subject.* field, and none carry any verification or integrity mechanism. See Runtime Subject Details. | [derived from architecture] |
| Q7 | User ID canonical path, provider, and use |  |  |
| Q8 | Whether simultaneous roles are supported |  |  |
| Q9 | Tool permissions and scope per role; use Role Permissions | Only faculty and phd_student may use get_events; guest cannot use this tool at all. Faculty may search across all three approved research areas; phd_student is further narrowed to their own dissertation_area (see Q10). See Role Permissions. | [derived from guidance.txt] |
| Q10 | Role-specific topics, values, or parameter combinations | PhD Student Narrow-Scope Rule: a phd_student may call get_events only when topic equals that student's own dissertation_area (a per-user system variable, one of the three approved areas). Faculty may search across all three approved areas and are not subject to this narrowing. Guidance explicitly warns this cannot be evaluated against the shared research_area list, since that list contains all three areas and checking topic membership in it would let a phd_student search any approved area, silently defeating the narrowing. | [derived from guidance.txt] |
| Q11 | Roles with no restrictions | None. Faculty is the least-restricted role (full access to all three approved areas up to limit 15) but is still bound by the global topic allowlist, the global disallowed-keywords list, and the absolute limit cap of 15 — guidance.txt states no role is exempt from these. | [derived from guidance.txt] |
| Q12 | Globally blocked enumerable values, formats, domains, or flags | topic must be exactly one of three approved values (verbatim, case-sensitive per tool_definitions.json): "Artificial intelligence", "Cybersecurity and privacy", "Software engineering" — any other topic is disallowed for every role. Separately, keywords must not contain (case-insensitively) any of: bioinformatics, genomics, clinical trials, drug discovery, quantum physics, materials science, renewable energy, economics, finance, marketing, supply chain, education, psychology, sociology, political science, trade show, career fair, startup expo, hackathon. | [derived from guidance.txt] |
| Q13 | Numeric hard caps | limit must be an integer between 1 and the cap allowed for the requesting user's role, and never above the absolute maximum of 15 per request. Faculty cap: 15. PhD student cap: 10. Guest: not applicable (guest cannot use the tool at all). | [derived from guidance.txt] |
| Q13b | Conditional approval paths; use Approval Paths | None described. guidance.txt defines no conditional-approval workflow (no escalation, override, or human-approval field for any parameter condition); the Approval Paths table is empty. | [derived from guidance.txt] |
| Q14 | Rejected patterns and their input source | The disallowed-keywords list in Q12 must not appear (case-insensitively) as a substring of input.args.keywords on the get_events tool. Governed input source: input.args.keywords (the LLM-chosen free-text search term forwarded by server.py). | [derived from guidance.txt] |
| Q15 | Per-session call limits; use Rate Limits | No more than 5 get_events searches per conversation session, applying to any role permitted to call the tool (faculty, phd_student). See Rate Limits. | [derived from guidance.txt] |
| Q16 | Counter owner, mechanism, and canonical policy path | guidance.txt states this cap is enforceable only if the agent itself supplies the running per-session search count as a genuine system variable at input.extensions.subject.queries_this_session. No code in the current implementation increments or maintains this counter (Phase A architecture finding); system_vars.json currently holds a static, unpopulated value (1), so there is no verified counter owner or mechanism today — this is an open gap for enforceability, though the intended canonical path (input.extensions.subject.queries_this_session) is stated by guidance itself. | [derived from guidance.txt] |
| Q17 | Post-response filtering |  |  |
| Q18 | Response fields suppressed by role |  |  |
| Q19 | Conditions making a result actionable |  |  |
| Q20 | Silent rejection or user explanation |  |  |
| Q21 | Hard-block and soft-block meanings; use Severity Levels | guidance.txt uses only hard-block ('must not', 'cannot', 'only') modal language throughout (role gating, topic allowlist, disallowed keywords, limit caps, PhD narrowing, session cap); no soft-block / warn-only language appears anywhere in guidance.txt. See Severity Levels. | [derived from guidance.txt] |
| Q22 | Denial logging and existing violation-code scheme | guidance.txt defines no denial-logging requirement and no violation-code scheme. No existing violation codes were found in guidance.txt, tool_definitions.json, or system_vars.json, so none can be recorded (violation codes must never be invented); the Violation Codes table is empty. This is an open gap. | [derived from guidance.txt] |

## Parameter Details

| Tool | Policy path | Type | Required | Valid values |
|---|---|---|---|---|
| get_events | input.args.keywords | string | true | Free text; must not contain (case-insensitively) any disallowed term: bioinformatics, genomics, clinical trials, drug discovery, quantum physics, materials science, renewable energy, economics, finance, marketing, supply chain, education, psychology, sociology, political science, trade show, career fair, startup expo, hackathon |
| get_events | input.args.topic | string | true | Exactly one of: "Artificial intelligence", "Cybersecurity and privacy", "Software engineering" (verbatim, case-sensitive per tool_definitions.json); for phd_student must additionally equal input.extensions.subject.dissertation_area |
| get_events | input.args.limit | integer | false (default 10) | Integer from 1 to 15 absolute max; further capped at 15 for faculty and 10 for phd_student |

## Runtime Subject Details

| Policy path | Provider | Provenance | Verification / integrity mechanism |
|---|---|---|---|
| input.extensions.subject.user_role | system_vars.json (declared) | Not read by any code path; would only reach the process today via an unvalidated, caller-supplied user_profile dict folded into the LLM prompt as advisory text, not structured subject data | None documented |
| input.extensions.subject.dissertation_area | system_vars.json (declared) | Not read by any code path; no verified runtime source distinct from the caller-asserted user_profile path | None documented |
| input.extensions.subject.research_area | system_vars.json (declared) | Not read by any code path | None documented |
| input.extensions.subject.queries_this_session | system_vars.json (declared) | Not read, tracked, or incremented anywhere in the implementation; no session-count state exists today | None documented |
| input.extensions.subject.user_name | system_vars.json (declared) | Not read by any code path; only reaches the process if included in caller-supplied user_profile | None documented |

## Role Permissions

| Tool | Role | Permission / scope | guidance.txt rule |
|---|---|---|---|
| get_events | faculty | May call get_events with topic equal to any of the three department-approved areas; limit up to 15 | Lines 15-19; line 43 (not subject to PhD narrowing) |
| get_events | phd_student | May call get_events only when topic equals their own dissertation_area; limit up to 10 | Lines 15-19; PhD Student Narrow-Scope Rule, lines 38-46 |
| get_events | guest | May not call get_events under any condition | Line 15 |

## Approval Paths

| Parameter condition | Approval field | guidance.txt rule |
|---|---|---|

## Rate Limits

| Role | Max calls per session |
|---|---|
| faculty | 5 |
| phd_student | 5 |

## Severity Levels

| Level | Examples |
|---|---|
| Hard block | guest calling get_events at all; topic not one of the three approved values; a phd_student's topic not equal to their dissertation_area; a disallowed keyword term present in keywords; limit below 1; limit above the requesting role's cap (15 faculty / 10 phd_student) or above the absolute maximum of 15; more than 5 get_events calls in a session (once a genuine counter exists) |

## Violation Logging

guidance.txt defines no denial-logging behavior and no violation-code scheme (open gap, Q22). No existing violation codes were found anywhere in the target agent's inputs, so none are recorded in the Violation Codes table per the no-invention rule.

## Violation Codes

| Existing code | Meaning |
|---|---|

## Phase Handoff

- Status: PASS
- Artifact schema: questionnaire-v2
- Summary: 22 questions answered or explicitly recorded as open gaps: 12 answers [derived from guidance.txt] (Q5, Q9-Q16, Q21-Q22), 2 answers [derived from architecture] (Q1-Q3 combined coverage, Q6), 0 [inferred - low confidence]. Open gaps left blank (no supporting source, one consolidated clarification would be needed): Q7 (no canonical user-ID path/provider is declared anywhere), Q8 (guidance.txt and system_vars.json do not state whether simultaneous roles are supported — user_role is an enumerated list of possibilities, not a resolved single role), Q17-Q18 (no post-response filtering or role-based field suppression described), Q19-Q20 (no actionability criteria or silent-vs-explained denial behavior described), Q22 violation-code scheme (none exists to reference; none invented). Covered tool: get_events (the only declared tool; 'other' in tool_definitions.json is non-governed Q&A). Key policy-relevant findings: role gating (guest excluded), a global topic allowlist and keyword denylist, per-role limit caps (15/10) under an absolute max of 15, a PhD-student topic-narrowing rule keyed to a per-user dissertation_area field, and a 5-calls-per-session cap whose enforcement guidance itself conditions on a genuine running counter that does not exist today. All modal language in guidance.txt is hard-block; no soft-block behavior is described.
