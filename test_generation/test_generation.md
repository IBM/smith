# Test Case Generation

## Step 0: Ask which kind of test cases to generate

Before running anything, ask the user what they want to generate:

1. **Guidance-targeted cases** — legitimate + adversarial cases derived from the target agent and its guidance (broad coverage of the guidance surface).
2. **Policy-bypass cases** — adversarial cases that specifically target divergences between the guidance and the **current policy** (`./assets/policy.rego`) **Remind user that it requires an existing, non-empty policy.**
3. **Both.**

Ask: "What kind of test cases would you like? (1) Guidance-targeted cases, (2) policy-bypass cases (requires a policy to already exist), or (3) both?"

Based on the answer, run the generation command(s) below, then proceed to Translation and Evaluation, which are the same regardless of which kind was generated.

## Step 0a: Offer to refresh the promptfoo config

Only ask this if promptfoo is enabled (`ATTACK_TOOLS` includes `promptfoo`). Skip it entirely otherwise.

Ask: "Your promptfoo config drives the red-team cases. Would you like me to regenerate it from your current guidance before generating test cases?"

If the user says yes, run it yourself:

```bash
smith --flag generate_promptfoo_config
```

Then tell the user where the config was written and that they should review it before generating — it is LLM-generated, and the `contexts` block in particular is worth a look.

If the user says no, continue with the existing config as-is.

## Step 0b: Ask fresh or update (guidance-targeted cases only)

Only ask this if the user chose (1) guidance-targeted or (3) both. Policy-bypass generation has no modes.

Ask: "Fresh or update? **Fresh** regenerates from your whole guidance file. **Update** compares your guidance against the snapshot from the last run and only regenerates the lines you changed, leaving every other test case untouched."

## Generation

### Guidance-targeted cases
If the user chose fresh mode, run: 
```bash
smith --flag test_generation --mode fresh
```

If the user choose update mode, run: or, 
```bash
smith --flag test_generation --mode update
```

### Policy-bypass cases

```bash
smith --flag bypass_case_generation
```

### Both

Run guidance-targeted generation first, then bypass generation:

```bash
smith --flag test_generation
smith --flag bypass_case_generation
```

All results are stored in `./references/test_cases/`

## Test Case Translation

After generation, translate the test cases into OPA input format. This is the same for every kind of case, since they all land in `./references/test_cases/`:

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
