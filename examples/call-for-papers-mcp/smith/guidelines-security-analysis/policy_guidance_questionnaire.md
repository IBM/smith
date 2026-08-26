# OPA Policy Guidance Questionnaire
# Tool: call-for-papers-mcp (get_events)

---

## Section 1: Tool Identity

**Q1. What is the tool name and what does it do in one sentence?**

> Tool name: `get_events` — searches WikiCFP for academic conferences matching given keywords, returning event name, description, dates, location, deadline, and link; limited to the CS department's three approved research areas. [derived from architecture]

---

**Q2. What external systems does it call?**

> - **WikiCFP** (`http://www.wikicfp.com/cfp/servlet/tool.search`): HTTP GET, read-only, no authentication. [derived from architecture]
> - **LLM inference** (local Ollama / OpenAI-compatible endpoint): read-only, agent reasoning only. [derived from architecture]

---

**Q3. Does it read data, write data, or both?**

> Read only — scrapes WikiCFP and returns conference listings. No database writes. [derived from architecture]

---

**Q4. What are its parameters?**

| Parameter | Type | Required | Valid values |
|-----------|------|----------|--------------|
| `keywords` | string | Yes | Free-text search terms; must NOT contain any disallowed substring from the blocked list |
| `topic` | string | Yes | Exactly one of: `"Artificial intelligence"`, `"Cybersecurity and privacy"`, `"Software engineering"` |
| `limit` | integer | No (default 10) | 1–15 for faculty; 1–10 for phd_student; absolute maximum 15 |

> [derived from architecture] — confirmed against `tool_definitions.json` and `guidance.txt`

---

## Section 2: Who Uses It

**Q5. What are the types of users? List every role.**

> - `faculty` — may search all three approved areas; limit cap 15.
> - `phd_student` — may search only their own `dissertation_area`; limit cap 10.
> - `guest` — may NOT use `get_events` at all.
>
> [derived from guidance.txt]

---

**Q6. Are those roles verified by your system, or supplied by the user themselves?**

> **Self-reported** — `user_role`, `dissertation_area`, and `queries_this_session` all come from the caller's `user_profile` JSON body field, injected verbatim into the system prompt. No authentication or cryptographic verification. [derived from architecture]

---

**Q7. Is there a user ID? Where does it come from?**

> `user_name` is in `system_vars.json` but is not used for access control. No user ID for authorization. [derived from architecture]

---

**Q8. Can a user belong to multiple roles at once?**

> `user_role` is a single string (not an array) in `system_vars.json`. A caller has exactly one role. [derived from architecture]

---

## Section 3: What Each Role Is Allowed To Do

**Q9. For each role, which tools are they allowed to use and with what conditions?**

| Tool | `faculty` | `phd_student` | `guest` | guidance.txt rule |
|------|-----------|---------------|---------|-------------------|
| `get_events` | Allowed; all 3 approved topics; limit ≤ 15 | Allowed; `topic` must equal own `dissertation_area`; limit ≤ 10 | Blocked entirely | "What the Agent May Do" section |

> [derived from guidance.txt]

---

**Q10. Are there topics, values, or parameter combinations some roles can use that others cannot?**

> - `topic` for `phd_student`: must equal `subject.dissertation_area` (single area restriction). [derived from guidance.txt]
> - `topic` for `faculty`: any of the three approved areas. [derived from guidance.txt]
> - `limit` cap differs by role: faculty ≤ 15, phd_student ≤ 10. [derived from guidance.txt]
> - `keywords` disallowed substrings apply to all roles equally. [derived from guidance.txt]

---

**Q11. Are there roles that have no restrictions?**

> No — `faculty` is the least restricted but still subject to: approved topics only, limit ≤ 15, disallowed keywords, and ≤ 5 searches per session. [derived from guidance.txt]

---

## Section 4: Hard Limits

**Q12. Are there parameter values that should always be blocked for everyone, regardless of role?**

> Yes — the following substrings must not appear (case-insensitively) in `keywords` for any role:
> - `bioinformatics`, `genomics`, `clinical trials`, `drug discovery`
> - `quantum physics`, `materials science`, `renewable energy`
> - `economics`, `finance`, `marketing`, `supply chain`
> - `education`, `psychology`, `sociology`, `political science`
> - `trade show`, `career fair`, `startup expo`, `hackathon`
>
> [derived from guidance.txt]

---

**Q13. Is there a maximum value for any numeric parameter that no role can exceed?**

> `limit` absolute maximum: 15 (no role may exceed this). Also minimum of 1 (below 1 is disallowed). [derived from guidance.txt]

---

**Q13b. Are there approval paths?**

> None. [derived from guidance.txt]

---

**Q14. Are there keywords or inputs that must always be rejected?**

> Yes — the blocked keyword list in Q12 above. [derived from guidance.txt]

---

## Section 5: Volume and Rate Limits

**Q15. Is there a maximum number of times this tool can be called in a single session?**

> Yes — maximum 5 `get_events` calls per session, enforced via `subject.queries_this_session`. [derived from guidance.txt]

| Role | Max calls per session |
|------|-----------------------|
| `faculty` | 5 |
| `phd_student` | 5 |

---

**Q16. Who keeps track of how many times the tool has been called?**

> The caller supplies `queries_this_session` in `user_profile`. This is self-reported and trivially forgeable. OPA reads `input.extensions.subject.queries_this_session`. [derived from architecture + guidance.txt]

---

## Section 6: Response Filtering

**Q17. After the tool returns results, does anything need to be hidden?**

> No response filtering is specified. WikiCFP results are returned as-is. [derived from guidance.txt]

---

**Q18. Are there fields in the response that should be suppressed?**

> None specified. [derived from guidance.txt]

---

**Q19. Are there conditions on a result that determine whether it is "actionable"?**

> No post-execution actionability checks. OPA blocks pre-execution. [derived from architecture]

---

## Section 7: Violations

**Q20. Should a blocked request be silently rejected or explained?**

> The agent is instructed to acknowledge denied tool results politely. OPA denials return an error envelope relayed by the LLM. [derived from architecture]

---

**Q21. Are there different severity levels?**

> | Level | Examples |
> |-------|----------|
> | Hard block | All identified violations — no soft-block paths identified. |
> | Soft block | None. |

---

**Q22. Does an existing violation-code scheme need to be reused?**

> No pre-existing OPA violation-code scheme for this agent. New codes minted in Step D.
>
> | Code | Meaning |
> |------|---------|
> | (none pre-existing) | — |

---

**Confidence breakdown:** `[derived from guidance.txt]`: 16 | `[derived from architecture]`: 9 | `[inferred — low confidence]`: 0 | blank: 0
