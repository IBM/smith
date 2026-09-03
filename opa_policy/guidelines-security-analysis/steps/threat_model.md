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
  beyond the short citations STEP 4 asks for.
- Input 4: `<TARGET_AGENT_PATH>/smith/tool_definitions.json` — the
  authoritative source for `input.args.*`, **per tool**: each entry's
  `parameters` array lists only the arguments that tool accepts. STEP 6
  verifies every cited field against it. Required — if it is absent,
  stop and tell the user to run `smith --flag get_mcp_parameter`.
- Input 5: `<TARGET_AGENT_PATH>/smith/system_vars.json` — the
  authoritative source for `input.extensions.subject.*` field names,
  used in the same verification.
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/threat_model.md`

### Workflow (follow strictly)

---

#### STEP 1 — Read inputs

Read `architecture.md`, `policy_guidance_questionnaire.md`, the full
`owasp_10_ai_catalog.json` catalog, `tool_definitions.json`, and
`system_vars.json` before proceeding.
If any file is missing, stop and tell the user which file is needed.

The catalog's `threats` array has exactly 10 entries, `id` ASI01 through
ASI10, in order. Each entry carries `name`, `description`, `impact`,
`mitigations`, `attack_scenarios`, `business_impact`, and
`threat_aliases`. Every one of these fields is used somewhere in this
workflow — do not skim any of them.

---

#### STEP 2 — Enumerate attack surfaces from architecture.md

Before applying any OWASP category, walk `architecture.md` and produce a
complete list of attack surfaces to reason over. This is the coverage
anchor for the rest of the workflow — if a field or layer doesn't
appear here, it will not be checked in STEP 3, so make this list
exhaustive.

Extract, in this order:

1. **Every row of the Trust Boundaries table** whose classification is
   not "Trusted". Self-reported, LLM-generated, External/untrusted, and
   Not-actually-live entries all count.
2. **Every non-trusted edge in the Data Flow** — every point where an
   input crosses a trust boundary between layers (e.g. caller → agent,
   agent → tool, tool → external service, external → tool → agent).
3. **Every input into every Layer** — HTTP API, Agent, MCP Tool, Tool
   Implementation, External Service (adapt to the actual layer names in
   `architecture.md`). Include indirect inputs, e.g. a system prompt
   that embeds a Self-reported field is an input to the Agent layer's
   reasoning even though it doesn't arrive as an argument.

Produce the Attack Surfaces list as a table:

| # | Field or Data Point | Source Layer | Classification | Enters where |
|---|---|---|---|---|
| 1 | `user_profile.*` (all keys the caller may set) | HTTP API | Self-reported | Agent layer (embedded in system prompt) |
| 2 | `keywords` (LLM-generated tool argument) | Agent | Self-reported | Tool → External |
| ... | ... | ... | ... | ... |

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
mere shape examples. For each scenario:
- If yes → produce a threat instance that names the specific field or
  layer of *this* tool that the scenario maps onto.
- If no → record a one-line reason (e.g. "no downstream agent to
  propagate to", "no persistent memory store"). These reasons go under
  "Scenarios considered but not applicable" in STEP 4. Do not silently
  skip a scenario; the completeness critic in STEP 5 checks that every
  scenario has been either matched or explicitly excluded.

Then do the same for `threat_aliases`: if an alias names a specific
sub-risk (e.g. "Cross-Agent Trust Exploitation" for ASI03) and the
architecture has the relevant substrate, produce a matching instance.

**3c — Decompose each attack surface by actor.** For every threat
instance, identify the actor that initiates or executes the attack:

- **Caller** — a user or upstream system sending crafted input in a
  Self-reported field (prompt injection via `user_profile`, forged
  session data, etc.).
- **LLM** — the agent's model reasoning incorrectly, hallucinating,
  falling for a prompt injection, or picking dangerous tool arguments
  from an otherwise-benign user question.
- **Tool** — the tool implementation processing input unsafely
  (unsanitized outbound query construction, missing bounds checks,
  unpinned dependencies).
- **External** — an external service returning adversarial content
  (poisoned scrape, spoofed response, compromised or typosquatted
  dependency).

A single ASI category can and often does have threat instances at
multiple actors. Reason each one separately — do NOT blur "the caller
or the LLM does X" into a single instance. If the same attack surface
is exploitable by two actors (e.g. `keywords` can be tainted by the
caller via prompt injection AND fabricated by the LLM on its own),
that is two distinct threat instances.

**3d — Assign severity.** For every threat instance, assign
Critical / High / Medium / Low, grounded in this ASI's `business_impact`
entry from the catalog. Use this rubric:

- **Critical** — data loss, financial loss, safety impact, or
  compromise of an authentication boundary; matches the catalog's most
  severe `business_impact` example for this ASI.
- **High** — bypass of an intended access-control rule, or of a policy
  the tool exists to enforce (role gating, disallowed-topic filter,
  hard limit cap).
- **Medium** — bypass of a soft guardrail (naming conventions,
  advisory quotas), reliability degradation, or information leakage
  that is not confidential.
- **Low** — nuisance, defense-in-depth concern, or a threat that is
  real but has no material impact on this tool's mission.

Pull from the catalog entry with matching `id`:
- `name` — the category display name used in the output heading
- `description` — paraphrase into one sentence for the "OWASP:" line;
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

Coverage sweep from architecture.md's Trust Boundaries and Data Flow.
Every row must be referenced in at least one ASI threat instance below,
or explicitly marked "N/A — <reason>" in the Covered-in column.

| # | Field or Data Point | Source Layer | Classification | Enters where | Covered in |
|---|---|---|---|---|---|
| 1 | `user_profile.*` | HTTP API | Self-reported | Agent layer | ASI01, ASI03 |
| 2 | `keywords` | Agent (LLM) | Self-reported | Tool → External | ASI02 |
| ... | ... | ... | ... | ... | ... |

---

## ASI01 — <name from catalog>
**Applicable:** Yes / Partial / No
**OWASP:** <one-sentence paraphrase of catalog `description`>
**Evidence:** <cite specific field, file, or behaviour from architecture.md / questionnaire>
**Threat instances:**
- **[Severity]** **Actor: Caller/LLM/Tool/External** — <concrete
  description naming the specific field/layer and attack vector>.
  *(Attack surface: row #N; Catalog scenario: <index into `attack_scenarios`> / novel-to-this-system)*
- [second instance, if a distinct actor or attack vector applies]
**Scenarios considered but not applicable:**
- <catalog scenario summary> — <one-line reason it doesn't apply here>
- [one bullet per scenario in the catalog `attack_scenarios` array that
  was NOT matched to a threat instance above]
**Not covered:** <one to two sentences on what this category as a whole
does not touch for this tool>

[repeat for ASI02 through ASI10, using each catalog entry's own `name`]
```

