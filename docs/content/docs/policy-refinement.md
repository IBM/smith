---
title: "Policy Refinement"
weight: 10
---

# Policy Refinement

Iterative improvement workflow that patches, formats, and deduplicates the policy. The prescribed order is:

1. **[Red Feedback Patching]({{< relref "/docs/refinement-patching" >}})** — Cluster failed adversarial inputs and patch policy rules to block each bypass category
2. **[Regal Formatting]({{< relref "/docs/refinement-regal" >}})** — Lint and format the policy with Regal, applying style and best-practice improvements
3. **[Deduplication]({{< relref "/docs/refinement-deduplication" >}})** — Detect and remove redundant rules via graph analysis and LLM review

## Related CLI Commands

```bash
# The following CLI commands are used in refinment skill to provide feebacks
smith --flag red_suggestion           # cluster failed test cases
smith --flag regal_suggestion         # get Regal suggestions
smith --flag duplication_suggestion   # get LLM and graph deduplication suggestions
```

## Shared Principles

All three refinement steps follow these rules:

- **Never increase FP or FN** — every change is tested and rolled back if it causes regressions
- **Minimal changes** — prefer editing existing logic over large refactors
- **Human approval** — the agent asks before applying changes (patching requires per-cluster approval)
- **Test after every change** — run `smith --flag policy_testing` to verify
