## Phase C — Threat model

Build a system-specific OWASP Agentic threat model from verified architecture
and policy intent. The shared contract in the parent workflow applies.

### Inputs

- Phase A and B structured data from `analysis_state.json`.
- `src/smith/data/owasp_10_ai_catalog.json`.
- Structured output: `threat_model.json`; the checkpoint renders
  `threat_model.md`.

Read only catalog IDs, names, descriptions, aliases, and attack scenarios in
this phase. Do not read mitigations; Phase D loads those only for applicable
categories.

### Build the model

Run the phase preparation command and populate these tables:

1. **Attack Surfaces:** one row per unique field/data point, source layer,
   provenance, and entry boundary. Use numeric or `#`-prefixed IDs consistently.
   Combine tools only when the field has the same provenance and behavior;
   otherwise use separate rows. Every surface must cite threats or contain an
   `N/A — reason` disposition.
2. **Evidence Index:** one ID per distinct grounded fact. Reuse IDs rather than
   copying evidence into multiple threats.
3. **Category Assessment:** exactly ASI01-ASI10, with `Yes`, `Partial`, or `No`
   applicability and a system-specific boundary.
4. **Threat Instances:** a concrete actor, surface, vector, effect, severity,
   evidence ID, and catalog scenario/alias or `novel`.
5. **Scenario Coverage:** exactly one disposition for every catalog scenario;
   cite threat IDs or `N/A — reason`.

Actors are `Caller`, `LLM`, `Tool`, or `External`. Use `Critical` for compromise
of a highest-impact data, financial, safety, or authentication boundary;
`High` for intended access-control or mission-critical bypass; `Medium` for
soft-guardrail/reliability failures; and `Low` for defense-in-depth findings.

### Scope and deduplication

- Apply the shared source-boundary rule to Q14 and do not clone a threat across
  unrelated surfaces.
- Runtime subject data is caller-forgeable only when its delivery evidence says
  so. Missing integrity documentation alone does not establish that claim.
- Generate only actor/surface combinations supported by distinct attack paths.
- Merge semantically equivalent threats and cite all supporting surfaces,
  scenarios, and evidence in the retained row.
- Do not create generic risks without a concrete system substrate.

Run one semantic completeness pass: check applicable actors, non-terminal
layers, severity, and evidence meaning. Repair once; preserve unresolved issues
as gaps and mark `FAIL`. Mechanical ID, field ownership, citation, category,
and scenario checks belong to the checkpoint.

### Complete the phase

Set `PASS` only after the semantic pass succeeds. The handoff should summarize
applicable categories, threat/severity counts, surface and scenario coverage,
citation verification, repair count, and open gaps.

Run:

```bash
smith --flag security_analysis_checkpoint --phase C
```
