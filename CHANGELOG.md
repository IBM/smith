# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/).

> **Types of changes:**
>
> - **Added**: for new features.
> - **Changed**: for changes in existing functionality.
> - **Deprecated**: for soon-to-be removed features.
> - **Removed**: for now removed features.
> - **Fixed**: for any bug fixes.
> - **Security**: in case of vulnerabilities.

## [Unreleased]

## [0.1.1] - 2026-06-29

### Changed

- Repackaged `scripts/` into an installable `smith` Python package using a `src/`
  layout, with `pyproject.toml` at the repo root declaring runtime dependencies
  (`[project.dependencies]`) and a `[dev]` extra. The CLI entry point is now
  `smith = smith.cli:main`.
- Package management and the build/publish workflow now use [uv](https://docs.astral.sh/uv/)
  (`make install`, `make package`, `make publish`).
- The OPA scorecard harness ships inside the package (`smith.policy_testing`) and
  writes all generated outputs to a `BASE_URL`-relative dir (`references/scorecard/`,
  via `TEST_OUTPUT_DIR`) instead of `scripts/tests/integration/`.
- Renamed `mcp_servers/` to `examples/`.

### Removed

- Legacy code unreachable from the CLI: a kubectl/mcpgateway/beeai cluster, duplicate
  entry points, a dead `visualization/` package, and the previous (non-functional)
  pytest suite. Also removed stray upstream ARES repository scaffolding; ARES is the
  external `ares-redteamer` tool, located via `ARES_HOME`.

## [0.1.0] - 2026-06-28

### Added

- Initial release of Smith — an agent skill (plugin) for AI code agents that automates the full lifecycle of [Open Policy Agent (OPA)](https://www.openpolicyagent.org/) (Rego) access-control policies for AI/MCP agents.
- Two-layer architecture: a skill layer (`SKILL.md` plus authoring guides under `opa_policy/` and `test_generation/`) that the agent follows, and a `smith` CLI backend (`scripts/cli.py`) that runs the heavy pipeline stages via `smith --flag <stage>`.
- **Policy creation** from natural-language guidance and an agent/MCP tool description, restricted to context available from tool arguments (`input.arguments.*`) and system variables (`input.extensions.subject.*`).
- **Test generation** producing both legitimate and adversarial cases: guidance decomposition, grey-condition and variable extraction, case generation, and red-teaming via ARES and Promptfoo (`test_generation`).
- **Test-case evaluation** with three-tier label validation (rule patterns → semantic embeddings/NLI → LLM judge), guidance classification, and an HTML report (`test_case_evaluation`).
- **Policy testing** harness that runs every generated and custom case against a running OPA server and emits a scorecard with false-positive/false-negative breakdowns (`policy_testing`).
- **Iterative refinement**: DBSCAN clustering of failed cases (`red_suggestion`), Regal lint/format suggestions (`regal_suggestion`), and graph + LLM redundancy detection (`duplication_suggestion`).
- **Cross-validation** of failed cases to distinguish mislabeled tests from policy bugs (`cross_validate`, `apply_cross_validate`).
- **MCP tool extraction** over SSE and stdio transports (`get_mcp_parameter`) and tool-call translation (`test_case_translation`).
- **Rego policy validation** with optional auto-fix (`policy_validation`, `policy_validation_fix`).
- Runtime configuration driven entirely from `.env` (see `.env_template`); target-agent selection via `TARGET_AGENT_PATH`, `GUIDANCE_FILE`, `SYSTEM_VAR_FILE`, `MCP_*`, and `AGENT_URL`.
- Example target agents under `examples/`, each carrying its Smith inputs (`guidance.txt`, `tool_definitions.json`, `system_vars.json`).

[Unreleased]: https://github.com/IBM/smith/compare/0.1.1...HEAD
[0.1.1]: https://github.com/IBM/smith/compare/0.1.0...0.1.1
[0.1.0]: https://github.com/IBM/smith/releases/tag/0.1.0
