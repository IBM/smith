## Test Case Generation

To generate test cases, run:

```bash
smith --flag test_generation
```

All results are stored in `./references/test_cases/`.

## Test Case Translation

After generation, translate the test cases into OPA input format:

```bash
smith --flag test_case_translation
```

This translates and overwrites test cases in `./references/test_cases/`.

## Test Case Evaluation (Optional)

Ask the user: "Would you like to evaluate the quality of the generated test cases? This produces an HTML report but does not affect policy testing. You can skip this step."

If the user wants to evaluate, run:

```bash
smith --flag test_case_evaluation
```

This generates an HTML report at `./references/test_case_report.html`.