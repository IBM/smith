---
title: "Regal Formatting"
weight: 12
---

# Regal Formatting

Lint and format the policy using [Regal](https://github.com/StyraInc/regal) — Styra's linter for Rego — applying style, structure, and best-practice improvements without changing policy semantics.

## CLI Usage

```bash
smith --flag regal_suggestion  # get suggestions
smith --flag policy_testing    # verify after changes
```

## Workflow

### 1. Baseline

Run `smith --flag policy_testing` to record current FP, FN, coverage, and policy line count.

### 2. Get Suggestions

Run `smith --flag regal_suggestion` to analyze the policy. Each suggestion includes:
- What to change
- A link to Regal documentation explaining the rule

### 3. Apply Improvements

For each suggestion:
- Read the linked documentation to understand why the suggestion was raised and how to fix it correctly
- If a suggestion appears incorrect or risky, skip it
- Apply only minimal, safe changes at a time

### 4. Test After Changes

Run `smith --flag policy_testing` again and compare:
- `FP_new` must be ≤ `FP_old`
- `FN_new` must be ≤ `FN_old`

If FP or FN increased, roll back the change and explain the regression.

### 5. Report

Present a summary:
- Policy line count: before → after
- FP: before → after
- FN: before → after
- Coverage: before → after

## Rules

- Never intentionally increase FP or FN
- Prefer smaller, incremental changes
- When running `opa fmt`, write directly to file — do not paste formatted output into chat
- Never change allow/deny semantics unless explicitly instructed
- If no safe improvements can be made, explain why and stop
