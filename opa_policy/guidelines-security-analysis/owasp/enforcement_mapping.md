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

**Violation codes.** Before minting a new code, check
`policy_guidance_questionnaire.md` Section 7 Q22. If it lists a
pre-existing violation-code scheme, reuse those codes for any rule they
apply to — do not rename them. Mint a new code (following the same
naming shape as the existing scheme, if any) only when no listed code
covers the rule. When a new code is minted, add it to the violation-code
reference in STEP 6's output; the questionnaire's Q22 table is not
edited.

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

The output is a specification for policy generation, not an
implementation. It is expected to name OPA-native field paths
(`input.name`, `input.arguments.*`, `input.extensions.*`) because those
are the interception surface. What it must NOT contain:

- Rego syntax — no `package`, no rule blocks, no `default allow := ...`,
  no `some x in ...`
- Concrete Rego helper choices or built-in names (e.g. `regex.match`,
  `net.cidr_contains`) — describe the matching semantics instead
  (exact / case-insensitive substring / regex / numeric comparison /
  CIDR membership)
- Any hint about how a downstream policy-authoring workflow should
  organise files, helpers, or test cases

---

#### STEP 6b — Verify citations

Before continuing, walk every rule in `owasp_policy_guidelines.md` and
confirm each cited identifier exists in its source. This is the same
principle as `threat_model.md`'s STEP 4 verification, extended to the
rule specifications this step produces.

For every rule under "Policy Rules (OPA scope only)":

1. **Fields.** Every `input.arguments.<x>` must appear in
   `tool_definitions.json`. Every `input.extensions.subject.<x>` (or any
   other `input.extensions.*`) must appear in `system_vars.json` or in
   `architecture.md`'s Trust Boundaries table. A rule that checks a
   field that does not exist at invocation time cannot be enforced.
2. **Mitigation grounding.** The mitigation cited from the catalog for
   the rule's ASI category must be present verbatim (or as a clear
   paraphrase) in that catalog entry's `mitigations` array. Do not
   invent mitigations to justify a rule.
3. **Threat linkage.** Every rule must trace back to at least one threat
   instance in `threat_model.md` — either its evidence line, or its
   threat-instance text. A rule with no upstream threat instance is a
   sign that STEP 2's decision logic was skipped; remove it or add the
   missing threat instance to `threat_model.md` (and re-run STEP 2 for
   that category).
4. **Questionnaire-sourced values.** If a rule's value set was pulled
   from a questionnaire answer, that answer must not be tagged
   `[inferred — low confidence]`. If it is, either drop the rule or
   mark the value set as `TBD — requires human confirmation` and treat
   the rule as pending rather than active.

Any rule that fails verification: fix the citation, or remove the rule
from `owasp_policy_guidelines.md`. Log a one-line result
(e.g. `Citations verified: 9/9` or
`Citations verified: 7/9 — 2 rules dropped for missing fields`).

---

#### STEP 7 — Build the combined candidate-rule list

Assemble one deduplicated list of candidate rules from two independent
sources. This step does NOT touch `guidance.txt`; that comparison is
STEP 8. Keeping these two concerns split makes it possible to attribute
a wrong `guidance_updated.txt` output to either "the candidate list was
wrong" or "the coverage check was wrong."

**Source 1 — OWASP-derived.** Every rule written under "Policy Rules (OPA
scope only)" in STEP 6 (post-verification per STEP 6b).

**Source 2 — questionnaire-derived.** Read
`policy_guidance_questionnaire.md` Sections 3-6 (Q9-Q19: role scoping,
hard parameter/numeric limits, approval paths, keyword blocks, rate
limits, response filtering). These answers do not need to map to any
OWASP category to be worth enforcing. For each answer, apply the same OPA
Enforcement Boundary test from the top of this file (is the condition
visible at invocation time as `input.name`/`input.arguments.*`/
`input.extensions.*`?). Keep only the answers that pass. Skip any answer
tagged `[inferred — low confidence]` — those are not eligible to become
candidate rules on their own (STEP 6b already applied this to Source 1).
An answer that fails the boundary test is out of OPA scope for the same
reason it would be in STEP 2 — note it in the gap register (STEP 4)
instead if it isn't there already.

**Deduplicate.** If a Source 2 candidate describes the same condition on
the same field as a Source 1 rule (this happens when a questionnaire
answer and an OWASP threat instance both surfaced the same control),
keep it once, tagged with both sources — do not list it twice. Use the
same three-criteria test as STEP 8 (same field, same operator,
overlapping value set) to decide whether two candidates are the same.

Produce a numbered list of candidates. For each candidate record: source
tags (`[ASI04 / VIOLATION_CODE]`, `[from questionnaire Q12]`, or both),
the structured field, the operator, and the value set. Log this list —
STEP 8 consumes it as input, and STEP 9 references it in the summary.

