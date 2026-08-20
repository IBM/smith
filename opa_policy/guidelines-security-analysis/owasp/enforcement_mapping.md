## Enforcement Mapping 

Maps each threat from `threat_model.md` to the layer that can enforce a
control, determines OPA scope, produces `owasp_policy_guidelines.md`, and
reconciles both the resulting OPA-scope rules AND the questionnaire's own
enforceable answers against the target's existing `guidance.txt` to
surface guidance gaps in `guidance_updated.txt`.
Requires `architecture.md` and `threat_model.md` in the target directory.

### Authoritative Paths

**Inputs:** Use ONLY these exact files. Do NOT read similarly-named files
from other folders. If a required file is missing here, stop and ask; do
not substitute one from elsewhere.
- Input 1: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`
- Input 2: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/threat_model.md`
- Input 3: `src/smith/data/owasp_10_ai_catalog.json` — repo-relative, not
  per-target-agent. Source of the `mitigations` used to ground STEP 5's
  rule proposals for each ASI category.
- Input 4: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/policy_guidance_questionnaire.md`
  — used only in STEP 7. Sections 3-6 (Q9-Q19: role scoping, hard limits,
  rate limits, response filtering) capture concrete policy intent that
  does not need to map to any OWASP category to be worth enforcing — STEP
  7 pulls these in as a second source of candidate rules, independent of
  the OWASP path in STEP 2-6.
- Input 5 (optional): `<TARGET_AGENT_PATH>/smith/guidance.txt` — the
  target's existing natural-language guidance, if present. Used only in
  STEP 7 to check which candidate rules (from STEP 5 and from the
  questionnaire) are not yet represented in it. If absent, note the gap
  and skip STEP 7's comparison (write `guidance_updated.txt` containing
  only the newly derived rules).
- Output 1: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/owasp_policy_guidelines.md`
- Output 2: `<TARGET_AGENT_PATH>/smith/guidance_updated.txt` — written next
  to `guidance.txt`, not under `guidelines-security-analysis/`

### OPA Enforcement Boundary (non-negotiable)

OPA can enforce a control if and only if ALL of the following are true:

1. The tool call is intercepted BEFORE the tool executes
2. The relevant data is present as a structured field at interception time
3. The field comes from `input.name`, `input.arguments.*`, or
   `input.extensions.*`

OPA CANNOT enforce controls over:
- The LLM's internal reasoning or generation
- The content of the system prompt
- The tool's return value / response
- External service behaviour or response integrity
- Library or dependency trust
- Post-hoc output processing

If a threat cannot be addressed at tool-invocation time with structured
fields, it is out of OPA scope — even if it is a real and serious risk.

### Workflow (follow strictly)

---

#### STEP 1 — Read inputs

Read `architecture.md`, `threat_model.md`, and the `owasp_10_ai_catalog.json`
catalog in full before proceeding.
If a required file is missing, stop and tell the user which file is needed.

---

#### STEP 2 — Per-threat enforcement mapping

For every threat instance in `threat_model.md`, apply the following
decision logic IN ORDER:

```
Q1: Is the threat visible at tool invocation time as a structured field?
    YES → go to Q2
    NO  → assign layer = Out of OPA scope, go to STEP 3

Q2: Which structured field carries the evidence for this threat?
    Name it explicitly (e.g. input.arguments.keywords,
    input.extensions.subject.role).

Q3: Can a Rego rule deny the request based solely on that field?
    YES → assign layer = OPA
    NO  → assign layer = Out of OPA scope

For threats assigned Out of OPA scope:
Q4: Which layer CAN address it?
    - Agent layer: threats in LLM reasoning, system prompt, output text
    - Tool implementation: unsanitised output, external call construction
    - Infrastructure/deployment: dependency pinning, supply chain
    - N/A: not applicable to this tool
```

---

#### STEP 3 — Build the scoping table

Produce a table with one row per OWASP category (not per threat instance):

| OWASP Category | In OPA scope? | Scope note | Out-of-scope owner |
|---|---|---|---|
| ASI01 | Yes / Partial / No | <what OPA covers> | <layer for the rest> |
...

Partial = the category has both OPA-enforceable and non-enforceable
threat instances. Describe the split in the scope note.

---

#### STEP 4 — Build the gap register

For every out-of-scope item, record:

| Threat | Layer | Recommended action |
|---|---|---|
| <specific threat instance> | Agent / Tool impl / Infra | <one-line action> |

This register is for the teams responsible for those layers. It does not
feed into the OPA policy.

---

#### STEP 5 — Write OPA policy rules

For each threat assigned layer = OPA in STEP 2, write a concrete,
implementation-agnostic rule in plain English. Ground the rule in the
`mitigations` listed for that threat's ASI category in the catalog — pick
the mitigation(s) that are enforceable as a structured-field check, and use
them to justify the condition. Each rule must state:

