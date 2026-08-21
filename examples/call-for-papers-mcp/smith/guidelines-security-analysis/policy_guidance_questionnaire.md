# OPA Policy Guidance Questionnaire
# Tool: get_events

Fill in each answer based on your tool and agent. You do not need to
know OPA or security to complete this — just describe how your tool
works and who should be able to use it.

---

## Section 1: Tool Identity

**Q1. What is the tool name and what does it do in one sentence?**

> Tool name: `get_events`
> Searches WikiCFP for academic conference Call-for-Papers matching given keywords, scoped to the department's three approved research areas. [derived from architecture]

---

**Q2. What external systems does it call?**

> WikiCFP (`http://www.wikicfp.com`) — scraped via unauthenticated HTTP GET (`requests` + `BeautifulSoup`), read-only, no API key. [derived from architecture]

---

**Q3. Does it read data, write data, or both?**

> Read only — scrapes conference listings, no writes anywhere in the flow. [derived from architecture]

---

**Q4. What are its parameters? For each: name, type, required or optional,
what counts as a valid value?**

| Parameter | Type | Required | Valid values |
|-----------|------|----------|--------------|
| keywords | string | Yes | Free text; must not contain any of the 20 disallowed terms (see Q12) [derived from guidance.txt] |
| topic | string | Yes | Exactly one of: "Artificial intelligence", "Cybersecurity and privacy", "Software engineering" [derived from guidance.txt] |
| limit | integer | No (default 10) | 1–15 absolute; role-capped (faculty ≤15, phd_student ≤10) [derived from guidance.txt] |

---

## Section 2: Who Uses It

**Q5. What are the types of users? List every role.**

> - `faculty` — may search all 3 approved areas, limit ≤15 [derived from guidance.txt]
> - `phd_student` — may search only their own `dissertation_area`, limit ≤10 [derived from guidance.txt]
> - `guest` — cannot use this tool at all [derived from guidance.txt]

---

**Q6. Are those roles verified by your system, or supplied by the user themselves?**

> Self-reported — `user_profile` (containing role) is supplied in the HTTP request body (`ChatRequest.user_profile`) with no authentication or verification mechanism present anywhere in the code. [derived from architecture]

---

**Q7. Is there a user ID? Where does it come from?**

> No dedicated user-ID field. `system_vars.json` has `user_name` (e.g. `"Bob"`), a free-text display name, not a verified identifier. [derived from architecture]

---

**Q8. Can a user belong to multiple roles at once?**

> `system_vars.json`'s `user_role` field is a list (`["faculty", "phd_student", "guest"]`), which is ambiguous: it may enumerate the *possible* role values in the system rather than the *current caller's* actual role(s). guidance.txt's rules are written as if each caller has exactly one role. [inferred — low confidence] — needs human confirmation of whether a single caller can hold >1 role simultaneously, and if so how the stricter rule (phd_student's narrow scope) interacts with a caller who is also faculty.

---

## Section 3: What Each Role Is Allowed To Do

**Q9. For each role, which tools are they allowed to use and with what
conditions or scope restrictions?**

| Tool | faculty | phd_student | guest | guidance.txt rule |
|------|---------|--------------|-------|-------------------|
| get_events | Allowed — any of the 3 approved topics, limit ≤15 | Allowed — only `topic == dissertation_area`, limit ≤10 | Blocked entirely | Rule under "What the Agent May Do" + "PhD Student Narrow-Scope Rule" |

[derived from guidance.txt]

---

**Q10. Are there topics, values, or parameter combinations some roles
can use that others cannot?**

> Yes — `phd_student` is restricted to `topic == dissertation_area` (their own single research area), while `faculty` may use any of the 3 department-approved areas. [derived from guidance.txt]

---

**Q11. Are there roles that have no restrictions?**

> None. Even `faculty` — the role with the widest access — is still capped at `limit ≤ 15` and restricted to the 3 approved topics, and is subject to the disallowed-keyword list. [derived from guidance.txt]

---

## Section 4: Hard Limits

