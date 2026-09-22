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

## Phase isolation and resumption

Steps A-D are separate jobs. Never execute two steps in the same model context.
For a full workflow, use a fresh isolated worker for each step and keep only
this orchestration state in the parent context:

- resolved authoritative paths;
- completed step and artifact path;
- the artifact's `Phase Handoff` section; and
- pass/fail status.

Give a worker only the resolved paths, its step guide, and the inputs named by
that guide. Do not pass prior conversation, scratch analysis, or another step's
guide. The worker writes its designated artifact, returns the `Phase Handoff`,
and stops. If fresh workers are unavailable, run one step in the current
invocation, report its checkpoint, and require a new invocation for the next
step. Do not fall back to a continuous A-D context.

Resume from the first missing or explicitly requested artifact. Before using an
existing artifact, confirm that it has a successful `Phase Handoff` and that
every required predecessor exists. Re-run only a stale, failed, or explicitly
requested step; never regenerate an earlier artifact merely to continue. For a
legacy artifact without a handoff, validate its required sections once and
append the checkpoint in place; re-run the phase only when that validation
fails.

## Phase routing

Load only the guide for the current step:

| Step | Guide | Existing checkpoint |
|---|---|---|
| A | `./steps/architecture_analysis.md` | `architecture.md` |
| B | `./steps/policy_guidance_questionnaire.md` | `policy_guidance_questionnaire.md` |
| C | `./steps/threat_model.md` | `threat_model.md` |
| D | `./steps/enforcement_mapping.md` | `owasp_policy_guidelines.md` |

Each guide is the single source of truth for that phase's inputs, output
format, validation, and bounds. After a worker returns, apply the user's chosen
review mode:

- **Gated:** present the checkpoint and wait for approval.
- **Isolated autonomous:** start the next fresh worker after a successful
  checkpoint without pausing.

Ask for the review mode once. Neither mode authorizes Step E.

## Completion

Report `owasp_policy_guidelines.md` and, when it exists,
`<GUIDANCE_UPDATE_FILE>`. Explain that the latter is a proposal and that no
merge or policy creation has occurred. If no addendum exists, report that
existing guidance already covers all enforceable candidates and there is
nothing to merge.

## Step E — Merge and policy-creation handoff (optional)

Step E starts only when the user explicitly asks to merge. The selected review
mode does not authorize it.

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

## Workflow invariants

- Run Steps A-D in order unless the user requests one phase and its required
  predecessors already exist.
- A phase writes only the outputs declared by its guide and never modifies its
  inputs.
- On a missing input or failed checkpoint, report the producing step and stop.
- Step E retains its explicit merge and policy-creation gates in every mode.
