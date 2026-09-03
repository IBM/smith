---
name: guidelines_security_analysis
description: Policy-foundation workflow for a new MCP tool — architecture, guidance questionnaire, threat model, and enforcement mapping. Run in order: Step A → B → C → D.
---

## Overview

This skill runs the foundation pipeline for any new MCP server: it turns
raw architecture and guidance into an OWASP-mapped enforcement spec.
Each step produces an artifact under `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/`.
That subfolder is created automatically on first write. Do not skip steps
or reorder them.

Step D is the last of the four required steps. Its outputs
(`owasp_policy_guidelines.md` and `guidance_updated.txt`) are the final
artifacts of the required pipeline; this workflow does not write any
Rego itself. An optional Step E performs the merge of
`guidance_updated.txt` into `guidance.txt` itself and hands off to
policy creation — but only once the human explicitly asks for the merge
to happen; it never starts on its own, in either confirmation mode.

## Prerequisites

Run `smith --flag get_current_agent` to confirm the active target agent
path and guidance file path (do not read `.env` for these). It prints
the active `target_agent:` (the `<TARGET_AGENT_PATH>`) and
`guidance_file:` (the resolved `<GUIDANCE_FILE>` path). Use those two
values everywhere `<TARGET_AGENT_PATH>` and `<GUIDANCE_FILE>` appear
below.

Then run `smith --flag get_mcp_parameter` to generate
`<TARGET_AGENT_PATH>/smith/tool_definitions.json`. This connects to the
MCP server and extracts every tool's name, parameters, types, and
descriptions — Step A treats it as the authoritative source for
`input.args.*` field names, Step B fills questionnaire Q4 from it,
and Steps C/D cite it during their citation-verification passes. Run
this command even if `tool_definitions.json` already exists, so the
extracted shapes match the server actually running.

Before starting Step A, ask the user how they want the four steps to
run:
- **Gated** — pause after each step and wait for the human to confirm the
  output before starting the next step.
- **Autonomous** — run Step A through Step D back-to-back with no pauses,
  then present all four outputs together at the end for one final review.

Use the answer for the entire run; do not ask again per step, and do not
switch modes mid-run unless the user explicitly asks to change it. Each
step below refers to this as "the confirmation mode."

All generated artifacts live under:
```
<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/
```

Source inputs remain at:
```
<TARGET_AGENT_PATH>/smith/guidance.txt
<TARGET_AGENT_PATH>/smith/system_vars.json
<TARGET_AGENT_PATH>/smith/tool_definitions.json
```
Steps A–D never modify any of these. Step E is the one exception: on
an explicit human trigger, it appends `guidance_updated.txt` to
`guidance.txt`, preserving the existing file byte-for-byte and adding
the newly proposed rules after it — see Step E below.

---

# Step A — Architecture Analysis

If the user asks to analyse the architecture of an MCP server, or when
starting this workflow for a new tool:

Strictly follow `./steps/architecture_analysis.md`.

