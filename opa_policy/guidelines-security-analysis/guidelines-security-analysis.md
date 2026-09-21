---
name: guidelines_security_analysis
description: Policy-foundation workflow for a new MCP tool — architecture, guidance questionnaire, threat model, and enforcement mapping. Run in order: Step A → B → C → D.
---

## Overview

Run Steps A-D in order to turn an MCP server's architecture and policy intent
into OWASP-grounded enforcement guidance. Each step writes its artifact under
`<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/`; the workflow does
not generate Rego. Step E is an optional, separately authorized merge and
policy-creation handoff.

## Prerequisites

Run:

```bash
smith --flag get_current_agent
smith --flag get_mcp_parameter
```

The first command reports `target_agent:` (`<TARGET_AGENT_PATH>`) and the
resolved `guidance_file:` (`<GUIDANCE_FILE>`). Do not read `.env` directly.
The current command does not expose `SYSTEM_VAR_FILE`, so use
`<TARGET_AGENT_PATH>/smith/system_vars.json` as `<SYSTEM_VAR_FILE>` when it
exists; otherwise ask the user for the configured path instead of searching
outside the target. `<GUIDANCE_UPDATE_FILE>` is `guidance_updated.txt` beside
`<GUIDANCE_FILE>`.

The second command refreshes
`<TARGET_AGENT_PATH>/smith/tool_definitions.json`, the authoritative per-tool
source for `input.args.*` names, types, and descriptions. Run it even when the
file already exists.

Ask once for the confirmation mode:

- **Gated:** pause for confirmation after each of Steps A-D.
- **Autonomous:** run Steps A-D without intermediate pauses and present all
  results at Completion.

Do not switch modes unless the user asks. The mode never authorizes Step E.

## Step A — Architecture Analysis

Follow `./steps/architecture_analysis.md`.

- Input: `<TARGET_AGENT_PATH>` plus the resolved inputs above.
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`.
- Purpose: discover only relevant source by behavior, then capture actual
  layers, canonical input paths, tool-argument disposition, runtime subject
  context, enforcement points, and undeclared fields.

Apply the configured gate before Step B.

## Step B — Policy Guidance Questionnaire

Follow `./steps/policy_guidance_questionnaire.md`.

- Inputs: `architecture.md`, optional `<GUIDANCE_FILE>`, optional
  `<SYSTEM_VAR_FILE>`, and `tool_definitions.json`.
- Output:
  `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/policy_guidance_questionnaire.md`.
- Purpose: capture policy intent with source-confidence markers. In Autonomous
  mode, unsupported answers use `[inferred — low confidence]`; never leave an
  untagged guess.

Apply the configured gate before Step C.

## Step C — Threat Model

Follow `./steps/threat_model.md`.

- Inputs: `architecture.md`, `policy_guidance_questionnaire.md`,
  `tool_definitions.json`, `<SYSTEM_VAR_FILE>`, and the Step C field projection
  from `src/smith/data/owasp_10_ai_catalog.json`.
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/threat_model.md`.
- Purpose: evaluate ASI01-ASI10, produce concrete threat instances, and verify
  every cited field against its governing tool or runtime subject schema.

Apply the configured gate before Step D.

## Step D — Enforcement Mapping

Follow `./steps/enforcement_mapping.md`.

- Inputs: the three prior artifacts, `tool_definitions.json`,
  `<SYSTEM_VAR_FILE>`, optional `<GUIDANCE_FILE>`, and the Step D mitigation
  projection from the OWASP catalog.
- Outputs:
  - `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/owasp_policy_guidelines.md`
  - `<GUIDANCE_UPDATE_FILE>` only when verified, uncovered rules are pending.
- Purpose: separate OPA-enforceable controls from other-layer gaps, validate
  candidates, and reconcile them against existing guidance.

The single `guidance_updated.txt` format and absence-on-no-results contract are
defined only in enforcement_mapping STEP 8 and validated by STEP 8d. Gap
Register content remains in `owasp_policy_guidelines.md`.

Apply the configured gate, then proceed to Completion.

## Completion

Report `owasp_policy_guidelines.md` and, when it exists,
`<GUIDANCE_UPDATE_FILE>`. Explain that the latter is a proposal and that no
merge or policy creation has occurred. If no addendum exists, report that
existing guidance already covers all enforceable candidates and there is
nothing to merge.

## Step E — Merge and policy-creation handoff (optional)

Step E starts only when the user explicitly asks to merge. The Gated or
Autonomous choice does not authorize it.

1. Re-read `<GUIDANCE_UPDATE_FILE>` and apply enforcement_mapping STEP 8d.
   Also reject any rule already covered by `<GUIDANCE_FILE>` and stop if STEP
   8b reported an unresolved Overlap or Conflict. If the file is absent, report
   that no proposal is pending and stop; do not recreate it. If it is a legacy
   empty file, delete it and report that no rules were merged. Stop on any
   other validation failure.
2. Append the validated addendum to `<GUIDANCE_FILE>` without altering its
   existing bytes. Add a separating newline when needed, read the result back,
   and confirm the old final line and first new rule remain separate.
3. Delete `<GUIDANCE_UPDATE_FILE>` only after the read-back confirms the
   append. On failure, preserve the addendum and report the problem.
4. Ask: “`guidance.txt` now has the merged rules. Do you want me to run policy
   creation against it now, or stop here?” The merge authorizes no further
   action.
5. Only after an explicit yes, follow
   `../policy_creation/opa_policy_creation.md`. Preserve that workflow's own
   confirmation point and handoff; do not continue into testing or refinement.

## General rules

- Never skip or reorder Steps A-D.
- Follow the selected confirmation mode for Steps A-D; Step E retains its two
  explicit human gates in both modes.
- On a missing required input, identify the missing file and producing step,
  then stop.
- Steps A-D write only their designated outputs and never modify existing
  inputs. Step E may append to `<GUIDANCE_FILE>` only after explicit approval;
  it never overwrites that file.
- Write analysis artifacts only under
  `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/`, except for the
  addendum beside `<GUIDANCE_FILE>` and policy creation's documented output.
