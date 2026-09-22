## Enforcement Mapping

Maps threat instances and confirmed questionnaire intent to their enforcement
layer, writes `owasp_policy_guidelines.md`, and proposes only missing,
OPA-enforceable rules in `guidance_updated.txt`.

### Authoritative inputs

Use only these paths; never substitute similarly named files:

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

- From `architecture.md`, load Architecture Summary/Layers, Runtime Subject
  Context, Tool Arguments (especially Disposition), Enforcement Points, and
  Undeclared Fields.
- From `threat_model.md`, load the Attack Surfaces table plus each category's
  applicability, evidence, and applicable threat instances. Do not load
  detailed scenario-exclusion prose for categories with no applicable
  instance.
- From the questionnaire, load Q9-Q19 and Q22. Load another answer only when a
  cited threat or candidate depends on it.
- From `tool_definitions.json`, load tool names and only the parameter records
  needed by threat or questionnaire candidates, including their schemas,
  descriptions, and enums.
- From `<SYSTEM_VAR_FILE>`, load subject keys and types.
- From the OWASP catalog, query only `id`, `name`, and `mitigations`; do not
  load descriptions, impacts, scenarios, aliases, or other fields. For example:

  ```bash
  jq '[.threats[] | {id, name, mitigations}]' \
    src/smith/data/owasp_10_ai_catalog.json
  ```

  If practical, filter that projection to categories having applicable threat
  instances. Query the existing catalog in place; do not create a copied or
  split catalog file.
- Defer `<GUIDANCE_FILE>` until STEP 8.

Apply the missing-input rules from Authoritative inputs before continuing.

#### STEP 2 — Map each threat to an enforcement layer

For every applicable threat instance:

1. Name the structured field carrying its evidence, if any.
2. If a pre-execution deny can be decided solely from an allowed OPA input
   path, assign it to OPA.
3. Otherwise assign it to Agent, Tool implementation, or Infrastructure and
   state why OPA cannot enforce it.

#### STEP 3 — Build the scoping table

Write one row per OWASP category:

| OWASP Category | In OPA scope? | Scope note | Out-of-scope owner |
|---|---|---|---|
| ASI01 | Yes / Partial / No | <OPA-visible portion> | Agent / Tool impl / Infra / N/A |

Use Partial only when the category has both OPA-enforceable and out-of-scope
instances.

#### STEP 4 — Build the gap register

Record every out-of-scope instance here; these rows never become guidance
rules:

| Threat | Layer | Recommended action |
|---|---|---|
| <specific instance> | Agent / Tool impl / Infra | <one-line action> |

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
<two-sentence layer and trust summary>

---

## OWASP Top 10 for Agentic AI Security — Scope Assessment

### <Category name>
**Risk:** <one sentence>
**Verdict:** <In scope / Partial / Out of scope> — <reason>

[repeat for all categories]

---

## Summary Table

| OWASP Category | In OPA scope? | Out-of-scope owner |
|---|---|---|
| ... | ... | ... |

Categories flowing into the OPA policy: <list>

---

## Gap Register

| Threat | Layer | Recommended action |
|---|---|---|
| ... | ... | ... |

---

## Policy Rules (OPA scope only)

### Input Schema
| Field | Source |
|---|---|
| ... | ... |

### Known values
<sets, enums, or term lists used by rules>

### Rule: <violation code>
- OWASP: <category>
- Severity: Hard block / Soft block
- Condition: <plain-English condition>
- Matching: <exact / substring / regex / numeric comparison / set membership>

[repeat per rule]

---

## Violation Code Reference

