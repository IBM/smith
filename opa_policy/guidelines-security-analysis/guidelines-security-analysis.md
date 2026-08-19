---
name: policy_foundation
description: End-to-end policy creation workflow for a new MCP tool. Run in order: Step A → B → C → D → E → F → G → H → I.
---

## Overview

This skill runs the full policy creation pipeline for any new MCP server.
Each step produces an artifact under `<mcp_server_dir>/policy_generation/`.
That subfolder is created automatically on first write. Do not skip steps
or reorder them.

The target MCP server directory is provided by the user at invocation time.
If not provided, ask before starting Step A.

All generated artifacts live under:
```
<mcp_server_dir>/policy_generation/
```

Source inputs (never modified by this pipeline) remain at:
```
<mcp_server_dir>/smith/guidance.txt
<mcp_server_dir>/smith/system_vars.json
<mcp_server_dir>/smith/tool_definitions.json
```

---

# Step A — Architecture Analysis

If the user asks to analyse the architecture of an MCP server, or when
starting this workflow for a new tool:

Strictly follow `./owasp/architecture_analysis.md`.

- Input: MCP server directory (e.g. `examples/call-for-papers-mcp/`)
- Output: `<mcp_server_dir>/policy_generation/architecture.md`
- Gate: do not proceed to Step B until the human confirms the output.

---

# Step B — Policy Guidance Questionnaire

After Step A is confirmed, or if `policy_generation/architecture.md` already exists:

Strictly follow `./owasp/policy_guidance_questionnaire.md`.

- Input: `<mcp_server_dir>/policy_generation/architecture.md`
- Input (optional): `<mcp_server_dir>/smith/guidance.txt` — primary source of policy intent; read before all other smith/ files
- Input (optional): `<mcp_server_dir>/smith/system_vars.json`
- Input (optional): `<mcp_server_dir>/smith/tool_definitions.json`
- Output: `<mcp_server_dir>/policy_generation/policy_guidance_questionnaire.md`
- Gate: do not proceed to Step C until the human confirms the questionnaire
  is complete.

---

# Step C — Threat Model

After Step B is confirmed, or if `policy_generation/policy_guidance_questionnaire.md` already exists:

Strictly follow `./owasp/threat_model.md`.

- Input: `<mcp_server_dir>/policy_generation/architecture.md`
- Input: `<mcp_server_dir>/policy_generation/policy_guidance_questionnaire.md`
- Output: `<mcp_server_dir>/policy_generation/threat_model.md`
- Gate: do not proceed to Step D until the human confirms the output.

---

# Step D — Enforcement Mapping

After Step C is confirmed, or if `policy_generation/threat_model.md` already exists:

Strictly follow `./owasp/enforcement_mapping.md`.

- Input: `<mcp_server_dir>/policy_generation/architecture.md`
- Input: `<mcp_server_dir>/policy_generation/threat_model.md`
- Output: `<mcp_server_dir>/policy_generation/owasp_policy_guidelines.md`
- Gate: do not proceed until the human confirms the output.

---

# Step E — Policy Writing

After Step D is confirmed, or if `policy_generation/owasp_policy_guidelines.md` already exists:

Strictly follow `./owasp/policy_writing.md`.

- Input: `<mcp_server_dir>/policy_generation/owasp_policy_guidelines.md`
- Output: `<mcp_server_dir>/policy_generation/policy.rego`
- Gate: do not proceed to Step F until the human confirms the output.

---

# Step F — Policy Coverage Check

After Step E is confirmed, or if `policy_generation/policy.rego` already exists:

Strictly follow `./owasp/policy_coverage_check.md`.

- Input: `<mcp_server_dir>/policy_generation/policy.rego`
- Input: `<mcp_server_dir>/policy_generation/owasp_policy_guidelines.md`
- Input (optional): `<mcp_server_dir>/smith/guidance.txt`
- Output: `<mcp_server_dir>/policy_generation/policy_coverage_report.md`
- Side effect: `policy_generation/policy.rego` may be patched if the human confirms proposed additions
- Gate: do not proceed to Step G until the human has reviewed the coverage
  report and responded to any proposed additions.

---

# Step G — Test Case Generation

