## Threat Model 

Applies the OWASP Top 10 for Agentic AI Security (ASI01–ASI10) to a target
MCP server and produces `threat_model.md`. Requires `architecture.md` and
`policy_guidance_questionnaire.md` to be present in
`<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/`.

### Phase inputs and output

The envelope's Shared Phase Contract applies.
- Input 1: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md` (from architecture_analysis skill)
- Input 2: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/policy_guidance_questionnaire.md`
- Input 3: `src/smith/data/owasp_10_ai_catalog.json` — repo-relative, not
  per-target-agent. This is the OWASP Top 10 for Agentic AI Security
  catalog (ASI01–ASI10). It is the single source of truth, but this phase
  consumes only the projection defined in STEP 1.
- Input 4: `<TARGET_AGENT_PATH>/smith/tool_definitions.json` — the
  authoritative source for `input.args.*`, **per tool**: each entry's
  `parameters` array lists only the arguments that tool accepts. STEP 6
  verifies every cited field against it. Required — if it is absent,
  stop and tell the user to run `smith --flag get_mcp_parameter`.
- Input 5: `<SYSTEM_VAR_FILE>` — the
  authoritative schema for runtime-provided
  `input.extensions.subject.*` field names, used in the same field-existence
  verification. It does not by itself establish how those values are
  authenticated or integrity-protected.
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/threat_model.md`

### Workflow (follow strictly)

---

#### STEP 1 — Read inputs

Load only the input sections needed by this phase:

- `architecture.md`: Run Context, Layers, Trust Boundaries, Data Flow,
  Enforcement Points, and Undeclared Fields.
- questionnaire: Answer Register rows Q1-Q19, their confidence markers, and
  only the detail tables referenced by those rows. Q20-Q22 are not needed for
  threat discovery.
- `tool_definitions.json`: tool names and parameter names/types for citation
  verification; defer detailed descriptions and enums to Step D.
- `<SYSTEM_VAR_FILE>`: subject keys and types.
- OWASP catalog: query only `id`, `name`, `description`, `attack_scenarios`,
  `business_impact`, and `threat_aliases` for all ten entries. For example:

  ```bash
  jq '[.threats[] | {id, name, description, attack_scenarios, business_impact, threat_aliases}]' \
    src/smith/data/owasp_10_ai_catalog.json
  ```

Do not load `impact`, `mitigations`, catalog metadata, or other fields in this
phase. Query the existing catalog in place; do not create a copied or split
catalog file.

---

#### STEP 2 — Enumerate attack surfaces from architecture.md

Before applying any OWASP category, walk `architecture.md` and produce a
complete list of attack surfaces to reason over. This is the coverage
anchor for the rest of the workflow — if a field or layer doesn't
appear here, it will not be checked in STEP 3, so make this list
exhaustive.

Extract, in this order:

1. **Every Tool Arguments row** that can be influenced by the caller or
   LLM. Preserve its canonical `input.args.<argument>` path and governing
   tool. Include unknown influence unless the architecture establishes that
   the value is fixed by trusted application code.
2. **Every Prompt Inputs row** that can be influenced by callers or external
   content, including free text interpolated into a system prompt.
3. **Every External Data row** without a documented integrity mechanism.
4. **Runtime Subject Context rows only when evidence identifies a threat to
   the subject-delivery channel.** A field declared by `system_vars.json` is
   runtime-provided and is not an attack surface merely because application
   source does not read it. Include `input.extensions.subject.<field>` only
   when the architecture documents caller influence, tampering, an untrusted
   provider, or another concrete integrity weakness. Missing documentation may
   justify an assurance gap, but not a claim that the field is self-reported or
   prompt-injectable.
5. **Every non-trusted edge in the Data Flow** — every point where an
   input crosses a trust boundary between layers (e.g. caller → agent,
   agent → tool, tool → external service, external → tool → agent).
6. **Every input into every Layer** — HTTP API, Agent, MCP Tool, Tool
   Implementation, External Service (adapt to the actual layer names in
   `architecture.md`). Include indirect inputs, such as caller-provided text
   embedded in a system prompt even though it does not arrive as a tool
   argument. The Runtime Subject Context rule in item 4 still applies; do not
   reintroduce those fields here without evidence of a vulnerable channel.

Produce the Attack Surfaces list as a table:

| # | Field or Data Point | Source Layer | Provenance / influence | Enters where |
|---|---|---|---|---|
| 1 | `user_profile.*` (all keys the caller may set) | HTTP API | Self-reported | Agent layer (embedded in system prompt) |
| 2 | `input.args.keywords` | Agent | LLM-generated / caller-influenced | Tool → External |
| ... | ... | ... | ... | ... |

Keep one row per unique field/data point, source layer, provenance, and entry
boundary. When several tools expose the same field shape, retain separate rows
only when their provenance or behavior differs; otherwise list the tools in one
row. Expand an instance across actors only when architecture evidence shows a
distinct actor path. Do not manufacture every actor/surface combination.

Draft this list now — it becomes the "Attack Surfaces" section of
`threat_model.md` in STEP 4, and the completeness critic in STEP 5
checks every entry against the threat instances.

**Every entry in this table must appear in at least one threat instance
in STEP 3**, or be explicitly marked N/A (with a one-line reason) during
STEP 5's completeness critic. A surface with no threat instance and no
N/A justification is a coverage gap, not an acceptable outcome.

---

#### STEP 3 — Apply the OWASP Top 10 for Agentic AI Security

Evaluate each of the 10 catalog threats, ASI01 through ASI10, IN ORDER
against this specific tool. For each ASI, apply four sub-steps in
sequence: 3a category triage, 3b scenario checklist, 3c actor
decomposition, 3d severity assignment.

**3a — Category-level triage.** Answer:
- **Does the attack surface exist for this tool?** Base this on the
  Attack Surfaces list from STEP 2 — which surfaces, if any, could an
  attacker of *this* class exploit?
- **Is there at least one specific threat instance?** A threat instance
  is concrete: it names a specific field, layer, or behaviour that is
  at risk. Generic statements ("the agent could be manipulated") are
  not threat instances.
- If both answers are yes, the category is Applicable — or Partial if
  some sub-risks apply and others do not. Otherwise, Not Applicable.

**3b — Walk the catalog's `attack_scenarios` as a checklist, not
calibration.** For every scenario in this ASI's `attack_scenarios`
array, ask: "does an analog of this scenario exist against this tool?"
This is a per-scenario coverage check — do not treat the scenarios as
mere shape examples. Record one compact coverage row per scenario: map it to a
threat ID when applicable, otherwise write `N/A` and a one-line reason. Do not
repeat the catalog scenario text. The completeness critic in STEP 5 checks
that every scenario index has a disposition.

Then do the same for `threat_aliases`: if an alias names a specific
sub-risk (e.g. "Cross-Agent Trust Exploitation" for ASI03) and the
architecture has the relevant substrate, produce a matching instance.

**3c — Decompose each attack surface by actor.** For every threat
instance, identify the actor that initiates or executes the attack:

| Actor | Meaning |
|---|---|
| Caller | User/upstream system supplies crafted prompts or influences tool arguments. |
| LLM | Model is manipulated, hallucinates, or selects dangerous arguments. |
| Tool | Tool implementation processes input or dependencies unsafely. |
| External | External service or dependency returns adversarial content. |

Treat runtime subject context as caller-forgeable only when architecture
evidence identifies a vulnerable provider or delivery channel.

A single ASI category can and often does have threat instances at
multiple actors. Reason each one separately — do NOT blur "the caller
or the LLM does X" into a single instance. If the same attack surface
is exploitable by two actors (e.g. `input.args.keywords` can be tainted by the
caller via prompt injection AND fabricated by the LLM on its own),
that is two distinct threat instances.

Deduplicate equivalent instances before writing. Within one ASI, instances are
equivalent when actor, attack-surface row, vulnerable field/layer, attack
vector, and impact are the same. Keep one instance and attach every matching
catalog scenario index; do not duplicate prose merely because two catalog
scenarios describe the same system-specific exploit. Assign stable document-
wide IDs (`T01`, `T02`, ...) after deduplication.

**3d — Assign severity.** For every threat instance, assign
Critical / High / Medium / Low, grounded in this ASI's `business_impact`
entry from the catalog. Use this rubric:

| Severity | Criterion |
|---|---|
| Critical | Data, financial, safety, or authentication-boundary compromise matching the category's highest business impact. |
| High | Intended access-control or mission-critical policy bypass. |
| Medium | Soft-guardrail bypass, reliability degradation, or non-confidential leakage. |
| Low | Nuisance or defense-in-depth risk without material mission impact. |

Pull from the catalog entry with matching `id`:
- `name` — the Category Assessment `Name`
- `description` — paraphrase into its one-sentence `OWASP summary`;
  do not quote the multi-paragraph field verbatim
- `attack_scenarios` — 3b uses these directly, per scenario
- `threat_aliases` — 3b uses these to check for named sub-risks
- `business_impact` — 3d uses this to calibrate severity
- `impact` / `mitigations` — do not restate here; `enforcement_mapping.md`
  reads them directly from the catalog in its own next step

---

#### STEP 4 — Write threat_model.md

Write the output file to
`<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/threat_model.md`
using exactly this structure:

```
# Threat Model: <tool-name>
Source catalog: src/smith/data/owasp_10_ai_catalog.json (OWASP Top 10 for Agentic AI Security)

