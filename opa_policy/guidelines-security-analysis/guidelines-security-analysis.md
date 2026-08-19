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

Step D's output (`owasp_policy_guidelines.md`) is the handoff point to the
`policy_build` skill (`./policy_build.md`), which writes, tests, and
integrates the actual `policy.rego`. This skill does not write any Rego.

The target MCP server directory is provided by the user at invocation time.
If not provided, ask before starting Step A.

Before starting Step A, also ask the user how they want the four steps to
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

Source inputs (never modified by this pipeline) remain at:
```
<TARGET_AGENT_PATH>/smith/guidance.txt
<TARGET_AGENT_PATH>/smith/system_vars.json
<TARGET_AGENT_PATH>/smith/tool_definitions.json
```

---

# Step A — Architecture Analysis

If the user asks to analyse the architecture of an MCP server, or when
starting this workflow for a new tool:

Strictly follow `./owasp/architecture_analysis.md`.

- Input: MCP server directory (e.g. `examples/call-for-papers-mcp/`)
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`
- Gate: if the confirmation mode is Gated, do not proceed to Step B until
  the human confirms the output. If Autonomous, continue to Step B
  immediately.

---

# Step B — Policy Guidance Questionnaire

After Step A is confirmed, or if `smith/guidelines-security-analysis/architecture.md` already exists:

Strictly follow `./owasp/policy_guidance_questionnaire.md`.

- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`
- Input (optional): `<TARGET_AGENT_PATH>/smith/guidance.txt` — primary source of policy intent; read before all other smith/ files
- Input (optional): `<TARGET_AGENT_PATH>/smith/system_vars.json`
- Input (optional): `<TARGET_AGENT_PATH>/smith/tool_definitions.json`
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/policy_guidance_questionnaire.md`
- Gate: if the confirmation mode is Gated, do not proceed to Step C until
  the human confirms the questionnaire is complete. If Autonomous,
  continue to Step C immediately — fill any remaining blanks per STEP 3
  of `policy_guidance_questionnaire.md` rather than pausing to ask.

---

# Step C — Threat Model

After Step B is confirmed, or if `smith/guidelines-security-analysis/policy_guidance_questionnaire.md` already exists:

Strictly follow `./owasp/threat_model.md`.

- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`
- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/policy_guidance_questionnaire.md`
- Input: `src/smith/data/owasp_10_ai_catalog.json` — repo-relative, not
  per-target-agent. The OWASP Top 10 for Agentic AI Security catalog
  (ASI01–ASI10). This step evaluates all 10 catalog categories against
  the tool's architecture and questionnaire answers to produce the
  concrete threat vectors written into `threat_model.md` — it is not
  optional context, it is the taxonomy the whole step is structured around.
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/threat_model.md`
- Gate: if the confirmation mode is Gated, do not proceed to Step D until
  the human confirms the output. If Autonomous, continue to Step D
  immediately.

---

# Step D — Enforcement Mapping

After Step C is confirmed, or if `smith/guidelines-security-analysis/threat_model.md` already exists:

Strictly follow `./owasp/enforcement_mapping.md`.

- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`
- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/threat_model.md`
- Input: `src/smith/data/owasp_10_ai_catalog.json` — repo-relative, not
  per-target-agent. Source of the `mitigations` this step grounds its
  policy-rule requirements in.
- Input (optional): `<TARGET_AGENT_PATH>/smith/guidance.txt` — the same
  existing per-target-agent guidance file already read in Step B, not a
  new file. Used here only to check which of this step's OPA-scope rules
  are not yet represented in it. If it does not exist, skip that check.
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/owasp_policy_guidelines.md`
- Output: `<TARGET_AGENT_PATH>/smith/guidance_updated.txt` — written next
  to `guidance.txt` itself (not under `guidelines-security-analysis/`):
  the existing guidance plus any OPA-scope rules this step found that
  `guidance.txt` is missing.
- Gate: if the confirmation mode is Gated, do not proceed to Completion
  until the human confirms the output. If Autonomous, proceed to
  Completion immediately and present all four step outputs together for
  one final review.

---

# Completion

When Step D is complete, inform the user:

> `smith/guidelines-security-analysis/owasp_policy_guidelines.md` is ready — architecture,
> guidance questionnaire, threat model, and enforcement mapping are all
> confirmed. Run the `policy_build` skill (`./policy_build.md`) to write,
> test, and integrate `policy.rego`.

## General Rules

- Never skip a step.
- Follow the confirmation mode (Gated or Autonomous) chosen before Step A
  for every step's Gate — do not stop for confirmation in Autonomous mode,
  and do not skip a confirmation pause in Gated mode.
- If any input file is missing, stop and tell the user exactly which
  file is needed and which step produces it — this applies regardless of
  confirmation mode.
- Do not modify any existing file other than writing the designated
  output for each step.
- All writes go to `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/`. Never write
  generated artifacts directly to the MCP server root.
