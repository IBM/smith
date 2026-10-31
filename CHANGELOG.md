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

### Security

- Enabled TLS certificate verification for every OpenAI-compatible HTTP client: `verify=False` is removed from all 16 call sites across 15 files ([#120]).
- Bumped mcp to 1.30.0 to fix [#118], and brought `uv.lock` back in step with `pyproject.toml`. mcp 2.x is capped out because it removes `mcp.shared.context.RequestContext`, which the example agents' `langchain-mcp-adapters` imports ([#120], [#121]).

### Added

- **Evaluation pipeline** (`tests/run_smith_pipeline.py`): drives the full workflow for one example agent as headless `/smith` prompts, one step at a time, with `--steps`, `--resume`, `--carry` and `--dry-run` ([#105]).
- **Per-step result tables**: each step prints the table its research question needs — suite composition, translation funnel, confusion matrix with coverage, cross-validation verdicts, and before/after effect tables for patching, Regal and duplication — and writes the same figures as CSV beside the run's logs. The refinement steps measure by re-running the analysis flags on each side of the step, so a delta is a fresh measurement; those runs are excluded from the cost table ([#105]).
- **`--save-artifacts DIR`**: archives each step's artifacts under `DIR/step<N>/`, mirroring the source tree. Refinement steps are saved twice, `before/` and `after/`, because the measurement rewrites the same suggestion files ([#105]).
- **`smith_evaluationn.md`**: the research questions, agent dataset, metrics and result tables ([#105]).

### Changed

- Reduced the LLM client timeout from 300s to 100s ([#120]).

### Fixed

- Duplication analysis resolves policy-directory symlinks before mounting them into Docker, reports OPA parse failures, and preserves the earlier AST when parsing fails ([#105]).
- Evaluation runs now stop on failed steps or incomplete refinement measurements, use the selected example's environment for measurements, and sum distinct session costs without counting resumed or carried sessions twice ([#105]).
- Policy creation keeps permission grants separate from the final `allow` decision so a matching deny cannot be bypassed by another grant ([#105]).
- `duplication_suggestion` no longer crashes when an `allow` rule body is a call term such as `count(deny) == 0`. The graph parser now links call operands, skips builtins and `__local*` temporaries, names partial set rules from their head ref, keeps isolated `allow` and `deny` heads, and skips the unreachable-rule report with a clear message when the policy has no `allow` rule ([#117]).
- `generate_promptfoo_config` now sets `max_tokens`, so a config for a larger guidance file is no longer truncated into a `JSONDecodeError` ([#105]).
- Integration tests no longer take their system variables from whatever agent `.env` points at. `decompose` may only choose an action from `action_list`, so a mismatched pair left `"other"` as the only valid answer and no generated case could target the extracted tool ([#119], [#120]).
- Fixed an over-strict assertion in `test_guidance_reconciliation_integration.py` that failed on a third-party import notice written to stderr ([#120]).

## [0.2.0] - 2026-10-17

### Security

- Removed the unused NLTK dependency and bumped cryptography, Pillow, pip, setuptools and PyTorch to patched versions ([#61]).
- Bumped anyio to fix CVE-2026-63374 ([#83]) and fixed CodeQL alerts ([#103]).
- Bumped pyjwt, urllib3, litellm and langgraph-sdk, in Smith and the example agents ([#88], [#89], [#90], [#91], [#99], [#101]).

### Added

- **Security-Grounded Guidance Analysis**: a four-step workflow (architecture, questionnaire, threat model, enforcement mapping) that derives security guidelines from the OWASP Agentic Top 10 ([#44]). Phases are resumable with validated handoffs, and guidance reconciliation and merge are gated ([#75], [#76]).
- **Incremental test generation** (`test_generation --mode update`): regenerates only the cases whose guidance changed, tracked in a guidance → case map ([#71]).
- **Parallel generation and translation**: `GENERATION_CONCURRENCY` ([#86]) and `TRANSLATION_CONCURRENCY`, plus online-model support for the target agent ([#74]).
- **Bypass test cases** (`bypass_case_generation`): adversarial cases for gaps between the policy and the guidance ([#27]).
- **Promptfoo**: policy-plugin red-teaming, `generate_promptfoo_config`, and LLM tool classification of its cases ([#15], [#39]). `ATTACK_TOOLS` selects which red-teaming tools run ([#15]).
- **CPEX translation** (`cpex_translate`) ([#39]).
- **Tools**: `reset_policy` ([#71]), `save_snapshot`, the Guidance Classifier UI, the Policy Explorer bridge and `SESSION_CONFIG_FILE` ([#39]).
- **Examples**: employee hub agent ([#34]) and HR agent ([#39]).
- **Tests**: unit and integration suites per pipeline stage, via `make unit` and `make integration` ([#45], [#92]).
- **Docs**: Hugo documentation site ([#15]) and `CONTRIBUTING.md` ([#63]).

### Changed

- Policy input `arguments` is now `args` in the guides, for CPEX compatibility ([#45]).
- Default agent port in Promptfoo configs is now 9000 (was 8000) ([#45]).
- Removed the top-k setting from LLM calls, since AWS models accept only temperature or top-k ([#45]).
- Renamed `RITS_*` variables to `INFERENCE_*`; `OLLAMA_BASE_URL` is now only for Promptfoo ([#15]).
- ARES and Promptfoo are optional ([#15]).
- Cross-validation checks only arguments and subject fields, adds a `remove` verdict, and discards failed adversarial probes ([#15], [#27]).
- Cluster indexing is sequential; the noise group is last instead of `-1` ([#15]).
- Promptfoo cases are written to `references/test_cases/disallow/` ([#15]).
- `test_case_translation` skips already-translated cases ([#27]).
- `bypass_case_generation` clears earlier bypass cases first ([#71]).
- `make ci` is now lint + license-check + unit; `make lint-policy` is no longer in the gate ([#45]).
- Security-analysis guides are leaner: one shared worker contract and compact artifacts ([#59], [#75], [#76]).
- README points to the HR agent; example outputs and `.env_template` defaults refreshed ([#92]).
- Raised minimum dependency versions: `mcp`, `networkx`, `sentence-transformers`, `pip-audit`, `build` and the CI setup actions ([#61]); `openai` (>=3.26.0, major bump), `numpy`, `tqdm`, `black`, `ruff` ([#107], [#108], [#109], [#110], [#111]); and `python-dotenv`, `pydantic`, `typer`, `twine`, `pytest-socket`, `matplotlib`, `pandas`, `requests`, `pydot` ([#64]–[#68], [#94]–[#98]).

### Fixed

- `apply_cross_validate` no longer overwrites an existing case on a `cv_` name collision ([#71]).
- ARES: reads JSON Lines output, pins the Qwen connector to `device: cpu` (MPS segfault), and passes guidance through to attack cases ([#71]); cases inherit the parent's confidence in the report ([#27]).
- A `null` numeric system variable no longer aborts `test_generation` ([#45]).
- `generate_promptfoo_config` no longer appends duplicate tool-parameter blocks ([#45]).
- Fixed AST graph indices carrying over between calls, and added missing `.env_template` variables ([#45]).
- Tier-3 label validation continues past a single LLM error ([#15]).
- The OPA scorecard excludes failed requests instead of scoring them as deny ([#15]).
- An invalid `ATTACK_TOOLS` value now errors instead of silently disabling red-teaming ([#15]).
- Missing attack files no longer crash the readers ([#27]).
- Test-case prompts include target tool parameters ([#15]).
- Security-analysis phases require a resolved-path envelope and reject rules on data OPA cannot see ([#76]).

## [0.1.1] - 2026-06-29
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

[Unreleased]: https://github.com/IBM/smith/compare/0.2.0...HEAD
[0.2.0]: https://github.com/IBM/smith/compare/0.1.1...0.2.0
[0.1.1]: https://github.com/IBM/smith/compare/0.1.0...0.1.1
[0.1.0]: https://github.com/IBM/smith/releases/tag/0.1.0

[#15]: https://github.com/IBM/smith/pull/15
[#27]: https://github.com/IBM/smith/pull/27
[#34]: https://github.com/IBM/smith/pull/34
[#39]: https://github.com/IBM/smith/pull/39
[#44]: https://github.com/IBM/smith/pull/44
[#45]: https://github.com/IBM/smith/pull/45
[#59]: https://github.com/IBM/smith/pull/59
[#61]: https://github.com/IBM/smith/pull/61
[#63]: https://github.com/IBM/smith/pull/63
[#64]: https://github.com/IBM/smith/pull/64
[#65]: https://github.com/IBM/smith/pull/65
[#66]: https://github.com/IBM/smith/pull/66
[#67]: https://github.com/IBM/smith/pull/67
[#68]: https://github.com/IBM/smith/pull/68
[#71]: https://github.com/IBM/smith/pull/71
[#74]: https://github.com/IBM/smith/pull/74
[#75]: https://github.com/IBM/smith/pull/75
[#76]: https://github.com/IBM/smith/pull/76
[#83]: https://github.com/IBM/smith/pull/83
[#86]: https://github.com/IBM/smith/pull/86
[#88]: https://github.com/IBM/smith/pull/88
[#89]: https://github.com/IBM/smith/pull/89
[#90]: https://github.com/IBM/smith/pull/90
[#91]: https://github.com/IBM/smith/pull/91
[#92]: https://github.com/IBM/smith/pull/92
[#94]: https://github.com/IBM/smith/pull/94
[#95]: https://github.com/IBM/smith/pull/95
[#96]: https://github.com/IBM/smith/pull/96
[#97]: https://github.com/IBM/smith/pull/97
[#98]: https://github.com/IBM/smith/pull/98
[#99]: https://github.com/IBM/smith/pull/99
[#101]: https://github.com/IBM/smith/pull/101
[#103]: https://github.com/IBM/smith/pull/103
[#107]: https://github.com/IBM/smith/pull/107
[#108]: https://github.com/IBM/smith/pull/108
[#109]: https://github.com/IBM/smith/pull/109
[#110]: https://github.com/IBM/smith/pull/110
[#111]: https://github.com/IBM/smith/pull/111
[#105]: https://github.com/IBM/smith/pull/105
[#117]: https://github.com/IBM/smith/issues/117
[#118]: https://github.com/IBM/smith/issues/118
[#119]: https://github.com/IBM/smith/issues/119
[#120]: https://github.com/IBM/smith/pull/120
[#121]: https://github.com/IBM/smith/issues/121
