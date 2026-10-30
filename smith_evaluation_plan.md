# Smith Evaluation

This reports the evaluation results.
Each section below answers exactly one RQ with the numbers a run produced. 

## Run details

| | |
|---|---|
| **Completed** | 2026-10-30 (runs of 2026-10-28/20/30) |
| **Smith version** | 0.2.1 |
| **Machine** | macOS 15.6.1, Apple silicon (arm64) |
| **Python** | 3.12.9 |
| **OPA** | 1.10.1 |
| **Pipeline model** | M2 — Claude 5 Sonnet (`aws/claude-sonnet-5`) |
| **Target-agent model** | Claude 4.5 Haiku (`aws/claude-haiku-4-5`), via `INFERENCE_MODEL` |
| **Harness** | `tests/run_smith_pipeline.py`, steps 1–10, one invocation per step |
| **Artifacts** | `baseline/<agent>/step<N>/`, per-step logs and CSVs under `baseline/<agent>/logs/` |

Detailed commands and how the numbers were counted please refer to `example.md`. Each
step prints its own table and writes the same figures as CSV beside the run's logs
(`suite_composition.csv`, `translation_funnel.csv`, `policy_score.csv`,
`cross_validation.csv`, `patch_effect.csv`, `regal_effect.csv`,
`duplication_effect.csv`). 