- Input: MCP server directory (e.g. `examples/call-for-papers-mcp/`)
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`
  — besides the layer/trust-boundary/enforcement sections, this step is
  the **only** one that reads the server implementation, so two of its
  findings are load-bearing for Step D and cannot be reconstructed
  later: the **Disposition** column on the Trust Boundaries table (does
  the tool act on an argument, merely echo it, or ignore it) and the
  **Undeclared Fields** table (fields existing guidance depends on that
  no tool declares, or that the governing tool does not declare).
- Gate: if the confirmation mode is Gated, do not proceed to Step B until
  the human confirms the output. If Autonomous, continue to Step B
  immediately.

---

# Step B — Policy Guidance Questionnaire

After Step A is confirmed, or if `smith/guidelines-security-analysis/architecture.md` already exists:

Strictly follow `./steps/policy_guidance_questionnaire.md`.

- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`
- Input (optional): `<TARGET_AGENT_PATH>/smith/guidance.txt` — primary source of policy intent; read before all other smith/ files
- Input (optional): `<TARGET_AGENT_PATH>/smith/system_vars.json`
- Input (optional): `<TARGET_AGENT_PATH>/smith/tool_definitions.json`
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/policy_guidance_questionnaire.md`
- Gate: if the confirmation mode is Gated, do not proceed to Step C until
  the human confirms the questionnaire is complete. If Autonomous,
  continue to Step C immediately — fill any remaining blanks per STEP 3
  of `policy_guidance_questionnaire.md` using its confidence markers
  (never guess without an `[inferred — low confidence]` tag) rather than
  pausing to ask.

---

# Step C — Threat Model

After Step B is confirmed, or if `smith/guidelines-security-analysis/policy_guidance_questionnaire.md` already exists:

Strictly follow `./steps/threat_model.md`.

- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`
- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/policy_guidance_questionnaire.md`
- Input: `src/smith/data/owasp_10_ai_catalog.json` — repo-relative, not
  per-target-agent. The OWASP Top 10 for Agentic AI Security catalog
  (ASI01–ASI10). This step evaluates all 10 catalog categories against
  the tool's architecture and questionnaire answers to produce the
  concrete threat vectors written into `threat_model.md` — it is not
  optional context, it is the taxonomy the whole step is structured around.
- Input: `<TARGET_AGENT_PATH>/smith/tool_definitions.json` and
  `<TARGET_AGENT_PATH>/smith/system_vars.json` — this step's STEP 6
  verifies every field cited in a threat instance or evidence line
  against the **governing tool's own** parameter list, not against the
  file as a whole. It runs before Step D, so an unverified evidence line
  is inherited downstream as established fact.
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/threat_model.md`
- Gate: if the confirmation mode is Gated, do not proceed to Step D until
  the human confirms the output. If Autonomous, continue to Step D
  immediately.

---

# Step D — Enforcement Mapping

After Step C is confirmed, or if `smith/guidelines-security-analysis/threat_model.md` already exists:

Strictly follow `./steps/enforcement_mapping.md`.

- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`
- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/threat_model.md`
- Input: `src/smith/data/owasp_10_ai_catalog.json` — repo-relative, not
  per-target-agent. Source of the `mitigations` this step grounds its
  policy-rule requirements in.
- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/policy_guidance_questionnaire.md`
  — the same file produced in Step B, not a new file. Step D's STEP 7
  (Build the combined candidate-rule list) pulls Sections 3-6's answers
  in directly as a second, independent source of candidate rules (they
  don't need to map to an OWASP category to be worth enforcing).
  Low-confidence questionnaire answers are excluded from the candidate
  list. Step D's STEP 8 (Reconcile candidates against guidance.txt) is
  the only step that touches guidance.txt.
- Input: `<TARGET_AGENT_PATH>/smith/tool_definitions.json` — the
  authoritative, per-tool source for `input.args.*`. Step D's STEP 6b and
  STEP 7 verify every candidate rule against it: a rule may only
  reference arguments the governing tool actually declares. Required — if
  it is missing, stop and run `smith --flag get_mcp_parameter`.
- Input: `<TARGET_AGENT_PATH>/smith/system_vars.json` — the authoritative
  source for `input.extensions.subject.*`, used in the same verification.
- Input (optional): `<TARGET_AGENT_PATH>/smith/guidance.txt` — the same
  existing per-target-agent guidance file already read in Step B, not a
  new file. Used here only to check which of this step's candidate rules
  (from both sources above) are not yet represented in it. If it does not
  exist, skip that check.
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/owasp_policy_guidelines.md`
- Output: `<TARGET_AGENT_PATH>/smith/guidance_updated.txt` — written next
  to `guidance.txt` itself (not under `guidelines-security-analysis/`):
  contains ONLY the newly proposed OPA-scope rules that `guidance.txt`
  is missing, numbered as an addendum that continues from
  `guidance.txt`'s last rule number. It is not a replacement for
  `guidance.txt` — Step E appends it, preserving the original file.
  Gap-register items (OWASP findings that are not OPA-enforceable) do
  NOT go into this file; their durable home is
  `owasp_policy_guidelines.md`'s Gap Register table so downstream
  policy/test generation never sees non-rule content.
