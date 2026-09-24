## Phase D — Enforcement mapping

Assign threats to enforcement owners and emit only novel,
OPA-policy-expressible guidance. The shared contract in the parent workflow
applies.

### Inputs

- Phase A-C structured data from `analysis_state.json`.
- `tool_definitions.json`, `system_vars.json`, and existing guidance.
- OWASP mitigations only for categories marked applicable in Phase C.
- Any existing `guidance_updated.txt`, solely for prior-proposal disposition.
- Structured output: `owasp_policy_guidelines.json`; the checkpoint renders
  `owasp_policy_guidelines.md`.

### Map threats and gaps

Run the phase preparation command. For each threat, add exactly one Threat
Disposition row assigning it to `OPA`, `Agent`, `Tool implementation`, or
`Infrastructure`. Assign OPA only when the shared OPA-policy-expressibility rule
and the eligibility gate below both pass.

Create one scope row per ASI category and reference threat IDs rather than
restating threats. Use `Partial` only when a category has both OPA and
other-layer threats. Put out-of-scope findings and unresolved human decisions
in the Gap Register. Do not treat missing future OPA wiring as a gap.

For each OPA threat, record an Input Schema row and a plain-language Rules row
with tool/field mapping, condition, match semantics, severity, threat IDs, and
violation code. Reuse documented codes; otherwise create a consistent new code.
Do not write Rego in this phase.

### Candidate eligibility

A candidate may proceed only when all are affirmative:

1. A supported threat, applicable mitigation, and non-low-confidence policy
   answer justify the deny.
2. Every tool exists in `tool_definitions.json`.
3. Every argument is declared by each exact tool to which it maps.
4. Runtime conditions use authoritative, pre-execution subject fields.
5. Types, operators, values, case behavior, defaults, and missing/null behavior
   define a complete Rego-translatable predicate.
6. No prompt reasoning, output inspection, post-processing, or undeclared data
   is required.
7. Outcome claims use only arguments marked `Acts on`. A rule that directly
   rejects a submitted value does not require the tool to act on that value.

If any check fails or is unclear, record the failed item in the Gap Register
and emit no candidate. Never invent or relocate a field to make a rule pass.

### Reconcile guidance

Normalize each candidate and reducible existing rule to:

`tool | subject scope | field expression | operator | values | deny`

Use only `eq`, `neq`, `in`, `not_in`, `contains_any`, `lt`, `lte`, `gt`, `gte`,
or `missing/null/empty`. Expand analysis rows per tool so field ownership can be
validated. Preserve conjunctive field groups and matching semantics.

First classify the contribution:

- **New intent:** adds a security outcome not required by existing guidance;
  eligible for `Novel` or `Additive`.
- **Enforcement mapping:** makes an existing requirement concrete; `Covered`,
  never emitted.
- **Clarification:** requires an interpretation not stated by guidance; record
  the question and emit nothing.
- **Enforcement gap:** cannot be decided at the OPA boundary; record the gap and
  emit nothing.

Then compare deny behavior, not wording:

- Exact or broader existing behavior → `Duplicate` or `Covered`.
- Candidate adds an independently expressible uncovered set → `Additive` for
  that difference only.
- No related behavior → `Novel`.
- Ambiguous or contradictory behavior → `Clarification`, `Overlap`,
  `Conflict`, or `Contradictory correction`; emit nothing and block completion
  for the last three.

Evaluate collective coverage, not only pairwise matches. Consolidate identical
controls across tools into one human guidance rule while retaining per-tool
Candidate Reconciliation rows. Give those rows the same `Guidance group` value;
one addendum rule is emitted per group. A universal content rule covers a tool
argument only when both use the same enforceable boundary and matching semantics.

Before comparing candidates, expand every role-independent or globally worded
existing rule into one normalization row for each applicable MCP tool and
canonical field. Do not narrow a rule merely because it does not name a tool.
When a candidate only makes such a rule tool- or field-specific without changing
its subjects, denied behavior, condition, values, or matching semantics, classify
it as `Covered` and never emit it. If the applicable tools or fields cannot be
determined from the rule and inspected schemas, classify it as `Clarification`
rather than `Novel` or `Additive`.

An implementation detail that necessarily realizes an existing closed rule is
an enforcement mapping. A new request-level hard block is not automatically
covered by an output requirement: for example, mandatory `select_fields`
changes accepted requests when safe defaults or response filtering were also
possible, so evaluate it independently.

Apply the shared source-boundary rule before creating any argument-content
candidate.

### Addendum

Record every previous addendum rule in Prior Proposal Reconciliation as
`Proposed`, `Merged`, or `Dropped` with a candidate link or reason. Then write
`guidance_updated.txt` with only the consolidated `Novel` and uncovered
`Additive` decisions. Preserve the presentation style, terminology, voice, and
structural conventions of that target's `guidance.txt`; never impose another
example's format or rewrite the additions as generic policy-engine commands.
Use sequential numbered rules only when the existing guidance uses numbered
rules. For sectioned Markdown, emit a concise Markdown addendum under matching
or clearly corresponding headings, with one top-level bullet per guidance
group. For plain one-rule-per-line guidance, emit one plain line per guidance
group. Do not copy scenario background or existing rules into the addendum.
Remove the addendum when no such decision remains. Never modify `guidance.txt`
in this phase.

Set `PASS` only when no blocking relationship or addendum error remains. The
handoff should summarize mapped threats, post-deduplication candidates, new
rules, gaps, addendum status, blockers, and open gaps.

Run:

```bash
smith --flag security_analysis_checkpoint --phase D
```