---

#### STEP 8 — Reconcile candidates against guidance.txt

Read `<TARGET_AGENT_PATH>/smith/guidance.txt` if it exists. If it does
not exist, skip the coverage check and write `guidance_updated.txt`
containing only STEP 7's candidate list, numbered starting from 1, with
their source tags preserved.

If `guidance.txt` exists, for each candidate from STEP 7, check whether
an existing numbered rule in `guidance.txt` already covers the same
condition on the same field. A candidate counts as covered only when an
existing rule matches the candidate on ALL THREE of the following:

1. **Same structured field.** The `input.*` path the candidate would
   check must correspond to the field the guidance.txt rule constrains
   (e.g. both talk about the `amount` argument, or both talk about the
   caller's role). Different fields → not covered, even if the rule
   sounds thematically similar.
2. **Same operator / matching semantics.** Exact-equality, substring,
   numeric threshold, set-membership, and regex are distinct. A
   guidance.txt rule that says "block `.exe` files" does not cover a
   candidate that says "block requests where the extension is not in
   {pdf, csv, json}" — the operators are opposite polarities.
3. **Overlapping value set.** For value-based conditions, the guidance.txt
   rule's allowed/blocked set must overlap the candidate's set on the
   value that would trigger the rule. A guidance.txt rule capping
   purchases at 500 does not cover a candidate capping purchases at 200
   for the `employee` role — the values differ AND the scoping differs.

Matching OWASP category, matching questionnaire section, or similar
natural-language phrasing alone is NOT enough. If even one of the three
criteria above fails, the candidate is missing.

For every candidate, write out the coverage decision explicitly in a
scratch table before producing `guidance_updated.txt`, so a reviewer can
audit the call:

| Candidate | Field | Operator | Value set | Matching guidance.txt rule # | Covered? |
|---|---|---|---|---|---|
| <one-line candidate> | <input.*> | <exact / substring / ...> | <values> | <rule # or "—"> | Yes / No |

Do NOT include this scratch table in `guidance_updated.txt`; log it
alongside the STEP 9 summary.

For every missing candidate, write a new `guidance.txt`-style line:
- Continue the existing numbering in `guidance.txt`; do not renumber
  existing rules
- Phrase it as a plain-English guidance rule, not as OPA/Rego syntax
- Tag it with its source in brackets so it stays traceable: `[ASI04 /
  VIOLATION_CODE]` for Source 1, `[from questionnaire Q12]` for Source 2,
  or both tags together for a deduplicated candidate

**Carry the Gap Register forward too.** STEP 7 only admits candidates
that pass the OPA Enforcement Boundary test, so a real finding from the
OWASP threat model that fails that test (Agent-layer, tool-implementation,
or infra-owned) never becomes a STEP 7 candidate and would otherwise
never reach `guidance_updated.txt` — even on a run where every STEP 7
candidate is already covered and the numbered-rule list has nothing to
add. Do not let that happen: every row in STEP 4's gap register must
show up in `guidance_updated.txt` too, written in the same
natural-language style `guidance.txt` itself uses (a plain descriptive
sentence, not OPA/Rego syntax) and tagged with its source ASI category
for traceability, e.g. `[ASI01]`. Match `guidance.txt`'s own section
conventions — either fold each item under the header it most naturally
belongs to if one exists, or add one new header in the same style as
`guidance.txt`'s existing ones (e.g. `## Additional Notes from OWASP
Analysis`) if none fits.

Write `<TARGET_AGENT_PATH>/smith/guidance_updated.txt` containing:
1. Every existing rule from `guidance.txt`, unchanged, in its original order
2. Every missing candidate identified above, appended after them,
   continuing the numbering
3. Every gap register item from STEP 4, appended after them, written in
   guidance.txt's own style as described above — nothing found by the
   OWASP analysis is dropped just because it isn't OPA-enforceable

Overwrite `guidance_updated.txt` in full on every run rather than
appending to a prior run's file — this keeps it consistent with the
current threat model and questionnaire instead of accumulating stale
entries from earlier iterations.

Do NOT modify `guidance.txt` or `policy_guidance_questionnaire.md`
themselves. `guidance_updated.txt` is a proposal for the human to review
and merge in manually.

---

#### STEP 9 — Human review

Present the summary table, the list of violation codes, the STEP 7
candidate list (with source tags), the list of newly proposed guidance
rules from STEP 8 (or "none — guidance.txt already covers every
OWASP-derived and questionnaire-derived candidate" / "none — no
guidance.txt found, all candidates written fresh"), and the gap register
items carried into `guidance_updated.txt` (or "none — gap register is
empty").

Log these, then hand control back to the top-level workflow, which
decides (per confirmation mode) whether to proceed to Completion. This
workflow ends at Completion; downstream policy authoring is out of
scope here.
