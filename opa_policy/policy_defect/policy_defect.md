# Policy Defect Introduction

Introduces intentional defects into the policy for testing the refinement workflow. Output goes to `<TARGET_AGENT_PATH>/smith/policy_defect.rego`, leaving `./assets/policy.rego` untouched.

---

## Workflow

1. Copy `./assets/policy.rego` to `<TARGET_AGENT_PATH>/smith/policy_defect.rego`

2. Introduce defects (DO NOT add label or anotations for defected rules, such as comments that include words: "DEFECT", "DUPLICATE", "ADDITIONAL", "ISOLATED", in the policy):
   - **Missing rules** — remove or weaken 1–2 deny rules so some cases produce mixed pass/fail
   - **Duplications** — duplicate an existing rule with a different name; add an isolated block that can never trigger
   - **Linting issues** — use `==` instead of `:=`, add unused variables, omit `if` keyword, add inconsistent indentation

3. Validate it still compiles:
   ```bash
   smith --flag policy_validation --policy_path <TARGET_AGENT_PATH>/smith/policy_defect.rego
   ```

4. Save defect details to `<TARGET_AGENT_PATH>/smith/defect_summary.txt`

5. Remind user: "Defective policy at `<TARGET_AGENT_PATH>/smith/policy_defect.rego`. Make sure do not add DEFECT labels or annotations in the policy. Copy to `./assets/policy.rego` and run policy testing to exercise the refinement workflow."

---

## Rules

- Never modify `./assets/policy.rego` directly
- Defective policy must still compile
- Do not add DEFECT labels or annotations in the policy, make sure the policy looks like a normal policy. 
- Do not modify test cases
