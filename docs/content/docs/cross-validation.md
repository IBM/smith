---
title: "Cross-Validation"
weight: 8
---

# Cross-Validation

Two cross-validation workflows handle different failure scenarios after policy testing.

## Policy Cross-Validation

When policy testing returns 0 test cases evaluated or 100% deny, the policy likely has structural issues (input path mismatches or OPA syntax bugs). The agent follows `opa_policy/policy_cross_validation/policy_cross_validation.md` to diagnose and fix these issues before proceeding to refinement.

## Test Case Cross-Validation

When policy testing produces mixed pass/fail results, some failures may be caused by mislabeled test cases rather than policy bugs. This workflow uses an LLM to check each failed case against the guidance and suggests corrections (move to correct folder or remove).

### CLI Usage

```bash
smith --flag cross_validate          # generate report of mislabeled cases
smith --flag apply_cross_validate    # apply approved corrections
```

### Decisions

The cross-validation report can suggest three actions for each failed case:

- **Move** — relocate to the correct allow/disallow folder
- **Remove** — delete ambiguous or invalid test cases
- **Keep** — the case is correctly labeled (policy bug, not label bug)
