# Smith — Automated Policy Lifecycle Management for AI Agents
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Docs](https://img.shields.io/badge/docs-README-green.svg)](https://github.ibm.com/security-foundation-models/smith/blob/hl/skill/README.md) 

An open skill for AI code agents that automates OPA policy creation, test generation, testing, and iterative refinement.

## What's Smith?

Smith is a skill (plugin) for AI code agents that manages the full lifecycle of [Open Policy Agent (OPA)](https://www.openpolicyagent.org/) policies (more types of policies will be supported). It enables agents to:

- **Create** OPA policies from natural language guidance and agent description. 
- **Generate** both synthetic legitimate and adversarial test cases using LLM-based fuzzing and existing red-teaming tools
- **Test** policies against generated and custom test suites
- **Refine** policies automatically through iterative feedback loops (patches for failed test cases, linting etc)

```
Guidance Description (NLP) + Agent Description → Enforceble Policy Creation → Test Generation → Policy Testing ⇄ Policy Refinement
```

## What Smith Needs from You

1. **Guidance file** — A natural language description of your access control policies (e.g., "managers can only view compensation for their own team")
2. **Agent server with endpoints** — Your agent must expose:
   - `/chat` — Used by Promptfoo for red-teaming test generation
   - `/extract_tool_call` — Used to auto-detect MCP tool parameters and definitions from user prompts
3. **System variable file** — A JSON file listing the system variables available in your agent (e.g., roles, teams, claims)
4. **Keep both your agent server and MCP server running** during Smith's operation

## Install

### Prerequisites

- Python 3.11+
- [Regal](https://github.com/StyraInc/regal#getting-started) (OPA linter)
- [ARES](https://github.com/IBM/ares) (red-teaming framework)
- [Promptfoo](https://www.promptfoo.dev/)(red-teaming framework) 

```
# Python enviroment preparation
python -m venv .venv
source .venv/bin/activate

# Ares installation and setups (default config file: ares/example_config/qwen-owasp-llm-01.yaml)

cd scripts/test_generation
curl https://raw.githubusercontent.com/IBM/ares/refs/heads/main/install.sh | bash
ares install-plugin ares-autodan
ares install-plugin ares-human-jailbreak
ares install-plugin ares-garak
cd ../..

## Promptfoo installation (config file: PROMPTFOO_CONFIG_FILE in .env)

npm install -g promptfoo
```


### Python Dependencies

```bash
pip install -r requirements.txt
```

### CLI Installation

```bash
cd scripts
pip install -e .
```

This installs the `smith` CLI command.

### Configuration

```bash
cp .env_template .env
```

Edit `.env` and fill in your values:

| Variable | Description |
|----------|-------------|
| `BASE_URL` | Absolute path to your skill folder, e.g., your path/.bob/skills/smith/ |
| `OPENAI_API_KEY` | API key for your LLM provider |
| `OPENAI_BASE_URL` | Base URL for LLM API endpoint |
| `MODEL_SONNET` | Model for test generation (e.g., `GCP/claude-4-sonnet` by default) |
| `AGENT_URL` | URL of the target agent server's endpoint (e.g., `http://localhost:9000` by default) |
| `MCP_URL` | MCP server URL (only for SSE transport), default is `http://localhost:8000/sse` |
| `MCP_TRANSPORT` | MCP transport type (`sse` or `stdio`) |
| `TARGET_AGENT_PATH` | Relative path to the target MCP server directory, e.g., `mcp_servers/RagChatbot_MCPServer/` for HR agent |
| `GUIDANCE_FILE` | Path to the policy guidance file for the target agent, e.g., `mcp_servers/RagChatbot_MCPServer/smith/guidance.txt` for HR agent |


### Deployment

Place the entire `smith` folder under the `skills/` or `plugin/` directory of your code agent.

#### Instructions for using HR agent example
1. Ask smith to generate an initial policy for the targeted agent
2. Generate the test cases, translate and evaluate the test cases: can be replaced with the following CLI commands:
```bash
smith --flag test_generation
smith --flag test_case_evaluation # could be skipped
smith --flag test_case_translation
```
3. Ask smith to test existing policy. If smith identifies failed test cases, ask it to improve the existing policy.



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
cd scripts/test_case_evaluation/visualization
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

### Policy Refinement

Iterative improvement workflow:

1. **Red Feedback** — Cluster failed malicious inputs and patch policy rules, following `opa_policy/policy_patch/policy_patch.md`
2. **Regal Formatting** — Lint and format policy with [Regal](https://github.com/StyraInc/regal). It follows `opa_policy/policy_regal/policy_regal.md`
3. **Duplication Removal** — Detect and remove redundant rules via graph analysis, LLM review, and voting. It follows `opa_policy/policy_duplication/policy_duplication.md`

```bash
# CLI commands used in the refinment loop
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
├── mcp_servers/             # Agent examples
├── opa_policy/              # Skills related to OPA policy
│   ├── policy_creation/     # OPA policy creation workflow
│   ├── policy_patch/        # OPA policy patching workflow
│   ├── policy_regal/        # Regal formatting workflow
│   └── policy_duplication/  # Deduplication workflow
├── references/              # All intermediate results
├── scripts/                 # Core Python packages
│   ├── cli.py               # Main CLI entry point
│   ├── policy_agent/        # OPA policy analysis and refinement
│   ├── policy_generation/   # MCP tool extraction and policy generation
│   ├── test_generation/     # Test case generation and translation pipeline
│   ├── test_case_evaluation/ # Label validation and report generation
│   ├── tests/               # Policy testing and validation
│   └── utils/               # Utility functions and helpers
├── test_generation/         # Test generation skill markdown file
├── .env_template            # Environment template
├── SKILL.md                 # Main agent skill instructions
├── requirements.txt         # Python dependencies
└── README.md
```

## Contributing

Contributions are welcome. Open an issue or submit a pull request.

## License

Apache 2.0
