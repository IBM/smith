## Threat Model 

Applies the OWASP Top 10 for Agentic AI Security (ASI01–ASI10) to a target
MCP server and produces `threat_model.md`. Requires `architecture.md` and
`policy_guidance_questionnaire.md` to be present in the target directory.

### Authoritative Paths

**Inputs:** Use ONLY these exact files. Do NOT read similarly-named files
from other folders. If a required file is missing here, stop and ask; do
not substitute one from elsewhere.
- Input 1: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md` (from architecture_analysis skill)
- Input 2: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/policy_guidance_questionnaire.md`
- Input 3: `src/smith/data/owasp_10_ai_catalog.json` — repo-relative, not
  per-target-agent. This is the OWASP Top 10 for Agentic AI Security
  catalog (ASI01–ASI10). It is the single source of truth for category
  names, definitions, and reference threat data — do not hardcode or
  duplicate its content into this skill file or into `threat_model.md`
  beyond the short citations STEP 3 asks for.
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/threat_model.md`

### Workflow (follow strictly)

---

#### STEP 1 — Read inputs

Read `architecture.md`, `policy_guidance_questionnaire.md`, and the full
`owasp_10_ai_catalog.json` catalog before proceeding.
If any file is missing, stop and tell the user which file is needed.

The catalog's `threats` array has exactly 10 entries, `id` ASI01 through
ASI10, in order. Each entry carries `name`, `description`, `impact`,
`mitigations`, `attack_scenarios`, `business_impact`, and `threat_aliases`.

---

#### STEP 2 — Apply the OWASP Top 10 for Agentic AI Security

Evaluate each of the 10 catalog threats, ASI01 through ASI10, IN ORDER
against this specific tool. For each, apply the three-question test:

1. **Does the attack surface exist for this tool?**
   Base this on `architecture.md` — what inputs does the tool accept,
   what external systems or agents does it call, what data flows
   through it, does it delegate to other agents or tools.

2. **Is there a specific threat instance for this tool?**
   A threat instance is concrete: it names the specific field, layer,
   or behaviour that is at risk. Generic statements ("the agent could
   be manipulated") are not threat instances. Use the catalog's `impact`
   and `attack_scenarios` entries for this threat ID as reference
   examples of the *shape and specificity* a real instance takes — do
   not copy them in; they describe other systems, not this tool.

3. **What is the evidence from the tool's design?**
   Cite specific fields, files, or behaviours from the input documents.

For each threat, pull from the catalog entry with matching `id`:
- `name` — the category display name used in the output heading
- `description` — paraphrase into one sentence for "OWASP definition";
  do not quote the multi-paragraph field verbatim
- `impact` / `attack_scenarios` — calibration examples only (see above)
- `mitigations` — do not restate here; `enforcement_mapping.md` reads
  them directly from the catalog in its own next step

---

#### STEP 3 — Write threat_model.md

Write the output file to `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/threat_model.md` using exactly
this structure for each of the 10 catalog categories, in ASI01→ASI10 order:

```
# Threat Model: <tool-name>
Source catalog: src/smith/data/owasp_10_ai_catalog.json (OWASP Top 10 for Agentic AI Security)

## ASI01 — <name from catalog>
**Applicable:** Yes / Partial / No
**Evidence:** <cite specific field, file, or behaviour>
**Threat instances:**
- <specific, concrete threat with field name and attack vector>
- [add only if a distinct second instance exists]
**Not covered:** <aspects of this category that do not apply to this tool>

[repeat for ASI02 through ASI10, using each catalog entry's own `name`]
```

Rules for writing threat instances:
- Every threat instance must name a specific field or layer
- Do not write generic agentic-risk statements
- If a category is Not Applicable, write one sentence explaining why
- Partial means some sub-risks apply and some do not — split them explicitly

---

#### STEP 4 — Verify citations

Before presenting the summary, walk every citation in `threat_model.md`
and confirm it exists in its source. This catches fabricated fields and
misattributed evidence before they propagate into Step D.

For every threat instance and every "Evidence:" line:

1. If it names an `input.arguments.<x>`, an `input.extensions.subject.<x>`,
   or any other structured field, confirm that exact field appears in
   `tool_definitions.json` (for `input.arguments.*`) or
   `system_vars.json` / architecture.md's Trust Boundaries table (for
   `input.extensions.*` and other subject fields).
2. If it cites `architecture.md` (a layer, file, or behaviour),
   confirm the citation matches text actually present in
   `architecture.md`.
3. If it cites a questionnaire answer (e.g. "per Q9"), confirm that
   question is answered — not blank, and not `[inferred — low
   confidence]`. Low-confidence answers must NOT be cited as evidence;
   remove or rewrite the threat instance if that is its only support.

Any citation that fails verification: either fix the citation
(pointing to a real field/section) or delete the threat instance.
Cite-and-hope is not acceptable — the enforcement_mapping step will
turn these citations into policy rules.

Log a one-line verification result (e.g. `Citations verified: 14/14`
or `Citations verified: 12/14 — 2 fabricated fields removed`).

---

#### STEP 5 — Human review

Present a summary table:

| Category | Applicable | # Threat instances |
|---|---|---|
| ASI01 | Yes/Partial/No | N |
...

Log the summary table and hand control back to the top-level workflow,
which decides (per confirmation mode) whether to proceed to the next
step.