After Step F is confirmed, or if `policy_generation/policy_coverage_report.md` already exists:

Strictly follow `./owasp/test_case_generation.md`.

- Input: `<mcp_server_dir>/policy_generation/owasp_policy_guidelines.md`
- Input: `<mcp_server_dir>/policy_generation/policy.rego`
- Output: `<mcp_server_dir>/policy_generation/tests/allow/*.json`
- Output: `<mcp_server_dir>/policy_generation/tests/deny/*.json`
- Gate: do not proceed to Step H until the human confirms coverage.

---

# Step H — Delta Testing

After Step G, or if test cases already exist:

Run `smith --flag policy_delta` against the test suite to measure the policy's
baseline pass rate.

```bash
smith --flag policy_delta \
    --policy_path <mcp_server_dir>/policy_generation/policy.rego \
    --test_cases_dir <mcp_server_dir>/policy_generation/tests \
    --delta_json <mcp_server_dir>/policy_generation/run1.json
```

- Input: `<mcp_server_dir>/policy_generation/policy.rego` (must be loaded on OPA server)
- Input: `<mcp_server_dir>/policy_generation/tests/` (OWASP-generated test cases from Step G)
- Output: pass rate, fail rate, list of failing cases, policy code snapshot
- Pass `--previous <mcp_server_dir>/policy_generation/run1.json` on subsequent runs to track delta.
- Continue automatically to Step I; report the pass rate inline.

---

# Step I — Delta Fix Loop

After Step H, if any test cases are still failing:

Strictly follow `./owasp/policy_delta_fix.md`.

Run the automated fix loop:

```bash
smith --flag policy_delta_fix \
    --policy_path <mcp_server_dir>/policy_generation/policy.rego \
    --test_cases_dir <mcp_server_dir>/policy_generation/tests \
    --max_iter 10 \
    --stall_limit 3
```

- Input: `<mcp_server_dir>/policy_generation/policy.rego` (loaded on OPA server)
- Input: `<mcp_server_dir>/policy_generation/tests/` (OWASP-generated test cases from Step G)
- Input: `<mcp_server_dir>/policy_generation/owasp_policy_guidelines.md`
- Output: updated `<mcp_server_dir>/policy_generation/policy.rego` at 100 % pass rate
- The loop runs autonomously — diagnoses failing cases, applies LLM fixes, validates with OPA,
  and re-measures until 100 % pass rate or a stopping condition is hit.
- Continue automatically to Step J once the loop reports SUCCESS.

---

# Step J — Pipeline Handoff

After Step I reaches 100 % pass rate on both allow and deny cases:

1. Run `smith --flag policy_validation_fix --policy_path <mcp_server_dir>/policy_generation/policy.rego`
   to auto-format and verify the final policy compiles cleanly.

2. Copy the validated policy to the active policy path used by `smith --flag policy_testing`:
   ```
   cp <mcp_server_dir>/policy_generation/policy.rego assets/policy.rego
   ```
   (`assets/policy.rego` is the path resolved from env vars `POLICY_DIR + POLICY_PATH`.)

3. Run `smith --flag test_generation` to generate the full test suite from `guidance.txt`.

4. Run `smith --flag policy_testing` to evaluate the policy against the generated test suite
   and record the baseline FP/FN/coverage scores.

- Output: baseline scorecard at `references/scorecard/scorecard_summary.txt`
- The policy is now integrated into the smith pipeline and ready for the
  enhancement workflow (policy_patch → policy_regal → policy_duplication).

---

# Completion

When Step J is complete, inform the user:

> `policy_generation/policy.rego` passes all allow and deny test cases and is
> integrated into the smith pipeline. Run `smith --flag policy_testing` at any
> time to re-evaluate, or follow the policy enhancement workflow in SKILL.md
> to further improve the policy.

## General Rules

- Never skip a step.
- Run all steps autonomously without stopping for human confirmation.
- If any input file is missing, stop and tell the user exactly which
  file is needed and which step produces it.
- Do not modify any existing file other than writing the designated
  output for each step.
- All writes go to `<mcp_server_dir>/policy_generation/`. Never write
  generated artifacts directly to the MCP server root.
