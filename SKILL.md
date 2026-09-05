---
name: smith
description: Responsible for creating policies, generating and evaluating test cases, testing policies, and automatically improving them.
---

## Overview
This skill is responsible for creating policies, generating and evaluating test cases, testing, and automatically improving the policy. The target policy file is `./assets/policy.rego`. 

## Prerequisites
Before running any `smith` commands, activate the project virtual environment:

```bash
source .venv/bin/activate
```

## Create OPA Policy
If the user asks to create an OPA policy, you should strictly follow instructions in `./opa_policy/policy_creation/opa_policy_creation.md` in the skill directory to create the policy without asking any additional questions.

After completion, remind the user: “The policy has been created. Next steps you can take: (1) generate test cases, (2) if you already have test cases, you can ask me to test the policy.”

## Create an OPA Policy with a Security-Grounded Guidance Analysis
If the user asks to **create an OPA policy with a security-grounded guidance analysis** (or asks to run the guidelines security analysis, threat-model an MCP server, or produce OWASP-mapped enforcement guidance for a new tool), strictly follow instructions in `./opa_policy/guidelines-security-analysis/guidelines-security-analysis.md`. This is a separate, standalone workflow that first grounds the guidance in an OWASP-mapped threat model and then (on explicit human trigger) runs "Create OPA Policy" above against the updated guidance. It runs in order:

- **Step A** — Architecture Analysis (`architecture.md`)
- **Step B** — Policy Guidance Questionnaire (`policy_guidance_questionnaire.md`)
- **Step C** — Threat Model against OWASP Top 10 for Agentic AI Security (`threat_model.md`)
- **Step D** — Enforcement Mapping (`owasp_policy_guidelines.md` + `guidance_updated.txt`)
- **Step E** *(optional, human-triggered)* — Merge `guidance_updated.txt` into `guidance.txt` and hand off to "Create OPA Policy" above

Before starting Step A, ask the user whether to run **Gated** (pause after each step) or **Autonomous** (Steps A–D back-to-back, one final review at the end). Step E stays dormant until the human explicitly asks for the merge; then it appends `guidance_updated.txt` to `guidance.txt` (preserving the existing file byte-for-byte) and continues into `./opa_policy/policy_creation/opa_policy_creation.md` (the same procedure as "Create OPA Policy" above).

After Step D completes, remind the user: "Review `guidance_updated.txt`. When you're satisfied, tell me to merge — I'll append it to `guidance.txt` (preserving your existing content) and run policy creation against the result."

## Test Case Generation
If the user asks to generate test cases, you should strictly follow instructions in `./test_generation/test_generation.md` in the skill directory.

After completion, remind the user: “Test cases have been generated. Note that some generated cases may have incorrect labels (allow vs disallow). Next steps: If you already have a policy, run policy testing.”

Adversarial (red-team) coverage depends on the `ATTACK_TOOLS` env var (ARES and/or Promptfoo; may be `none`). The CLI prints which tools were enabled vs skipped. If any attack tool was skipped, tell the user that adversarial coverage is reduced or absent, so “all tests passed” later reflects the legitimate cases only and not resistance to red-teaming.

## Test Existing Policy
If the user asks to test an existing policy, you should run `smith --flag policy_testing`.

After reporting results, remind the user of next steps based on the outcome:
- If all tests pass: “All tests passed. You can proceed to generate more test cases, or ask me to check for formatting/duplication issues.”
- If 0 test cases were evaluated OR 100% of test cases are rejected: follow `./opa_policy/policy_cross_validation/policy_cross_validation.md` to diagnose and fix structural/syntax issues before proceeding.
- If tests fail (mixed pass/fail): “Some tests failed. Next steps: consider cross-validating test cases first (labels may be wrong), then ask me to improve/patch the policy.”

## Cross-Validate Failed Test Cases
If the user asks to cross-validate failed test cases, follow the instructions in `./test_generation/cross_validate.md` in the skill directory.

After completion, remind the user: “Cross-validation is complete. 

## Policy Enhancement
When the user asks to update or improve their policy, or you identify failed test cases, you should follow the workflow below strictly:

### Step 1.
Run `smith --flag policy_testing` to identify FP/FN cases. Report the results clearly to the human.

After reporting, remind the user: “Next step: I will patch the policy to fix failed cases. Shall I proceed?”

### Step 2.
If any false positives or false negatives are detected, read and follow `./opa_policy/policy_patch/policy_patch.md` to fix the failed cases. Remember, `policy_patch` needs to fix all clusters before you move to the next step.

After patching, remind the user: “All failed cases have been patched. Next step: format the policy with Regal to fix style issues. Shall I proceed?”

### Step 3.
After all clusters and failed cases are fixed, read and follow `./opa_policy/policy_regal/policy_regal.md` to format your policy.

After formatting, remind the user: “Policy has been formatted. Next step: check for and remove duplicate rules. Shall I proceed?”

### Step 4.
Read and follow `./opa_policy/policy_duplication/policy_duplication.md` to reduce duplication in your policy.

After deduplication, remind the user: “Duplication check complete. The policy enhancement workflow is finished. You can re-run `smith --flag policy_testing` to confirm all tests still pass.”

## Translate policy to cpex format
If users ask to translate policy to cpex format, run `smith --flag cpex_translate`. 

## Save Copies of Results
If the user asks to save, snapshot, back up, or archive their results, run `smith --flag save_snapshot --dest <directory>`, where `<directory>` is the destination the user wants the copies written to. If the user does not specify a destination, ask them for one.
## General Rules
- Never modify the policy without explicit human “yes”.
- Always run tests after every change.
- Do NOT rewrite or refactor the entire policy.
- Keep rule names, structure, and logic consistent.
- Add only narrowly scoped conditions to block bypasses.
- Maintain the existing allow/deny semantics and namespace checks.