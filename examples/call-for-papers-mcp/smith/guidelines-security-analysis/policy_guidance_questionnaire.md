# OPA Policy Guidance Questionnaire
# Tool: get_events

Fill in each answer based on your tool and agent. You do not need to
know OPA or security to complete this — just describe how your tool
works and who should be able to use it.

---

## Section 1: Tool Identity

**Q1. What is the tool name and what does it do in one sentence?**

> Tool name: `get_events`
> Searches WikiCFP for upcoming academic conferences matching caller-supplied keywords and returns structured event data (name, description, dates, location, deadline, link). [derived from architecture]

---

**Q2. What external systems does it call?**

> WikiCFP HTTP API (`http://www.wikicfp.com/cfp/servlet/tool.search`), GET, no authentication, read-only scrape of publicly indexed conference data. [derived from architecture]

---

**Q3. Does it read data, write data, or both?**

> Read only — retrieves and parses public HTML; makes no writes to any external system. [derived from architecture]

---

**Q4. What are its parameters? For each: name, type, required or optional, what counts as a valid value?**

| Parameter | Type | Required | Valid values |
|-----------|------|----------|--------------|
| `keywords` | string | Yes | Free-text search terms for WikiCFP; must not contain any of the blocked substrings listed in guidance.txt (bioinformatics, genomics, clinical trials, drug discovery, quantum physics, materials science, renewable energy, economics, finance, marketing, supply chain, education, psychology, sociology, political science, trade show, career fair, startup expo, hackathon) [derived from guidance.txt] |
| `topic` | string | Yes | Exactly one of: `"Artificial intelligence"`, `"Cybersecurity and privacy"`, `"Software engineering"` (verbatim, including capitalisation). PhD students are further restricted to their own `dissertation_area`. [derived from guidance.txt] |
| `limit` | integer | No (default 10) | 1–15 for faculty; 1–10 for phd_student; absolute cap 15. [derived from guidance.txt] |

---

## Section 2: Who Uses It

**Q5. What are the types of users? List every role.**

> - `faculty` — department faculty member; full topic access; limit cap 15
> - `phd_student` — PhD student; topic restricted to own dissertation area; limit cap 10
> - `guest` — guest user; may not use `get_events` at all
> [derived from guidance.txt]

---

**Q6. Are those roles verified by your system, or supplied by the user themselves?**

> Self-reported — `user_role` is provided by the caller in the `user_profile` POST body field; it is embedded in the system prompt and surfaced at OPA time as `input.extensions.subject.user_role`. There is no external verification of the role claim. [derived from architecture]

---

**Q7. Is there a user ID? Where does it come from?**

> `user_name` (e.g. `"Bob"`) is present in `system_vars.json` and is caller-supplied via `user_profile`. It is available as `input.extensions.subject.user_name`. It is not verified and is not used in any access-control rule. [derived from architecture]

---

**Q8. Can a user belong to multiple roles at once?**

> `user_role` is declared as a list in `system_vars.json` (e.g. `["faculty", "phd_student", "guest"]`), so the schema supports multiple roles simultaneously. Policy rules must evaluate membership in that list, not equality to a single string. [derived from architecture]

---

## Section 3: What Each Role Is Allowed To Do

**Q9. For each role, which tools are they allowed to use and with what conditions or scope restrictions?**

| Tool | `faculty` | `phd_student` | `guest` | guidance.txt rule |
|------|-----------|---------------|---------|-------------------|
| `get_events` | Allowed; `topic` must be one of three approved areas; `limit` ≤ 15 | Allowed; `topic` must equal the student's own `dissertation_area`; `limit` ≤ 10 | Blocked entirely | Role access + topic + limit rules from guidance.txt |

---

**Q10. Are there topics, values, or parameter combinations some roles can use that others cannot?**

> Yes. `phd_student` is restricted to a single `topic` value (their `dissertation_area`), whereas `faculty` may use any of the three approved topic values. `faculty` may set `limit` up to 15; `phd_student` up to 10. [derived from guidance.txt]

---

**Q11. Are there roles that have no restrictions?**

