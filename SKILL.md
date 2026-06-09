---
name: smith
description: responsible for creating policies, generating and evaluating test cases, testing policy, and automatically improving policy.
---

## Overview
This skill is responsible for planning skills to create policies, generating and evaluating test cases for policies, testing, and automatically improving the policy. The target policy file is `./assets/policy.rego`. 

# Policy Creation

## Create OPA policy
If the user asks for creating an OPA policy: you should strictly follow instructions in `./opa_policy/policy_creation/opa_policy_creation_mcp.md` in the skill directory to create the policy without asking any additional questions.

# Policy Testing

## Test Existing Policy
If the user asks for testing existing policy, you should run `smith --flag policy_testing`.

## Test Case Generation & Evaluation & Translation
If the user asks for generating/evaluating/translating test cases, you should strictly follow instructions in `./test_generation/test_generation.md` in the skill directory.

# Policy enhanchment
When the user ask for updating/improving their policy, you should follow the following the workflow strictly:

### Step 1. 
Run the `smith --flag policy_testing` to identify FP/FN Cases. Report the results clearly to the human.

### Step 2. 
If any false positives or false negatives are detected: Read and follow `./opa_policy/policy_patch/policy_patch.md` to fix the failed cases. Remember, `policy_patch` needs to fix all clusters before you move to the next step.

### Step 3.
After all clusters and failed cases are fix, read and follow `./opa_policy/policy_regal/policy_regal.md` to format your policy

### Step 4.
Read and follow `./opa_policy/policy_duplication/policy_duplication.md` to reduce duplication of your policy

## General Rules
- Never modify policy without explicit human “yes”.
- Always run tests after every change.
- Do NOT rewrite or refactor the entire policy.
- Keep rule names, structure, and logic consistent.
- Add only narrowly scoped conditions to block the bypasses.
- Maintain the existing allow/deny semantics and namespace check.