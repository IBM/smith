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
- Input 6: `<TARGET_AGENT_PATH>/smith/tool_definitions.json` — the
  authoritative source for `input.args.*` field names and types,
  **per tool**: each entry's `parameters` array lists only the arguments
  that tool accepts. STEP 6b and STEP 7 verify every candidate rule
  against it. This input is required, not optional — without it no rule
  can be verified. If it is absent, stop and tell the user to run
  `smith --flag get_mcp_parameter`.
- Input 7: `<TARGET_AGENT_PATH>/smith/system_vars.json` — the
  authoritative source for `input.extensions.subject.*` field names. It
  takes precedence over what is inferred from source code. If absent,
  fall back to `architecture.md`'s Trust Boundaries table and note the
  gap.
- Output 1: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/owasp_policy_guidelines.md`
- Output 2: `<TARGET_AGENT_PATH>/smith/guidance_updated.txt` — written next
  to `guidance.txt`, not under `guidelines-security-analysis/`

### OPA Enforcement Boundary (non-negotiable)

OPA can enforce a control if and only if ALL of the following are true:

1. The tool call is intercepted BEFORE the tool executes
2. The relevant data is present as a structured field at interception time
3. The field comes from `input.name`, `input.args.*`, or
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

Read `architecture.md`, `threat_model.md`, the `owasp_10_ai_catalog.json`
catalog, `tool_definitions.json`, and `system_vars.json` in full before
proceeding.
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
    Name it explicitly (e.g. input.args.keywords,
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
(`input.name`, `input.args.*`, `input.extensions.*`) because those
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
principle as `threat_model.md`'s STEP 6 citation verification, extended to the
rule specifications this step produces.

For every rule under "Policy Rules (OPA scope only)":

1. **Fields.** A rule may only reference data the MCP server actually
   declares. Verify this per tool, not per field:

   a. List the tool(s) the rule governs, using ONLY names that appear in
      `tool_definitions.json`. A rule may govern several — list them all.
      A rule that governs a tool the server does not expose is not a
      rule; drop it.
   b. For EACH governed tool independently, every `input.args.<x>` the
      rule needs must appear in THAT tool's own `parameters` array. A
      field present on one governed tool and absent from another does
      NOT verify the rule for the second tool. Checking only that the
      field name appears somewhere in `tool_definitions.json` is not
      sufficient and is the specific mistake this criterion exists to
      prevent.
   c. Every `input.extensions.subject.<x>` (or any other
      `input.extensions.*`) must appear in `system_vars.json` or in
      `architecture.md`'s Trust Boundaries table, spelled exactly as the
      key spells it — if the key is `roles`, the field is
      `subject.roles`, never `subject.role`. Do not singularize,
      pluralize, or otherwise rename a declared key.
   d. Where the declared input enumerates a field's permitted values,
      the values the rule depends on must appear in THAT tool's own
      enumeration. Value domains are declared in two places: a
      parameter's `input_schema` enum, and the tool's `description`
      text, which for list-valued parameters often names the permitted
      members ("Available fields: …") and for string parameters often
      names the permitted options. Read both. A rule whose trigger
      values are absent from the governed tool's domain is vacuous on
      that tool even though the field name exists — it can never fire,
      and it generates test cases that can never be satisfied. Narrow
      it to the tools whose domain actually contains those values, per
      the remedy below.

   e. If the rule's ALLOW path depends on the tool acting on an
      argument — that is, the rule permits the call *because* a
      protective flag is set — confirm from `architecture.md` that the
      tool actually acts on it. `architecture.md` is Step A's reading of
      the server implementation and is this step's only sanctioned view
      of it; do not open the server source here. If `architecture.md`
      does not say either way, treat the argument as unverified: note
      the gap for the reviewer rather than assuming the tool honours
      it. A parameter the tool accepts and then
      only echoes back, logs, or ignores is **inert**: permitting a call
      because the flag is set grants a false assurance, because the call
      behaves identically whether it is set or not. Deny-path rules are
      unaffected: when OPA denies on a flag, the block itself is the
      enforcement and what the tool would have done is irrelevant. The
      asymmetry is the whole point — the same boolean can be sound to
      deny on and worthless to permit on.

      Worked example: `email_compensation_report` declares
      `encryption_required: bool = True`, and the implementation only
      interpolates it into its response string — nothing is encrypted.
      A rule blocking the call when the flag is explicitly `false` looks
      enforceable and passes every check above, yet the permitted call
      sends exactly the same unencrypted data. Contrast
      `external_sharing` on the same tool, equally un-acted-upon: a rule
      denying when it is `true` is sound, because the denial stops the
      call outright.

      Where a permit depends on an inert argument, write no rule.
      Record it in the gap register (STEP 4) as a tool-implementation
      item — the control is real and wanted, it just cannot come from
      OPA until the tool honours the flag.

   A rule that checks a field that does not exist at invocation time,
   or a value that tool can never carry, cannot be enforced.

   Worked example — one rule, two governed tools, one verdict each:

   | Rule | Governed tool | Field | On that tool's `parameters`? | Verified? |
   |---|---|---|---|---|
   | Managers may only view or export compensation data for their own team | `view_team_compensation` | `input.args.department` | yes | Yes |
   | (same rule) | `export_compensation_data` | `input.args.department` | no | No |

   The rule verifies for `view_team_compensation` only. Per the remedy
   below it is narrowed to that tool rather than kept whole — keeping it
   whole would produce a policy rule whose body can never evaluate.

   Worked example for 1d — the field exists on both tools, but only one
   tool's value domain contains the values the rule cares about:

   | Rule | Governed tool | Field | Field on tool? | Trigger value in that tool's domain? | Verified? |
   |---|---|---|---|---|---|
   | Exclude `ssn` from any `select_fields` selection | `view_team_compensation` | `input.args.select_fields` | yes | yes — its description lists `ssn` among available fields | Yes |
   | (same rule) | `export_compensation_data` | `input.args.select_fields` | yes | no — its description lists only `employee_id, name, title, level, current_salary, total_comp_2024, performance_rating` | No |

   Field existence alone would have passed both. The rule is narrowed to
   `view_team_compensation`.

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

   The linkage must also be the rule's actual justification, not merely
   a citation attached to it. Read the reason the rule gives for
   existing: if that reason argues from another rule rather than from a
   threat — "matching the limits already applied to the same roles",
   "by analogy with", "for consistency with rule N", "the same
   treatment as" — then the rule's basis is symmetry with existing
   policy, not risk, and the linkage fails no matter which threat
   instance is cited alongside it. Symmetry is not a threat: two
   operations that look alike can carry opposite risk (a spend and a
   refund both move money, and capping the second protects nothing).
   Either restate the rule's justification as the threat it actually
   mitigates, or drop it. Do not add a threat instance to
   `threat_model.md` for the purpose of satisfying this check.
4. **Questionnaire-sourced values.** If a rule's value set was pulled
   from a questionnaire answer, that answer must not be tagged
   `[inferred — low confidence]`. If it is, either drop the rule or
   mark the value set as `TBD — requires human confirmation` and treat
   the rule as pending rather than active.

Any rule that fails verification: fix the citation, **narrow the rule to
only the governed tools where it verifies**, or remove it from
`owasp_policy_guidelines.md`. Narrowing is the right remedy whenever
criterion 1b splits a rule — a rule enforceable for some of its governed
tools should be kept for those tools and dropped for the rest, not
discarded whole and not kept whole. Record which tools were dropped and
why. Log a one-line result (e.g. `Citations verified: 9/9`,
`Citations verified: 7/9 — 2 rules dropped for missing fields`, or
`Citations verified: 9/9 — 1 rule narrowed to 1 of 2 governed tools`).

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
visible at invocation time as `input.name`/`input.args.*`/
`input.extensions.*`?). Keep only the answers that pass. Skip any answer
tagged `[inferred — low confidence]` — those are not eligible to become
candidate rules on their own (STEP 6b already applied this to Source 1).
An answer that fails the boundary test is out of OPA scope for the same
reason it would be in STEP 2 — note it in the gap register (STEP 4)
instead if it isn't there already.

Then apply STEP 6b criterion 1 to every surviving Source 2 candidate,
exactly as it is applied to Source 1: resolve the governed tool(s)
against `tool_definitions.json`, and verify each needed
`input.args.<x>` against that tool's own `parameters` array and each
subject field against `system_vars.json`. Questionnaire answers state
policy *intent* and are written without reference to the tool list, so
they are the likeliest source of a rule about a capability this server
does not have — an answer constraining who may reset a password, when no
password tool exists, is not a candidate at all. Drop any candidate that
names an undeclared tool or field and log the reason; narrow it per the
STEP 6b remedy if only some of its governed tools verify. Do not carry
an unverified Source 2 candidate into STEP 8.

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
an existing rule in `guidance.txt` already covers the same condition on
the same field. `guidance.txt` may express its rules in different
shapes across bundled examples — flat numbered lines (e.g.
RagChatbot's `1. ...`, `2. ...` style, or bare one-per-line rules in
hr-agent style), bulleted lists nested under `#`/`##` section headers
(call-for-papers, car-price, employee style), or paragraphs of prose
that state a rule. Treat every such statement as an existing rule for
the coverage check regardless of formatting; the format never protects
a candidate from being marked "covered" if the substance matches.

