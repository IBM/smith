## Policy Delta Fix Skill

Uses delta measurements from `policy_delta_test.py` to identify exactly which
test cases are failing, diagnose the cause in `policy.rego`, apply a targeted
fix, and repeat until all allow and deny cases pass (100 % pass rate).

Requires `policy.rego` to be loaded on the OPA server and labelled test cases
to be present before starting.

### Authoritative Paths

- Input: `<mcp_server_dir>/policy_generation/policy.rego` (loaded on OPA server)
- Input: `<mcp_server_dir>/policy_generation/tests/` (OWASP-generated test cases, `/allow/` and `/deny/` sub-paths)
- Input: `<mcp_server_dir>/policy_generation/owasp_policy_guidelines.md` (to verify intended rule behaviour)
- Output: updated `<mcp_server_dir>/policy_generation/policy.rego` at 100 % pass rate

---

### Workflow (follow strictly)

---

#### STEP 1 — Establish baseline measurement

Run `smith --flag policy_delta` and save the result as the baseline:

```bash
smith --flag policy_delta \
    --policy_path <mcp_server_dir>/policy_generation/policy.rego \
    --test_cases_dir <mcp_server_dir>/policy_generation/tests \
    --delta_json <mcp_server_dir>/policy_generation/baseline.json
```

Record:
- Total test cases, allow cases, deny cases
- Current pass rate and fail rate
- The list of failing cases with their labels (expected allow / expected deny)

If pass rate is already 100 %: stop. No fix is needed.

---

#### STEP 2 — Classify each failing case

For every failing case, determine the failure type:

| Failure type | Symptom | Meaning |
|---|---|---|
| **False deny** | Expected ALLOW, got DENY | A deny rule is firing when it should not |
| **False allow** | Expected DENY, got ALLOW | No deny rule is firing when one should |

Group the failing cases by failure type before proceeding to STEP 3.

---

#### STEP 3 — Diagnose the cause

For each failing case:

1. Read the input JSON for the case.
2. Trace through `policy.rego` manually:
   - For a **false deny**: find which `deny[...]` rule fires for this input
     and identify the condition that is incorrectly true.
   - For a **false allow**: find which `deny[...]` rule should fire for this
     input and identify the condition that is not matching.
3. Cross-check the intended behaviour against `owasp_policy_guidelines.md`
   — the rule's condition and matching semantics are the ground truth.
4. State the diagnosis in one sentence before writing any fix:
   > "Rule X fires because condition Y evaluates to Z, but the spec says
   > it should only fire when ..."

Do not write a fix until the diagnosis is confirmed.

---

#### STEP 4 — Apply a targeted fix

Fix one rule at a time. For each diagnosed issue:

- **Condition too broad** (false deny): narrow the condition — add an
  additional guard, tighten a comparison, or adjust a set membership check.
- **Condition too narrow** (false allow): widen the condition — relax a
  guard, add a missing case, or extend a set.
- **Wrong matching semantics**: correct the operator or function to match
  the spec (exact vs substring vs numeric comparison).
- **Missing rule**: add the deny rule as specified in `owasp_policy_guidelines.md`.
- **Incorrect set contents**: update the set literal to match the spec's
  known values exactly.

Rules:
- Change only the rule(s) implicated by the diagnosis.
- Do not refactor, rename, or restructure unrelated rules.
- After editing, run `opa fmt -w` and `opa check` to confirm the file
  compiles cleanly before measuring.

---

#### STEP 5 — Measure delta

Re-run `smith --flag policy_delta` passing the previous run's JSON as `--previous`:

```bash
smith --flag policy_delta \
    --policy_path <mcp_server_dir>/policy_generation/policy.rego \
    --test_cases_dir <mcp_server_dir>/policy_generation/tests \
    --previous <mcp_server_dir>/policy_generation/baseline.json \
    --delta_json <mcp_server_dir>/policy_generation/run2.json
```

Interpret the output:

| Delta | Interpretation |
|---|---|
| Positive, fewer failures | Fix is working. Continue. |
| Zero | Fix had no effect on decisions. Re-diagnose. |
| Negative | Fix introduced a regression. Revert and re-diagnose. |

Update `--previous` to the latest run JSON on each subsequent measurement.

---

#### STEP 6 — Repeat until 100 %

Return to STEP 2 with the updated failing case list from the latest run.

Continue the diagnose → fix → measure cycle until the output shows:

```
Passed  : N  (100.0%)
Failed  : 0  (0.0%)
```

Both allow and deny cases must reach 100 % independently — a policy that
passes all allow cases but fails deny cases is not complete.

---

#### STEP 7 — Human review

Present:
1. The initial pass rate and the final pass rate.
2. A summary of every fix applied (one line per rule changed).
3. The delta at each iteration.

Log the final pass rate and the list of fixes applied, then continue automatically to the pipeline handoff step.

---

### Stopping conditions

| Condition | Action |
|---|---|
| 100 % pass rate on both allow and deny | Success — stop |
| A fix causes a regression and the original diagnosis was wrong | Revert, re-read spec, re-diagnose |
| A failing case contradicts `owasp_policy_guidelines.md` | Stop and ask the user — the test case or the spec may need updating |
| Three consecutive iterations with zero delta | Stop and report which cases are still failing — manual policy redesign is needed |