- Gate: if the confirmation mode is Gated, do not proceed to Completion
  until the human confirms the output. If Autonomous, proceed to
  Completion immediately and present all four step outputs together for
  one final review.

---

# Completion

When Step D is complete, inform the user:

> This workflow is finished. Two artifacts are ready for review:
>
> 1. `smith/guidelines-security-analysis/owasp_policy_guidelines.md` —
>    the enforcement specification (architecture + questionnaire +
>    threat model + enforcement mapping), all confirmed.
> 2. `smith/guidance_updated.txt` — the newly proposed OPA-scope
>    rules Step D found missing from `guidance.txt`, numbered as an
>    addendum. This is a proposal for you to review. OWASP findings
>    that aren't OPA-enforceable are recorded in the Gap Register
>    table inside `owasp_policy_guidelines.md` above, not appended
>    here, so downstream policy/test generation only ever sees rules.
>
> Once you're satisfied with it, tell me to merge — I'll append it to
> `guidance.txt` (preserving your existing content) and then run
> policy creation against the result. I won't touch `guidance.txt`
> until you say so.

---

# Step E — Merge and Hand Off to Policy Creation (optional, human-triggered)

This step does not start automatically, in either confirmation mode, and
it is not covered by the Step A–D Gate logic above. It stays dormant
until the human explicitly asks for the merge to be applied (e.g.
"merge"/ "yes"). Do not infer this from
silence, and do not merge on your own initiative just because Step D
finished — wait for the explicit instruction.

Once triggered:

1. **Merge (append, not overwrite).** Append the contents of
   `<TARGET_AGENT_PATH>/smith/guidance_updated.txt` to
   `<TARGET_AGENT_PATH>/smith/guidance.txt`. `guidance_updated.txt` is
   built (Step D, STEP 8) to contain ONLY the newly proposed numbered
   rules, so this merge is a straight append — the existing
   `guidance.txt` (including any headings, blank lines, comments, or
   paragraphs of context beyond the numbered rules) is preserved
   byte-for-byte, and the new rules land after it with their numbering
   already continuing from where `guidance.txt` left off. Ensure
   there is a trailing newline on `guidance.txt` before the append so
   the first new rule starts on its own line. This is the one
   exception to "Steps A–D never modify guidance.txt" in the Overview
   above — it happens only here, and only after the explicit human
   trigger. Do NOT overwrite `guidance.txt` — that would discard any
   non-rule content the human authored.
2. **Policy creation.** Strictly follow
   `../policy_creation/opa_policy_creation.md` to generate
   `<TARGET_AGENT_PATH>/smith/policy_generated.rego` from the
   just-merged `guidance.txt`. This is the same procedure `SKILL.md`'s
   "Create OPA Policy" section already describes — this step exists only
   to trigger it against the guidance this workflow just updated, not to
   redefine policy creation.
3. **Hand off.** After it completes, hand off exactly as `SKILL.md`
   prescribes: tell the user, "The policy has been created. Next steps
   you can take: (1) generate test cases, (2) if you already have test
   cases, you can ask me to test the policy." Do not continue on your
   own into test generation, policy testing, or refinement
   (patch/regal/dedup) — those remain separate, human-requested steps
   per `SKILL.md`.

## General Rules

- Never skip a Step A–D step. Step E is optional and only ever runs on
  an explicit human trigger; it is not subject to "never skip."
- Follow the confirmation mode (Gated or Autonomous) chosen before Step A
  for every Step A–D Gate — do not stop for confirmation in Autonomous
  mode, and do not skip a confirmation pause in Gated mode. Step E has
  its own, separate trigger and ignores this setting.
- If any input file is missing, stop and tell the user exactly which
  file is needed and which step produces it — this applies regardless of
  confirmation mode.
- Do not modify any existing file other than writing the designated
  output for each step, except Step E's sanctioned overwrite of
  `guidance.txt` on explicit human trigger.
- All writes go to `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/`, except Step E's
  merge into `guidance.txt` and its `policy_generated.rego` output, which
  per `opa_policy_creation.md` are both written to
  `<TARGET_AGENT_PATH>/smith/` directly. Never write generated artifacts
  directly to the MCP server root.