- The condition to check (which field, what value or pattern)
- The violation code to emit on a match
- The severity (Hard block / Soft block)
- The matching semantics (exact / case-insensitive substring / numeric comparison)

Group rules by OWASP category. Do not write Rego — write requirements.

---

#### STEP 6 — Write owasp_policy_guidelines.md

Write the output file to `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/owasp_policy_guidelines.md`
using exactly this structure:

```
# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines
# Tool: <tool-name>

---

## Architecture Summary
<two-sentence description of the tool's layers and trust model,
 derived from architecture.md>

---

## OWASP Top 10 for Agentic AI Security — Scope Assessment

### <Category name>
**Risk:** <one sentence>
**Verdict:** <In scope / Partial / Out of scope> — <one sentence reason>

[repeat for each category]

---

## Summary Table

| OWASP Category | In OPA scope? | Out-of-scope owner |
|---|---|---|
...

Categories flowing into the OPA policy: <comma-separated list>

---

## Gap Register

| Threat | Layer | Recommended action |
|---|---|---|
...

---

## Policy Rules (OPA scope only)

### Input Schema
| Field | Source |
...

### Known values
[sets, enums, or term lists that rules reference]

### Rule: <violation code>
- OWASP: <category>
- Severity: Hard block / Soft block
- Condition: <plain-English condition>
- Matching: <exact / case-insensitive substring / numeric comparison>

[one block per violation code]

---

## Violation Code Reference

| Code | OWASP | Severity |
|---|---|---|
...
```

Do NOT include Rego code. Do NOT include OPA hints. The output is a
specification for policy generation, not an implementation.

---

#### STEP 7 — Reconcile against guidance.txt

This step builds one combined candidate-rule list from two independent
sources, then checks both against `guidance.txt`. The two sources do not
depend on each other — a candidate from either one is checked and
included on its own merits.

**Source 1 — OWASP-derived.** Every rule written under "Policy Rules (OPA
scope only)" in STEP 6.

**Source 2 — questionnaire-derived.** Read
`policy_guidance_questionnaire.md` Sections 3-6 (Q9-Q19: role scoping,
hard parameter/numeric limits, approval paths, keyword blocks, rate
limits, response filtering). These answers do not need to map to any
OWASP category to be worth enforcing. For each answer, apply the same OPA
Enforcement Boundary test from the top of this file (is the condition
visible at invocation time as `input.name`/`input.arguments.*`/
`input.extensions.*`?). Keep only the answers that pass; an answer that
fails is out of OPA scope here for the same reason it would be in STEP 2
— note it in the gap register (STEP 4) instead if it isn't there already.

**Deduplicate before comparing to guidance.txt.** If a Source 2 candidate
describes the same condition on the same field as a Source 1 rule (this
happens when a questionnaire answer and an OWASP threat instance both
surfaced the same control), keep it once, tagged with both sources — do
not list it twice.

Read `<TARGET_AGENT_PATH>/smith/guidance.txt` if it exists. If it does
not exist, skip the comparison below and write `guidance_updated.txt`
containing only the deduplicated candidate list, numbered starting from 1.

For each candidate in the deduplicated list, check whether an existing
numbered rule in `guidance.txt` already covers the same condition on the
same field — matching OWASP category, or matching questionnaire section,
alone is not enough. A candidate counts as missing only if no existing
`guidance.txt` rule already enforces that specific structured-field check.

For every missing candidate, write a new `guidance.txt`-style line:
- Continue the existing numbering in `guidance.txt`; do not renumber
  existing rules
- Phrase it as a plain-English guidance rule, not as OPA/Rego syntax
- Tag it with its source in brackets so it stays traceable: `[ASI04 /
  VIOLATION_CODE]` for Source 1, `[from questionnaire Q12]` for Source 2,
  or both tags together for a deduplicated candidate

Write `<TARGET_AGENT_PATH>/smith/guidance_updated.txt` containing:
1. Every existing rule from `guidance.txt`, unchanged, in its original order
2. Every missing candidate identified above, appended after them,
   continuing the numbering

Overwrite `guidance_updated.txt` in full on every run rather than
appending to a prior run's file — this keeps it consistent with the
current threat model and questionnaire instead of accumulating stale
entries from earlier iterations.

Do NOT modify `guidance.txt` or `policy_guidance_questionnaire.md`
themselves. `guidance_updated.txt` is a proposal for the human to review
and merge in manually.

---

#### STEP 8 — Human review

Present the summary table, the list of violation codes, and the list of
newly proposed guidance rules from STEP 7 (or "none — guidance.txt
already covers every OWASP-derived and questionnaire-derived candidate" /
"none — no guidance.txt found, all candidates written fresh").

Log these, then continue automatically to the policy_writing skill.
