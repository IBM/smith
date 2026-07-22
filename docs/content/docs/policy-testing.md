---
title: "Policy Testing"
weight: 7
---

# Policy Testing

Evaluate the current policy against all test cases and report pass/fail with coverage metrics.

## CLI Usage

```bash
smith --flag policy_testing
```

## How It Works

The harness starts an OPA server with `assets/policy.rego` and curls `localhost:8181/v1/data/mcp/policies/allow` for every JSON case under `references/test_cases/{allow,disallow}/`.

- A case in `disallow/` is expected to return `allow: false`
- A case in `allow/` is expected to return `allow: true`

## Output

Results land in `references/scorecard/`:

- `scorecard_summary.txt` — overall pass/fail metrics
- `score_test_failures.txt` — list of failed cases
- `tp.txt`, `fp.txt`, `tn.txt`, `fn.txt` — breakdown by category

## OPA Server Management

```bash
make opaserver/start    # start OPA server on :8181 with assets/policy.rego, policy_testing will automatically start it
make opaserver/restart  # restart the OPA server
make opaserver/status   # show whether the OPA container is running
make opaserver/stop     # stop the OPA server
```
