## Details steps:

### Tools it can use
- `smith --flag regal_suggestion`: analyze the current policy and return formatting / style / structure / best-practice suggestions, and document links to explain that kind of suggestion.
- `smith --flag policy_testing `: run the full test pipeline and return:
  - number of false positives (FP)
  - number of false negatives (FN)
  - test coverage
  - any other quality metrics the tool provides

### Workflow (follow strictly):

1. Baseline check BEFORE any change
   - Run `smith --flag policy_testing `. Parse and remember: FP count, FN count, coverage and the current policy line count.

2. Get Regal suggestions
   - Call the Regal tool on the current policy to get suggestions. Each suggestion was paired with the link of its document.

3. Propose and apply policy improvements
   - Based on the Regal suggestions you selected:
     - you must search the documentation based on the link of its documents to understand what the suggestion means, why it is raised, and how to correctly fix it according to Regal best practices. If you think any suggestion is wrong, skip this suggestion
     - Propose concrete edits to the policy (which files, which rules, what changes).
     - Apply ONLY minimal and safe changes at a time; avoid large refactors.
   - Make the changes using small, reviewable diffs.

4. Run tests AFTER the change. Run `smith --flag policy_testing ` again. Parse the new FP/FN counts and coverage. Compute the new policy line count.

5. Safety check on quality
   - Compare BEFORE vs AFTER:
     - FP_new <= FP_old
     - FN_new <= FN_old
   - If FP or FN increased:
     - Roll back the last change (or undo the risky part).
     - Clearly explain which change caused the regression and why it was reverted.
     - Return to step 2 or stop if no safe changes can be applied.

6. Report results to the user
   - Always present a clear summary including:
     - Policy line count:
       - Before: XX lines
       - After:  YY lines
     - Test metrics:
       - FP: before → after
       - FN: before → after
       - Coverage: before → after

## General principles:
- Never intentionally increase FP or FN.
- Prefer smaller, incremental changes.
- When you run `opa fmt`, do NOT print or paste the formatted policy into the chat. Instead, rewrite the file directly using `opa fmt assets/policy.rego > assets/policy.rego` (or any equivalent write-to-file method).  
- Never change the high-level allow/deny semantics unless explicitly instructed.
- If you cannot safely improve the policy using Regal suggestions without increasing FP/FN, explain why and stop.