Rules for writing threat instances:
- Every instance must name (a) a specific field or layer, (b) an actor,
  and (c) a severity — no exceptions.
- Every instance must reference an Attack Surfaces row number and
  either a catalog `attack_scenarios` index or the word "novel".
- Do not write generic agentic-risk statements.
- If a category is Not Applicable, still list the catalog scenarios you
  considered under "Scenarios considered but not applicable" so the
  completeness critic can verify. "Not applicable" is a conclusion, not
  a shortcut for skipping analysis.
- Partial means some sub-risks apply and some do not — split them
  explicitly (threat instances for the sub-risks that apply; "Scenarios
  considered but not applicable" for the rest).

---

#### STEP 5 — Completeness critic

Before verifying citations, run an independent self-check pass on the
draft. This step exists because it is easy to write a threat model that
covers the categories you thought of and silently omits the ones you
didn't — and that omission is invisible to citation verification, which
only checks that what you *did* write is well-grounded.

Check every one of the following. Anything that fails is a gap; go back
to STEP 3 and add the missing threat instance (or, for scenarios/fields
that genuinely don't apply, add an N/A entry).

1. **Attack surface coverage.** Every row in the "Attack Surfaces" table
   must appear in at least one threat instance's `Attack surface:
   row #N` reference. Any row that no instance references must be
   annotated in the table's Covered-in column as "N/A — <reason>". A
   Self-reported or untrusted surface with no ASI at all is almost
   always a real miss, not a genuine N/A — treat that outcome with
   suspicion.
2. **Architecture layer coverage.** Every non-terminal layer in
   architecture.md's Layers section must be referenced by at least one
   threat instance's actor, evidence line, or attack-surface entry.
   Layers that genuinely contribute nothing (pure passthrough with no
   input transformation) get an explicit note in "Not covered" for the
   most applicable ASI.
3. **Catalog scenario coverage.** For every ASI where Applicable = Yes
   or Partial, every entry in the catalog's `attack_scenarios` array
   must be either matched to a threat instance or listed under
   "Scenarios considered but not applicable" with a reason. Silent
   skipping is the most common source of the miss this critic exists
   to catch.
4. **Multi-actor consideration.** For every ASI where Applicable = Yes,
   check whether more than one actor (Caller/LLM/Tool/External) could
   plausibly cause the harm this category describes. If yes, confirm
   the corresponding threat instances exist. This is where "the caller
   can prompt-inject via a Self-reported field" gets picked up
   alongside "the LLM can hallucinate the same argument on its own".
5. **Severity sanity.** Scan the assigned severities across the
   document. If every Applicable ASI has only Low or Medium instances,
   double-check — either the tool has genuinely low blast radius (rare
   for anything that touches an external service or self-reported
   identity), or the severity rubric is being under-applied.

Loop back to STEP 3 for anything missing, then re-run this critic on
the updated draft. Do not proceed to STEP 6 until this pass finds no
gaps.

Log a one-line result (e.g. `Completeness: 12/12 attack surfaces,
30/30 catalog scenarios, no gaps found` or `Completeness: added 2
threat instances after critic pass — user_profile-into-system-prompt
(ASI01) and requests/beautifulsoup4 supply chain (ASI04)`).

---

#### STEP 6 — Verify citations

Walk every citation in `threat_model.md` and confirm it exists in its
source. This catches fabricated fields and misattributed evidence
before they propagate into Step D.

For every threat instance and every "Evidence:" line:

1. If it names an `input.args.<x>`, an `input.extensions.subject.<x>`,
   or any other structured field, confirm that exact field is declared
   where the threat instance needs it:
   - For `input.args.<x>`: name the tool the threat instance concerns,
     then confirm the field appears in **that tool's own** `parameters`
     array in `tool_definitions.json`. Do not accept the field merely
     appearing somewhere in the file — many tools share a parameter
     name, and a field declared on one tool says nothing about another.
     A threat instance citing `args.department` as evidence against a
     tool that has no `department` argument is a fabricated evidence
     line, even though the name exists elsewhere.
   - For `input.extensions.subject.<x>` and other subject fields:
     confirm the key appears in `system_vars.json` or
     architecture.md's Trust Boundaries table, spelled exactly as that
     source spells it (`roles`, not `role`).

   This check runs here as well as in the enforcement_mapping step
   because it runs *first*. A threat instance that verifies clean here
   is inherited downstream as established, and enforcement_mapping's
   own threat-linkage check will then find genuine upstream support for
   a rule built on a field that tool never receives.
2. If it cites `architecture.md` (a layer, file, or behaviour), confirm
   the citation matches text actually present in `architecture.md`.
3. If it cites a questionnaire answer (e.g. "per Q9"), confirm that
   question is answered — not blank, and not `[inferred — low
   confidence]`. Low-confidence answers must NOT be cited as evidence;
   remove or rewrite the threat instance if that is its only support.
4. If it cites a catalog `attack_scenarios` index or a `threat_aliases`
   entry, confirm that index/alias exists in the catalog entry for
   that ASI.
5. If it cites an Attack Surfaces row number, confirm the row exists
   and matches the description.

Any citation that fails verification: either fix the citation (pointing
to a real field/section) or delete the threat instance. Cite-and-hope
is not acceptable — the enforcement_mapping step will turn these
citations into policy rules.

Log a one-line verification result (e.g. `Citations verified: 18/18`
or `Citations verified: 15/18 — 3 fabricated fields removed`).

---

#### STEP 7 — Human review

Present the completeness result from STEP 5, the citation verification
result from STEP 6, and a summary table:

| Category | Applicable | # Threat instances | Severity distribution |
|---|---|---|---|
| ASI01 | Yes/Partial/No | N | Critical: A, High: B, Medium: C, Low: D |
| ... | ... | ... | ... |

Also log the overall Attack Surfaces coverage figure (e.g. "12/12
covered, 0 marked N/A") so the reviewer can see the coverage stance at
a glance.

Hand control back to the top-level workflow, which decides (per
confirmation mode) whether to proceed to the next step.
