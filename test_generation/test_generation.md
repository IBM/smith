## Test Case Generation

To generate the test cases, run `smith --flag test_generation`.

All test generation results are stored in the `./references/test_cases` folder.

## Test Case Translation

To translate the test cases for OPA policy testing, run `smith --flag test_case_translation`.

It tranlates and then overwrites test cases in the `./references/test_cases` folder.

## Test Case Evaluation

To evaluate the quality of generated test cases, run `smith --flag test_case_evaluation`.

This performs three steps:
1. Classify promptfoo cases to match them to specific guidance rules
2. Validate all test case labels using a hybrid approach (Tier 1 rule-based detection + Tier 2 NLI semantic check + Tier 3 LLM judge for flagged cases)
3. Generate an HTML report

The final output is the report at `./references/test_case_report.html`.