| Code | OWASP | Severity |
|---|---|---|
| ... | ... | ... |
```

Use canonical OPA paths. Do not include Rego syntax, Rego built-ins, file
organization, helpers, or test-generation advice.

#### STEP 6b — Verify every rule

Apply all checks before a rule can enter the candidate list:

1. **Tool and field:** every governed tool exists. For each tool separately,
   each `input.args.<x>` exists in that tool's parameters; each
   `input.extensions.subject.<x>` exists in `<SYSTEM_VAR_FILE>` or the Runtime
   Subject Context table. Preserve exact spelling.
2. **Value domain:** every trigger value is possible for that tool according to
   its schema, enum, and parameter description.
3. **Argument behavior:** when an allow path relies on a protective argument,
   architecture.md's Tool Arguments table must mark it Acts on. Echoed,
   Ignored, or Unclear arguments cannot justify an allow. This restriction does
   not invalidate a deny whose enforcement is the OPA block itself.
4. **Mitigation grounding:** the cited mitigation appears in the matching
   catalog entry's `mitigations` projection.
5. **Threat linkage:** the rule's actual justification traces to an applicable
   threat instance; similarity to another policy rule is not a threat.
6. **Questionnaire confidence:** questionnaire-derived values are not
   `[inferred — low confidence]`; otherwise drop the rule or mark it pending
   human confirmation rather than active.

Fix a citation, narrow a rule to the tools where it verifies, or drop it. Never
retain a rule for a tool where its field or value cannot occur. Record dropped
tools and a one-line verification count.

#### STEP 7 — Build one candidate list

Combine and deduplicate:

- verified rules from STEP 6; and
- OPA-enforceable questionnaire answers from Q9-Q19, including Q13b, excluding
  low-confidence answers and fields or tools that fail STEP 6b.

Two candidates are equivalent when they constrain the same field with the same
operator and overlapping value set. Keep one candidate with both source tags.
For every candidate record its sources, governed tools, canonical field,
operator, and value set. Do not read `<GUIDANCE_FILE>` yet.

#### STEP 8 — Reconcile with existing guidance and write the addendum

Read `<GUIDANCE_FILE>` once. For each candidate, record:

| Candidate | Verified tool/field | Field | Operator | Value set | Covering rule | Covered? |
|---|---|---|---|---|---|---|
| <candidate> | <tool and path> | <input path> | <operator> | <values> | <rule or —> | Yes / No |

A candidate is covered when an existing rule either:

- denies the same tool under a broader condition for the same subjects; or
- matches the same structured field, operator semantics, and triggering value
  set.

Similar wording, category, or intent is insufficient. Before writing, reject
any candidate that lacks a verified tool/field or cannot reduce to
`field · operator · value · deny on match`. Put monitoring, logging,
definitions, cross-rule interpretation, and other non-decisions in the Gap
Register or Input Schema/Known values as appropriate.

Before replacing any existing addendum, capture its numbered rules and log one
of: `prior proposal: <N> rules`, `prior proposal: none (no file)`, or
`prior proposal: empty (legacy 0-byte file)`.

**Single authoritative addendum contract:**

- `<GUIDANCE_UPDATE_FILE>` contains only uncovered, verified, reducible rules;
  never Gap Register content or copies of existing guidance.
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

Compare existing guidance plus the proposed addendum as the post-merge rule
set. For each pair on the same tool/field, report:

- **Overlap:** same operator with overlapping values.
- **Conflict:** incompatible outcomes or thresholds without distinguishing
  scope.
- **Additive correction:** candidate only adds values; emit only the added
  values as a normal rule.
- **Contradictory correction:** candidate removes values or narrows scope;
  emit no addendum line and report the required edit to the existing rule.

Do not resolve overlaps or conflicts automatically. Log the compared rules,
verdict, field, operator, and value relationship for human review. Any
unresolved Overlap or Conflict blocks Step E.

#### STEP 8c — Check regressions against the captured proposal

For every previously proposed rule, classify it as Still proposed, Merged into
current guidance, Deliberately dropped by a named check, or Regression. Report
unexplained regressions without re-adding them. If no prior rules exist, log
that state explicitly; do not infer it when STEP 8 failed to capture a state.

#### STEP 8d — Validate the addendum on disk

Re-read the actual file, or confirm its required absence. Verify the single
contract in STEP 8 plus these invariants:

- every line names only declared fields and is not semantically covered by
  existing guidance;
- numbering is contiguous and begins at the required value;
- Gap Register content remains in `owasp_policy_guidelines.md`;
- a non-empty candidate set has a non-empty file, while an empty candidate set
  has no file.

Correct violations once and rerun this check. If violations remain, mark the
phase `FAIL` instead of starting another repair loop. If cleanup removes all
rules, delete the file. Report whether the gate passed directly or after the
single cleanup pass.

#### STEP 9 — Human review

Present:

- category scope summary and violation codes;
- candidate list and newly proposed rules, or the explicit no-new-rules result;
- Gap Register;
- verification narrowing or dropped tools;
- overlaps, conflicts, additive/contradictory corrections;
- regressions; and
- addendum validation result.

Call out conflicts, contradictory edits to existing guidance, regressions, and
rejected non-decisions explicitly. End `owasp_policy_guidelines.md` with:

```markdown
## Phase Handoff

- Status: PASS / FAIL
- Applicable threats mapped: <mapped>/<total>
- OPA candidates after deduplication: <count>
- Newly proposed rules: <count>
- Other-layer gaps: <count>
- Addendum validation: PASS / FAIL / not created
- Blocking overlaps, conflicts, or regressions: <none, or concise list>
- Open gaps: <none, or concise list>
```

Mark the phase `FAIL` when addendum validation fails or any blocking overlap,
conflict, or regression remains. Return the handoff to the orchestrator and
stop. Step D does not merge guidance or start policy creation.
