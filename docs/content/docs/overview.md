---
title: "Overview"
weight: 1
---

# What's Smith?

Smith is a skill (plugin) for AI code agents that manages the full lifecycle of [Open Policy Agent (OPA)](https://www.openpolicyagent.org/) policies (more types of policies will be supported). It enables agents to:

- **Create** OPA policies from natural language guidance and an agent description.
- **Generate** both synthetic legitimate and adversarial test cases using LLM-based fuzzing and existing red-teaming tools.
- **Test** policies against generated and custom test suites.
- **Refine** policies automatically through iterative feedback loops (patches for failed test cases, linting, etc.).

## Architecture

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

## What Smith Needs from You

1. **Guidance file** — A natural language description of your access control policies (e.g., "managers can only view compensation for their own team")
2. **Agent server with endpoints** — Your agent must expose:
   - `/chat` — Used by Promptfoo for red-teaming test generation
   - `/extract_tool_call` — Used to auto-detect MCP tool parameters and definitions from user prompts
3. **System variable file** — A JSON file listing the system variables available in your agent (e.g., roles, teams, claims)
4. **Keep both your agent server and MCP server running** during Smith's operation

## Deployment

Place the entire `smith` folder under the `skills/` or `plugin/` directory of your code agent (Claude Code, Bob, Aider, etc.). The coding agent automatically recognizes Smith as an open skill.

For more details on how to use skills in different coding agents:

- **Bob**: https://bob.ibm.com/docs/ide/features/skills
- **Claude Code**: https://code.claude.com/docs/en/skills
- **Aider Desk**: https://aiderdesk.hotovo.com/docs/features/skills

## Project Structure

```
smith/
├── .claude/                 # Claude Code agent configuration
├── assets/                  # Policy files and OPA data
│   ├── policy.rego          # Target policy under management
│   └── opa/                 # OPA intermediate results (AST, graphs, backups)
├── examples/                # Agent examples
├── opa_policy/              # Skills related to OPA policy
│   ├── policy_creation/     # OPA policy creation workflow
│   ├── policy_cross_validation/ # Fix structural/syntax issues
│   ├── policy_patch/        # OPA policy patching workflow
│   ├── policy_regal/        # Regal formatting workflow
│   └── policy_duplication/  # Deduplication workflow
├── references/              # All intermediate results (incl. scorecard/ outputs)
├── scripts/                 # Utility bash scripts (e.g. clean_generated.sh)
├── pyproject.toml           # Packaging, dependencies, ruff/black config
├── src/smith/               # The smith Python package
│   ├── cli.py               # Main CLI entry point (smith.cli:main)
│   ├── policy_agent/        # OPA policy analysis and refinement
│   ├── policy_generation/   # MCP tool extraction and policy generation
│   ├── test_generation/     # Test case generation and translation pipeline
│   ├── test_case_evaluation/ # Label validation and report generation
│   ├── policy_testing/      # OPA scorecard harness
│   └── tools/               # Repo tooling (e.g. license headers)
├── test_generation/         # Test generation skill markdown file
├── .env_template            # Environment template
├── SKILL.md                 # Main agent skill instructions
└── README.md
```
