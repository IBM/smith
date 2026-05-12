## Details steps:

### Tools it can use
- duplication_suggestion_generation: returns
  (1) three types of LLM-generated duplication suggestions,
  (2) graph-based unreachable / dead-policy parts (high-confidence redundancy).
- policy_testing: returns FP, FN, and coverage.

### Workflow (follow strictly):

#### STEP 1 — Baseline
1. Run `smith --flag policy_testing` and remember FP_base, FN_base, coverage_base, and policy line count.

#### STEP 2 — Get duplication suggestions
2. Run `smith --flag duplication_suggestion` tool.
3. Compare LLM suggestions and graph-based unreachable results.  
   - If both sources flag the same duplication → HIGH confidence (fix first).  
   - LLM-only → MEDIUM/LOW confidence, fix only if clearly safe.  
   - Graph-only unreachable → MEDIUM/LOW confidence, fix only if clearly safe and does not break allow/deny logics.
- You also need to think independently to decide if these duplication are real duplicates.

#### STEP 3 — Apply safe improvements
4. Plan small, minimal edits.  
   - Fix HIGH-confidence duplication first.  
   - Only fix MEDIUM/LOW confidence if it clearly does not change semantics.

5. After each small batch of edits:
   - Run policy_testing again → get FP_new, FN_new, coverage_new.
   - FP_new must ≤ FP_base, and FN_new must ≤ FN_base.  
     If not, revert the batch entirely.
   - Prefer coverage_new ≥ coverage_base and line count reduces.
     If coverage drops and uncertainty is high → revert.

#### STEP 4 — Final report
6. Show user:
   - Policy line count: before → after
   - FP: before → after
   - FN: before → after
   - Coverage: before → after
   - Which duplication suggestions were fixed and their confidence level
   - Which were skipped and why (risk / low confidence)

### General rules:
- Never increase FP or FN.
- Make small, reversible changes.
- Overlapping LLM + graph duplication = highest priority and most reliable.
- Be cautious with LLM-only suggestions; verify semantics before applying.
