# Smith — Automated Policy Lifecycle Management for AI Agents
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Docs](https://img.shields.io/badge/docs-README-green.svg)](https://github.ibm.com/security-foundation-models/smith/blob/hl/skill/README.md) 

An open skill for AI code agents that automates OPA policy creation, test generation, testing, and iterative refinement.

## What's Smith?

Smith is a skill (plugin) for AI code agents that manages the full lifecycle of [Open Policy Agent (OPA)](https://www.openpolicyagent.org/) policies (more types of policies will be supported). It enables agents to:

- **Create** OPA policies from natural language guidance
- **Generate** both synthetic legitimate and adversarial test cases using LLM-based fuzzing and existing red-teaming tools
- **Test** policies against generated and custom test suites
- **Refine** policies automatically through iterative feedback loops (patches for falied test cases, deduplication, formatting etc)

```
Guidance Description (NLP) → Enforceble Policy Creation → Test Generation → Policy Testing ⇄ Policy Refinement
```

## Install

### Prerequisites

- Python 3.11+
- [Regal](https://github.com/StyraInc/regal#getting-started) (OPA linter)
- [ARES](https://github.com/IBM/ares) (red-teaming framework)
- [Promptfoo](https://www.promptfoo.dev/)(red-teaming framework) 

```
python -m venv .venv
source .venv/bin/activate

# Ares installation and setups (default config file: ares/example_config/qwen-owasp-llm-01.yaml)

curl https://raw.githubusercontent.com/IBM/ares/refs/heads/main/install.sh | bash
ares install-plugin ares-autodan
ares install-plugin ares-human-jailbreak
ares install-plugin ares-garak

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
cp scripts/.env_template scripts/.env
```

Edit `scripts/.env` and fill in your values:

| Variable | Description |
|----------|-------------|
| `BASE_URL` | Absolute path to your skill folder |
| `OPENAI_API_KEY` | API key for your LLM provider |
| `OPENAI_BASE_URL` | Base URL for LLM API endpoint |
| `MODEL` | Model for policy refinement and analysis (i.e., duplication detection) (e.g., `GCP/claude-opus-4`) |
| `MODEL_SONNET` | Model for test generation (e.g., `GCP/claude-4-sonnet`) |
| `ARES_HOME` | Path to your ARES installation |

### Deployment

Place the entire `smith` folder under the `skills/` directory of your code agent.

## How It Works

Smith operates as an agent skill with a CLI backend. The AI agent reads instructions from `SKILL.md` and orchestrates the appropriate workflows by invoking the `smith` CLI or following embedded markdown guides.

```
┌──────────────────────────────────────────────────────────────────────┐
│                                  Smith                               │
│                                                                      │
│  SKILL.md ──→ Orchestration ──→ smith CLI                            │
│                                    │                                 │
│              ┌─────────────────────┼───────────────┬─────────┐       │
│              ▼                     ▼               ▼         ▼       │
│         Policy              Test Case Gen       Policy     Policy    │
│         Creation                 │              Testing   Refinement │
│              │          ┌────────┼────────┐       │         │        │
│              ▼          ▼        ▼        ▼       └────⇄────┘        │
│         OPA Policy  Legitimate  ARES  Promptfoo  (iterative loop)    │
│         (.rego)                                                      │
└──────────────────────────────────────────────────────────────────────┘
```


## Core Concepts

### Policy Creation

Create OPA policies from natural language specifications. The agent follows `opa_policy/policy_creation/opa_policy_creation.md` to generate a `.rego` policy file.

```bash
# CLI command in backend
smith --flag policy_creation
```

### Test Case Generation

The agent follows `test_generation/test_generation.md` to generate test cases through a multi-stage pipeline:

1. **Decomposition** — Break guidance into testable atomic conditions
2. **Variable Extraction** — Identify system/mutable variables and their domains
3. **Grey Condition Extraction** — Identify ambiguous boundary conditions, user needs to approve guidancies from grey condition extraction and then merge them to clean space. 
4. **Legitimate and Adversarial Case Generation** — Create benign (including allow and disallow) inputs that should pass the policy. Create adversarial inputs using ARES and promptfoo. Finally, combine into CMF compatitable structured test cases

```bash
# CLI commands used for test case generation
smith --flag test_generation
```

### Policy Testing

Evaluate the current policy against all test cases and report pass/fail with coverage metrics.

```bash
smith --flag policy_testing
```

### Policy Refinement

Iterative improvement workflow:

1. **Red Feedback** — Cluster failed malicious inputs and patch policy rules, following `opa_policy/policy_patch/policy_patch.md`
2. **Regal Formatting** — Lint and format policy with [Regal](https://github.com/StyraInc/regal). It follows `opa_policy/policy_duplication/policy_duplication.md`
3. **Duplication Removal** — Detect and remove redundant rules via graph analysis, LLM review, and voting.

```bash
# CLI commands used in the refinment loop
smith --flag red_suggestion # clustering failed test cases
smith --flag regal_suggestion # get regal suggestions
smith --flag duplication_suggestion # get both LLM and graph generated duplication removal suggestions
```

### Policy Visualization (Beta)

Visualize the policy's rule dependency graph:

```bash
cd scripts/visualization
python parse_graph_to_json.py
python -m http.server 8000
```

Then open http://localhost:8000/graph.html in your browser.

## Project Structure

```
smith/
├── assets/                  # Policy files and OPA data
│   ├── policy.rego          # Target policy under management
│   └── opa/                 # OPA intermidiate results e.g., inputs/outputs/backups (AST parsed policy, graphs)
├── mcp_servers/             # MCP server and agent running examples
├── opa_policy/              # Skills rtelated to opa policy
│   ├── policy_creation/     # OPA policy creation workflow
│   ├── policy_patch/        # OPA policy patching workflow
│   ├── policy_regal/        # Regal formatting workflow
│   └── policy_duplication/  # Deduplication workflow
├── references/              # All intermediate results
├── scripts/                 # Core Python packages
│   ├── cli.py               # Main CLI entry point
│   ├── policy_agent/        # OPA policy analysis and refinement
│   ├── test_generation/     # Test case generation pipeline
│   ├── tests/               # Integration and unit tests
│   └── visualization/       # Graph visualization (HTML)
├── test_generation/         # Test generation skill markdown file
├── SKILL.md                 # Main agent skill instructions
├── requirements.txt         # Python dependencies
└── README.md
```

## Configuration

All configuration is managed through environment variables in `scripts/.env`. See `scripts/.env_template` for the full list with descriptions.

Key configuration groups:

- **Paths** — Policy, data, and output directories
- **LLM** — Model selection, API keys, temperature/top-p
- **Test Generation** — Guidance files, decomposition outputs, batch settings
- **Policy Refinement** — Red feedback, Regal, and deduplication output paths

### Batch Processing

For large test generation tasks, enable batch processing:

```env
BATCH_PROCESSING=true
BATCH_SIZE=10
```

## Contributing

Contributions are welcome. Open an issue or submit a pull request.

## License

Apache 2.0
