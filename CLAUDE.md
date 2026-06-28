# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Smith is an **agent skill** (plugin) that manages the full lifecycle of [OPA](https://www.openpolicyagent.org/) (Rego) access-control policies for AI/MCP agents: creating policies from natural-language guidance, generating legitimate + adversarial test cases, testing the policy, and iteratively refining it.

Smith has two layers that must be understood together:

1. **The skill layer** — `SKILL.md` plus markdown guides under `opa_policy/` and `test_generation/`. These are *instructions the agent (you) follows*, not code. When a user asks to create, test, or improve a policy, the agent reads the relevant markdown guide and orchestrates the work, often by invoking the `smith` CLI.
2. **The CLI backend** — `scripts/cli.py` exposes a single `smith --flag <stage>` command that runs the heavy Python pipelines (decomposition, attack generation, label validation, clustering, etc.).

So: high-level control flow lives in markdown guides; deterministic pipeline stages live behind CLI flags.

## Commands

```bash
# Setup (from repo root)
python -m venv .venv && source .venv/bin/activate
make install                   # pip install -r requirements.txt + editable scripts/ (installs the `smith` CLI)
cp .env_template .env          # then fill in values (see Configuration below)

# Dev workflow — the root Makefile mirrors CI (.github/workflows/ci.yml); `make ci` is the gate
make lint            # ruff check + black --check (config in scripts/pyproject.toml)
make format          # ruff --fix + black (apply fixes)
make lint-policy     # Regal (falls back to OPA) lint of assets/policy.rego
make license-check   # verify SPDX Apache-2.0 headers (scripts/tools/license_headers.py)
make build           # editable install + `smith --help` smoke test
make ci              # the gate: lint + lint-policy + license-check
make test            # policy scorecard (delegates to scripts/Makefile; needs Docker + the OPA server)

# CLI pipeline stages (run from anywhere once installed; reads paths from .env)
smith --flag get_mcp_parameter      # auto-extract MCP tool defs -> <TARGET_AGENT_PATH>/smith/tool_definitions.json
smith --flag test_generation        # full test-case generation pipeline
smith --flag test_case_evaluation   # classify + validate labels + HTML report
smith --flag test_case_translation  # resolve tool calls via agent /extract_tool_call
smith --flag policy_testing         # run policy against all test cases (needs OPA server)
smith --flag red_suggestion         # cluster failed cases (refinement)
smith --flag regal_suggestion       # Regal lint/format suggestions (refinement)
smith --flag duplication_suggestion # LLM + graph redundancy suggestions (refinement)
smith --flag cross_validate         # LLM cross-check failed cases → references/cross_validate_report.json
smith --flag apply_cross_validate   # apply approved label corrections from cross_validate report
smith --flag policy_validation --policy_path <file.rego>      # validate a rego file
smith --flag policy_validation_fix --policy_path <file.rego>  # validate and auto-fix

# Policy-testing harness (scripts/Makefile — what `smith --flag policy_testing` and root `make test` invoke)
cd scripts
make opaserver/start   # start OPA server on :8181 with assets/policy.rego (lints first)
make test              # run tests/integration/score_card.sh, output scorecard + failures
make test/verbose      # per-test-case results
make lint/policy       # OPA check on the rego policy
make lint/code         # ruff + black over scripts tests visualization
make opaserver/stop
```

`make test` requires the OPA server to be running and curls `localhost:8181/v1/data/mcp/policies/allow` for every JSON case under `references/test_cases/{allow,disallow}/`. A case in `disallow/` is expected to return `allow: false`; `allow/` expects `true`. Results land in `scripts/tests/integration/{scorecard_summary.txt,score_test_failures.txt,tp.txt,fp.txt,tn.txt,fn.txt}`.

## External tools (install separately)

- **OPA** + **Regal** (Styra linter) — required for testing and `regal_suggestion`.
- **ARES** (IBM red-teaming) and **Promptfoo** (`npm install -g promptfoo`) — required for adversarial test generation. ARES installs under `scripts/test_generation/ares/` and needs its plugins (`ares-autodan`, `ares-human-jailbreak`, `ares-garak`).

## Repo conventions

