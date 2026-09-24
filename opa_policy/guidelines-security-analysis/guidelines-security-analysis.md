---
name: guidelines_security_analysis
description: Analyze an MCP system and produce non-duplicative, OPA-policy-expressible security guidance through four isolated phases.
---

## Purpose

Run phases A-D in order: architecture, policy questionnaire, threat model, and
enforcement mapping. The workflow proposes guidance; it does not create Rego.
Merging guidance and creating policy remain separately authorized actions.

## Resolve inputs

Run:

```bash
smith --flag get_current_agent
smith --flag get_mcp_parameter
```

Use the reported target and guidance paths. The second command refreshes
`<TARGET_AGENT_PATH>/smith/tool_definitions.json`; it is authoritative for tool
names and `input.args.*` schemas. Use
`<TARGET_AGENT_PATH>/smith/system_vars.json` when present; otherwise ask for the
configured system-variable path. Do not inspect `.env` or search outside the
target.

## Shared phase contract

Run each phase in a fresh context and load only its guide. Give it resolved
paths for `TARGET_AGENT_PATH`, `GUIDANCE_FILE` or `ABSENT`, `SYSTEM_VAR_FILE` or
`ABSENT`, `TOOL_DEFINITIONS_FILE`, and `GUIDANCE_UPDATE_FILE` or `ABSENT`.

For phase `<P>`:

1. Run `smith --flag security_analysis_checkpoint --phase <P> --prepare`.
2. Fill the generated phase JSON. It is the primary intermediate; preserve its
   keys and table columns, use strings for cell values, and use empty arrays for
   tables with no rows.
3. Set top-level `status` and `handoff.Status` to `PASS` only after completing
   the phase. Preserve the generated schema value.
4. Run `smith --flag security_analysis_checkpoint --phase <P>`. The command
   validates structured state, updates `analysis_state.json`, and renders the
   corresponding Markdown artifact for human review.
5. Stop on failure. Do not edit rendered Markdown because the next checkpoint
   replaces it from JSON.

Read predecessor data from `analysis_state.json`, not from rendered Markdown.
Do not inherit scratch reasoning between phases. If an existing phase has only
Markdown, rerun it to create the structured source.

## Shared analysis rules

- Treat `system_vars.json` fields as runtime subject data at
  `input.extensions.subject.*`. Keep provenance separate from whether an
  integrity mechanism is documented.
- Treat tool parameters as `input.args.*` belonging to the exact declaring
  tool. Never use a field declared only by another tool.
- Prompt, conversation, retrieved content, runtime subject data, tool
  arguments, and returned data are distinct sources and boundaries. Do not turn
  a prompt-only control into repeated tool-argument controls.
- “OPA-policy-expressible” means a future pre-execution Rego decision can use
  declared structured inputs to decide the complete predicate. Existing OPA
  wiring is not required and its planned absence is not a gap.
- Preserve modal intent: `only`, `must`, `cannot`, and `no one` establish hard
  boundaries. `can` and `may` do not create exclusive allowlists.
- Record uncertainty instead of inventing tools, fields, values, role
  precedence, enforcement visibility, or security intent.
- State a fact once in the phase where it is established and reference its ID
  later. The checkpoint owns mechanical schema, citation, coverage, numbering,
  and reconciliation checks.

## Phase routing

| Phase | Guide | Structured source | Rendered review |
|---|---|---|---|
| A | `steps/architecture_analysis.md` | `architecture.json` | `architecture.md` |
| B | `steps/policy_guidance_questionnaire.md` | `policy_guidance_questionnaire.json` | `policy_guidance_questionnaire.md` |
| C | `steps/threat_model.md` | `threat_model.json` | `threat_model.md` |
| D | `steps/enforcement_mapping.md` | `owasp_policy_guidelines.json` | `owasp_policy_guidelines.md` |

Resume at the first missing or requested phase. A phase is reusable only when
its structured source validates and its schema matches the prepared template.

## Completion and optional merge

Report `owasp_policy_guidelines.md` and `guidance_updated.txt` when the latter
exists. Explain that no merge or policy creation has occurred.

Only after explicit merge approval:

1. Run `smith --flag guidance_merge`. It validates the Phase D checkpoint,
   numbering, duplicates, and current hashes before atomically merging and
   removing the addendum.
2. Ask whether to begin policy creation.
3. Only after a separate yes, follow `../policy_creation/opa_policy_creation.md`.
