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
- Gate: do not proceed to Step B until the human confirms the output.

---

# Step B — Policy Guidance Questionnaire

After Step A is confirmed, or if `smith/guidelines-security-analysis/architecture.md` already exists:

Strictly follow `./owasp/policy_guidance_questionnaire.md`.

- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`
- Input (optional): `<TARGET_AGENT_PATH>/smith/guidance.txt` — primary source of policy intent; read before all other smith/ files
- Input (optional): `<TARGET_AGENT_PATH>/smith/system_vars.json`
- Input (optional): `<TARGET_AGENT_PATH>/smith/tool_definitions.json`
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/policy_guidance_questionnaire.md`
- Gate: do not proceed to Step C until the human confirms the questionnaire
  is complete.

---

# Step C — Threat Model

After Step B is confirmed, or if `smith/guidelines-security-analysis/policy_guidance_questionnaire.md` already exists:

Strictly follow `./owasp/threat_model.md`.

- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`
- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/policy_guidance_questionnaire.md`
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/threat_model.md`
- Gate: do not proceed to Step D until the human confirms the output.

---

# Step D — Enforcement Mapping

After Step C is confirmed, or if `smith/guidelines-security-analysis/threat_model.md` already exists:

Strictly follow `./owasp/enforcement_mapping.md`.

- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`
- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/threat_model.md`
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/owasp_policy_guidelines.md`
- Gate: do not proceed until the human confirms the output.

---

# Completion

When Step D is complete, inform the user:

> `smith/guidelines-security-analysis/owasp_policy_guidelines.md` is ready — architecture,
> guidance questionnaire, threat model, and enforcement mapping are all
> confirmed. Run the `policy_build` skill (`./policy_build.md`) to write,
> test, and integrate `policy.rego`.

## General Rules

- Never skip a step.
- Run all steps autonomously without stopping for human confirmation.
- If any input file is missing, stop and tell the user exactly which
  file is needed and which step produces it.
- Do not modify any existing file other than writing the designated
  output for each step.
- All writes go to `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/`. Never write
  generated artifacts directly to the MCP server root.
