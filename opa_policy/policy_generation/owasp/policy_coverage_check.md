## Policy Coverage Check Skill

Audits `policy.rego` against two independent sources of truth:

1. **Guidance coverage** — every rule in `guidance.txt` must map to at
   least one `deny["CODE"]` rule in the policy.
2. **OWASP coverage** — every in-scope threat instance from
   `owasp_policy_guidelines.md` must map to at least one `deny["CODE"]` rule.

Produces `policy_coverage_report.md`. If gaps are found, proposes the
missing deny rules and waits for human confirmation before patching them
into `policy.rego`.

### Authoritative Paths

- Input 1: `<mcp_server_dir>/policy_generation/policy.rego`
- Input 2: `<mcp_server_dir>/policy_generation/owasp_policy_guidelines.md`
- Input 3 (optional): `<mcp_server_dir>/smith/guidance.txt`
- Output: `<mcp_server_dir>/policy_generation/policy_coverage_report.md`
- Side effect (if gaps confirmed): updated `<mcp_server_dir>/policy_generation/policy.rego`

---

### Workflow (follow strictly)

---

#### STEP 1 — Read inputs

Read all three files. If `guidance.txt` is absent, skip guidance coverage
and note that in the report. If either required input is missing, stop and
tell the user which file is needed.

---

#### STEP 2 — Extract the policy rule inventory

From `policy.rego`, extract:
- Every `deny["CODE"]` rule head — this is the set of implemented codes
- For each code, the conditions in its rule body (one sentence description)
- The `allowed_tools` set

Produce an internal table:

| Code | Condition summary |
|------|-------------------|
| UNKNOWN_TOOL | input.name not in all_known_tools |
| ... | ... |

---

#### STEP 3 — Guidance coverage check

If `guidance.txt` is present:

For each numbered rule in `guidance.txt`:
1. Paraphrase the rule as a one-line enforcement condition.
2. Determine which `deny["CODE"]` rule(s) in the policy implement it.
3. Classify:
   - **Covered** — one or more deny rules fully implement the condition
   - **Partial** — a deny rule exists but misses a sub-condition (e.g.
     scope restriction, approval path, keyword list)
   - **Uncovered** — no deny rule addresses this rule at all

Produce the guidance coverage table:

| guidance.txt rule | Condition | Status | Implementing code(s) | Gap description |
|---|---|---|---|---|
| Rule 1 | <condition> | Covered / Partial / Uncovered | CODE | <gap if any> |
| ... | | | | |

---

#### STEP 4 — OWASP coverage check

From `owasp_policy_guidelines.md`, read the Policy Rules section.

For each violation code listed in the Violation Code Reference table:
1. Check that a `deny["CODE"]` rule with that exact code exists in
   `policy.rego`.
2. Read the rule's condition from Step 2 and compare it against the
   spec condition in `owasp_policy_guidelines.md`.
3. Classify:
   - **Implemented** — code exists and condition matches the spec
   - **Condition mismatch** — code exists but the Rego condition does
     not fully match the spec (e.g. wrong threshold, missing field)
   - **Missing** — code is in the spec but not in the policy

Produce the OWASP coverage table:

| Violation code | OWASP category | Status | Gap description |
|---|---|---|---|
| UNKNOWN_TOOL | LLM04 | Implemented | — |
| ... | | | |

---

#### STEP 5 — Write policy_coverage_report.md

Write to `<mcp_server_dir>/policy_coverage_report.md` using this structure:

```
# Policy Coverage Report
# Tool: <tool-name>

---

## Guidance Coverage

| guidance.txt rule | Condition | Status | Implementing code(s) | Gap |
|---|---|---|---|---|
...

Guidance rules covered: N / M
Guidance rules partial: N / M
Guidance rules uncovered: N / M

---

## OWASP Coverage

| Violation code | OWASP category | Status | Gap |
|---|---|---|---|
...

Violation codes implemented: N / M
Violation codes with condition mismatch: N / M
Violation codes missing: N / M

---

## Gap Summary

### Uncovered guidance rules
<list each, with the rule text and the deny rule that would cover it>

### Missing or mismatched OWASP violation codes
<list each, with the spec condition and the Rego it should produce>

### Proposed additions to policy.rego
<for each gap, write the exact deny rule(s) to add — full Rego, ready to paste>
```

If there are no gaps, write:
```
All guidance rules and OWASP violation codes are fully covered.
No changes to policy.rego are needed.
```

---

#### STEP 6 — Human review

Present the gap summary (not the full tables).

If there are NO gaps:
> Coverage check complete. All guidance rules and OWASP violation codes
> are implemented. Proceeding to test case generation.

If there ARE gaps:

Automatically apply the proposed additions:
- Append each proposed deny rule to `policy.rego` inside the deny rules
  section, before `valid_envelope`.
- Re-run `opa fmt -w` and `opa check` on the updated file.
- Update `policy_coverage_report.md` to mark the added rules as
  Implemented.
- Log: "Added N rules. `opa check` clean. Proceeding to test case generation."

Continue automatically to test case generation.
