## Enforcement Mapping

Maps threat instances and confirmed questionnaire intent to their enforcement
layer, writes `owasp_policy_guidelines.md`, and proposes only missing,
OPA-enforceable rules in `guidance_updated.txt`.

### Phase inputs and outputs

The envelope's Shared Phase Contract applies. In particular, STEP 8 requires
`<GUIDANCE_FILE>` to be either a resolved path or explicitly `ABSENT`.

- `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`
- `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/threat_model.md`
- `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/policy_guidance_questionnaire.md`
- `src/smith/data/owasp_10_ai_catalog.json`
- `<TARGET_AGENT_PATH>/smith/tool_definitions.json` — required, authoritative
  per-tool source for `input.args.*`; if absent, run
  `smith --flag get_mcp_parameter`.
- `<SYSTEM_VAR_FILE>` — authoritative schema for runtime-provided
  `input.extensions.subject.*`; if absent, use architecture.md's Runtime
  Subject Context table and record the gap.
- `<GUIDANCE_FILE>` — optional existing policy intent.

Outputs:

- `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/owasp_policy_guidelines.md`
- `<GUIDANCE_UPDATE_FILE>` — a pending-rule addendum beside
  `<GUIDANCE_FILE>`.

### OPA enforcement boundary

A control is in OPA scope only when the call is intercepted before execution,
the required data is structured at that point, and every condition uses
`input.name`, `input.args.*`, or `input.extensions.*`. LLM reasoning, prompt
content, return values, post-processing, external-service integrity, and
dependency trust are out of OPA scope; assign those findings to the agent,
tool implementation, or infrastructure.

### Workflow

#### STEP 1 — Load only required input sections

Do not reread every input in full:

- From `architecture.md`, load Run Context, Layers,
  Runtime Subject Context, Tool Arguments (especially Disposition), Enforcement
  Points, and Undeclared Fields.
- From `threat_model.md`, load Attack Surfaces, Evidence Index, Category
  Assessment, and Threat Instances. Do not load Scenario Coverage.
- From the questionnaire, load Answer Register rows Q9-Q19, Q21, and Q22 plus
  only the detail tables they reference. Load another answer only when a cited
  threat or candidate depends on it.
- From `tool_definitions.json`, make one query for only the tool/field pairs
  named by threat or questionnaire candidates. Populate `wanted` from those
  candidates:

  ```bash
  jq --argjson wanted '[{"tool":"<tool>","fields":["<field>"]}]' \
    '[.tools[] as $tool |
      ($wanted[] | select(.tool == $tool.name)) as $selection |
      {name: $tool.name,
       parameters: [$tool.parameters[] |
         select(.name as $name | $selection.fields | index($name))],
       input_schema: {properties: ($tool.input_schema.properties |
         with_entries(.key as $key |
           select($selection.fields | index($key))))}}]' \
    <TOOL_DEFINITIONS_FILE>
  ```
- From `<SYSTEM_VAR_FILE>`, load subject keys and types.
- From the OWASP catalog, query `id`, `name`, and `mitigations` only for ASIs
  represented by applicable Threat Instances or confirmed questionnaire
  candidates. Populate the JSON ID list from those inputs:

  ```bash
  jq --argjson ids '["ASI01", "ASI03"]' \
    '[.threats[] | select(.id as $id | $ids | index($id)) |
      {id, name, mitigations}]' \
    src/smith/data/owasp_10_ai_catalog.json
  ```

  Query the existing catalog in place; do not create a copied or split file.
- Defer `<GUIDANCE_FILE>` until STEP 8.

#### STEP 2 — Map each threat to an enforcement layer

For every applicable threat ID:

1. Name the structured field carrying its evidence, if any.
2. If a pre-execution deny can be decided solely from an allowed OPA input
   path, assign it to OPA.
3. Otherwise assign it to Agent, Tool implementation, or Infrastructure and
   state why OPA cannot enforce it.

Record that decision once:

| Threat ID | Field / surface | Owner | Reason |
|---|---|---|---|
| T01 | `input.args.<field>` / #N | OPA / Agent / Tool / Infrastructure | <one line> |

#### STEP 3 — Build the scoping table

Summarize one row per OWASP category, referencing threat IDs instead of
restating their descriptions:

| OWASP | Scope | OPA threat IDs | Other-layer threat IDs | Reason / owner |
|---|---|---|---|---|
| ASI01 | Yes / Partial / No | T01 | T02 | <one line> |

Use Partial only when the category has both OPA-enforceable and out-of-scope
instances.

#### STEP 4 — Build the gap register

Record every out-of-scope instance and every unresolved human decision needed
to interpret or classify a candidate. These rows never become guidance rules.

Always evaluate Q21 and its confidence marker. Unless a direct user answer or a
guidance-derived answer explicitly defines the required Hard-block versus
Soft-block behavior, add Q21 as a `Guidance (human decision)` gap. This includes
blank, low-confidence, and incomplete answers. Ask the human to define the
tiers and which controls use them; do not infer a warn-and-proceed behavior or
emit the decision in `<GUIDANCE_UPDATE_FILE>`.

| Finding ID | Layer | Recommended action |
|---|---|---|
| T02 | Agent / Tool impl / Infra | <one-line action> |
| Q21 | Guidance (human decision) | Define Hard- versus Soft-block behavior and which controls use each tier. |

#### STEP 5 — Derive OPA policy requirements

For each OPA-scoped threat, choose an enforceable mitigation from the matching
catalog entry and write a plain-English requirement containing:

- governed tool(s) and canonical field;
- deny condition and matching semantics;
- violation code;
- Hard block or Soft block severity.

Reuse a code listed in questionnaire Q22 when applicable. Otherwise mint a
code consistent with any existing scheme and include it in the output's code
reference. Write requirements, not Rego or implementation advice.

#### STEP 6 — Write `owasp_policy_guidelines.md`

Preserve this output structure:

```markdown
# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines
# Tool: <tool-name>

---

## Architecture Summary
<one-sentence layer and trust summary>

## Threat Disposition

| Threat ID | Field / surface | Owner | Reason |
|---|---|---|---|
| T01 | `input.args.<field>` / #N | OPA / Agent / Tool / Infrastructure | <one line> |

## OWASP Top 10 for Agentic AI Security — Scope Assessment

| OWASP | Scope | OPA threat IDs | Other-layer threat IDs | Reason / owner |
|---|---|---|---|---|
| ASI01 | In scope / Partial / Out | T01 | T02 | <one line> |

Categories flowing into the OPA policy: <list>

---

## Gap Register

| Finding ID | Layer | Recommended action |
|---|---|---|
| T02 | Agent / Tool impl / Infra | <one-line action> |
| Q21 | Guidance (human decision) | Define Hard- versus Soft-block behavior and which controls use each tier. |

---

## Policy Rules (OPA scope only)

### Input Schema
| Field | Source |
|---|---|
| ... | ... |

### Known values
<sets, enums, or term lists used by rules>

### Rules

| Code | OWASP | Threat IDs | Severity | Tool(s) / field | Condition | Matching |
|---|---|---|---|---|---|---|
| <code> | <ASI> | <T IDs> | Hard / Soft | <tools and canonical path> | <plain-English deny condition> | exact / substring / regex / numeric / set |

## Candidate Reconciliation

| Candidate ID | Tool | Subject scope | Field expression | Operator | Values | Action | Sources | Related rule | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| C01 | <one tool> | <roles or all> | <canonical path(s)> | <canonical operator> | <normalized values> | deny | T01, Q13 | <rule or —> | <verdict> |
```

Use canonical OPA paths. Do not include Rego syntax, Rego built-ins, file
organization, helpers, or test-generation advice.

#### Validation matrix

Apply each row at the named stage and follow its Failure action; only rows that
explicitly say so block Step E.