**Subsumption test — apply this BEFORE the three criteria below.** A
candidate is also covered when an existing rule already denies the whole
tool, or a strictly broader condition on that tool, for the same
subject population the candidate targets. The three criteria below test
for an *equivalent* rule; they cannot see a *broader* one, because a
broader rule usually constrains a different field. A narrower condition
on a tool that is already fully denied can never fire.

Worked example: an existing rule says employees cannot export
compensation data at all (a deny on `export_compensation_data` keyed on
role). A candidate says employees may not request `export_type`
`"detailed"` on that tool. The fields differ — role versus
`export_type` — so all three criteria below report "not covered," yet
the candidate is unreachable for every caller it applies to. It is
covered by subsumption; do not write it. Record it in the scratch table
as covered, naming the subsuming rule.

Where subsumption does not apply, a candidate counts as covered only
when an existing rule matches the candidate on ALL THREE of the
following:

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

| Candidate | Verified (tool, field) | Field | Operator | Value set | Matching guidance.txt rule # | Covered? |
|---|---|---|---|---|---|---|
| <one-line candidate> | <tool>.<param> / subject.<key> | <input.*> | <exact / substring / ...> | <values> | <rule # or "—"> | Yes / No |

The "Verified (tool, field)" column carries forward the STEP 6b
criterion 1 result for that candidate — the governed tool(s) it survived
verification for, and the declared field on each. Before writing any
line to `guidance_updated.txt`, confirm it has an entry in that column:
**do not write a candidate whose `(tool, field)` set failed
verification**, and where a candidate was narrowed, write only the
narrowed form. A line with no verified `(tool, field)` is a claim about
a capability the MCP server does not declare, and merging it would push
that claim into test generation and policy creation.

