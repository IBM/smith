# OPA Policy Guidance Questionnaire
# Tool: call-for-papers-mcp / get_events

Fill in each answer based on your tool and agent. You do not need to
know OPA or security to complete this — just describe how your tool
works and who should be able to use it.

---

## Section 1: Tool Identity

**Q1. What is the tool name and what does it do in one sentence?**

> Tool name: `get_events`
> Searches WikiCFP for academic conference Call-for-Papers matching caller-supplied keywords, scoped to one of three approved research topics. [derived from guidance.txt]

---

**Q2. What external systems does it call?**

> WikiCFP (`http://www.wikicfp.com/cfp/servlet/tool.search`) — HTTP GET, unauthenticated, read-only web scrape. [derived from architecture]

---

**Q3. Does it read data, write data, or both?**

> Read only — scrapes publicly available conference listings from WikiCFP; no data is written to any system. [derived from architecture]

---

**Q4. What are its parameters? For each: name, type, required or optional, what counts as a valid value?**

| Parameter | Type | Required | Valid values |
|-----------|------|----------|--------------|
| `keywords` | string | Yes | Free-text search terms; must not contain any term from the blocked-keyword list (bioinformatics, genomics, clinical trials, drug discovery, quantum physics, materials science, renewable energy, economics, finance, marketing, supply chain, education, psychology, sociology, political science, trade show, career fair, startup expo, hackathon) [derived from guidance.txt] |
| `topic` | string | Yes | Exactly one of: `"Artificial intelligence"`, `"Cybersecurity and privacy"`, `"Software engineering"` (verbatim, case-sensitive); for `phd_student` callers further constrained to their `dissertation_area` [derived from guidance.txt] |
| `limit` | integer | No (default 10) | Integer 1–15; upper cap depends on role: faculty ≤ 15, phd_student ≤ 10; absolute max 15 [derived from guidance.txt] |

---

## Section 2: Who Uses It

**Q5. What are the types of users? List every role.**

> - `faculty` — department faculty; may search across all three approved areas; limit cap 15 [derived from guidance.txt]
> - `phd_student` — PhD student; topic restricted to own `dissertation_area`; limit cap 10 [derived from guidance.txt]
> - `guest` — cannot use `get_events` at all [derived from guidance.txt]

---

**Q6. Are those roles verified by your system, or supplied by the user themselves?**

> Self-reported — `user_role` is passed as part of `user_profile` in the HTTP POST body with no cryptographic verification or authentication. [derived from architecture]

---

**Q7. Is there a user ID? Where does it come from?**

> `user_name` is present in `system_vars.json` and passed via `user_profile`, but it is self-reported with no binding to an authenticated identity. No verified user ID exists. [derived from architecture]

---

**Q8. Can a user belong to multiple roles at once?**

> `user_role` in `system_vars.json` is defined as an array (`["faculty", "phd_student", "guest"]`), suggesting a single caller may carry multiple roles. The guidance does not address multi-role callers; the strictest matching role should apply. [derived from architecture]

---

## Section 3: What Each Role Is Allowed To Do

**Q9. For each role, which tools are they allowed to use and with what conditions or scope restrictions?**

| Tool | faculty | phd_student | guest | guidance.txt rule |
|------|---------|-------------|-------|-------------------|
| `get_events` | Allowed; topic ∈ {Artificial intelligence, Cybersecurity and privacy, Software engineering}; limit 1–15 | Allowed; topic must equal own `dissertation_area`; limit 1–10 | Blocked — cannot use this tool | "Only `faculty` and `phd_student` may use the `get_events` tool. A `guest` cannot use this tool." |

---

**Q10. Are there topics, values, or parameter combinations some roles can use that others cannot?**

> PhD students are limited to `topic` == `input.extensions.subject.dissertation_area` (a per-user system variable). Faculty may use any of the three approved topic values. [derived from guidance.txt]

---

**Q11. Are there roles that have no restrictions?**