| Stage | Check | Pass condition | Failure action |
|---|---|---|---|
| Candidate | Tool/field | Tool exists; argument belongs to that tool, or subject field exists and is OPA-visible before execution | Narrow tool scope or move to Gap Register |
| Candidate | Value domain | Trigger value is allowed by schema, enum, and description | Narrow or drop |
| Candidate | Argument behavior | Protective allow-path argument is `Acts on`; an OPA deny may enforce independently | Drop unsafe allow path |
| Candidate | Mitigation | Matching ASI mitigation supports the control | Drop |
| Candidate | Threat | Applicable threat ID supports the rule | Drop |
| Candidate | Confidence | Questionnaire source is not low-confidence | Require confirmation or drop |
| Reconciliation | Reducibility | Rule reduces to field, operator, value, and deny-on-match | Move to Gap Register |
| Reconciliation | Semantic coverage | No candidate or existing rule already denies every request this candidate would deny | Mark Duplicate/Covered; do not emit |
| Reconciliation | Relationship | Novel or Additive; no unresolved Overlap, Conflict, or Contradictory correction | Report and block Step E |
| Reconciliation | Prior proposal | Still proposed, merged, or deliberately dropped by a named check | Report regression and block Step E |
| On disk | Format | Numbered single-line rules only; contiguous required numbering | Correct once, then fail |
| On disk | Semantics | Declared, OPA-visible fields; uncovered and enforceable; no gap content | Correct once, then fail |
| On disk | Presence | Non-empty candidate set has a file; empty set has no file | Correct once, then fail |

#### STEP 6b — Verify every rule

Apply all Candidate rows in the matrix before STEP 7. Preserve exact field
spelling and validate each tool separately; a field existing on another tool
does not pass. Record narrowed/dropped tools and a one-line verification count.

#### STEP 7 — Build one candidate list

Combine and deduplicate:

- verified rules from STEP 6; and
- OPA-enforceable questionnaire answers from Q9-Q19, including Q13b, excluding
  low-confidence answers and fields or tools that fail STEP 6b.

Normalize once before comparing:

1. Expand a multi-tool proposal into one atomic candidate per tool. Keep fields
   together when they form one conjunctive condition; never split a condition
   into a broader rule.
2. Validate each atomic candidate against that tool. Remove impossible
   tool/field/value combinations rather than retaining values supported only by
   another tool. If tools have different behavior or value domains, keep
   separate rules.
3. Record one tuple in Candidate Reconciliation:
   `tool | subject scope | sorted field expression | canonical operator |
   normalized values | deny`. Canonical operators are `eq`, `neq`, `in`,
   `not_in`, `contains_any`, `lt`, `lte`, `gt`, `gte`, and
   `missing/null/empty`. Normalize value case only when matching is explicitly
   case-insensitive.
4. Group by tool, field expression, and action. Compare subject scopes by set
   inclusion (`all` contains every named role), then compare conditions using
   set inclusion, numeric intervals, Boolean equality, missing/null/empty
   states, and explicit domain predicates.
5. Deduplicate candidates against one another before reading guidance. Keep one
   tuple with every source ID; when one deny covers another, retain the one
   covering the larger request set.
6. Within an identical tool, subject scope, field expression, and action,
   replace multiple deny conditions with one simpler condition when their union
   is exactly equivalent and expressible with a canonical operator. Preserve
   every source ID. For example, the union of the conditions
   `eq manager` and `not_in {employee, manager}` is `neq employee`. Prove
   equivalence using the same value domain, case handling, and missing/null
   semantics; otherwise keep the
   candidates separate. Never union conditions across tools, subject scopes,
   field expressions, actions, or conjunctive field groups, and never broaden
   or narrow the denied request set merely to shorten wording.
7. Assign stable IDs (`C01`, `C02`, ...) after deduplication and exact union
   simplification.

For domain rules, an explicit allowlist complement such as
`destination.domain != ibm.com` subsumes a denylist containing only non-IBM
domains. Do not claim implication when domain parsing, case handling, subdomain
handling, or another matching semantic is unspecified; record an unresolved
overlap instead. Do not repeat source prose or read `<GUIDANCE_FILE>` yet.

#### STEP 8 — Reconcile with existing guidance and write the addendum

Read `<GUIDANCE_FILE>` once. Normalize each explicit existing rule into the same
tuple. Expand a general or multi-tool existing rule per tool only when
`tool_definitions.json` makes that mapping unambiguous; otherwise classify the
comparison as unresolved. Use the questionnaire's guidance-rule mapping and
architecture's canonical paths to resolve explicit natural-language aliases;
do not guess between multiple plausible fields or tools. Compare only within
matching tool/field/action groups and fill Candidate Reconciliation without
restating rule prose.

A candidate is Covered when an existing rule's subject scope contains the
candidate scope and every request denied by the candidate is already denied by
the existing rule. This includes a broader deny on the same field, not merely
identical wording. A candidate is a Clarification when it only makes an
existing decision more implementable without changing behavior; recommend
editing the existing rule and emit no addendum line.