**Reducibility gate.** Every line about to be written must be
expressible as a single decision: *field · operator · value · deny on
match*. State that quadruple for the line before writing it. If the
line cannot be reduced to one, it is not a rule, and it does not go in
`guidance_updated.txt` no matter how sound it is:

- A requirement to **record, log, audit, or report** something is not a
  decision — OPA returns allow/deny and writes nothing. It is an
  Agent-layer or infrastructure concern and belongs in the gap register
  (STEP 4).
- A statement that **defines a term, equates two values, or says how
  other rules should be interpreted** ("treat X and Y as the same
  role", "evaluate a caller with several roles against all of them") is
  not a decision either. It constrains no single call. Its home is the
  Input Schema / Known values section of `owasp_policy_guidelines.md`,
  where the policy author will read it while encoding the rules it
  qualifies.
- A **recommendation to review, monitor, or flag** something for human
  attention is not a deny. Either state the deny it implies, or put it
  in the gap register.

This restates the gap-register prohibition further down as a test
applied per line, because the prohibition on its own has proven easy to
satisfy in the abstract and skip in practice. Log each rejected line
with which of the three shapes above it matched and where it was sent
instead.

Do NOT include this scratch table in `guidance_updated.txt`; log it
alongside the STEP 9 summary.

For every missing candidate, write a new `guidance.txt`-style line:
- Continue the existing numbering in `guidance.txt`; do not renumber
  existing rules
- Phrase it as a plain-English guidance rule, not as OPA/Rego syntax
- Do NOT append source tags, violation codes, or questionnaire
  references inside `guidance_updated.txt` itself (no `[ASI04 /
  VIOLATION_CODE]`, no `[from questionnaire Q12]`, no similar
  suffixes). The file must mirror `guidance.txt`'s own flat
  natural-language style so it can be merged in unchanged. Per-rule
  traceability from each new line back to its ASI category and
  violation code already lives in `owasp_policy_guidelines.md`'s
  "Policy Rules (OPA scope only)" section and STEP 7's candidate
  list; do not duplicate it into this file.

**Do NOT carry the Gap Register into `guidance_updated.txt`.** Every
row in STEP 4's gap register is by definition not OPA-enforceable
(Agent-layer, tool-implementation, or infra-owned). If those items
were appended to `guidance_updated.txt` and then merged into
`guidance.txt` under Step E, downstream stages would ingest them as
if they were enforceable policy rules — `smith --flag test_generation`
decomposes each numbered rule into legitimate + adversarial test cases,
and the policy creation skill maps each rule to a `deny` block. Both
would misfire on a natural-language note that doesn't reduce to a
structured-field check.

The gap register's durable home is the Gap Register table in
`owasp_policy_guidelines.md` — this document already writes every row
there with its ASI category, layer, and recommended action, and STEP 9
below surfaces the same table for the reviewer. Nothing from the OWASP
analysis is dropped; it just doesn't ride along in a file whose only
consumer is Rego generation.

Write `<TARGET_AGENT_PATH>/smith/guidance_updated.txt` containing ONLY
the newly proposed rules — the missing candidates STEP 8 identified
above. Do NOT copy the existing `guidance.txt` rules into this file;
do NOT append natural-language notes about OWASP findings (those live
in `owasp_policy_guidelines.md`'s Gap Register table, not here). The
file is the addendum that Step E appends to `guidance.txt`; it is not
a replacement.

**The file has exactly one permitted format. Do not choose a shape, do
not match `guidance.txt`'s style, do not adapt to the target agent.**
Every run of every target agent writes `guidance_updated.txt` in this
one form:

```
<N+1>. <rule text on a single line>
<N+2>. <rule text on a single line>
```

- One rule per line, each line beginning `<number>. ` and nothing else.
- `N` is the highest rule number already in `guidance.txt`. If
  `guidance.txt` has no numbered lines, `N` is the count of its
  rule-bearing lines. If `guidance.txt` does not exist, `N` is 0.
- **No headers.** Never write `#`, `##`, or any heading line — not
  `## Additional Rules from Security Analysis`, not any variant.
- **No comments.** Never write `<!-- ... -->`, `#`-prefixed notes, or
  any other comment syntax. The file is consumed as plain text and has
  no comment convention; a comment becomes guidance content.
- **No prose, blank-line sections, titles, dates, provenance lines, or
  "see also" pointers to other artifacts.**
- Nothing before the first rule line and nothing after the last.

This format is fixed because the file is machine-consumed, not read:
`decompose` opens the merged `guidance.txt` with a single `f.read()`
and hands the whole blob to the Guidance Flattening Agent, whose job is
explicitly to promote headings and sub-items into numbered guidance
statements. A header you add to make the append "read naturally"
therefore does not stay decoration — it is flattened into a rule, and
policy creation then tries to map it to a `deny` block. Visual
consistency with `guidance.txt` is not a goal; there is no human in
this file's consumption path.

**When there are no new rules to propose.** This is a normal, common
outcome: `guidance.txt` already covers every OPA-enforceable candidate
STEP 7 produced. Handle it as follows.

- **Do not create `guidance_updated.txt`. If one is already on disk,
  delete it.** No file at all — not a 0-byte file, not a blank line, not
  whitespace. The file's *presence* is what signals that proposed rules
  are waiting to be merged, so its absence is how "nothing to add" is
  expressed. Delete it only after the prior-run capture below has logged
  what the old file contained.
- **The invariant this maintains:** `guidance_updated.txt` exists if and
  only if there are unmerged proposed rules. A run that proposes nothing
  leaves no file; Step E deletes the file once it has merged it. Anyone —
  human or later step — can therefore read the presence of the file as
  "there is a pending proposal" without opening it.
- **There are no exceptions to this, for any target agent.** The empty
  outcome does not vary with `guidance.txt`'s format. Whatever
  `guidance.txt` looks like — flat-numbered, bare-line, or prose with
  `#`/`##` headers and blockquotes — "no new rules" is expressed the same
  way: no file. Specifically, do NOT write any of the following:
  - a heading such as `## Additional Rules from Security Analysis`,
    with or without content under it;
  - an HTML comment such as `<!-- No new rules proposed -->`, or any
    other comment syntax;
  - a plain-prose status line such as "No new rules were proposed" or
    "existing guidance already covers all candidates";
  - a coverage summary, gap-register row, or rule-to-candidate mapping;
  - a "see also" or "refer to `owasp_policy_guidelines.md`" pointer;
  - a copy of rules that are already in `guidance.txt`.
  If you have written any of these, delete the file — do not truncate it
  to 0 bytes and leave it behind, because a present-but-empty file still
  reads as a pending proposal.
- **Why there is no comment or heading escape hatch.** `decompose` reads
  the guidance with a single `f.read()` and passes the entire file to the
  LLM as one blob. There is no line parsing, no `#` or `<!-- -->` comment
  convention, and no filtering anywhere in the pipeline. The Guidance
  Flattening Agent it feeds is specifically built to promote headings and
  sub-items into numbered guidance statements, so a heading is not
  ignored — it is converted into a rule. Every non-empty byte you leave
  in this file becomes guidance that the decomposer expands into test
  conditions and that policy creation tries to map to a `deny` block.
  "Visually contained" is not a property the consumer has any way to
  observe.
- **Report the finding in STEP 9, not in the file.** "None —
  `guidance.txt` already covers every OWASP-derived and
  questionnaire-derived candidate", together with which existing rules
  cover which candidates, is human-review output. The reviewer sees it
  in your STEP 9 summary; `guidance_updated.txt` is consumed by Rego and
  test generation, which have no use for it.

The failure mode this prevents: a run that finds nothing to add, then
writes its reasoning trail — coverage mapping, gap register, tooling
notes — into the addendum instead of reporting it. Step E appends all of
it to `guidance.txt`, and every later stage reads that prose as policy
rules.

**Mandatory write check — run this before writing, every run, and do
not treat it as optional judgement.** Assemble the candidate lines you
intend to write, then apply these four tests in order and act on them
mechanically:

1. **Drop already-covered rules.** For each line, check whether
   `guidance.txt` already expresses that rule. If it does, delete the
   line. This is a semantic check, not a string comparison — a
   reworded restatement of an existing rule is still already covered.
   Never emit a line that restates, paraphrases, or verbatim copies
   something already in `guidance.txt`; the file is a delta, and a
   partial copy of the parent file is always a bug.
2. **Drop every non-rule line.** Delete anything that is not a single
   enforceable rule: headings, comments, blank-line separators, titles,
   status messages, coverage notes, pointers to other artifacts.
3. **If nothing survives 1-2, write no file and stop here** — and delete
   any `guidance_updated.txt` left over from a previous run. Do not
   substitute a status message for the empty result, do not write a
   0-byte file to have something on disk, and do not fall back to
   emitting the covered rules you dropped in test 1 "so the file isn't
   empty". No file is the correct, expected, common answer.
4. **If lines survive, verify the written file against the one permitted
   format.** Read it back and confirm: every line matches
   `^<digits>\. `, the first number is `N+1`, numbering is contiguous,
   and the file contains no `#`, no `<!--`, and no blank lines. If any
   check fails, rewrite the file — do not merge and do not proceed.

This check is what makes the output deterministic across runs and across
target agents. Two runs that reach the same conclusion must produce
byte-identical files; the shape of the output must never depend on which
example you are analysing or on how you decided to phrase things this
time.

**Why the file is an addendum, not a replacement.** `guidance.txt` may
contain more than numbered rules — headings, blank lines, comments,
paragraphs of context authored by the human. Overwriting it would
discard that content. Step E instead appends `guidance_updated.txt` to
`guidance.txt`, preserving every byte of the original file and adding
only the new numbered rules after it. Test generation and policy
creation still see a flat numbered-rule list because the append is
line-oriented and the new rules follow the same numbered format.

When there ARE rules to propose, overwrite `guidance_updated.txt` in full
rather than appending to a prior run's file — this keeps it consistent
with the current threat model and questionnaire instead of accumulating
stale entries from earlier iterations. When there are none, delete it per
the rules above. Either way the previous run's file does not survive this
step.

**Before overwriting or deleting, read the existing
`guidance_updated.txt` if one is present and log its numbered rules
verbatim.** They are the previous run's proposal and this step is the only
thing that destroys them — STEP 8c compares against this captured copy,
and once the overwrite or delete has happened there is nothing left on
disk to compare against. This applies equally to the delete path: a run
that proposes nothing still has to capture what the last run proposed,
otherwise deleting the file silently discards the only evidence a rule was
ever dropped.

Log exactly one of these states, so STEP 8c can tell them apart:

- **`prior proposal: <N> rules`** — a non-empty file was present.
  Capture the rules verbatim.
- **`prior proposal: none (no file)`** — no file on disk. This is a
  normal state, not a fault, and it is the common one: Step D has never
  run for this target agent, or the last run proposed nothing, or Step E
  merged the last proposal and deleted the file. Do not report it as a
  lost capture or an error, and do not treat it as evidence that
  something went wrong.
- **`prior proposal: empty (legacy 0-byte file)`** — a 0-byte file was
  present. Runs under the current rules never produce this; it is left
  over from a run that wrote an empty file instead of deleting it. There
  is nothing to capture. Delete the file as part of this step whichever
  path you take, so the leftover stops reading as a pending proposal.

In the last two cases there are no prior rules to regress against, so
STEP 8c has nothing to compare. If you need to know whether a merge
happened, look at `guidance.txt` — merged rules are there. They are not
missing; they succeeded.

Absence carries less information under this scheme than a 0-byte file
would have: "proposed nothing" and "already merged" and "never ran" all
look identical on disk. That is deliberate — the file is a work queue for
Step E, not a run log. The durable record of what each run concluded is
`owasp_policy_guidelines.md` and your STEP 9 summary, so state the
"no new rules" outcome there rather than trying to encode it in the
filesystem.

Do NOT modify `guidance.txt` or `policy_guidance_questionnaire.md`
themselves. `guidance_updated.txt` is a proposal for the human to review
and merge in manually.

---

#### STEP 8b — Redundancy self-check on `guidance_updated.txt`

STEP 8 checks whether every new candidate is already covered by an
existing `guidance.txt` rule — one direction only. It does NOT catch
overlap between two *existing* rules, or between two newly appended
rules, or an existing rule and a newly appended one that STEP 8 marked
as "not covered" for a reason that later turns out to be phrasing-only.
This step closes that gap using the same three-criteria test STEP 8
already applies.

Under STEP 8's revised semantics, `guidance_updated.txt` holds only
the newly proposed rules — so the redundancy check must scan the
*post-merge* state, i.e., `guidance.txt`'s existing rules 1..N
followed by `guidance_updated.txt`'s new rules N+1..M as they would
appear after Step E's append. Read both files, concatenate the
numbered-rule content in that order, and compare each pair (i, j)
with i < j against the three criteria from STEP 8:

1. **Same structured field.** The `input.*` path the two rules
   ultimately constrain must be the same (e.g., both talk about
   `input.args.select_fields` on the same tool set, or both talk
   about `input.extensions.subject.roles`).
2. **Same operator / matching semantics.** Exact-equality, substring,
   numeric threshold, set-membership, and regex are distinct;
   allow-polarity vs deny-polarity are distinct.
3. **Overlapping value set.** For value-based conditions the two
   rules' allowed/blocked sets must overlap on the value that would
   trigger the rule.

If all three match, the pair is an **Overlap** candidate.

The same pairwise scan produces two further verdicts. Both are cheap
because the pairs are already enumerated, and neither is an overlap, so
the three-criteria test above would report nothing for them:

- **Conflict.** The two rules constrain the same field on the same
  tool but prescribe incompatible outcomes — block versus flag-for-
  review, deny versus allow, or two different numeric thresholds on the
  same value with no scoping to tell them apart. Criterion 2 treats
  opposite polarities as *distinct*, which is right for coverage and
  wrong here: distinctness is exactly what makes them a conflict. A
  conflicting pair must be resolved before Step E merges, because the
  policy author will otherwise pick one arbitrarily and the other rule
  becomes silently dead. Two rules that both appeared in this run's
  candidate list can conflict with each other, so scan new-vs-new pairs
  as well as new-vs-existing.
- **Correction.** The candidate constrains the same field as an existing
  rule with a value set that *diverges* from it. Split by the kind of
  divergence, because only one kind can be expressed by appending:

  - *Additive* — the candidate adds values and removes none, and
    narrows no scope. Write it as a plain rule stating only the
    additional values. The existing rule stays, the union is correct,
    and nothing needs to reference anything. Do NOT write "in addition
    to X and Y" or name the rule being extended: rule numbers are not
    stable across runs (`guidance.txt` is appended to and renumbered),
    and the cross-reference buys nothing the union does not already
    give.
  - *Contradictory* — the candidate requires a value to be **removed**
    from the existing rule's set, or its scope **narrowed** to fewer
    tools. This cannot be written as an appended line at all.
    Appending never removes: both lines end up in `guidance.txt` as
    independent numbered rules, and per this document's own note on
    downstream consumers, `test_generation` will decompose both and
    policy creation will emit a `deny` block for both — so the value
    the candidate meant to retire stays enforced and the two rules
    contradict each other permanently. A line that opens "Correcting
    rule N" is the clearest instance of this failure: it reads as a
    fix and functions as a conflict.

  For a contradictory divergence, write **no** guidance line. Record it
  as a proposed edit to the existing numbered rule and surface it in
  STEP 9 for the human to apply by hand: name the rule, state the full
  replacement value set and scope, and say what is being removed and
  why. Where a removed value was found not to exist at all —
  `architecture.md` records fields no tool declares — cite that.
  Step D never edits `guidance.txt`, so a correction is always a
  recommendation, never an output line.

Record all three verdicts in one table:

| Rule i | Rule j | Verdict | Field | Operator | Value set relationship |
|---|---|---|---|---|---|
| <rule-i text> | <rule-j text> | Overlap / Conflict / Correction | <input.*> | <exact / substring / …> | <overlap, or what diverges> |

For an **Overlap** or a **Conflict**, do NOT auto-merge and do NOT
rewrite either rule. Which wording to keep, whether to broaden one to
absorb the other, and which side of a conflict wins are semantic calls
the human makes during STEP 9 — the skill's job here is only to surface
the pair before the merge into `guidance.txt` happens, so the
duplication doesn't have to be caught downstream at the Rego layer by
`policy_duplication.md` / `duplication_suggestion` (which operate on
the compiled policy, not on guidance).

A **Correction** is the one verdict that changes what gets written, and
in only one direction: an *additive* divergence is written as a plain
rule carrying just the new values, and a *contradictory* one is written
nowhere — it leaves `guidance_updated.txt` entirely and becomes a
proposed edit in STEP 9. Never rewrite the existing `guidance.txt` rule
here; Step D does not edit that file.

Log the resulting table for STEP 9. If no pair yields any of the three
verdicts, log a one-line result (`Redundancy self-check: no overlapping,
conflicting, or correcting pairs found`) so the human can see the check
ran.

Cost note: this is an O(N²) pairwise scan across `guidance_updated.txt`;
for a typical file of 20-40 rules that is trivial. Per STEP 8,
`guidance_updated.txt` contains numbered rules only, so every row in
the scan has a structured-field check to compare — no exempt-notes
carve-out is needed here.

---

#### STEP 8c — Regression check against the previous run

STEP 8 overwrites `guidance_updated.txt` in full on every run, by
design, so the file stays consistent with the current threat model
instead of accumulating stale entries. The cost of that is real: a
control this workflow proposed on an earlier run can silently fail to
reappear, because nothing compares the two runs. Every other check in
this document asks "is this candidate sound?" — none asks "is anything
the last run found now missing?" A control can be correct, verified,
and quietly gone.

Use the previous run's rules **as captured in STEP 8 immediately before
the overwrite** — not the file on disk, which by this point holds this
run's output and would compare the run against itself, reporting every
rule as still-proposed and detecting nothing. For each captured rule,
decide which of these applies:

1. **Still proposed** — a candidate in this run covers the same field
   and condition. Nothing to report.
2. **Merged** — the rule is now present in `guidance.txt`, because the
   human ran Step E since the last run. Nothing to report; it is no
   longer a candidate precisely because it succeeded.
3. **Deliberately dropped** — this run's checks rejected it. Report it
   with the check that rejected it (criterion 1b/1d/1e, subsumption,
   reducibility, justification). This is the healthy case and the
   reviewer should still see it.
4. **Unexplained** — none of the above. It simply is not in this run's
   candidate list and no check rejected it. Report it as a regression.

Case 4 is the one this step exists for. Do not re-add the rule
automatically: the threat model may have legitimately changed, and
silently resurrecting a candidate would defeat the point of rebuilding
the file from the current analysis. Present it to the human in STEP 9
with its text and the run it came from, and let them decide whether it
belongs.

Record the result as:

| Prior rule | Status | Explanation |
|---|---|---|
| <rule text from the previous run> | Still proposed / Merged / Dropped / **Regression** | <covering candidate, or rejecting check, or "unexplained"> |

Report according to what STEP 8 logged:

- `prior proposal: <N> rules` — run the comparison above and record the
  table.
- `prior proposal: none (no file)` — log `Regression check: no prior
  proposal on disk (first run for this agent, or the last run proposed
  nothing, or the last proposal was merged and deleted)`. This is not a
  missing-file fault and must not be reported as one. It is the expected
  state most of the time.
- `prior proposal: empty (legacy 0-byte file)` — log `Regression check:
  prior proposal was an empty legacy file, nothing to regress against`.
- STEP 8 logged nothing either way — say exactly that. It is a skipped
  capture, which is a real gap in the check, and it must not be reported
  as any of the states above. Note the trap: under the current rules
  "no file on disk" is normal and common, so a genuinely skipped capture
  looks exactly like the normal case unless STEP 8 logged the state
  explicitly. The log line is the only thing that distinguishes them —
  never infer `none (no file)` from the absence of a log entry.

Log one of these even when there is nothing to compare, so the human can
see the check ran rather than silently passing.

---

#### STEP 8d — Non-rule content gate on `guidance_updated.txt`

STEP 8 states the prohibition ("Do NOT carry the Gap Register into
`guidance_updated.txt`"; "do NOT append natural-language notes about
OWASP findings"). STEP 8b checks redundancy and STEP 8c checks
regressions, but nothing re-reads the written file to confirm the
prohibition actually held. A run that drafts a "Blind Spot Register",
"Known Limitations", or similar section into the addendum therefore
passes every existing check, and Step E then merges it into
`guidance.txt` verbatim. This step closes that hole.

**Re-read the `guidance_updated.txt` you just wrote** — do not check
your draft from memory, check the bytes on disk. If STEP 8 correctly
wrote no file because it proposed nothing, confirm that on disk too
(check 6 below) rather than skipping this step. Reject the file if any
of the following is true:

1. **A markdown table is present.** Rules are numbered lines or
   bullets. A pipe table (`|---|`) in this file is a gap register, a
   limitations matrix, or a mitigation index — none of which are rules.
2. **A heading matches non-rule content**, case-insensitively: `blind
   spot`, `gap register`, `known limitation`, `not enforceable`,
   `non-enforceable`, `out of scope`, `future work`, `blast radius`,
   `mitigation`.
3. **Any line asserts that something cannot be enforced** — "cannot be
   enforced", "is a blind spot", "not OPA-enforceable", "requires a
   database lookup", "absent by design", "requires wall clock". The
   addendum states what the policy MUST do; a statement about what it
   cannot do belongs in the Gap Register.
4. **A variable is named that is absent from `system_vars.json` and
   from every tool's declared arguments** — e.g. a recommended
   `current_date`, `blacklist`, or `request_owner_id`. Proposing new
   input fields is the Gap Register's job; a rule here that references
   one would push policy creation toward a phantom variable, which
   `../policy_creation/opa_policy_creation.md` forbids.
5. **A cross-reference points outside the file** — "below", "above",
   "see the gap register", "as documented in the table". After Step E's
   append these resolve to nothing, or worse, to unrelated text.
6. **STEP 8 proposed no new rules, but a `guidance_updated.txt` exists**
   — per STEP 8's "When there are no new rules to propose", there must be
   no file at all, with no exception for any `guidance.txt` format. This
   check fails on a 0-byte file just as it fails on one holding a
   heading, an HTML comment, a status line, a coverage mapping, or a
   gap-register note: the non-empty variants get appended into
   `guidance.txt` and read as rules, and the empty variant misreports
   itself to Step E and the next human as a pending proposal. Delete the
   file. Conversely, if STEP 8 *did* propose rules, a missing or empty
   file is a lost write — re-run STEP 8 rather than passing the gate.
   Note that this check cannot be skipped just because there is no file
   to re-read: "no file" is the passing state here, so confirm it
   deliberately rather than treating the whole of STEP 8d as
   inapplicable.
7. **The file violates the one permitted format.** Every non-empty line
   must match `^<digits>\. ` — one rule per line, numbering contiguous
   and starting at `N+1` where `N` is `guidance.txt`'s last rule number.
   Reject any `#`/`##` heading (including `## Additional Rules from
   Security Analysis`), any `<!-- ... -->` comment, any blank line, any
   bullet, and any prose line without a leading number. There is no
   "matches the target agent's style" defence: the format is fixed
   across every target agent precisely so the output does not vary
   run-to-run.
8. **A line duplicates a rule already in `guidance.txt`.** Compare each
   line against the existing guidance semantically, not textually. This
   file is a delta; a line that restates or copies an existing rule is a
   defect even though it looks like valid rule text, and appending it
   gives `guidance.txt` two numberings of the same rule. If every line
   is a duplicate, there should be no file — delete it.

On any hit: delete the offending section or line from
`guidance_updated.txt`, confirm the content it carried is present in
`owasp_policy_guidelines.md`'s Gap Register table (add the row if it is
not — nothing may be dropped, only relocated), then re-run this check
against the rewritten file. Do not proceed to STEP 9 until it passes. If
the cleanup leaves no rule lines at all, delete the file rather than
leaving an empty one behind.

Report the outcome in STEP 9 as `Non-rule content gate: passed` or
`Non-rule content gate: N section(s) removed and relocated to the Gap
Register`, naming each one. A silent pass and a pass after cleanup must
not look the same to the reviewer.

---

#### STEP 9 — Human review

Present the summary table, the list of violation codes, the STEP 7
candidate list (with source tags), the list of newly proposed guidance
rules from STEP 8 (or "none — guidance.txt already covers every
OWASP-derived and questionnaire-derived candidate" / "none — no
guidance.txt found, all candidates written fresh"), the gap register
items recorded in `owasp_policy_guidelines.md`'s Gap Register table
(or "none — gap register is empty") — note that these are NOT
appended to `guidance_updated.txt`, so if the reviewer wants any of
them enforced they will need to be reformulated as OPA-enforceable
rules and added to `guidance.txt` manually, and the STEP 8b redundancy
self-check result (either the table for the human to reconcile, or
"Redundancy self-check: no overlapping, conflicting, or correcting pairs
found").

Call out explicitly, rather than leaving the reviewer to find them in
the tables:
- Any **Conflict** pair from STEP 8b. These must be resolved before
  Step E merges, so name them and say which rules disagree.
- Any candidate rejected by STEP 8's **reducibility gate**, and where it
  was sent instead (gap register, or the Input Schema / Known values
  section). A reviewer expecting a control to be enforced should learn
  here that it became a monitoring item.
- Any **regression** from STEP 8c — a rule the previous run proposed that
  this run neither proposes nor explains. Name each one and say it was
  not re-added automatically, so the human can decide. A control that
  disappears without a stated reason is the failure mode this whole
  workflow is least able to notice on its own.
- Any **proposed edit to an existing `guidance.txt` rule** from STEP 8b's
  contradictory-Correction path, as a numbered list the human can work
  through: the rule number, its full replacement text, and what is being
  removed and why. These are the only findings in the whole workflow that
  cannot be delivered by appending, so they are the easiest to lose —
  present them as work the human still has to do, not as something the
  run already handled.
- Any rule **narrowed** by STEP 6b criterion 1 — which governed tools it
  was narrowed to and which were dropped, and whether the drop was for a
  missing field (1b) or a value outside that tool's domain (1d). This is
  the reviewer's only chance to notice that a control they expected to
  cover two tools now covers one.

Log these, then hand control back to the top-level workflow, which
decides (per confirmation mode) whether to proceed to Completion. This
workflow ends at Completion; downstream policy authoring is out of
scope here.
