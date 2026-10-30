# Smith Evaluation Plan

This plan implements the research questions stated in `motivation.tex`
(§Research Questions). Each section below answers exactly one RQ and reports the
metrics that RQ promises.

| RQ | Question | Limitation | Section |
|----|----------|-----------|---------|
| RQ1 | Does Smith produce a valid initial policy from the guidance? | I | [Policy creation](#rq1--policy-creation) |
| RQ2 | Does Smith generate a useful suite of legitimate and adversarial cases? | II | [Test case generation](#rq2--test-case-generation) |
| RQ3 | Are the generated labels correct enough to serve as ground truth? | II | [Label validation](#rq3--label-validation) |
| RQ4 | Does refinement improve the policy without regressing or bloating it? | III | [Refinement loop](#rq4--refinement-loop) |
| RQ5 | Is the automation cheap enough to be practical? | — | [Cost](#rq5--cost) |
| RQ6 | Does the security analysis stage add requirements the guidance never contained? | I | [Security enhancement](#rq6--security-enhancement) |
| RQ7 | Does refinement recover a policy whose defects were introduced deliberately, and what does that cost? | III | [Seeded-defect policy](#rq7--refinement-and-cost-on-a-seeded-defect-policy) |

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
Smith's contribution from the underlying model's capability. Every RQ1-RQ7 table is
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
| `A1` | Y| 0| 32| 18| 2| 4| 73.8%| 157|
| `A2` | Y| 0| 26| 20| 0| 8| 94.4%| 77|
| `A3` | Y| 0| 45| 9| 0| 2| 92.6%| 126|
| `A4` |Y | 0|112 | 125| 0| 10| 100%| 108|
| `A5` | | | | | | | | | |

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
| `A1` | 21 |53  | 16 | 6 |96  | 
| `A2` | 18 |  18| 12 | 10 | 58 | 
| `A3` | 14 | 49 | 6 | 8 | 77 | 
| `A4` | 134 | 121 | 12 | 10 | 277 | 
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

| Agent | Initial generated | Removed (tool-name mismatch) | Removed(cross-validation)| corrected (cross-validation) | Final | 
|-------|------------------:|-----------------------------:|-----:|-------------------------------------:|------:|
| `A1` |96 |16+21 |3+0 | 1+1| 56| 
| `A2` |58 | 1+0| 3+0| 1+1| 54| 
| `A3` | 77| 0+20| 1+0| 5+0| 56|
| `A4` | 277| 3+23| 2+2| 10+4| 243|
| `A5` | | | | | |

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
| `A1` |2/0 |2/0 |4/0 |157/177 |73.8%/79.4% | #note: passed cases increased the coverage rate
| `A2` |3/0 | 0/0|8/0 | 77/95| 94.4%/95.7%| 
| `A3` |1/0 | 0/0| 2/0|126/130 | 92.6%/92.9%| 
| `A4` |3/0 | 0/6*|10/0 | 53/54| 100%/100%|   #note the 6 are identified mislabeled during patching. 
| `A5` | | | | | | 

**Table (linting and duplication)**

| Agent | Linting problems fixed | Duplication problems fixed | Failing cases introduced | Policy lines (before → after linting -> after duplication) | Coverage (before → after linting -> after duplication) |
|-------|-----------------------:|-----------------------:|-----------------------:|---:|---:|
| `A1` |2 | 0| 0| 177/177/177| 79.4%/79.4%/79.4%|
| `A2` |1 | 1| 0|95/95/100 | 95.7%/95.7%/95.9%| #note: why fixing duplication makes the line increases? the coverage increases. 
| `A3` | 5|0 | 0|130/133/133 |92.9%/93.0%/93.0% |
| `A4` |3 |0 |0 |112/117/117 |100%/100%/100% |
| `A5` | | | | | |

<!-- The semantics argument holds. The agent reasoned that

subject-match ∪ body-match ∪ combined-match
  ==  subject-match ∪ body-match ∪ (combined-match AND NOT subject-match AND NOT body-match)

which is correct — excluding cases already covered by the earlier rules can't change the deny set. And it verified empirically: FP=0, FN=0, 54/54 passing, coverage 95.7% → 95.9%.

So the policy is behaviourally identical and conceptually less redundant, at the cost of 5 lines. Whether that counts as success depends on what you're measuring — redundant evaluation paths went down, textual size went up. -->

---

## RQ5 — Cost

*Is the automation cheap enough to be practical, and where is the cost concentrated?*

**Claim under test.** Automation costing more than hand-writing the policy is a
curiosity rather than a tool.

**Metrics.** Total tokens per stage × agent. Reported per model setting, since cost
and capability trade off against each other.

**Table (tokens per stage)**

| Agent |  Policy generation | Test generation | Label validation | Policy testing| Policy patching | Regal linting | Duplication |Security analysis | Total |
|-------|------------------:|------------------:|----------------:|-----------------:|----------------:|--------------:|------------:|------:|------:|
| `A1` |533096 |72354+79448 |85860+98074 | 104980| 3354414| 2324819| 894541| 2090517| 9639345|
| `A2` |562994 |213050+151591 | 323776+359013|301232 | 253983|2466371 |2116601 | 24245004|31003339 |
| `A3` |604333 |215073+233559  |249992+362916  | 300263 |229220 |3969814 |2962109 |16192943 |25328188 |
| `A4` |633087 | 226620+249748| 271809+723747|227887 | 727835|335866 |875663 |20897371 | 25169633|
| `A5` | | | | | | | | | |


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

**Table (guidance growth)** #note: no added guidance

| Agent | Guidance lines (before) | Guidance lines (after) | Added | 
|-------|------------------------:|-----------------------:|------:|
| `A1` | 14 |  14|  0|
| `A2` | 5 | 5 | 0 | 
| `A3` | 29 | 29 | 0 |
| `A4` | 33 | 33 | 0 | 
| `A5` |  | — | — |

**Case studies.** One per agent, naming the overlooked requirement and its threat
class, since the informative result is *which* class the author was blind to, not how many lines were added.

- A1 —
- A2 — 
- A3 —
- A4 —
- A5 —

---

## RQ7 — Refinement and cost on a seeded-defect policy

*Does refinement recover a policy whose defects were introduced deliberately, and
what does that cost?*

**Claim under test.** RQ4 scores refinement against whatever defects Smith's own
generation happened to leave behind, so the defect population is uncontrolled and can
be empty — `A1` had no linting and no duplication problems to fix, which makes its
"0 fixed" uninterpretable rather than good. Seeding defects fixes the denominator:
each class is present by construction, so detection becomes a recall measure.

This RQ is reported separately, and **its tokens are excluded from RQ5**, so the cost
in RQ5 remains the cost of producing and refining one policy from guidance. Mixing the
two would make neither figure reproducible.

**Steps**
- Start from the validated policy and suite RQ4 finished with.
- Run `-s 11`, which follows `opa_policy/policy_defect/policy_defect.md` to write
  `<TARGET_AGENT_PATH>/smith/policy_defect.rego` and a `defect_summary.txt` recording
  what it injected. Three classes are seeded: weakened or removed deny rules,
  duplicated and unreachable rules, and style violations. No `DEFECT`/`DUPLICATE`
  annotations are added, so refinement cannot pattern-match the seeds.
- Copy the defective policy over `assets/policy.rego` and re-run steps 4–9 against
  the unchanged suite, reporting the same two tables RQ4 does so the columns can be
  read side by side.
- Use `defect_summary.txt` to interpret them: it names what was seeded, so a class
  that stays unfixed is a miss rather than an absent defect.

**Table (failed-case patching)**

| Agent | #cluster(before → after) |FP (before → after) | FN (before → after) | Policy lines (before → after) | Coverage (before → after) |
|-------|:-------------------:|-----:|:-------------------:|:-----------------------------:|:-------------------------:|
| `A1` | 4/0| 0/0| 25/0| 141/150| 47.4%/75.3%|
| `A2` | 3/0| 0/0| 8/0| 100/127| 87.2%/90.0%|
| `A3` |3/0 |0/0 |15/0 | 147/156|81.8%/84.9% |
| `A4` |8/0 |0/0 |29/0 |127/137 |91.8%/94.1% |
| `A5` | | | | | |

**Table (linting and duplication)**

| Agent | Linting problems fixed | Duplication problems fixed | Failing cases introduced | Policy lines (before → after linting -> after duplication) | Coverage (before → after linting -> after duplication) |
|-------|-----------------------:|-----------------------:|-----------------------:|---:|---:|
| `A1` |5 | 1| 0|150/151/144 |75.3%/75.3%/73.7%| #note: why the coverage decreases? deny[msg] lines?
| `A2` |5 | 1+1 | 0| 127/126/118| 90.0%/89.8%/96.4%|
| `A3` |1 | 1+1| 0| 156/156/145| 84.9%/84.9%/90.0%|
| `A4` |2 | 2+0| 0| 137/137/118| 94.1%/94.1%/98.2%|
| `A5` | | | | | |