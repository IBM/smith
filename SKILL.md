---
name: smith
description: responsible for creating different policies, generating test cases, testing, and automatically improving policy.
---

## Overview
This skill is responsible for planning skills to create different policies, generating test cases for these policies, testing, and automatically improving the policy. The target policy file is `./assets/policy.rego`. Notice that all files are only in the skill directory. 

# Policy Creation

## Create OPA policy
If the user asks for creating an OPA policy for them: you should strictly follow instructions in `./opa_policy/policy_creation/opa_policy_creation.md` in the skill directory to create the policy without asking any additional questions.

## Create other policies
If the user asks for creating other kinds of policies, you should tell user this functionality is still under development.

# Policy Testing

## General testing
If the user asks for testing existing policy, you should run `smith --flag policy_testing`.

## Test Case Generation & Evaluation
If the user asks for generating test cases or evaluating test case quality, you should strictly follow instructions in `./test_generation/test_generation.md` in the skill directory.

# Policy enhanchment
When the user ask for updating/improving their policy, you should follow the following the workflow strictly:

### Step 1. 
Run the `smith --flag policy_testing` to identify FP/FN Cases, unlabeled cases should be considered as malicious and get denied. Report the results clearly to the human.

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