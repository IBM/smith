---
name: guidelines_security_analysis
description: Policy-foundation workflow for a new MCP tool — architecture, guidance questionnaire, threat model, and enforcement mapping. Run in order: Step A → B → C → D.
---

## Overview

Run Steps A-D in order to turn an MCP server's architecture and policy intent
into OWASP-grounded enforcement guidance. Each step writes its artifact under
`<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/`; the workflow does
not generate Rego. Step E is an optional, separately authorized merge and
policy-creation handoff. A single generated `analysis_state.json` in that
directory holds compact, machine-readable tables, phase handoffs, and artifact
hashes; each phase checkpoint updates it in place rather than creating scratch
copies or archives.

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

The second command refreshes `<TARGET_AGENT_PATH>/smith/tool_definitions.json`,
the authoritative per-tool source for `input.args.*` names, types, and
descriptions. Run it even when the file already exists so the manifest matches
the configured MCP server. Steps A-D read this file in place and must not copy
or relocate it.

## Phase isolation and resumption

Steps A-D are separate jobs. Never execute two steps in the same model context.
For a full workflow, use a fresh isolated worker for each step and keep only
this orchestration state in the parent context:

- resolved authoritative paths;
- completed step and artifact path;
- the artifact's `Phase Handoff` section; and
- pass/fail status.

Give every worker this phase envelope with concrete values; never pass literal
`<PLACEHOLDER>` text or omit an optional path silently:

```text
PHASE: A | B | C | D
TARGET_AGENT_PATH: <resolved path>
GUIDANCE_FILE: <resolved path> | ABSENT
SYSTEM_VAR_FILE: <resolved path> | ABSENT
TOOL_DEFINITIONS_FILE: <TARGET_AGENT_PATH>/smith/tool_definitions.json
GUIDANCE_UPDATE_FILE: <resolved path beside GUIDANCE_FILE> | ABSENT
PREDECESSOR_ARTIFACTS: <resolved paths, or none for Step A>
```

Attach this Shared Phase Contract verbatim to every worker envelope. This is the
single definition; step guides do not restate it:

1. Use only the envelope paths and the current guide's named inputs. Do not read
   `.env`, search for substitutes, load another step guide, or inherit prior
   conversation or scratch analysis.
2. Stop with `FAIL` on an unresolved, omitted, missing, or conflicting required
   value. An optional path is absent only when explicitly set to `ABSENT`.
3. Cross-check the envelope against `architecture.md`'s Run Context when that
   artifact is a predecessor.
4. For a Markdown predecessor, first index its headings with
   `rg -n '^#{1,3} ' <path>`, then read only the line ranges for sections named
   by the current guide. When `analysis_state.json` contains the required table,
   read it there instead. Do not open the whole file merely to locate sections.
5. Write only the current guide's designated outputs, return its `Phase
   Handoff`, and stop.

If fresh workers are unavailable, run one step in the current invocation,
report its checkpoint, and require a new invocation for the next step. Do not
fall back to a continuous A-D context.

Resume from the first missing or explicitly requested artifact. Before using an
existing artifact, confirm that its `Phase Handoff` is successful, its
`Artifact schema` matches the current guide, and every required predecessor
exists. Re-run only a stale, failed, schema-mismatched, or explicitly requested
step. For a legacy artifact without a handoff, validate its required sections
once and append the current checkpoint; re-run the phase when validation fails.

## Phase routing

Load only the guide for the current step:

| Step | Guide | Existing checkpoint | Artifact schema |
|---|---|---|---|
| A | `./steps/architecture_analysis.md` | `architecture.md` | `architecture-v2` |
| B | `./steps/policy_guidance_questionnaire.md` | `policy_guidance_questionnaire.md` | `questionnaire-v2` |
| C | `./steps/threat_model.md` | `threat_model.md` | `threat-model-v3` |
| D | `./steps/enforcement_mapping.md` | `owasp_policy_guidelines.md` | `enforcement-mapping-v8` |

Each guide is the single source of truth for that phase's inputs, output
format, validation, and bounds. At the end of each phase, run
`smith --flag security_analysis_checkpoint --phase <A|B|C|D>`. The command
validates all artifacts through that phase and atomically refreshes
`analysis_state.json`; do not proceed on failure. After a worker returns, apply
the user's chosen review mode:

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

1. Confirm that Phase D and its deterministic checkpoint passed. If the
   addendum is absent, report that no proposal is pending and stop.
2. Run `smith --flag guidance_merge`. This explicit command rejects a stale
   Phase D checkpoint, malformed or non-contiguous numbering, duplicate rules,
   and an empty addendum. It then atomically appends the validated bytes,
   verifies the result, and deletes `<GUIDANCE_UPDATE_FILE>` only after the
   read-back passes. Do not reproduce these file operations manually.
3. Ask: “`guidance.txt` now has the merged rules. Do you want me to run policy
   creation against it now, or stop here?” The merge authorizes no further
   action.
4. Only after an explicit yes, follow
   `../policy_creation/opa_policy_creation.md`. Preserve that workflow's own
   confirmation point and handoff; do not continue into testing or refinement.

## Workflow invariants

- Run Steps A-D in order unless the user requests one phase and its required
  predecessors already exist.
- Step E retains its explicit merge and policy-creation gates in every mode.