## Attack Surfaces

| # | Field or Data Point | Source Layer | Provenance / influence | Enters where | Threat IDs / N/A |
|---|---|---|---|---|---|
| 1 | `user_profile.*` | HTTP API | Self-reported | Agent layer | T01, T03 |
| 2 | `input.args.keywords` | Agent (LLM) | LLM-generated / caller-influenced | Tool → External | T02 |
| ... | ... | ... | ... | ... | ... |

## Evidence Index

Give each distinct source citation one ID and state it once. Reuse the ID in
all threat rows that depend on the same evidence.

| ID | Source | Grounded fact |
|---|---|---|
| E01 | `architecture.md` — Tool Arguments row N | <concise fact> |
| E02 | questionnaire Q9 | <concise confirmed intent> |

## Category Assessment

| ASI | Name | Applicability | OWASP summary | Boundary (optional) |
|---|---|---|---|---|
| ASI01 | <catalog name> | Yes / Partial / No | <one-sentence description paraphrase> | <one sentence or —> |

## Threat Instances

| ID | ASI | Severity | Actor | Surface | Catalog basis | Evidence | Concrete threat |
|---|---|---|---|---|---|---|---|
| T01 | ASI01 | High | Caller | #2 | 1, 3 | E01, E02 | <field/layer, vector, and impact> |

