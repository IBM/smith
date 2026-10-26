# Smith Evaluation Plan

This plan implements the research questions stated in `motivation.tex`
(§Research Questions). Each section below answers exactly one RQ and reports the
metrics that RQ promises.

| RQ | Question | Limitation | Section |
|----|----------|-----------|---------|
| RQ1 | Does Smith produce a valid initial policy from the guidance? | I | [Policy creation](#rq2--policy-creation) |
| RQ2 | Does Smith generate a useful suite of legitimate and adversarial cases? | II | [Test case generation](#rq3--test-case-generation) |
| RQ3 | Are the generated labels correct enough to serve as ground truth? | II | [Label validation](#rq4--label-validation) |
| RQ4 | Does refinement improve the policy without regressing or bloating it? | III | [Refinement loop](#rq5--refinement-loop) |
| RQ5 | Is the automation cheap enough to be practical? | — | [Cost](#rq6--cost) |
| RQ6 | Does the security analysis stage add requirements the guidance never contained? | I | [Security enhancement](#rq1--security-enhancement) |

**Dependency order.** RQ3 produce the validated suite that RQ1 and RQ4 are scored against.

## Evaluation Setup

### Agent datasets

We use the five agent examples as the benchmark. They have different formats for guidance, different mcp tools:

| Agent | Guidance lines | MCP tools | Domain |
|-------|---------------:|----------:|--------|
| `A1: RagChatbot_MCPServer` | 14 | 12 | HR RAG chatbot |
| `A2: hr-agent` | 5 | 6 | HR agent |
| `A3: employee` | 31 | 33 | Employee hub |
| `A4: call-for-papers-mcp` | 29 | 1 | Conference CFP |
| `A5: car-price-mcp-main` | 33 | 3 | Car-price lookup |

The **MCP tools** column counts only valid, agent-exposed tools (functions registered as MCP tools), excluding internal helper functions and any commented-out/disabled tool definitions.

The **Guidance lines** column counts non-empty lines in each agent's `smith/guidance.txt`; blank separator lines are excluded. `A3`, `A4` and `A5` use a sectioned format, so their counts include section headings (4, 8 and 7 respectively); their rule-bearing lines alone are 27, 21 and 26.

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
Smith's contribution from the underlying model's capability. Every RQ1-RQ5 table is
reported per model setting.

### Parameter settings

| Parameter | Value | Role |
|-----------|-------|------|
| `TEMP` (temperature) | 0.2 | low-variance, near-deterministic generation |
| `CLUSTER_EPS` / `CLUSTER_MIN_SAMPLES` | 0.3 / 2 | DBSCAN clustering of failed cases in refinement |

### Evaluation metrics

- **TP / TN / FP / FN** — scorecard outcome per test case. 
- **Coverage** — fraction of policy reached by existing test cases.
- **Policy lines** — length of `policy.rego`, reported as a reviewability proxy.
- **Tokens** — per stage, per agent.

---



## RQ1 — Policy creation

*Does Smith produce a valid initial policy from the guidance?*

**Claim under test.** A policy can be well-formed Rego and still encode the wrong
rule, so validity and faithfulness are separate failures and are measured separately.

**Steps**
- Run `policy_creation` per agent, from the RQ1-enhanced guidance.
- Check whether `opa fmt` / Regal passes, and count the automatic fix iterations
  needed to reach a parsing policy.
- Score the **initial** policy, before any refinement, against the RQ4-validated
  suite via the scorecard.

**Table**

| Agent | opa fmt passes | Auto-fix iterations | TP | TN | FP | FN | Coverage | Policy lines |
|-------|:--------------:|--------------------:|---:|---:|---:|---:|---------:|-------------:|
| `A1` | | | | | | | | |
| `A2` | Y | 0| 61 | 14| 1| 1| 96.721|144 |
| `A3` | | | | | | | | |
| `A4` | | | | | | | | |
| `A5` | | | | | | | | |

---

## RQ2 — Test case generation

*Does Smith generate a useful suite of legitimate and adversarial cases?*

**Claim under test.** Limitation II asserts that a comprehensive suite needs
legitimate, adversarial, and policy-based bypass cases together, and that existing
red-teaming frameworks supply only the prompt-level kind. 

The test datasets are **not hand-curated**: they are produced by Smith's own
test-case generation phase. For each agent we therefore report the exact composition
of the generated suite, for each model setting.

**Steps**
- Run `test_generation` per agent (legitimate allow/disallow, Promptfoo).
- Run `bypass_case_generation` to synthesize cases from guidance-vs-policy
  divergences.
- Report composition by provenance, one table per model setting.

**Table (suite composition, one per model setting M1/M2/M3)**

| Agent | Legit. allow | Legit. disallow |Adv. bypass | Adv. Promptfoo | Total |
|-------|-------------:|------------:|------------:|---------------:|------:|
| `A1` | — | — | — | — | — | 
| `A2` | 20 | 66 | 8 | 4 | 98 | 
| `A3` | — | — | — | — | — | 
| `A4` | — | — | — | — | — | 
| `A5` | — | — | — | — | — | 

---

## RQ3 — Label validation

*Are the generated labels correct enough to serve as ground truth?*

**Claim under test.** This is load-bearing: every number in RQ2 and RQ5 is computed
against this suite, and a refinement loop that patches to satisfy mislabeled cases
degrades the policy while reporting success. No existing generation tool validates
its own labels.

**Steps**
- Run `cross_validate` on failed cases, then `apply_cross_validate`.
- Manually verify a sampled subset of the final suite; report sample size.

**Metrics**
- Initial generated case count.
- Removed by tool-name mismatch.
- Removed or corrected by cross-validation.
- Final count, and accuracy under manual verification.

**Table (filtering funnel and accuracy)**

| Agent | Initial generated | Removed (tool-name mismatch) | Removed(cross-validation)| corrected (cross-validation) | Final | Accuracy |
|-------|------------------:|-----------------------------:|-----:|-------------------------------------:|------:|---------:|
| `A1` | | | | | | |
| `A2` | 98| 18|3 |4 |95| |
| `A3` | | | | | | |
| `A4` | | | | | | |
| `A5` | | | | | | |

Accuracy is reported on the final suite under manual verification of the sampled
subset, because cross-validation uses an LLM to check LLM-generated labels and the
manual sample is what bounds that circularity.

---

## RQ4 — Refinement loop

*Does refinement improve the policy without regressing or bloating it?*

**Claim under test.** The approach claims Smith detects and fixes all three defect
classes: failed test cases, formatting violations, and duplicated rules. Patching a
failing cluster is also the operation most likely to break a neighbouring case, so
improvement must be shown without regression or unbounded growth.

**Steps**
- Start from RQ2's initial policy and RQ4's validated suite.
- Run the refinement contract: `red_suggestion` (cluster failed cases) → patch →
  `regal_suggestion` → `duplication_suggestion`, re-running `policy_testing` after
  each step.

**Table (failed-case patching)**

| Agent | #cluster(before → after) |FP (before → after) | FN (before → after) | Policy lines (before → after) | Coverage (before → after) |
|-------|:-------------------:|-----:|:-------------------:|:-----------------------------:|:-------------------------:|
| `A1` | | | | | | 
| `A2` |4/0 | 0/0| 23/0| 147/163| 84.8/87.8|
| `A3` | | | | | | 
| `A4` | | | | | | 
| `A5` | | | | | | 

**Table (linting and duplication)**

| Agent | Linting problems fixed | Duplication problems fixed | Failing cases | Policy lines (before → after) | Coverage (before → after) |
|-------|-----------------------:|-----------------------:|-----------------------:|---:|---:|:-----------------------------:|---------:|
| `A1` | | | | | | |
| `A2` |2 | 1| | 163/163|87.8/87.8|
| `A3` | | | | | | |
| `A4` | | | | | | |
| `A5` | | | | | | |

---

## RQ5 — Cost

*Is the automation cheap enough to be practical, and where is the cost concentrated?*

**Claim under test.** Automation costing more than hand-writing the policy is a
curiosity rather than a tool.

**Metrics.** Total tokens per stage × agent. Reported per model setting, since cost
and capability trade off against each other.

**Table (tokens per stage)**

| Agent | Security analysis | Policy generation | Test generation | Label validation | Policy patching | Regal linting | Duplication | Total |
|-------|------------------:|------------------:|----------------:|-----------------:|----------------:|--------------:|------------:|------:|
| `A1` | | | | | | | | |
| `A2` | | | | | | | | |
| `A3` | | | | | | | | |
| `A4` | | | | | | | | |
| `A5` | | | | | | | | |


The expected result, that test generation dominates as the only stage scaling with
guidance line count, is worth confirming rather than assuming.

---

## RQ6 — Security enhancement

*Does the security analysis stage add correct requirements the guidance never contained?*

**Claim under test.** Limitation I asserts that guidance is a product document rather
than a threat model, so requirements originating in security standards are absent by construction. The stage is worth running only if the requirements it proposes are new
rather than restatements of what the prose already said.

**Steps**
- Run the guidelines security analysis per agent.
- Record guidance length before and after the stage.
- For each agent, identify the requirement its prose was missing.

**Table (guidance growth)**

| Agent | Guidance lines (before) | Guidance lines (after) | Added | 
|-------|------------------------:|-----------------------:|------:|
| `A1` | 13 | — | — |
| `A2` | 5 | — | — | 
| `A3` | 79 | — | — |
| `A4` | 45 | — | — | 
| `A5` | 49 | — | — |

**Case studies.** One per agent, naming the overlooked requirement and its threat
class, since the informative result is *which* class the author was blind to, not how many lines were added.

- A1 —
- A2 — expected: `adjust_compensation` is an unguarded write, as G1-G5 govern only
  reads. (This is the case `motivation.tex` uses.)
- A3 —
- A4 —
- A5 —