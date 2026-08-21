---
title: "Test Generation"
weight: 5
---

# Test Case Generation

The agent follows `test_generation/test_generation.md` to generate test cases through a multi-stage pipeline.

## Overview

Building a trustworthy test suite takes three stages, run in order:

1. **Generation** — Turn the guidance into a broad set of test cases: benign inputs that *should* be allowed or denied, plus adversarial inputs from red-teaming tools that try to bypass the rules. *Why:* a policy is only as good as the cases you test it against — this stage creates that coverage.

2. **Translation** — Resolve each case into a concrete tool call by asking the agent what tool and arguments the prompt actually triggers. *Why:* the policy is evaluated against real tool calls (`input.name`, `input.arguments.*`), not raw prompts. Translation grounds every case in what the agent would truly do, and drops cases that don't map to the expected tool.

3. **Evaluation** — Classify each case against a guidance rule and verify its allow/disallow label is correct. *Why:* generated labels can be wrong, and a mislabeled case makes a correct policy look broken (or hides a real gap). This stage cleans the labels so policy-testing results are meaningful.

The result is a labeled, tool-grounded test suite ready for [policy testing]({{< relref "/docs/policy-testing" >}}).

## Prerequisites

- If using Promptfoo red-teaming, ensure you have a `promptfooconfig.yaml` in place. You can generate one automatically with `smith --flag generate_promptfoo_config` (see [Promptfoo Configuration]({{< relref "/docs/promptfoo-config" >}})).
- If using the Policy Explorer UI with IR-generated specs, the explorer writes a `session_config.json` (configurable via `SESSION_CONFIG_FILE`) containing `use_ir` and `selected_tools`. When present, translation will filter out test cases targeting tools not in `selected_tools`.

## CLI Usage

```bash
smith --flag test_generation
```

## Pipeline Stages

1. **Decomposition** — Break guidance into testable atomic conditions
2. **Variable Extraction** — Identify system/mutable variables and their domains
3. **Grey Condition Extraction** — Identify ambiguous boundary conditions; user needs to manually approve candidate guidances from grey condition extraction and then merge them to clean space
4. **Legitimate and Adversarial Case Generation** — Create benign (allow and disallow) inputs that should pass the policy. Create adversarial inputs using red teaming tool. Finally, combine into structured test cases

The case generation stage now includes **target tool parameter definitions** in the LLM prompt, ensuring that generated test cases contain concrete values for all required tool parameters (rather than abstract placeholders).

## Red-Teaming Tools

Which tools are used is controlled by the `ATTACK_TOOLS` environment variable:

| Value | Behavior |
|-------|----------|
| `ares` | Run ARES only |
| `promptfoo` | Run Promptfoo only |
| `ares,promptfoo` | Run both (default) |
| `none` | Skip red-teaming entirely |

Both tools are optional — see [Quick Start]({{< relref "/docs/quickstart" >}}) for installation instructions.

If Promptfoo is selected, make sure you have configured the `promptfooconfig.yaml` file for your target agent. See the [Promptfoo Configuration]({{< relref "/docs/promptfoo-config" >}}) guide for instructions.

## Output

All results are stored in `./references/test_cases/`.

---

# Test Case Translation

Once cases are generated, they are resolved into concrete tool calls before evaluation.

```bash
smith --flag test_case_translation
```

Calls the agent's `/extract_tool_call` endpoint to resolve tool names and argument values for each test case. The agent receives the user prompt and user profile, and returns the resolved tool name and arguments, which are written back into the test case files.

- Cases where the returned tool name doesn't match the expected one are flagged as mismatches and moved to `./references/test_cases/wrong_cases/misclassified/`, detailed report will be stored in  `./references/test_cases/wrong_cases/miscalled_cases.json`.
- Cases labeled as "other" (general questions that don't invoke any tool) are moved to `./references/test_cases/wrong_cases/mcp_unrelated` for future guardrail features.
- The tool-name mismatch check now applies uniformly to **all** cases, including Promptfoo-generated ones (which are classified to a target tool via LLM before translation).
- **IR mode filtering:** When a `session_config.json` is present (written by the Policy Explorer UI) and contains a `selected_tools` list, `translate_case` filters out any test case whose resolved target tool is not in that list. This keeps the test suite focused on the subset of tools currently under review.

---

# Test Case Evaluation

```bash
smith --flag test_case_evaluation
```

### 1. Classify Promptfoo Cases

Match each Promptfoo red-team case to a specific guidance rule. Uses local embedding similarity (sentence-transformers) to retrieve top-N candidate guidances, then an LLM selects the most relevant one from the candidates.

### 2. Validate Labels

Verify that each test case's assigned label (allow/disallow) is correct using a three-tier approach, each tier assigns a confidence score:

- **Tier 1 (Rule-based)** — Fast pattern matching for clear-cut cases (e.g., bypass keywords)
- **Tier 2 (Embedding + NLI)** — Semantic similarity check; cases with high confidence and label agreement are resolved, others are escalated
- **Tier 3 (LLM Judge)** — Cases with low confidence or label disagreement from Tier 2 are judged by an LLM

### 3. Generate HTML Report

Produces an interactive report at `references/test_case_report.html`.

The report groups all test cases by guidance item, with condition sub-tabs. Cases are labeled by source (Generated, ARES, Promptfoo) and type (allow/disallow) with color coding.

To regenerate the HTML report standalone:

```bash
cd src/smith/test_case_evaluation/visualization
python build_report.py
```
