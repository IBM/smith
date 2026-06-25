# Policy Cross-Validation

## Overview

Invoked when `smith --flag policy_testing` returns **0 test cases** or **100% failure**. Fixes the policy so tests produce meaningful results before the normal enhancement workflow.

If the scorecard shows mixed results (some pass, some fail), skip this — use `policy_patch` instead.

---

## Paths

- Policy: `./assets/policy.rego`
- Test case template: `./references/test_case_template.json`
- Scorecard: `./scripts/tests/integration/scorecard_summary.txt`

---

## Workflow

### Step 1: Classify Failure

Read the scorecard:
- `Total: 0` → **Mode A** (input path mismatch)
- All FAIL (0 passes) → **Mode B** (syntax / grammar bug)

### Step 2A: Fix Input Path Mismatches

The policy references fields that don't exist in test cases.

1. Read `./references/test_case_template.json` and one sample test case from `./references/test_cases/allow/`
2. Read `./assets/policy.rego` and list all `input.*` paths it references
3. Fix mismatches — common ones:

   | Wrong | Correct |
   |-------|---------|
   | `input.tool` / `input.tool_name` | `input.name` |
   | `input.params.*` / `input.parameters.*` | `input.arguments.*` |
   | `input.user.*` / `input.subject.*` | `input.extensions.subject.*` |
   | `input.method` / `input.operation` | `input.action` |
   | `input.type` | `input.kind` |

4. Ensure standard accessors:
   ```rego
   subject := input.extensions.subject
   args := object.get(input, "arguments", {})
   ```

### Step 2B: Fix Syntax / Grammar Issues

The policy loads but produces wrong results for every case.

1. Read `./assets/policy.rego`
2. Check OPA syntax:

   | Broken | Correct |
   |--------|---------|
   | `rule_name { ... }` | `rule_name if { ... }` |
   | `deny[msg] { ... }` | `deny contains msg if { ... }` |
   | `default allow = false` | `default allow := false` |
   | `x == set[_]` | `x in set` |
   | `x = collection[_]` | `some x in collection` |

3. Check type bugs:

   | Bug | Fix |
   |-----|-----|
   | `role == valid_roles` (set) | `role in valid_roles` |
   | `user_role == "admin"` (user_role is array) | `"admin" in user_role` |
   | `input.arguments.field` (may be undefined) | Use `object.get(input, "arguments", {})` |

4. Fix all issues

### Step 3: Validate and Test

```bash
smith --flag policy_validation --policy_path ./assets/policy.rego
```

If validation fails after 3 fix attempts, run:
```bash
smith --flag policy_validation_fix --policy_path ./assets/policy.rego
```

Then:
```bash
smith --flag policy_testing
```

### Step 4: Evaluate

- **Some tests now pass** → done. Report results. Remaining mixed failures go to `policy_patch`.
- **Still 0 or 100% fail** → re-diagnose (max 3 iterations total). If still failing after 3, report diagnostic summary to user and ask for guidance.
- **Validation breaks** → revert from backup, try different fix.

---

## Rules

- Back up first: `cp ./assets/policy.rego ./assets/opa/outputs/policy_backup_cross_validation.rego`
- Only fix path/syntax issues — do not change rule logic or delete rules
- Never modify test cases — the template is the source of truth
- Get human approval after fixes are applied and tests improve