- **Packaging + tool config live in `scripts/pyproject.toml`** (not at the repo root): flat layout (`cli.py` is the import root), console entry `smith = cli:main`, and `[tool.ruff]`/`[tool.black]` config. Black is pinned to `target-version = py311` so formatting is deterministic across interpreters; the vendored ARES tree is excluded from packaging and linting.
- **CI** (`.github/workflows/ci.yml`) mirrors `make ci` and pins `ruff==0.15.20` / `black==26.5.1` — bump these deliberately alongside a reformat commit. The Rego-lint job is currently disabled in CI; still run `make lint-policy` locally.
- **License headers:** every in-scope file (`.py`, `.rego`, `.sh`, `.yaml`, `.yml`, plus `Makefile`/`Dockerfile`) carries an Apache-2.0 SPDX header. `make license` inserts, `make license-check` verifies (`scripts/tools/license_headers.py`). Excludes `scripts/test_generation/ares/`, `examples/`, `references/`, and generated outputs.
- **DCO sign-off** is required on every commit (`git commit -s`).
- **Changelog:** user-facing changes get an entry under `## [Unreleased]` in `CHANGELOG.md` (Keep a Changelog); maintainers promote it to a dated version when cutting a release tag.
- `smith --help` and a bare `smith` (no flag) work without a populated `.env` — args are parsed before any env-derived path assembly, so don't reintroduce eager `BASE_URL + os.getenv(...)` work ahead of `argparse`.

## Configuration model — important

Almost every path in the codebase is **assembled from `.env` at runtime** via `os.getenv`, not hardcoded. The dominant pattern is `BASE_URL + os.getenv("SOME_PATH")`. `BASE_URL` is the absolute path to the skill folder (trailing slash). When you change where files are read/written, you are almost always editing `.env`, not Python.

Target-agent selection is driven by a small set of vars: `TARGET_AGENT_PATH`, `GUIDANCE_FILE`, `SYSTEM_VAR_FILE`, `MCP_*`, and `AGENT_URL`. Pointing Smith at a different agent example (under `examples/`) means repointing these, not changing code.

Key model vars: `MODEL_SONNET` (the LLM used across pipelines), `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `TEMP`, `TOP_P`.

## Per-target-agent inputs

Each target agent under `examples/<agent>/` carries its Smith inputs in a `smith/` subfolder:
- `guidance.txt` — natural-language policy rules (the source of truth).
- `tool_definitions.json` — MCP tools + params (auto-generated by `get_mcp_parameter`); maps to `input.arguments.*` in the policy.
- `system_vars.json` — session/system variables (roles, teams, claims); maps to `input.extensions.subject.*`.

The generated policy may **only** reference data available from tool arguments or system variables. A guidance rule needing context absent from both is logged as a suggestion, not encoded into the policy.

## Data flow (where artifacts live)

- `assets/policy.rego` — **the policy under management** (the target of all testing/refinement).
- `assets/opa/` — OPA intermediate results: AST (`ast.json`), graph (`ast.dot`), backups.
- `references/` — all generated intermediates: `decomp_file.json`, `vars_file.json`, `test_cases.json`, attack files, `label_validation_results.json`, `test_case_report.html`, and final `test_cases/{allow,disallow,malicious}/`.

## scripts/ package map

- `policy_generation/` — MCP tool extraction (`extract_tools.py`) and rego validation (`validate_policy.py`).
- `test_generation/` — generation pipeline stages run in order by the `test_generation` flag: `decompose` → `grey_condition` → `variable_extraction` → `case_generation` → `attack` (ARES) → `attack_promptfoo` → `convert_test_case`. Also `extract_tool_args.py` for translation.
- `test_case_evaluation/` — three-tier label validation: `tier1_rules.py` (pattern match) → `tier2_semantic.py` (embeddings + NLI) → `tier3_llm_judge.py` (LLM), plus `classify_guidance.py` and `visualization/build_report.py`.
- `policy_agent/` — refinement engine: `red_feedback/` (DBSCAN clustering of failed cases, tuned by `CLUSTER_EPS`/`CLUSTER_MIN_SAMPLES`), `policy_analysis/regal/` (Regal), `reduce_improve/` (graph + LLM dedup), `policy_evaluation/`.
- `tests/integration/` — the `make test` scorecard harness (bash + curl against the OPA server).

## Refinement workflow (the SKILL.md contract)

When asked to improve/update a policy, the prescribed order is: (1) `policy_testing` to find FP/FN, (2) follow `opa_policy/policy_patch/policy_patch.md` to fix **every** cluster, (3) `opa_policy/policy_regal/policy_regal.md` to format, (4) `opa_policy/policy_duplication/policy_duplication.md` to dedup.

Hard rules from `SKILL.md` when editing `assets/policy.rego`:
- Never modify the policy without explicit human "yes".
- Always run tests after every change.
- Do not rewrite/refactor the whole policy; add only narrowly scoped conditions to block bypasses.
- Keep rule names, structure, and allow/deny + namespace semantics consistent.