> None — all roles are constrained. `faculty` has the broadest access but is still subject to the approved-topic list, the absolute limit cap, blocked keywords, and the session cap. [derived from guidance.txt]

---

## Section 4: Hard Limits

**Q12. Are there parameter values that should always be blocked for everyone, regardless of role?**

> Yes:
> - `topic` must be exactly one of `"Artificial intelligence"`, `"Cybersecurity and privacy"`, `"Software engineering"`. Any other value must be denied for all roles.
> - `keywords` must not contain (case-insensitively) any of: `bioinformatics`, `genomics`, `clinical trials`, `drug discovery`, `quantum physics`, `materials science`, `renewable energy`, `economics`, `finance`, `marketing`, `supply chain`, `education`, `psychology`, `sociology`, `political science`, `trade show`, `career fair`, `startup expo`, `hackathon`.
> [derived from guidance.txt]

---

**Q13. Is there a maximum value for any numeric parameter that no role can exceed?**

> `limit`: absolute maximum is 15 (no role may exceed this). Minimum is 1 (below 1 is also blocked). [derived from guidance.txt]

---

**Q13b. Are there approval paths — actions allowed conditionally when an approval field is set?**

> | Parameter condition | Approval field | guidance.txt rule |
> |---------------------|----------------|-------------------|
> | (none) | n/a | n/a |
>
> No approval-flag patterns exist for this tool. [derived from guidance.txt]

---

**Q14. Are there keywords or inputs that must always be rejected?**

> Yes — the `keywords` free-text field must not contain any of the blocked substrings listed in Q12 above (case-insensitive substring match). This applies to all roles. [derived from guidance.txt]

---

## Section 5: Volume and Rate Limits

**Q15. Is there a maximum number of times this tool can be called in a single conversation session?**

> Yes — 5 calls per session maximum, applicable to all roles.
>
> | Role | Max calls per session |
> |------|-----------------------|
> | faculty | 5 |
> | phd_student | 5 |
> | guest | 0 (tool blocked entirely) |
>
> [derived from guidance.txt]

---

**Q16. Who keeps track of how many times the tool has been called — your app, or should the policy enforce it?**

> The caller supplies the running count as `queries_this_session` (an integer) in `user_profile`, surfaced at OPA time as `input.extensions.subject.queries_this_session`. The policy enforces the cap by reading this field. However, the count is entirely self-reported; a caller can set it to 0 to bypass the limit. The rule is enforceable only when the caller supplies an honest count. [derived from guidance.txt + architecture]

---

## Section 6: Response Filtering

**Q17. After the tool returns results, does anything need to be hidden, flagged, or categorised before the user sees it?**

> None specified in guidance.txt. The tool returns public WikiCFP data with no sensitive fields. [inferred — low confidence]

---

**Q18. Are there fields in the response that should be suppressed for certain roles?**

> None specified. [inferred — low confidence]

---

**Q19. Are there conditions on a result that determine whether it is "actionable"?**

> None specified in guidance.txt. [inferred — low confidence]

---

## Section 7: Violations

**Q20. Should a blocked request be silently rejected, or should the user receive an explanation?**

> Not specified in guidance.txt. [inferred — low confidence]: OPA returns `allow: false`; explanation delivery is handled at the agent/application layer and is out of OPA scope.

---

**Q21. Are there different severity levels — hard block vs. warning?**

> | Level | Examples |
> |-------|----------|
> | Hard block | Guest calling get_events; topic outside approved list; limit above role cap; blocked keyword in keywords; session cap exceeded |
> | Soft block with redirect | None specified |
>
> [derived from guidance.txt — all rules are hard blocks]

---

**Q22. Do you need to log which rule was violated, or just that a request was denied? Does an existing violation-code scheme need to be reused?**

> Not specified in guidance.txt. No pre-existing violation-code scheme.
>
> | Code | Meaning |
> |------|---------|
> | (none — no pre-existing scheme) | |

---

**Confidence breakdown:** 15 answers `[derived from guidance.txt]` or `[derived from architecture]`; 5 answers `[inferred — low confidence]` (Q17, Q18, Q19, Q20, Q21 soft-block row); 0 blank.
