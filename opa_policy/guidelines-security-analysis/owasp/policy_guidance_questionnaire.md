## Policy Guidance Questionnaire 

Produces `policy_guidance_questionnaire.md` for a target MCP server.
This document captures policy intent — who can use the tool, what they
are allowed to do, and what must be blocked. It is required input for
the threat_model skill.

Requires `architecture.md` to be present (produced by architecture_analysis
skill). Use it to answer questions about parameters, external calls, and
data flow rather than asking the user to look up source files.

### Authoritative Paths

**Inputs:** Use ONLY these exact files. Do NOT read similarly-named files
from other folders. If a required file is missing here, stop and ask; do
not substitute one from elsewhere.
- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`
- Input (optional): `<TARGET_AGENT_PATH>/smith/guidance.txt` — **primary source
  of policy intent**. If present, read every rule and map each one to the
  questionnaire section it belongs to. Rules in guidance.txt take precedence
  over inferences from architecture.md.
- Input (optional): `<TARGET_AGENT_PATH>/smith/system_vars.json` — use for
  exact field names and types in Sections 2 and 5
- Input (optional): `<TARGET_AGENT_PATH>/smith/tool_definitions.json` — use
  for exact parameter names and types in Section 1
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/policy_guidance_questionnaire.md`

---

### Workflow (follow strictly)

---

#### STEP 1 — Read inputs

Read `architecture.md` in full. If any of the following exist under
`<TARGET_AGENT_PATH>/smith/`, read them too — do NOT proceed until all
available files are read:
- `guidance.txt` — **read this first among the smith/ files**. Parse
  every numbered rule. For each rule, note which questionnaire section
  it maps to (see mapping below) and what OPA-enforceable condition it
  implies.
- `system_vars.json`
- `tool_definitions.json`

**guidance.txt → questionnaire mapping:**
| guidance.txt rule type | Questionnaire section |
|---|---|
| Role-based tool access (who can/cannot use a tool) | Section 3, Q9 |
| Field-level restrictions (which fields are forbidden per role) | Section 3, Q10 + Section 6, Q17–Q18 |
| Scope restrictions (e.g. manager's own team only) | Section 3, Q9 — add as a sub-condition |
| Hard parameter blocks (external_sharing, blocked domains) | Section 4, Q12 |
| Numeric caps (purchase amounts) | Section 4, Q13–Q14 |
| Approval paths (action allowed with approval flag) | Section 4, Q14 — note approval field name |
| Prompt injection / keyword blocks | Section 4, Q13–Q14 |
| Format or value enumerations (CSV/PDF/JSON) | Section 4, Q12 |

Pre-fill every answer you can derive from these files. Mark each
pre-filled answer with `[derived from guidance.txt]` when it comes from
guidance.txt, or `[derived from architecture]` when inferred from source
files. Leave genuinely unknown answers blank.

---

#### STEP 2 — Fill the questionnaire

Write the output file to `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/policy_guidance_questionnaire.md`
using exactly this structure. Pre-fill where possible; ask the user only
for answers that cannot be derived from the input files.

```
# OPA Policy Guidance Questionnaire
# Tool: <tool-name>

Fill in each answer based on your tool and agent. You do not need to
know OPA or security to complete this — just describe how your tool
works and who should be able to use it.

---

## Section 1: Tool Identity

**Q1. What is the tool name and what does it do in one sentence?**

> Tool name: `<tool_name>`
> <one-sentence description>

---

**Q2. What external systems does it call?**

> <service name, protocol, authentication, read/write>

---

**Q3. Does it read data, write data, or both?**

> <read / write / both — with brief explanation>

---

**Q4. What are its parameters? For each: name, type, required or optional,
what counts as a valid value?**

| Parameter | Type | Required | Valid values |
|-----------|------|----------|--------------|
| <name> | <type> | Yes / No | <description> |

---

## Section 2: Who Uses It

**Q5. What are the types of users? List every role.**

> - `<role>` — <description>

---

**Q6. Are those roles verified by your system, or supplied by the user themselves?**

> <Verified / Self-reported> — <explain mechanism>

---

**Q7. Is there a user ID? Where does it come from?**

> <yes/no, field name, source, how it is used>

---

**Q8. Can a user belong to multiple roles at once?**

> <yes/no — explain how the calling application handles this>

---

## Section 3: What Each Role Is Allowed To Do

**Q9. For each role, which tools are they allowed to use and with what
conditions or scope restrictions?**

| Tool | <role 1> | <role 2> | guidance.txt rule |
|------|----------|----------|-------------------|
| <tool> | <allowed/blocked + scope condition> | <allowed/blocked + scope condition> | Rule N |

---

**Q10. Are there topics, values, or parameter combinations some roles
can use that others cannot?**

> <describe per-role restrictions, or "none">

---

**Q11. Are there roles that have no restrictions?**

> <role name(s) or "none">

---

## Section 4: Hard Limits

**Q12. Are there parameter values that should always be blocked for
everyone, regardless of role?**

> <list them, or "none">

---

**Q13. Is there a maximum value for any numeric parameter that no role
can exceed?**

> <parameter name>: <hard cap value>, or "none">

---

**Q13b. Are there approval paths — actions allowed conditionally when an
approval field is set?**

> | Parameter condition | Approval field | guidance.txt rule |
> |---------------------|----------------|-------------------|
> | <e.g. amount >= 200, role=employee> | <e.g. subject.approval == true> | Rule N |

---

**Q14. Are there keywords or inputs that must always be rejected?**

> <list them with the free-text field they appear in, or "none">

---

## Section 5: Volume and Rate Limits

**Q15. Is there a maximum number of times this tool can be called in
a single conversation session?**

> <yes/no — if yes, per-role table>

| Role | Max calls per session |
|------|-----------------------|
| <role> | <integer> |

---

**Q16. Who keeps track of how many times the tool has been called —
your app, or should the policy enforce it?**

> <explain the mechanism; name the field the policy should read>

---

## Section 6: Response Filtering

**Q17. After the tool returns results, does anything need to be hidden,
flagged, or categorised before the user sees it?**

> <describe per-role filtering rules, or "none">

---

**Q18. Are there fields in the response that should be suppressed for
certain roles?**

> <field names and roles, or "none">

---

**Q19. Are there conditions on a result that determine whether it is
"actionable"?**

> <describe conditions, or "none">

---

## Section 7: Violations

**Q20. Should a blocked request be silently rejected, or should the
user receive an explanation?**

> <silent / explanation — if explanation, describe what to say>

---

**Q21. Are there different severity levels — hard block vs. warning?**

> | Level | Examples |
> |-------|----------|
> | Hard block | <examples> |
> | Soft block with redirect | <examples> |

---

**Q22. Do you need to log which rule was violated, or just that a
request was denied?**

> <log specific rule / log denial only>
>
> | Code | Meaning |
> |------|---------|
> | <CODE> | <description> |
```

---

#### STEP 3 — Finalise and continue

Fill in any remaining blanks using best inference from available files — do not
leave any answer empty. Log which answers were derived from `guidance.txt`,
which from architecture/source files, and which were inferred. Continue
automatically to the threat_model skill.