**Q12. Are there parameter values that should always be blocked for
everyone, regardless of role?**

> `keywords` must not contain (case-insensitively) any of: `bioinformatics`, `genomics`, `clinical trials`, `drug discovery`, `quantum physics`, `materials science`, `renewable energy`, `economics`, `finance`, `marketing`, `supply chain`, `education`, `psychology`, `sociology`, `political science`, `trade show`, `career fair`, `startup expo`, `hackathon`.
> `topic` must be exactly one of the 3 approved values for anyone (not just phd_student). [derived from guidance.txt]

---

**Q13. Is there a maximum value for any numeric parameter that no role
can exceed?**

> `limit`: absolute maximum 15 for everyone (faculty's own cap), 10 for phd_student. [derived from guidance.txt]

---

**Q13b. Are there approval paths — actions allowed conditionally when an
approval field is set?**

> None. [derived from guidance.txt]

---

**Q14. Are there keywords or inputs that must always be rejected?**

> Same 20-term disallowed list as Q12, checked against the `keywords` parameter, case-insensitive substring match. [derived from guidance.txt]

---

## Section 5: Volume and Rate Limits

**Q15. Is there a maximum number of times this tool can be called in
a single conversation session?**

> Yes. [derived from guidance.txt]

| Role | Max calls per session |
|------|-----------------------|
| faculty | 5 |
| phd_student | 5 |
| guest | 0 (blocked entirely, so moot) |

---

**Q16. Who keeps track of how many times the tool has been called —
your app, or should the policy enforce it?**

> guidance.txt states this explicitly: enforceable only if the calling application supplies a running per-session count as `queries_this_session` in `system_vars.json`. [derived from guidance.txt] Per the architecture.md coverage sweep, nothing in this codebase (`agent.py`/`server.py`/`app.py`) currently increments or persists this value anywhere — it is declared as a static value in `system_vars.json`. [derived from architecture] This rule is not enforceable by a stateless policy today.

---

## Section 6: Response Filtering

**Q17. After the tool returns results, does anything need to be hidden,
flagged, or categorised before the user sees it?**

> None specified. [derived from guidance.txt]

---

**Q18. Are there fields in the response that should be suppressed for
certain roles?**

> None specified. [derived from guidance.txt]

---

**Q19. Are there conditions on a result that determine whether it is
"actionable"?**

> None apparent in guidance.txt or the source. [inferred — low confidence]

---

## Section 7: Violations

**Q20. Should a blocked request be silently rejected, or should the
user receive an explanation?**

> Not specified anywhere in guidance.txt or the source code. [inferred — low confidence] — needs human input.

---

**Q21. Are there different severity levels — hard block vs. warning?**

> guidance.txt phrases every rule as an absolute ("must not", "cannot") with no soft-block or redirect language anywhere. All rules read as Hard block. [derived from guidance.txt]

| Level | Examples |
|-------|----------|
| Hard block | Role gating (guest), disallowed keywords, topic restriction, limit cap, PhD narrow-scope, session-count cap |
| Soft block with redirect | None found |

---

**Q22. Do you need to log which rule was violated, or just that a
request was denied? Does an existing violation-code scheme need to be
reused (e.g. codes already emitted by the calling application or by
another policy)?**

> Not specified in guidance.txt or the source. [inferred — low confidence] — no pre-existing violation-code scheme found; leaving the table empty per instructions (codes are minted in Step D).
>
> | Code | Meaning |
> |------|---------|
> | (none — no pre-existing scheme found) | |

---

## Confidence breakdown

- `[derived from guidance.txt]`: Q1 (partial), Q4, Q5, Q9, Q10, Q11, Q12, Q13, Q13b, Q14, Q15, Q16 (partial), Q17, Q18, Q21, Q22 (partial)
- `[derived from architecture]`: Q1 (partial), Q2, Q3, Q6, Q7, Q16 (partial)
- `[inferred — low confidence]`: Q8, Q19, Q20, Q22 (partial)
- Blank: none
