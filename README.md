<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/IBM/smith/blob/main/docs/figures/smith_header-dark.png?raw=true">
  <img alt="Smith — Automated Policy Lifecycle Management for AI Agents" src="https://github.com/IBM/smith/blob/main/docs/figures/smith_header.png?raw=true" width="560">
</picture>

[![CI](https://github.com/IBM/smith/actions/workflows/ci.yml/badge.svg)](https://github.com/IBM/smith/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

An open skill for AI code agents that automates OPA policy creation, test generation, testing, and iterative refinement.

## What's Smith?

Smith is a skill (plugin) for AI code agents that manages the full lifecycle of [Open Policy Agent (OPA)](https://www.openpolicyagent.org/) policies (more types of policies will be supported). It enables agents to:

- **Create** OPA policies from natural language guidance and an agent description.
- **Generate** both synthetic legitimate and adversarial test cases using LLM-based fuzzing and existing red-teaming tools.
- **Test** policies against generated and custom test suites.
- **Refine** policies automatically through iterative feedback loops (patches for failed test cases, linting, etc.).

```
Guidance Description (NLP) + Agent Description → Enforceable Policy Creation → Test Generation → Policy Testing ⇄ Policy Refinement
```

## What Smith Needs from You

1. **Guidance file** — A natural language description of your access control policies (e.g., "managers can only view compensation for their own team")
2. **Agent server with endpoints** — Your agent must expose:
   - `/chat` — Used by Promptfoo for red-teaming test generation
   - `/extract_tool_call` — Used to auto-detect MCP tool parameters and definitions from user prompts
3. **System variable file** — A JSON file listing the system variables available in your agent (e.g., roles, teams, claims)
4. **Keep both your agent server and MCP server running** during Smith's operation

## Deployment

Place the entire `smith` folder under the `skills/` or `plugin/` directory of your code agent (Claude Code, Bob, Aider, etc.). The coding agent automatically recognizes Smith as an open skill.

For more details of how to use skills in different coding agents, you can refer to the following links:

If you are using bob: https://bob.ibm.com/docs/ide/features/skills

If you are using Claude: https://code.claude.com/docs/en/skills

If you are using Aider Desk: https://aiderdesk.hotovo.com/docs/features/skills

## Install

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package management)
- [OPA](https://www.openpolicyagent.org/) + [Regal](https://github.com/StyraInc/regal#getting-started) (policy testing / linting; OPA runs in Docker for the scorecard)
- [ARES](https://github.com/IBM/ares) (red-teaming framework)
- [Promptfoo](https://www.promptfoo.dev/) (red-teaming framework)

**1. Python environment**

```bash
python -m venv .venv
source .venv/bin/activate
```

**2. ARES** (red-teaming framework). Installs into `src/smith/test_generation/ares/` with its own `.venv`, which is the layout the test-generation pipeline expects (`src/smith/test_generation/attack.py` invokes `ares/.venv/bin/ares`):

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

**3. Promptfoo** (red-teaming framework).

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
| `MODEL_SONNET` | Model used across the pipelines (e.g., `GCP/claude-4-sonnet` by default) |
| `AGENT_URL` | URL of the target agent server (must expose `/chat` and `/extract_tool_call`); default `http://localhost:9000` |
| `RITS_MODEL` | Model name for the target agent's LLM (e.g., `qwen3.5:latest` for Ollama, or a RITS model name) |
| `RITS_BASE_URL` | Base URL for the agent's LLM API (e.g., `http://localhost:11434/v1` for Ollama) |
| `RITS_API_KEY` | API key for the agent's LLM (use `ollama` for local Ollama) |
| `MCP_TRANSPORT` | MCP transport type: `sse` or `stdio` |
| `MCP_URL` | MCP server URL (SSE transport only); default `http://localhost:8000/sse` |
| `MCP_COMMAND` / `MCP_ARGS` / `MCP_CWD` | MCP launch command, args, and working dir (**stdio transport only** — see the commented examples in `.env_template`) |
| `TARGET_AGENT_PATH` | Relative path to the target MCP server directory, e.g., `examples/RagChatbot_MCPServer/` for the HR agent |
| `GUIDANCE_FILE` | Path to the policy guidance file, e.g., `examples/RagChatbot_MCPServer/smith/guidance.txt` |
| `SYSTEM_VAR_FILE` | Path to the system-variables JSON (e.g., `examples/<agent>/smith/system_vars.json`). **Required** — test generation fails without it |
| `PROMPTFOO_CONFIG_FILE` / `PROMPTFOO_OUTPUT_FILE` | Promptfoo red-team config and generated output paths |
| `ARES_HOME` | Absolute path to the ARES installation directory (e.g., `/path/to/smith/src/smith/test_generation/ares`). Smith uses this to locate `ares/.venv/bin/ares` |

See `.env_template` for the full list, including model sampling (`TEMP`, `TOP_P`), test-case evaluation thresholds, and refinement/clustering parameters.

### Start the target agent and MCP server

Detailed instructions for each agent example can be found in the `examples/<agent>/README.md`.

Smith talks to a **running** target agent (for `/chat` and `/extract_tool_call`) and to its MCP server (to extract tool definitions). Start both before running any `smith` flag.

Each example under `examples/<agent>/` ships its own `agent.py` (a FastAPI app exposing `/chat` and `/extract_tool_call`), `server.py` (the MCP server), and a `requirements.txt`. Using `call-for-papers-mcp` as a concrete example:

```bash
cd examples/call-for-papers-mcp
pip install -r requirements.txt

# Start the agent server on the port AGENT_URL points to (default 9000).
uvicorn agent:app --port 9000
```

This example's agent **spawns its MCP server itself over stdio** (`agent.py` launches `python server.py`), so you do not start the MCP server separately. Match `.env` accordingly:

```
MCP_TRANSPORT=stdio
MCP_COMMAND=python
MCP_ARGS=server.py
MCP_CWD=examples/call-for-papers-mcp
```

For an SSE-based MCP server instead, set `MCP_TRANSPORT=sse` and `MCP_URL=http://localhost:8000/sse`, and start that server on its own. Check each example's own `README.md` for specifics.

## How It Works

Smith operates as an agent skill with a CLI backend. The AI agent reads instructions from `SKILL.md` and orchestrates the appropriate workflows by invoking the `smith` CLI or following embedded markdown guides.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                  Smith                                   │
│                                                                          │
│  SKILL.md ──→ Orchestration ──→ smith CLI                                │
│                                    │                                     │
│              ┌─────────────────────┼────────────────┬─────────┐          │
│              ▼                     ▼                ▼         ▼          │
│         Policy              Test Case Gen        Policy     Policy       │
│         Creation                 │               Testing   Refinement    │
│              │          ┌────────┼────────┐        │         │           │
│              ▼          ▼        ▼        ▼        └────⇄────┘           │
│         OPA Policy  Legitimate  ARES  Promptfoo                          │
│         (.rego)         │        │        │                              │
│                         └────────┼────────┘                              │
│                                  ▼                                       │
│                          Test Case Evaluation                            │
└──────────────────────────────────────────────────────────────────────────┘
```


## Core Concepts

### Policy Creation

Create OPA policies from natural language specifications. The agent follows `opa_policy/policy_creation/opa_policy_creation.md` to generate a `.rego` policy file.

**Inputs** (located in `<TARGET_AGENT_PATH>/smith/`):
- `guidance.txt` — natural language policy rules
- `tool_definitions.json` — MCP tool list with parameters (auto-generated by `smith --flag get_mcp_parameter`), maps to `input.arguments.*`
- `system_vars.json` — system/session variables (e.g., roles, teams), maps to `input.extensions.subject.*`
- `test_case_template.json` (in `./references/`) — defines the OPA input envelope structure

**Output**: OPA policy saved to `<TARGET_AGENT_PATH>/smith/policy_generated.rego`

The policy only references data available from tool arguments and system variables. If a guidance rule requires context not available in either, it is logged as a suggestion rather than added to the policy.

### Test Case Generation

The agent follows `test_generation/test_generation.md` to generate test cases through a multi-stage pipeline:

```bash
# CLI commands used for test case generation
smith --flag test_generation
```

This runs the following stages:

1. **Decomposition** — Break guidance into testable atomic conditions
2. **Variable Extraction** — Identify system/mutable variables and their domains
3. **Grey Condition Extraction** — Identify ambiguous boundary conditions, user needs to approve guidances from grey condition extraction and then merge them to clean space
4. **Legitimate and Adversarial Case Generation** — Create benign (allow and disallow) inputs that should pass the policy. Create adversarial inputs using ARES and Promptfoo. Finally, combine into structured test cases

All results are stored in `./references/test_cases/`.

### Test Case Evaluation

```bash
# CLI commands used for test case evaluation
smith --flag test_case_evaluation
```

This runs three steps:

1. **Classify promptfoo cases** — Match each promptfoo red-team case to a specific guidance rule. Uses local embedding similarity (sentence-transformers) to retrieve top-N candidate guidances, then an LLM selects the most relevant one from the candidates.
2. **Validate labels** — Verify that each test case's assigned label (allow/disallow) is correct using a three-tier approach, each tier assigns a confidence score:
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

### Policy Testing

Evaluate the current policy against all test cases and report pass/fail with coverage metrics.

```bash
# CLI commands used in policy testing
smith --flag policy_testing
```

### Cross-Validation

Two cross-validation workflows handle different failure scenarios after policy testing:

**Policy Cross-Validation** — When policy testing returns 0 test cases evaluated or 100% failure, the policy likely has structural issues (input path mismatches or OPA syntax bugs). The agent follows `opa_policy/policy_cross_validation/policy_cross_validation.md` to diagnose and fix these issues before proceeding to refinement.

**Test Case Cross-Validation** — When policy testing produces mixed pass/fail results, some failures may be caused by mislabeled test cases rather than policy bugs. This workflow uses an LLM to check each failed case against the guidance and suggests corrections (move to correct folder or remove).

```bash
smith --flag cross_validate          # generate report of mislabeled cases
smith --flag apply_cross_validate    # apply approved corrections
```


### Policy Refinement

Iterative improvement workflow:

1. **Red Feedback** — Cluster failed malicious inputs and patch policy rules, following `opa_policy/policy_patch/policy_patch.md`
2. **Regal Formatting** — Lint and format policy with [Regal](https://github.com/StyraInc/regal). It follows `opa_policy/policy_regal/policy_regal.md`
3. **Duplication Removal** — Detect and remove redundant rules via graph analysis, LLM review, and voting. It follows `opa_policy/policy_duplication/policy_duplication.md`

```bash
# CLI commands used in the refinement loop
smith --flag red_suggestion # clustering failed test cases
smith --flag regal_suggestion # get regal suggestions
smith --flag duplication_suggestion # get both LLM and graph generated duplication removal suggestions
```

## Project Structure

```
smith/
├── assets/                  # Policy files and OPA data
│   ├── policy.rego          # Target policy under management
│   └── opa/                 # OPA intermediate results (AST, graphs, backups)
├── examples/             # Agent examples
├── opa_policy/              # Skills related to OPA policy
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
│   └── tools/               # Repo tooling (e.g. license headers)
├── tests/                   # Placeholder for the test suite (TODO)
├── test_generation/         # Test generation skill markdown file
├── .env_template            # Environment template
├── SKILL.md                 # Main agent skill instructions
└── README.md
```

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for the
development workflow, coding standards, source-file license headers, and the
Developer Certificate of Origin (DCO) sign-off requirement. A green `make ci`
locally means a green pipeline.

## Security

Please report security vulnerabilities privately — see [SECURITY.md](SECURITY.md).
Do not open public issues for security reports.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By
participating, you are expected to uphold it.

## License

Smith is licensed under the [Apache License 2.0](LICENSE).
