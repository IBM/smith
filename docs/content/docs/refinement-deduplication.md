---
title: "Deduplication"
weight: 13
---

# Deduplication

Detect and remove redundant policy rules using a combination of graph analysis and LLM review, with a confidence-based voting system.

## CLI Usage

```bash
smith --flag duplication_suggestion  # get suggestions
smith --flag policy_testing          # verify after changes
```

## Workflow

### 1. Baseline

Run `smith --flag policy_testing` and record FP, FN, coverage, and policy line count.

### 2. Get Duplication Suggestions

Run `smith --flag duplication_suggestion`, which produces two types of results:

| Source | What it finds |
|--------|---------------|
| **LLM-generated** | Three types of semantic duplication (equivalent logic, overlapping conditions, subsumed rules) |
| **Graph-based** | Unreachable or dead policy parts identified from the AST graph |

### 3. Confidence Assessment

Compare results from both sources to determine confidence:

| Overlap | Confidence | Action |
|---------|------------|--------|
| Both LLM and graph flag the same duplication | **HIGH** | Fix first |
| LLM-only | MEDIUM/LOW | Fix only if clearly safe |
| Graph-only unreachable | MEDIUM/LOW | Fix only if clearly safe and doesn't break allow/deny logic |

The agent also independently evaluates whether flagged duplications are truly redundant.

### 4. Apply Safe Improvements

- Fix HIGH-confidence duplications first
- Only fix MEDIUM/LOW confidence if it clearly does not change semantics
- After each batch of edits, run `smith --flag policy_testing`:
  - `FP_new` must be ≤ `FP_base`
  - `FN_new` must be ≤ `FN_base`
  - If either increases, revert the entire batch
  - Prefer: coverage stays the same or improves, line count decreases

### 5. Report

Present a summary:
- Policy line count: before → after
- FP: before → after
- FN: before → after
- Coverage: before → after
- Which suggestions were fixed and their confidence level
- Which were skipped and why

## Rules

- Never increase FP or FN
- Make small, reversible changes
- Overlapping LLM + graph duplication = highest priority and most reliable
- Be cautious with LLM-only suggestions — verify semantics before applying
