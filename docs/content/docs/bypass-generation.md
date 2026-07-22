---
title: "Bypass Generation"
weight: 6
---

# Bypass Test Case Generation

Standard [test generation]({{< relref "/docs/test-generation" >}}) derives cases from the guidance alone. Bypass generation is complementary: it analyzes the **current policy against the guidance** to find where they diverge, then synthesizes adversarial cases that target each gap.

## Overview

A generated or hand-written policy can silently fail to enforce a rule — a guard that skips when a field is omitted, a numeric comparison with no type check, a substring match a malformed value slips past. Guidance-derived cases rarely probe these implementation-level weaknesses because they describe *intent*, not the policy's *code*.

Bypass generation closes that gap in three steps:

1. **Detect** — An LLM reads the full Rego policy together with the guidance, tool definitions, and system variables, and reports every place the policy's composed allow/deny decision disagrees with what the guidance intends. Each divergence is classified by the mechanism that causes it (see below). *Why:* the policy text *is* the composed decision, so reasoning over it as a whole surfaces gaps that per-rule inspection misses.

2. **Synthesize** — Each divergence becomes one or more concrete abstract cases that exercise it. *Why:* a divergence is only useful as a test if it can be turned into a request the policy actually mis-decides.

3. **Convert** — Cases are written into `./references/test_cases/{allow,disallow}/` with a `bypass_test_case` prefix. *Why:* they land in the same folders as guidance-targeted cases, so the downstream steps ([translation]({{< relref "/docs/test-generation" >}}) and [policy testing]({{< relref "/docs/policy-testing" >}})) are identical — no separate flow to maintain.

## Prerequisites

Bypass generation compares against an existing policy, so a **non-empty** policy must exist at `assets/policy.rego`. If the policy is missing or empty, the step is skipped with a message — create a policy first (see [Policy Creation]({{< relref "/docs/policy-creation" >}})).

## CLI Usage

```bash
smith --flag bypass_case_generation
```

Because bypass cases share the downstream pipeline, a typical run is:

```bash
smith --flag test_generation          # guidance-targeted cases
smith --flag bypass_case_generation    # policy-bypass cases (requires an existing policy)
smith --flag test_case_translation     # shared; skips cases already translated
smith --flag policy_testing            # run all cases against the policy
```

## Divergence Mechanisms

Each detected divergence is classified by *how* the policy is evaded:

| Category | Description |
|----------|-------------|
| `omitted_field` | A rule references a field with no default / existence check, so omitting the field from the request evades the guard. |
| `type_confusion` | A numeric/boolean comparison without a type assertion, evadable by sending the value as a different type (e.g. a number as a string). |
| `malformed_value` | A substring/regex match on structured data (email, URL, path) that a malformed but accepted value slips past. |
| `keyword_evasion` | An exact keyword/substring match evadable by casing, splitting, spacing, or encoding. |

## Robust Detection

The detector expects the model to return a strict JSON array. If the model returns malformed JSON, the call is **retried** (up to `MAX_BYPASS_PARSE_ATTEMPTS`, default 3) with a notice on each retry. Only after all attempts fail does it report the failure and return an empty report — so a parse failure is never silently mistaken for "no bypasses found."

## Output

- **Divergence report** — `./references/bypass/bypass_report.json` (plus a human-readable `bypass_report.md`), listing each vector's category, direction, the guidance rule it contradicts, the policy rule(s) involved, an exploit strategy, and a severity.
- **Synthesized cases** — `./references/test_cases/{allow,disallow}/bypass_test_case*.json`.

## Handling Bypass Cases in Cross-Validation

Because bypass cases are adversarial probes, [cross-validation]({{< relref "/docs/cross-validation" >}}) treats them specially: if the auditor judges a `bypass_test_case*` (or `promptfoo_test_case*`) as anything other than `keep`, the action is collapsed to `remove` rather than relabeled — a failed malicious probe is discarded instead of being moved into `allow/`.
