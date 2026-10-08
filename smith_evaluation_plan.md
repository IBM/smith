## Evaluation Setup

### Agent datasets

We use the five agent examples as the benchmark. They have different formats for guidance, different mcp tools:

| Agent | Guidance lines | MCP tools | Domain |
|-------|---------------:|----------:|--------|
| `A1: RagChatbot_MCPServer` | 13 | 12 | HR RAG chatbot |
| `A2: hr-agent` | 5 | 6 | HR agent |
| `A3: employee` (TBD, guidance needs modification) | 79 | 33 | Employee hub |
| `A4: call-for-papers-mcp` | 45 | 1 | Conference CFP |
| `A5: car-price-mcp-main` | 49 | 3 | Car-price lookup |

The **MCP tools** column counts only valid, agent-exposed tools (functions registered as MCP tools), excluding internal helper functions and any commented-out/disabled tool definitions.

### Model settings

Smith uses two distinct LLM roles, which we configure independently:

- **Target-agent model** — the model *inside* the agent. By default the target agent runs a local ollama qwen 3.5:latest model. 

- **Pipeline model** — the model that runs every Smith
  generation/analysis stage (guidance decomposition, test-case generation, label
  validation, policy patching, deduplication). This is the model whose capability we vary.

| Setup | Pipeline model | 
|-------|--------------------------|
| M1 (old) | Claude 4.5 haiku | 
| M2 (mid) | Claude 5 Sonnet | 
| M3 (new) | Claude 5 opus | 

(include gpt models)

### Parameter settings

| Parameter | Value | Role |
|-----------|-------|------|
| `TEMP` (temperature) | 0.2 | low-variance, near-deterministic generation |
| `top_k` | 40 | candidate-token cap (where the provider exposes it) |
| `max_tokens` | 4096 | per-call completion budget |
| `CLUSTER_EPS` / `CLUSTER_MIN_SAMPLES` | 0.3 / 2 | DBSCAN clustering of failed cases in refinement |

### Evaluation metrics

TN, TP, FN, FP, policy coverage, number of policy lines. 


## Evaluation

### Security enhanchement

| Agent | Original line of guidance | After line|
|-------|-------------:|----------------:|
| `A1` | — | — | — |
| `A2` | — | — | — |
| `A3` | — | — | — |
| `A4` | — | — | — | 
| `A5` | — | — | — |

**Case Study**
- A1
- A2
- A3
- A4
- A5

### Test case generation

The test datasets are **not hand-curated**: they are produced by Smith's own test-case
generation phase. For each agent we therefore report the exact composition of the generated suite, for each model setting. 

We distinguish **legitimate** cases from **adversarial** cases, and further split the
adversarial cases into three kinds by their source:

(three tables for three model setting)
| Agent | Legit. allow | Legit. disallow | Adv. native | Adv. bypass | Adv. Promptfoo | Total |
|-------|-------------:|----------------:|------------:|------------:|---------------:|------:|
| `A1` | — | — | — | — | — | — |
| `A2` | — | — | — | — | — | — |
| `A3` | — | — | — | — | — | — |
| `A4` | — | — | — | — | — | — |
| `A5` | — | — | — | — | — | — |

1. motivation section. (draft a few RQs, draft of an example)
2. script for each example (set of claude commands), open an issue for it. 


### Policy creation: does Smith produce a valid initial policy?

*Can Smith turn natural-language guidance into an enforceable OPA policy that matches the
guidance?*

**Steps** 
- Run `policy_creation` per agent; 
- Evaluate the **initial** policy (before any
  refinement) on the test suite via the scorecard.
- Evaluate if the opa fmt passes or not, how many steps needed to fix the gramar problem. 

**Table**
| Agent | TN | TP | FN | FP | Coverage | Policy lines | auto fix required?|
|-------|---:|---:|---:|---:|---------:|-------------:|:--------: |
| A1  |  |  |  |  |  |  |  |
| A2  |  |  |  |  |  |  |  |
| A3  |  |  |  |  |  |  |  |
| A4  |  |  |  |  |  |  |  |
| A5  |  |  |  |  |  |  |  |

### Test generation-cross validation

*Does Smith generate a useful legitimate + adversarial test suite?*

**Steps** 
- Run `test_generation` (legitimate allow/disallow + Promptfoo).

**Metrics**
  - Initial generated numbers of cases. 
  - Number of removed tool-name mismatches
  - Number of cross validation removed cases
  - Accuracy: Each test case either consistent with policy classification, or manually verified correctness. 

**Table (cross validation results)**

| Agent | Initial generated | Removed (tool-name mismatch) | Removed (cross-validation) | Final |Accuracy |
|-------|------------------:|-----------------------------:|---------------------------:|------:|------:|
| A1 | 1/2/3/4 |  |  |  |  |
| A2 |  |  |  |  |  |


**Table (policy testing)**
| Agent | TN | TP | FN | FP | Coverage | Policy lines |
|-------|---:|---:|---:|---:|---------:|-------------:|
| A1  |  |  |  |  |  |  | 
| A2  |  |  |  |  |  |  | 
| A3  |  |  |  |  |  |  | 
| A4  |  |  |  |  |  |  | 
| A5  |  |  |  |  |  |  | 


### Refinement loop: does iterative refinement improve the policy without regressing or bloating it?

**Defect step**

*Starting from the initial policy of RQ1 and the test suite of RQ2, does the refinement
contract turn a partially-correct policy into a correct one without breaking cases it
already handled or bloating the rule set?*

- **Setup.** Run the refinement contract: `red_suggestion` (cluster failed cases)
  → patch → `regal_suggestion` → `duplication_suggestion`, iterating `policy_testing` after each step. 

**Table for patching**

| Agent | FPs | FNs | Iterations | Policy lines | Coverage |
|-------|:--------------------------:|-----------:|------------:|:-----------------------------:|:----------------------:|
| A1 |    |  |  |    |   |
| A2 |    |  |  |    |    |

**Table for linting/duplication**
| Agent | FPs | FNs | # of linting problems | Policy lines | Coverage |
|-------|:--------------------------:|-----------:|------------:|:-----------------------------:|:----------------------:|
| A1 |    |  |  |    |    |
| A2 |    |  |  |    |    |

**Comparison with baseline**
| Agent | FPs | FNs | Policy lines | Coverage |
|-------|:--------------------------:|-----------:|------------:|:-----------------------------:|
| A1 |    |  |  |    |    |
| A2 |    |  |  |    |    |

### Time and resource costs

*Is the automation cheap enough to be practical, and where is the cost concentrated?*

- **Metrics.** For each stage × agent: **total tokens**

| Agent | Policy generation | Test case evaluation | Policy patching | Policy regal linting | Policy Duplication linting |
|-------|:--------------------------:|-----------:|------------:|:-----------------------------:|:-----------------------------:|
| A1 |    |  |  |    |    |
| A2 |    |  |  |    |    |