Similar wording, category, or intent is insufficient. Before writing, reject
any candidate that lacks a verified tool/field or cannot reduce to
`field · operator · value · deny on match`. Put monitoring, logging,
definitions, cross-rule interpretation, and other non-decisions in the Gap
Register or Input Schema/Known values as appropriate.

Never write a candidate described anywhere in the analysis as unenforceable,
not OPA-visible, pending runtime integration, or dependent on a counter that is
not updated before evaluation. Such a candidate belongs in the Gap Register.

Before replacing any existing addendum, capture its numbered rules and log one
of: `prior proposal: <N> rules`, `prior proposal: none (no file)`, or
`prior proposal: empty (legacy 0-byte file)`.

**Single authoritative addendum contract:**

- `<GUIDANCE_UPDATE_FILE>` contains only uncovered, verified, reducible rules;
  never Gap Register content or copies of existing guidance.
- Emit only candidates classified Novel or Additive, and for Additive emit only
  the uncovered value/tool/scope difference. Never emit Duplicate, Covered,
  Clarification, Overlap, Conflict, or Contradictory correction rows.
- Before writing, confirm that no emitted group with the same tool, subject
  scope, field expression, and action has an exactly equivalent single-condition
  union. Apply STEP 7's union simplification when it does.
- Each non-empty line is exactly `<number>. <single-line rule>`. Numbering is
  contiguous from one after the highest existing rule number; if existing
  guidance has no numbered lines, start after its count of rule-bearing lines.
- The file contains no headings, comments, blank lines, provenance tags,
  violation codes, status text, tables, cross-references, or Rego syntax.
- If rules remain, overwrite the previous addendum completely. If none remain,
  do not create the file and delete any prior or legacy empty addendum.
- Never modify `<GUIDANCE_FILE>` or the questionnaire in Step D.

The file's presence means unmerged rules are pending. Human-facing status and
out-of-scope findings belong in STEP 9 and `owasp_policy_guidelines.md`, not in
the addendum.

#### STEP 8b — Check post-merge redundancy and conflicts

Apply the Reconciliation rows to existing guidance plus the proposal. Classify
same-tool/field pairs with this vocabulary:

| Verdict | Meaning / action |
|---|---|
| Novel | No related existing rule; emit the candidate. |
| Duplicate | Same normalized tuple exists in the candidate set; retain one tuple with all source IDs. |
| Covered | Every request this row would deny is already denied by another candidate or existing rule; emit nothing. |
| Additive | Candidate only adds values; emit only the added values. |
| Clarification | Same behavior with more precise wording or field naming; recommend an edit in the Gap Register and emit nothing. |
| Overlap | Same operator has overlapping, non-identical values; report and block. |
| Conflict | Outcomes or thresholds are incompatible without distinct scope; report and block. |
| Contradictory correction | Candidate removes values or narrows scope; emit nothing, identify the required existing-rule edit, and block. |

Log IDs, field, operator, and value relationship without copying full rule
prose.

#### STEP 8c — Check regressions against the captured proposal

Apply the Prior proposal row in the matrix to every captured rule. If no prior
rules exist, log that explicit state. Do not re-add unexplained regressions.

#### STEP 8d — Validate the addendum on disk

Re-read the actual file, or confirm its required absence, and apply all On disk
rows in the matrix plus the STEP 8 addendum contract. Correct once and recheck;
then fail if any violation remains. Delete the file if cleanup removes all
rules, and report whether validation passed directly or after cleanup.

#### STEP 9 — Human review

Do not repeat tables already written. Direct the reviewer to Threat
Disposition, Scope Assessment, Gap Register, Policy Rules, and the candidate
reconciliation table. Call out only blockers, dropped/narrowed candidates, and
the no-new-rules result when applicable. End the artifact with:

```markdown
## Phase Handoff

- Status: PASS / FAIL
- Artifact schema: enforcement-mapping-v6
- Applicable threats mapped: <mapped>/<total>
- OPA candidates after deduplication: <count>
- Newly proposed rules: <count>
- Gap-register entries: <count>
- Addendum validation: PASS / FAIL / not created
- Blocking overlaps, conflicts, or regressions: <none, or concise list>
- Open gaps: <none, or concise list>
```

Mark the phase `FAIL` when addendum validation fails or any blocking overlap,
conflict, or regression remains. Step D does not merge guidance or start policy
creation.
