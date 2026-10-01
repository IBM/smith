<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/IBM/smith/blob/main/docs/figures/smith_header-dark.png?raw=true">
  <img alt="Smith — Automated Policy Lifecycle Management for AI Agents" src="https://github.com/IBM/smith/blob/main/docs/figures/smith_header.png?raw=true" width="560">
</picture>

[![CI](https://github.com/IBM/smith/actions/workflows/ci.yml/badge.svg)](https://github.com/IBM/smith/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

An open skill for AI code agents that supports security-grounded guidance analysis and automates OPA policy creation, test generation, testing, and iterative refinement.

## What's Smith?

Smith is a skill (plugin) for AI code agents that manages the full lifecycle of [Open Policy Agent (OPA)](https://www.openpolicyagent.org/) policies (more types of policies will be supported). It enables agents to:

- **Analyze** MCP servers and guidance through an OWASP-mapped threat model and enforcement review without modifying a policy (experimental and in progress).
- **Create** OPA policies from natural language guidance and an agent description.
- **Generate** synthetic legitimate and adversarial test cases using LLM-based fuzzing and existing red-teaming tools, as well as policy-bypass cases that target divergences between the guidance and the current policy.
- **Test** policies against generated and custom test suites.
- **Refine** policies automatically through iterative feedback loops that patch policy rules in response to failed test cases, lint the policy, and remove duplicate rules.

```
Guidance (NLP) + Agent Description
   → [optional, experimental] Security-Grounded Guidance Analysis 
   → [separate human approval] Policy Creation
   → Test Case Generation 
   → Policy Testing ⇄ Policy Refinement
```

## What Smith Needs from You

1. **Guidance file** — A natural language description of your access control policies (e.g., "managers can only view compensation for their own team")
2. **Agent server with endpoints** — Your agent must expose:
   - `/chat` — Used by Promptfoo for red-teaming test generation
   - `/extract_tool_call` — Used to auto-detect MCP tool parameters and definitions from user prompts
3. **System variable file** — A JSON file listing the system variables available in your agent (e.g., roles, teams, claims)
4. **Keep both your agent server and MCP server running** during Smith's operation

## Deployment

1. Place the entire `smith` folder under the `skills/` or `plugin/` directory of your code agent (Claude Code, Bob, Aider, etc.). 

   For example, if your project is in `/my_project`, Smith goes to `/my_project/.claude/skills/`.

2. Start your coding agent from `/my_project`, for example, with `claude --model "your model"`. We used `claude-sonnet-5` for testing.

For instructions on using skills with different coding agents, see [Bob](https://bob.ibm.com/docs/ide/features/skills), [Claude](https://code.claude.com/docs/en/skills), and [Aider](https://aiderdesk.hotovo.com/docs/features/skills).

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package management)
- [OPA](https://www.openpolicyagent.org/) + [Regal](https://github.com/StyraInc/regal#getting-started) (policy testing / linting; OPA runs in Docker for the scorecard)
- [ARES](https://github.com/IBM/ares) (red-teaming framework) — **optional**
- [Promptfoo](https://www.promptfoo.dev/) (red-teaming framework) — **optional**

The `ATTACK_TOOLS` environment variable selects the red-teaming tools (see [Configuration](#configuration)). Set it to `none` to skip red-teaming. The default is `ATTACK_TOOLS=promptfoo`.

**1. Python environment**

```bash
python -m venv .venv
source .venv/bin/activate
```

**2. ARES** (optional red-teaming tool). Install it into `src/smith/test_generation/ares/` with its own `.venv`. The test-generation pipeline expects this layout because `src/smith/test_generation/attack.py` invokes `ares/.venv/bin/ares`:

```bash
cd src/smith/test_generation/ares
python -m venv .venv
source .venv/bin/activate
curl https://raw.githubusercontent.com/IBM/ares/refs/heads/main/install.sh | bash
ares install-plugin ares-autodan
ares install-plugin ares-human-jailbreak
ares install-plugin ares-garak
deactivate
# Setup ares configuration
cp ../ares_config/qwen-owasp-llm-01.yaml ./example_configs
cp ../ares_config/human_jailbreaks.json ./assets
export ARES_HOME=/absolute/path/to/smith/src/smith/test_generation/ares
# Switch back to the original Python environment
cd ../../../../
source .venv/bin/activate
```

**3. Promptfoo** (optional red-teaming tool)

```bash
npm install -g promptfoo
# To disable promptfoo remote connection:
export PROMPTFOO_DISABLE_TELEMETRY=1
export PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION=true
export PROMPTFOO_DISABLE_SHARING=true
```

### Install Smith

Smith uses [uv](https://docs.astral.sh/uv/) for package management. From the repo root:

```bash
make install        # creates a uv venv and installs Smith (editable) + dev tools
```

Or install directly (dependencies are declared in `pyproject.toml`):

```bash
uv pip install -e .   # or: pip install -e .
```

This installs the `smith` CLI command.


### Configuration

```bash
cd ..
cp .env_template .env
```

Fill in **every** placeholder value in `.env` before running Smith. The most important variables:

| Variable | Description |
|----------|-------------|
| `BASE_URL` | Absolute path to your skill folder, **with a trailing slash**, e.g. `/path/.bob/skills/smith/` |
| `OPENAI_API_KEY` | API key for your LLM provider |
| `OPENAI_BASE_URL` | Base URL for LLM API endpoint |
| `MODEL_SONNET` | Model used across the pipelines (e.g., `aws/claude-sonnet-4-6` by default) |
| `INFERENCE_MODEL` | Model name for the target agent's LLM (e.g., `qwen3.5:latest` for Ollama, or a RITS model name) |
| `ATTACK_TOOLS` | Comma-separated list of red-teaming tools to run during test generation. Valid values: `ares`, `promptfoo`, `ares,promptfoo`, `none`. Default: `promptfoo` |
| `ARES_HOME` | Absolute path to the ARES installation directory (e.g., `/path/to/smith/src/smith/test_generation/ares`). Only required when `ATTACK_TOOLS` includes `ares` |

See `.env_template` for the full list.

### Running the tests

```bash
make unit           # offline subset: no .env, no network, no Docker (run by `make ci`)
make integration    # stage-level tests driving the real smith CLI (opt-in)
```

`tests/integration/` holds both lanes — the pytest **marker** decides which runs, and a bare
`pytest` selects the unit lane. Most pipeline stages have a pair of modules,
Unit tests fake the
external boundaries and run against frozen fixtures; integration tests use the real services
and skip cleanly when one (Docker/OPA, an LLM, the example agent, ARES, Promptfoo) is absent.
If a pipeline stage just simply reads variables from .env or start an online server, a unit test is not needed. 

The separate `make test` target is the OPA policy scorecard, which scores the current
policy against your generated test cases rather than testing Smith itself.

## Start Smith with Agent Examples

Detailed instructions for each agent example can be found in the `examples/<agent>/README.md`.

Example layouts vary: an MCP server may use Python, JavaScript, or TypeScript;
may run over stdio, HTTP, or SSE; and may use entrypoint names such as
`server.py`, `mcp_server.py`, or `index.js`. Some targets also contain an agent
or UI, while standalone MCP servers may not. Follow the selected example's
README rather than assuming fixed filenames. 

## How Smith Works

Smith operates as an agent skill with a CLI backend. The AI agent reads instructions from `SKILL.md` and orchestrates the appropriate workflows by invoking the `smith` CLI or following embedded markdown guides.

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                                     Smith                                      │
│                                                                                │
│  SKILL.md ──→ Orchestration ──→ smith CLI                                      │
│                                       │                                        │
│              ┌────────────────────────┼───────────────────┬─────────┐          │
│              ▼                        ▼                   ▼         ▼          │
│         Policy              Test Case Generation       Policy     Policy       │
│         Creation                      │                Testing   Refinement    │
│              │        ┌──────────┬────┼─────┬────────┐    │         │          │
│              ▼        ▼          ▼          ▼        ▼    └────⇄────┘          │
│         OPA Policy Legitimate  ARES    Promptfoo  Bypass                       │
│         (.rego)        │        │          │        │                          │
│                        └────────┴─────┬────┴────────┘                          │
│                                       ▼                                        │
│                              Test Case Evaluation                              │
└────────────────────────────────────────────────────────────────────────────────┘
```

## Core Concepts

### Policy Creation

Create OPA policies from natural language specifications. The agent follows `opa_policy/policy_creation/opa_policy_creation.md` to generate a `.rego` policy file.

**Inputs** (located in `<TARGET_AGENT_PATH>/smith/`):
- `guidance.txt` — natural language policy rules
- `tool_definitions.json` — MCP tool list with parameters (auto-generated by `smith --flag get_mcp_parameter`), maps to `input.args.*`
- `system_vars.json` — system/session variables (e.g., roles, teams), maps to `input.extensions.subject.*`
- `test_case_template.json` (in `./references/`) — defines the OPA input envelope structure

**Output**: OPA policy saved to `./assets/policy.rego`

The policy only references data available from tool arguments and system variables. If a guidance rule requires context not available in either, it is logged as a suggestion rather than added to the policy.

### Security-Grounded Guidance Analysis (Experimental)

A separate, standalone workflow that grounds guidance in an OWASP-mapped threat model. It produces guidance only and never generates, modifies, or writes Rego or an OPA policy. Use it when you want an OWASP review of the guidance itself, to threat-model an MCP server, to produce enforcement guidance for a new tool, or to run any individual analysis stage. This process follows `opa_policy/guidelines-security-analysis/guidelines-security-analysis.md`, which runs in this order:

1. **Step A — Architecture Analysis** → `architecture.md`. Uses the configured target and extracted tool definitions to discover only source files that implement relevant roles, regardless of filename, language, or MCP transport. It then describes the layers actually present, with trust boundaries, data flow, and available enforcement points. UI-only, test, dependency, and generated files are skipped unless they participate in tool invocation or enforcement.
2. **Step B — Policy Guidance Questionnaire** → `policy_guidance_questionnaire.md`. Turns `guidance.txt` plus the architecture into a compact answer register covering roles, hard limits, rate limits, and response filtering, with confidence tags on every answer.
3. **Step C — Threat Model** → `threat_model.md`. Evaluates all 10 OWASP Top 10 for Agentic AI Security categories (ASI01–ASI10) against the architecture and questionnaire, producing deduplicated threat and scenario-coverage tables backed by a shared evidence index. It queries only the catalog fields used for threat discovery.
4. **Step D — Enforcement Mapping** → `owasp_policy_guidelines.md` and, only when missing rules are found, `guidance_updated.txt`. Maps stable threat IDs to the layer that can enforce them (OPA vs. Agent / Tool implementation / Infra), loading only mitigation fields for relevant OWASP categories and avoiding repeated threat prose. It normalizes candidate and existing rules per tool, suppresses duplicate or subsumed decisions, and emits only novel or additive OPA-enforceable rules. Non-OPA-enforceable findings and wording-only clarifications are recorded in the Gap Register table inside `owasp_policy_guidelines.md`, NOT in `guidance_updated.txt`. When no new rules are proposed, `guidance_updated.txt` is not created.

Each step is a separate, resumable job with its own model context. In **Gated** mode, Smith pauses after each phase checkpoint; in **Isolated autonomous** mode, it starts the next phase in a fresh worker context after the checkpoint passes. The four analysis artifacts live under `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/`; when generated, the proposed `guidance_updated.txt` addendum lives beside the configured `GUIDANCE_FILE`.

After the analysis is complete, the human may separately ask the agent to move `guidance_updated.txt` to `guidance.txt` and start policy creation. 

### Test Case Generation

The agent follows `test_generation/test_generation.md`, which first asks which kind of test cases you want, then runs the matching command(s):

- **Guidance-targeted cases** — legitimate + adversarial cases derived from the guidance (broad coverage).
- **Policy-bypass cases** — adversarial cases that target divergences between the guidance and the **current policy** (requires an existing, non-empty policy).
- **Both.**

#### Promptfoo config auto-generation

If you use Promptfoo for red-teaming, you can auto-generate the `promptfooconfig.yaml` instead of writing it manually:

```bash
smith --flag generate_promptfoo_config
```

This generates `purpose`, `contexts`, and `policy` text from your guidance and system variables, and appends tool parameter definitions to `testGenerationInstructions` so Promptfoo generates prompts with concrete values for all required parameters. Generation combines LLM output with deterministic steps. Review the output before running red-team tests.

#### Guidance-targeted generation

```bash
# CLI commands used for test case generation
smith --flag test_generation --mode fresh
```

Add `--mode update` to regenerate only the test cases whose guidance changed since the last run, instead of rebuilding the whole suite:

```bash
smith --flag test_generation --mode update
```

Guidance that was removed or edited loses its test cases; guidance that was added or edited is regenerated and appended, so every other case is left untouched. Reformatting guidance is not a content change, and an unchanged guidance file stops the run before any model call. Update mode needs the snapshots a previous run wrote (`references/guidance_snapshot.txt` and `references/guidance_raw_snapshot.txt`); without them it says so and exits, so a first run must use `--mode fresh` (the default).

This runs the following stages:

1. **Decomposition** — Break guidance into testable atomic conditions
2. **Variable Extraction** — Identify system/mutable variables and their domains
3. **Grey Condition Extraction** — Identify ambiguous boundary conditions. The user approves guidance proposed during this stage before it is merged into the clean guidance.
4. **Legitimate and Adversarial Case Generation** — Create benign (allow and disallow) inputs that should pass the policy. Create adversarial inputs using ARES and Promptfoo. Finally, combine into structured test cases

All results are stored in `./references/test_cases/`.

#### Policy-bypass generation

```bash
# Requires an existing, non-empty policy at assets/policy.rego
smith --flag bypass_case_generation
```

This stage compares the **current policy with the guidance** to find divergences, such as a missing existence check, a numeric comparison without a type assertion, or a substring match that lets a malformed value slip through. It then synthesizes adversarial cases for each divergence:

1. **Detect** — Compare the full Rego policy to the guidance and classify each divergence by mechanism (`omitted_field`, `type_confusion`, `malformed_value`, `keyword_evasion`). If the model returns malformed JSON, the call is retried (up to `MAX_BYPASS_PARSE_ATTEMPTS`, default 3) before giving up with an empty report.
2. **Synthesize** — Turn each divergence into concrete abstract cases.
3. **Convert** — Write them into `./references/test_cases/{allow,disallow}/` with a `bypass_test_case` prefix.

The divergence report is saved to `./references/bypass/` (JSON + Markdown). If the policy is missing or empty, generation is skipped with a message.

### Test Case Evaluation

```bash
# CLI commands used for test case evaluation
smith --flag test_case_evaluation
```

This runs three steps:

1. **Classify promptfoo cases** — Match each promptfoo red-team case to a specific guidance rule. Uses local embedding similarity (sentence-transformers) to retrieve top-N candidate guidances, then an LLM selects the most relevant one from the candidates.
2. **Validate labels** — Verify each test case's assigned label (allow/disallow) using a three-tier approach. Each tier assigns a confidence score:
   - **Tier 1 (Rule-based)** — Fast pattern matching for clear-cut cases (e.g., bypass keywords)
   - **Tier 2 (Embedding + NLI)** — Semantic similarity check; cases with high confidence and label agreement are resolved, others are escalated
   - **Tier 3 (LLM Judge)** — Cases with low confidence or label disagreement from Tier 2 are judged by an LLM
3. **Generate HTML report** — Produces an interactive report at `references/test_case_report.html`

The report groups all test cases by guidance item, with condition sub-tabs. Cases are labeled by source (Generated, ARES, Promptfoo) and type (allow/disallow) with color coding.

To regenerate the HTML report standalone:

```bash
cd src/smith/test_case_evaluation/visualization
python build_report.py
```

### Test Case Translation

```bash
# CLI commands used for test case translation
smith --flag test_case_translation
```

Calls the agent's `/extract_tool_call` endpoint to extract tool names and argument values for each test case. The agent receives the user prompt and user profile, and returns the resolved tool name and arguments, which are written back into the test case files.

- Cases where the returned tool name doesn't match the expected one are flagged as mismatches and removed
- Cases labeled as "other" (general questions that don't invoke any tool) are moved to `./references/test_cases/malicious/` for future guardrail features
- Cases that already carry an `arguments` block are skipped, so translation is re-runnable. After adding bypass cases, you can rerun it to translate only the new cases instead of retranslating the whole corpus

### Policy Testing

Evaluate the current policy against all test cases and report pass/fail with coverage metrics.

```bash
# CLI commands used in policy testing
smith --flag policy_testing
```

### Cross-Validation

Two cross-validation workflows handle different failure scenarios after policy testing:

**Policy Cross-Validation** — When policy testing returns 0 test cases evaluated or 100% failure, the policy likely has structural issues (input path mismatches or OPA syntax bugs). The agent follows `opa_policy/policy_cross_validation/policy_cross_validation.md` to diagnose and fix these issues before proceeding to refinement.

**Test Case Cross-Validation** — When policy testing produces mixed pass/fail results, some failures may be caused by mislabeled test cases rather than policy bugs. This workflow uses an LLM to check each failed case against the guidance and suggests corrections (move to correct folder or remove). Adversarial cases (filenames prefixed `bypass_test_case` or `promptfoo_test_case`) are an exception: any non-`keep` verdict is collapsed to `remove` rather than relabeled, so a failed malicious probe is discarded instead of being moved into `allow/`.

```bash
smith --flag cross_validate          # generate report of mislabeled cases
smith --flag apply_cross_validate    # apply approved corrections
```


### Policy Refinement

Iterative improvement workflow:

1. **Red Feedback** — Cluster failed malicious inputs and patch policy rules, following `opa_policy/policy_patch/policy_patch.md`
2. **Regal Formatting** — Lint and format the policy with [Regal](https://github.com/StyraInc/regal), following `opa_policy/policy_regal/policy_regal.md`
3. **Duplication Removal** — Detect and remove redundant rules through graph analysis, LLM review, and voting, following `opa_policy/policy_duplication/policy_duplication.md`

```bash
# CLI commands used in the refinement loop
smith --flag red_suggestion # clustering failed test cases
smith --flag regal_suggestion # get regal suggestions
smith --flag duplication_suggestion # get both LLM and graph generated duplication removal suggestions
```

## Project Structure

```
smith/
├── .claude/                 # Claude Code agent configuration
├── assets/                  # Policy files and OPA data
│   ├── policy.rego          # Target policy under management
│   └── opa/                 # OPA intermediate results (AST, graphs, backups)
├── examples/                # Agent examples
├── opa_policy/              # Skills related to OPA policy
│   ├── guidelines-security-analysis/ # Security-grounded guidance analysis workflow
│   ├── policy_creation/     # OPA policy creation workflow
│   ├── policy_cross_validation/ # Fix structural/syntax issues (0 cases or 100% fail)
│   ├── policy_defect/       # Introduce intentional defects for testing (only for testing purpose, it is not part of Smith main skill)
│   ├── policy_patch/        # OPA policy patching workflow
│   ├── policy_regal/        # Regal formatting workflow
│   └── policy_duplication/  # Deduplication workflow
├── references/              # All intermediate results (incl. scorecard/ outputs)
├── pyproject.toml           # Packaging, dependencies, ruff/black config
├── src/smith/               # The `smith` Python package
│   ├── cli.py               # Main CLI entry point (smith.cli:main)
│   ├── policy_agent/        # OPA policy analysis and refinement
│   ├── policy_generation/   # MCP tool extraction and policy generation
│   ├── test_generation/     # Test case generation and translation pipeline
│   ├── test_case_evaluation/ # Label validation and report generation
│   ├── policy_testing/      # OPA scorecard harness (score_card.sh, coverage)
│   └── tools/               # Developer utilities (explorer UI, license headers)
├── tests/                   # Test suite
│   └── integration/         # Stage-level tests driving the smith CLI (`make integration`)
│       └── fixtures/        # Frozen policy + test-case inputs
├── test_generation/         # Test generation skill markdown file
├── .env_template            # Environment template
├── SKILL.md                 # Main agent skill instructions
└── README.md
```

## Contributing

Contributions are welcome. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## Security

Please report security vulnerabilities privately — see [SECURITY.md](SECURITY.md).
Do not open public issues for security reports.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By
participating, you are expected to uphold it.

## License

Smith is licensed under the [Apache License 2.0](LICENSE).