## Scenario Coverage

| ASI | Scenario | Disposition |
|---|---|---|
| ASI01 | 1 | T01 |
| ASI01 | 2 | N/A — <one-line system-specific reason> |
```

Rules for writing threat instances:
- Each threat row must name a specific field/layer, actor, severity, Attack
  Surface row, evidence ID, and catalog basis: scenario indexes, an alias, or
  `novel`.
- Cite each distinct fact once in the Evidence Index; reuse its ID rather than
  repeating the citation or grounded fact in category prose.
- Do not write generic agentic-risk statements.
- Category Assessment has exactly one row for each ASI01-ASI10. Every catalog
  scenario gets exactly one Scenario Coverage row. A threat ID
  means applicable; `N/A — <reason>` means considered but inapplicable.
- Partial means some scenario rows map to threats and others are N/A.

---

#### STEP 5 — Completeness critic

Run one semantic critic pass that automation cannot perform: check whether
each applicable ASI needs distinct Caller, LLM, Tool, or External instances;
whether every non-terminal architecture layer is represented or explicitly a
passthrough; and whether severity matches the documented business impact. Do
not classify runtime-provided subject data as caller-controlled without
evidence about its delivery channel. Repair once; if semantic gaps remain,
record them and mark the phase `FAIL`.

The phase checkpoint performs the mechanical completeness checks for unique
IDs, all ten category rows, attack-surface dispositions, and every catalog
scenario. Do not duplicate those counts manually beyond the Phase Handoff.

---

#### STEP 6 — Verify citations

Verify only source meaning that requires judgment: each architecture citation
must support the stated behavior, and each catalog alias or scenario must
support the claimed threat. Fix or remove unsupported claims. The phase
checkpoint checks the remaining mechanical links: Evidence IDs, surface IDs,
questionnaire confidence, catalog indexes, and tool-specific argument and
subject-field declarations. Record its verified/total result in the handoff.

---

#### STEP 7 — Human review

Do not produce another category summary: Category Assessment already contains
the reviewable result. Append the checkpoint below; call out only failed
checks or open gaps that require human attention.

Append:

```markdown
## Phase Handoff

- Status: PASS / FAIL
- Artifact schema: threat-model-v3
- OWASP categories evaluated: 10/10
- Applicable categories: <count and IDs>
- Threat instances: <count after deduplication>
- Severity distribution: Critical <n>, High <n>, Medium <n>, Low <n>
- Attack surfaces covered: <covered>/<total>; N/A: <count>
- Catalog scenarios accounted for: <covered>/<total>
- Citations verified: <verified>/<total>, or not run after a failed critic
- Repair passes: <0 or 1>
- Open gaps: <none, or concise list>
```

Run `smith --flag security_analysis_checkpoint --phase C` after writing the
handoff. Continue only when it passes. The checkpoint deterministically checks
category and scenario coverage, internal evidence references, structured
fields, and predecessor questionnaire citations, then refreshes
`analysis_state.json`.