> None — faculty has the broadest access but is still subject to topic allowlist, limit cap, keyword blocklist, and session rate limit. [derived from guidance.txt]

---

## Section 4: Hard Limits

**Q12. Are there parameter values that should always be blocked for everyone, regardless of role?**

> `keywords` must not contain (case-insensitively) any of the following:
> `bioinformatics`, `genomics`, `clinical trials`, `drug discovery`, `quantum physics`, `materials science`, `renewable energy`, `economics`, `finance`, `marketing`, `supply chain`, `education`, `psychology`, `sociology`, `political science`, `trade show`, `career fair`, `startup expo`, `hackathon`
> [derived from guidance.txt]
>
> `topic` must be exactly one of the three approved values; any other value is always blocked. [derived from guidance.txt]

---

**Q13. Is there a maximum value for any numeric parameter that no role can exceed?**

> `limit`: absolute maximum 15 (no role may set limit > 15); minimum 1 (limit < 1 always blocked). [derived from guidance.txt]

---

**Q13b. Are there approval paths — actions allowed conditionally when an approval field is set?**

> None described in guidance.txt. [derived from guidance.txt]

---

**Q14. Are there keywords or inputs that must always be rejected?**

> Yes — see Q12 blocked-keyword list for the `keywords` free-text field. [derived from guidance.txt]

---

## Section 5: Volume and Rate Limits

**Q15. Is there a maximum number of times this tool can be called in a single conversation session?**

> Yes — maximum 5 `get_events` searches per session (all roles). [derived from guidance.txt]

| Role | Max calls per session |
|------|-----------------------|
| faculty | 5 |
| phd_student | 5 |
| guest | 0 (blocked entirely) |

---

**Q16. Who keeps track of how many times the tool has been called — your app, or should the policy enforce it?**

> The session counter `queries_this_session` is supplied by the caller as part of `user_profile` (system_vars.json). The policy reads `input.extensions.subject.queries_this_session` and denies if value ≥ 5. However, the counter is self-reported — the calling application is responsible for incrementing it accurately. A caller who supplies a falsified count defeats this control. [derived from guidance.txt + architecture]

---

## Section 6: Response Filtering

**Q17. After the tool returns results, does anything need to be hidden, flagged, or categorised before the user sees it?**

> None specified in guidance.txt. WikiCFP results are public conference listings; no sensitive fields are returned. [derived from guidance.txt]

---

**Q18. Are there fields in the response that should be suppressed for certain roles?**

> None specified. [derived from guidance.txt]

---

**Q19. Are there conditions on a result that determine whether it is "actionable"?**

> None specified. [derived from guidance.txt]

---

## Section 7: Violations

**Q20. Should a blocked request be silently rejected, or should the user receive an explanation?**

> Explanation — guidance.txt implies the caller should understand why the request was denied (role, topic, limit, or keyword violation). [inferred — low confidence]

---

**Q21. Are there different severity levels — hard block vs. warning?**

> | Level | Examples |
> |-------|----------|
> | Hard block | Wrong role (guest), blocked keyword, out-of-scope topic, limit > absolute max, limit < 1 |
> | Hard block | PhD student topic ≠ dissertation_area |
> | Hard block | Session count ≥ 5 (when counter is trusted) |

[derived from guidance.txt for hard blocks; soft-block vs hard-block split is inferred — low confidence as guidance.txt does not specify warning tiers]

---

**Q22. Do you need to log which rule was violated, or just that a request was denied? Does an existing violation-code scheme need to be reused?**

> Log specific rule violated — guidance.txt has named, distinct rules, making per-rule codes useful. No pre-existing violation-code scheme is defined. [inferred — low confidence]
>
> | Code | Meaning |
> |------|---------|
> | *(none pre-existing — codes will be minted in Step D)* | |

---

**Confidence breakdown:** derived from guidance.txt: 18 | derived from architecture: 7 | inferred — low confidence: 3 | blank: 0
