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

## Existing Guidance Normalization

| Existing ID | Rule number | Tool | Subject scope | Field expression | Operator | Values | Action |
|---|---|---|---|---|---|---|---|
| E01 | <guidance rule number> | <one tool> | <roles or all> | <canonical path(s)> | <canonical operator> | <normalized values> | deny |

## Prior Proposal Reconciliation

| Prior ID | Original number | Normalized rule | Disposition | Candidate / reason |
|---|---|---|---|---|
| P01 | <number> | <normalized decision tuple> | Proposed / Merged / Dropped | <candidate ID or named validation reason> |
```

Use canonical OPA paths. Do not include Rego syntax, Rego built-ins, file
organization, helpers, or test-generation advice.

#### STEP 6b — Verify semantic support

Keep only candidates whose argument behavior, matching OWASP mitigation,
applicable threat, and non-low-confidence questionnaire evidence support the
deny. A protective allow-path argument must be `Acts on`; otherwise drop it.
Move non-reducible or unavailable-runtime-data requirements to the Gap
Register. The CLI checks field spelling, per-tool membership, value domains,
and cross-artifact IDs later, so do not repeat those mechanical scans.

#### STEP 7 — Build one candidate list

Combine:

- verified rules from STEP 6; and
- OPA-enforceable questionnaire answers from Q9-Q19, including Q13b, excluding
  low-confidence answers and fields or tools that fail STEP 6b.

Expand multi-tool proposals into one row per tool, preserving conjunctive field
groups. Normalize each row to the Candidate Reconciliation columns using only
the documented canonical operators. Preserve case, missing, and null semantics;
do not simplify ambiguous domain or subdomain matching. Assign stable IDs after
the reconciliation command has identified duplicates and exact unions. Do not
read `<GUIDANCE_FILE>` yet.

#### STEP 8 — Reconcile with existing guidance and write the addendum

Read `<GUIDANCE_FILE>` once. Use the questionnaire's guidance-rule mapping and
architecture's canonical paths to resolve explicit natural-language aliases;
do not guess between multiple plausible fields or tools.

##### Semantic deduplication

Normalize every reducible existing rule into Existing Guidance Normalization
and every candidate into Candidate Reconciliation as:

`tool | subject scope | field | operator | values | action`

Compare rules only when tool, field semantics, action, case handling, and
missing/null behavior are compatible.

- If an existing rule covers a candidate, emit nothing.
- If one candidate covers another, retain only the broader candidate and
  combine their sources.
- If a candidate broadens an existing rule, emit only the uncovered difference.
  If that difference cannot be expressed independently, record a replacement
  recommendation instead of appending the broader rule.
- Do not infer role precedence or other unspecified semantics; classify those
  cases as unresolved.
- Keep rules separate when they enforce different tools, fields, conditions,
  scopes, formats, or security constraints.

A rule covers another only when every request denied by the narrower rule is
also denied by the broader rule. Expand a general or multi-tool rule per tool
only when `tool_definitions.json` makes the mapping unambiguous. Fill Candidate
Reconciliation without restating rule prose.

Classify with this vocabulary:

| Verdict | Meaning / action |
|---|---|
| Novel | No related existing rule; emit. |
| Duplicate / Covered | Same or broader behavior already exists; emit nothing. |
| Additive | Emit only the uncovered values, tool, or scope. |
| Clarification | Behavior is unchanged; recommend an edit in the Gap Register. |
| Overlap / Conflict / Contradictory correction | Record the relationship, emit nothing, and block Step E. |

After writing the normalized Candidate Reconciliation table to
`owasp_policy_guidelines.md`, run:

```bash
smith --flag guidance_reconciliation
```

It performs the deterministic field, value, duplicate, coverage, overlap,
conflict, and exact-union checks without writing files or calling a model.
Apply its suggestions once and rerun only when the table changed. Missing or
malformed inputs fail the phase; findings themselves are review results.

Never write a candidate described anywhere in the analysis as unenforceable,
not OPA-visible, pending runtime integration, or dependent on a counter that is
not updated before evaluation. Such a candidate belongs in the Gap Register.

Before replacing any existing addendum, capture its numbered rules in Prior
Proposal Reconciliation. Use one row per prior rule and give every row a
`Proposed`, `Merged`, or `Dropped` disposition with a candidate link or named
validation reason. When no prior rules exist, leave the table empty and log one
of: `prior proposal: none (no file)` or `prior proposal: empty (legacy 0-byte
file)`.

Write `<GUIDANCE_UPDATE_FILE>` with only Novel or Additive uncovered decisions,
one numbered single-line rule per candidate and no headings or metadata. Start
after the highest existing rule number. If no rule remains, leave the file
absent. Never modify `<GUIDANCE_FILE>` or the questionnaire in Step D; the phase
checkpoint owns format, numbering, presence, and duplicate validation.

The file's presence means unmerged rules are pending. Human-facing status and
out-of-scope findings belong in STEP 9 and `owasp_policy_guidelines.md`, not in
the addendum.

#### STEP 9 — Human review

Do not repeat tables already written. Direct the reviewer to Threat
Disposition, Scope Assessment, Gap Register, Policy Rules, and the candidate
reconciliation table. Call out only blockers, dropped/narrowed candidates, and
the no-new-rules result when applicable. End the artifact with:

```markdown
## Phase Handoff

- Status: PASS / FAIL
- Artifact schema: enforcement-mapping-v8
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

After the addendum and Phase Handoff are final, run:

```bash
smith --flag security_analysis_checkpoint --phase D
```

The phase is complete only when this command passes and refreshes the single
`analysis_state.json` handoff.