| RQ | Question  | Section |
|----|----------|---------|
| RQ1 | Does Smith produce a valid initial policy from the guidance? | [Policy creation](#rq1--policy-creation) |
| RQ2 | Does Smith generate a useful suite of legitimate and adversarial cases? | [Test case generation](#rq2--test-case-generation) |
| RQ3 | Are the generated labels correct enough to serve as ground truth? | [Label validation](#rq3--label-validation) |
| RQ4 | Does refinement improve the policy without regressing or bloating it? | [Refinement loop](#rq4--refinement-loop) |
| RQ5 | Is the automation cheap enough to be practical? | [Cost](#rq5--cost) |
| RQ6 | Does the security analysis stage add requirements the guidance never contained? | [Security enhancement](#rq6--security-enhancement) |
| RQ7 | Does refinement recover a policy whose defects were introduced deliberately, and what does that cost? | [Defected policy](#rq7--refinement-and-cost-on-a-seeded-defect-policy) |

**Dependency order.** RQ3 produce the validated suite that RQ1 and RQ4 are scored against.

## Evaluation Setup

### Agent datasets

We use the five agent examples as the benchmark. They have different formats for guidance, different mcp tools:

| Agent | Guidance lines | MCP tools | Domain |
|-------|---------------:|----------:|--------|
| `A1: RagChatbot_MCPServer` | 14 | 12 | HR RAG chatbot |
| `A2: hr-agent` | 5 | 6 | HR agent |
| `A3: call-for-papers-mcp` | 29 | 1 | Conference CFP |
| `A4: car-price-mcp-main` | 33 | 3 | Car-price lookup |
| `A5: employee` | 31 | 33 | Employee hub |

The **MCP tools** column counts only valid, agent-exposed tools (functions registered as MCP tools), excluding internal helper functions and any commented-out/disabled tool definitions.

The **Guidance lines** column counts non-empty lines in each agent's `smith/guidance.txt`. Blank separator lines are excluded. 

### Model settings

Smith uses two distinct LLM roles, which we configure independently:

- **Target-agent model** — the model *inside* the agent. By default the target agent runs `aws/claude-haiku-4-5`.

- **Pipeline model** — the model that runs every Smith
  generation/analysis stage (guidance decomposition, test-case generation, label
  validation, policy patching, deduplication). This is the model whose capability we vary.

| Setup | Pipeline model | 
|-------|--------------------------|
| M1 (old) | Claude 4.5 haiku | 
| M2 (mid) | Claude 5 Sonnet | 
| M3 (new) | Claude 5 opus | 

Varying the pipeline model while holding the scaffolding fixed is what separates
Smith's contribution from the underlying model's capability. 

### Parameter settings

| Parameter | Value | Role |
|-----------|-------|------|
| `TEMP` (temperature) | 0.2 | low-variance, near-deterministic generation |
| `CLUSTER_EPS` / `CLUSTER_MIN_SAMPLES` | 0.3 / 2 | DBSCAN clustering of failed cases in refinement |

### Evaluation metrics

- **TP / TN / FP / FN** — scorecard outcome per test case. 
- **Coverage** — fraction of coverable policyy lines reached by existing test cases.
- **Policy lines** — length of `policy.rego`.
- **Tokens** — per stage, per agent.



## RQ1 — Policy creation

*Does Smith produce a valid initial policy from the guidance?*

**Claim under test.** A policy can be well-formed Rego and still encode the wrong
rule, so validity and faithfulness are separate failures and are measured separately.

**Steps**
- Run `step1: policy_creation` per agent.
- Check whether `opa fmt` / `validation` passes, and count the automatic fix iterations
  needed to reach a satisfied policy.
- Score the **initial** policy, before any refinement, against the RQ3-validated
  suite via the scorecard.

**Table**

| Agent | opa fmt passes | Auto-fix iterations | TP | TN | FP | FN | Coverage | Policy lines |
|-------|:--------------:|--------------------:|---:|---:|---:|---:|---------:|-------------:|
| `A1` | Y| 0| 32| 18| 2| 4| 73.8%| 157|
| `A2` | Y| 0| 26| 20| 0| 8| 94.4%| 77|
| `A3` | Y| 0| 45| 9| 0| 2| 92.6%| 126|
| `A4` |Y | 0|112 | 125| 0| 10| 100%| 108|
| `A5` |Y | 1| 73| 73| 0| 1| 100%| 121|

---

## RQ2 — Test case generation

*Does Smith generate a useful suite of legitimate and adversarial cases?*

**Claim under test.** we asserts that a comprehensive suite needs
legitimate, adversarial, and policy-based bypass cases together, and that existing
red-teaming frameworks supply only the prompt-level kind. 

The test datasets are **not hand-curated**: they are produced by Smith's own
test-case generation phase. For each agent we therefore report the exact composition
of the generated suite.

**Steps**
- Run `Step2: test_generation` per agent (legitimate allow/disallow, Promptfoo based adversarial cases).
- Run `bypass_case_generation` to synthesize cases from guidance-vs-policy
  divergences.
- Report composition by provenance, one table per model setting.

**Table (suite composition, one per model setting M1/M2/M3)**

| Agent | Legit. allow | Legit. disallow |Adv. bypass | Adv. Promptfoo | Total |
|-------|-------------:|------------:|------------:|---------------:|------:|
| `A1` | 21 |53  | 16 | 6 |96  | 
| `A2` | 18 |  18| 12 | 10 | 58 | 
| `A3` | 14 | 49 | 6 | 8 | 77 | 
| `A4` | 134 | 121 | 12 | 10 | 277 | 
| `A5` | 78 | 60 | 12 | 6 | 156 | 

---

## RQ3 — Label validation

*Are the generated labels correct enough to serve as ground truth?*

**Claim under test.** This is load-bearing: every number in RQ2 and RQ5 is computed
against this suite, and a refinement loop that patches to satisfy mislabeled cases
degrades the policy while reporting success. No existing generation tool validates
its own labels.

**Steps**
- Run `Step3: translation` to translate each test case to CMF.
- Run `Step4: policy testing` to obtain failed test cases.
- Run `Step 5: cross validation` on failed cases, it will diagonosis labels and `apply_cross_validate`.

**Metrics**
- Initial generated case count.
- Removed by tool-name mismatch (translation phase).
- Removed or corrected by cross-validation.
- Final count.

**Table (filtering funnel and accuracy)**

| Agent | Initial generated | Removed (tool-name mismatch, translation phase) | Removed(cross-validation, from disallow+from allow)| corrected (cross-validation, moved to disallow+moved to allow) | Final | 
|-------|------------------:|-----------------------------:|-----:|-------------------------------------:|------:|
| `A1` |96 |16+21 |3+0 | 1+1| 56| 
| `A2` |58 | 1+0| 3+0| 1+1| 54| 
| `A3` | 77| 0+20| 1+0| 5+0| 56|
| `A4` | 277| 3+23| 2+2| 10+4| 243|
| `A5` |156 |1+7 | 1+0| 8+0| 147|

---

## RQ4 — Refinement loop

*Does refinement improve the policy without regressing or bloating it?*

**Claim under test.** The approach claims Smith detects and fixes all three defect
classes: failed test cases, formatting violations, and duplicated rules. Patching a
failing cluster is also the operation most likely to break a neighbouring case, so
improvement must be shown without regression or unbounded growth.
Notice that, the failed-case patching can also identify mislabeled cases by itseif, which provides addtional guratees beside the cross validation phase. 

**Steps**
- Start from initial policy and validated suite.
- Run `Step 4: policcy testing` to report initial results in RQ1. 
- Run the refinement contract: `Step 6: patching` (cluster failed cases) → red_suggestion → patch →
  `Step 7: regal_suggestion` → `Step 8: duplication_suggestion`.

**Table (failed-case patching)**

| Agent | #cluster(before → after) |FP (before → after) | FN (before → after) | Policy lines (before → after) | Coverage (before → after) |
|-------|:-------------------:|-----:|:-------------------:|:-----------------------------:|:-------------------------:|
| `A1` |2/0 |2/0 |4/0 |157/177 |73.8%/79.4% | 
| `A2` |3/0 | 0/0|8/0 | 77/95| 94.4%/95.7%| 
| `A3` |1/0 | 0/0| 2/0|126/130 | 92.6%/92.9%| 
| `A4` |3/0 | 0/6*|10/0 | 53/54| 100%/100%|   #note the 6 are identified mislabeled during patching. 
| `A5` |1/0 |0/0 |1/0 | 121/138| 100%/98.4%| 

**note1: passed cases usually make more test cases testable and increase the coverage rate, it is not always certain and also depends on which lines the model added to solved failed test cases**

**note2: In A4, the model introduced 6 false positives, these cases are originally generated as benign cases, but during patching, model identified them as mislabeled cases so it choose to not patch for them.**

**Table (linting and duplication)**

| Agent | Linting problems fixed | Duplication problems fixed | Failing cases introduced | Policy lines (before → after linting -> after duplication) | Coverage (before → after linting -> after duplication) |
|-------|-----------------------:|-----------------------:|-----------------------:|---:|---:|
| `A1` |2 |0 | 0| 177/177/177| 79.4%/79.4%/79.4%|
| `A2` |1 |1 | 0|95/95/100 | 95.7%/95.7%/95.9%| 
| `A3` |5 |0 | 0|130/133/133 |92.9%/93.0%/93.0% |
| `A4` |3 |0 |0 |112/117/117 |100%/100%/100% |
| `A5` | 5|0 |0 |138/136/136 |98.4%/98.4%/98.4% |

**note3: In A2, the policy lines increases after deduplication, which is correct. The policy is behaviourally identical and conceptually less redundant, at the cost of 5 lines (rather than remove one rule, the model makes them identical). Whether that counts as success depends on what we are measuring, redundant evaluation paths went down, coverage went up, textual size went up.**



## RQ5 — Cost

*Is the automation cheap enough to be practical, and where is the cost concentrated?*

**Claim under test.** Automation costing more than hand-writing the policy is a
curiosity rather than a tool.

**Metrics.** Total tokens per stage × agent. Reported per model setting, since cost
and capability trade off against each other.

**Table (tokens per stage)**

| Agent |  Policy generation (step 1) | Test generation (step 2,3) | Label validation (step 4,5) | Policy testing (step 4)| Policy patching (step 6) | Regal linting (step 7) | Duplication (step 8) |Security analysis (step 9) | Total |
|-------|------------------:|------------------:|----------------:|-----------------:|----------------:|--------------:|------------:|------:|------:|
| `A1` |533,096 |72,354+79,448 |85,860+98,074 | 104,980| 3,354,414| 2,324,819| 894,541| 2,090,517| 9,639,345|
| `A2` |562,994 |213,050+151,591 | 323,776+359,013|301,232 | 253,983|2,466,371 |2,116,601 | 24,245,004|31,003,339 |
| `A3` |604,333 |215,073+233,559  |249,992+362,916  | 300,263 |229,220 |3,969,814 |2,962,109 |16,192,943 |25,328,188 |
| `A4` |633,087 | 226,620+249,748| 271,809+723,747|227,887 | 727,835|335,866 |875,663 |20,897,371 | 25,169,633|
| `A5` | 1,351,871|271,996+291,242 |412,152+572,489 |3,372,273 | 424,838|480,637 | 1,520,897| 28,178,383| 33,886,310|

---

## RQ6 — Security enhancement

*Does the security analysis stage add correct requirements the guidance never contained?*

**Claim under test.** Limitation I asserts that guidance is a product document rather
than a threat model, so requirements originating in security standards are absent by construction. The stage is worth running only if the requirements it proposes are new
rather than restatements of what the prose already said.

**Steps**
- Run the `Step 9: guidelines security analysis` per agent.
- Record guidance length before and after the stage.
- For each agent, identify the requirement its prose was missing.

**Table (guidance growth)** #note: no added guidance

| Agent | Guidance lines (before) | Guidance lines (after) | Added | 
|-------|------------------------:|-----------------------:|------:|
| `A1` | 14 |  14|  0|
| `A2` | 5 | 5 | 0 | 
| `A3` | 29 | 29 | 0 |
| `A4` | 33 | 33 | 0 | 
| `A5` |  31| 31 | 0 |

**note 4: no security enhanchment for current guidancies**
---

## RQ7 — Refinement and cost on a seeded-defect policy

**Claim under test.** RQ4 scores refinement against whatever defects Smith's own
generation happened to leave behind, so the policy can be perfect: have no failed cases/linting issues/duplication e.g., `A1` , which makes its
"0 fixed" uninterpretable rather than good. 
Seeding defects fixes the denominator:
each class is present by construction. This RQ is reported separately.

**Steps**
- Copy the defective policy over `assets/policy.rego` and re-run steps 4–9 against
  the unchanged suite, reporting the same two tables RQ4 does so the columns can be
  read side by side.

**Table (failed-case patching)**

| Agent | #cluster(before → after) |FP (before → after) | FN (before → after) | Policy lines (before → after) | Coverage (before → after) |
|-------|:-------------------:|-----:|:-------------------:|:-----------------------------:|:-------------------------:|
| `A1` | 4/0| 0/0| 25/0| 141/150| 47.4%/75.3%|
| `A2` | 3/0| 0/0| 8/0| 100/127| 87.2%/90.0%|
| `A3` |3/0 |0/0 |15/0 | 147/156|81.8%/84.9% |
| `A4` |8/0 |0/0 |29/0 |127/137 |91.8%/94.1% |
| `A5` |2/0 | 0/0|6/0 |141/157 |89.6%/90.9%|

**Table (linting and duplication)**

| Agent | Linting problems fixed | Duplication problems fixed | Failing cases introduced | Policy lines (before → after linting -> after duplication) | Coverage (before → after linting -> after duplication) |
|-------|-----------------------:|-----------------------:|-----------------------:|---:|---:|
| `A1` |5 | 1+0| 0|150/151/144 |75.3%/75.3%/73.7%|
| `A2` |5 | 1+1| 0| 127/126/118| 90.0%/89.8%/96.4%|
| `A3` |1 | 1+1| 0| 156/156/145| 84.9%/84.9%/90.0%|
| `A4` |2 | 2+0| 0| 137/137/118| 94.1%/94.1%/98.2%|
| `A5` |5 | 0+1| 0| 77/73/67|90.9%/90.4%/98.5% |

**note 5: why the coverage decreases in A1: Because the duplicate it removed was fully covered by tests
Coverable lines: 
before:  61 / 81 = 75.3%
after:   56 / 76 = 73.7%
Both numbers dropped by exactly 5 — so all 5 removed lines were covered. Taking fully-tested code out of a policy that's only 75% covered pulls the ratio down.**