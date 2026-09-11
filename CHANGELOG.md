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

### Fixed

- Fixed handling of `null` system variables in test-case translation (`src/smith/test_generation/convert_test_case.py`). A null previously reached `_convert_var`, where `int(None)`/`float(None)` raised `TypeError` and aborted the whole `test_generation` run after all the expensive generation work had completed; a null that survived was written to the case as a JSON `null`, which OPA treats differently from a missing field, so the case tested the wrong policy outcome. Null variables are now handled in `_fill_template` before any coercion: the field is omitted (clearing any placeholder the case template ships), or set to `[]` for a list-typed variable.
- Repeated `generate_promptfoo_config` runs no longer append duplicate tool-parameter blocks to `testGenerationInstructions`. De-duplication only recognised the `[smith:tool-parameters]` marker, so a block written before that marker existed was treated as user-authored prose and kept, with a second block appended after it — leaving stale tool names in the instructions. The block's opening line now serves as a fallback anchor, and is shared with the builder so the two cannot drift apart.
- Tier-3 label validation no longer aborts the entire loop on a single LLM error. Transient failures now fall back for that case and continue; the loop only aborts after N consecutive failures (default 5, configurable via `run_validation`) indicating the LLM is genuinely unavailable. On abort, the remaining un-evaluated cases are still recorded as uncertain so validation metrics no longer silently shrink.
- OPA scorecard no longer silently scores request failures as "deny". Added a curl timeout and exit-code checking; failed requests are logged to `errors.txt` and excluded from TP/FP/TN/FN counts.
- Invalid `ATTACK_TOOLS` values now fail with an actionable error instead of silently disabling red-teaming, and the CLI prints which attack tools are enabled vs skipped.
- Attack-case readers no longer crash with `FileNotFoundError` when an attack file was never created (e.g. `ATTACK_TOOLS` differed between the generation and evaluation runs). `classify_promptfoo_cases`, `merge_with_ares`, and `merge_with_promptfoo` now guard on the file existing before reading it and skip gracefully with a log message when it is absent.
- ARES cases now inherit their parent test case's confidence score, verdict, and predicted label in the evaluation report instead of showing a blank confidence. An ARES case is a jailbreak-transformed variant of a parent `disallow` case, so it carries the parent's `ValidationResult` (matched by the parent's `user_input`) rather than being independently re-validated.
- Updated SKILL.md documentation to reflect "all test deny" instead of "all test failed".
- Updated car-price and call-for-papers examples' Promptfoo configuration with missing system variables.
- `opa_policy_creation.md` Step 7: changed `cp` to `mv` for the generated policy file.
- Include target tool parameters in the LLM prompt so generated test cases include concrete parameter values: src/smith/test_generation/case_generation.py

### Added

- **Test suite** (`tests/integration/`): two lanes selected by pytest marker, one pair of modules (`test_<flag>_unit.py` + `test_<flag>_integration.py`) per pipeline stage. `make unit` is offline with external boundaries faked, and is now part of `make ci`; `make integration` drives the real `smith` CLI against real services and skips cleanly when a dependency is absent. `tests/integration/TESTING_GUIDE.md` documents how to add a stage's tests.
- **Policy-bypass test-case generation** (`smith --flag bypass_case_generation`): a new pipeline that analyzes the current policy against the guidance to find divergences, then synthesizes adversarial cases targeting each gap.
  - New package `src/smith/policy_agent/policy_analysis/bypass/`: `analyze_bypass.py` (`detect_bypass_vectors`), `synthesize_cases.py` (`synthesize_bypass_cases`), `schema.py` (`BypassVector`/`BypassReport`).
  - `cli.py`: new `generate_bypass_cases()` function and the `bypass_case_generation` flag (detect → synthesize → convert), guarded against a missing/empty policy.
  - `convert_test_case.py`: new `convert_bypass_case()` routes bypass cases into `disallow/` or `allow/` with a `bypass_test_case` prefix.
  - `.env_template`: new vars `BYPASS_CASE_FILE` and `BYPASS_REPORT_DIR`.
  - `test_generation.md` rewritten to ask up front which cases to generate. User can choose general test cases (legitimate allow, disallow, ares, promptfoo), or/and bypass test cases.
- **`ATTACK_TOOLS`** environment variable to select which red-teaming tools to run (`ares`, `promptfoo`, `ares,promptfoo`, or `none`).
- **Promptfoo Improvements**
  - Integrated Promptfoo policy plugin for generating malicious test cases from guidances, with translation support for string-typed variables.
  - Promptfoo config auto-generation (`smith --flag generate_promptfoo_config`): generates or updates a Promptfoo redteam configuration file from guidance and system variables, with a customizable template (`PROMPTFOO_CONFIG_TEMPLATE`). Also appends tool parameter definitions to `testGenerationInstructions` so Promptfoo generates prompts that include concrete values for all required parameters.
  - LLM-based tool classification for promptfoo cases**: during test generation, promptfoo cases are now classified to a target tool name via a single LLM call against the MCP tool definitions, removing the hardcoded "Promptfoo" placeholder. This steps aims to make test translation apply the same tool-name mismatch check to all cases uniformly.
- **Tools**
  - Clean-up bash script (`scripts/clean_generated.sh`) to reset generated intermediates when switching examples.
  - Artifact snapshots (`smith --flag save_snapshot --dest <dir>`): copies a run's key artifacts — policy, its `_cpex` variant, guidance, tool definitions, promptfoo config, and translated test cases — flat into a destination directory. Missing sources are skipped with a warning rather than failing the snapshot.

- **Added agent examples**
  - Added an employee hub agent example. 
  - Added an HR agent example (`examples/hr-agent/`), the reference example for **CPEX support**: it demonstrates the per-tool policy workflow end to end, generating a Rego policy and its CPEX-translated `policy_cpex.rego` per tool under `smith/smith_outputs/{get_compensation,search_repo,send_email}/`. `policy-opa-2.yaml` then deploys those as an in-process OPA PDP on a policy gateway, one package per tool route (`data.compensation.allow`, `data.search_repo.allow`, `data.send_email.allow`). Includes a `README.md` walking through the Guidance Classifier and the full workflow. The agent speaks both A2A and the Smith HTTP shim (`/chat`, `/extract_tool_call`), and serves its tool definitions at `GET /tool_definitions` (`MCP_TRANSPORT=http`, no MCP server needed).
- **CPEX policy translation** (`smith --flag cpex_translate`): translates a generated OPA policy into a CPEX-compatible input shape and writes a `*_cpex.rego` copy next to the original.
- **Guidance Classifier UI** (`smith --flag classify_guidance`): maps each line of a guidance document to the tool call it constrains, then combines the selected lines into the guidance for the targeted tool(s). Serves on port 8110; the uploaded document is never modified. `src/smith/tools/guidance_classifier_server.py` + `classify_guidance_lines.py` + `guidance_classifier.html`.
- **Policy Explorer UI bridge**: `src/smith/tools/explorer_server.py` serves an interactive HTML view of the policy alongside IR (intermediate representation) data for visual inspection.
- **Session config for IR and selected tools** (`SESSION_CONFIG_FILE`, default `references/session_config.json`): when working with IR-generated specs via the Policy Explorer UI, the explorer writes this file with `use_ir` and `selected_tools`. During test generation, `translate_case` filters out test cases whose target tool is not in `selected_tools`.

### Changed

- Made ARES and Promptfoo optional dependencies — either tool can be used independently or skipped entirely.
- Cross-validation now focuses on arguments and subject fields only, improving accuracy. "Remove" decision category in cross-validation for ambiguous/invalid test cases. Cross-validation now also discards failed adversarial probes instead of relabeling them: for bypass and promptfoo cases, any audit verdict other than `keep` is collapsed to `remove` (with a marker appended to the reason), since their intent is malicious and a failed probe should not pollute the ordinary case set.
- Cluster indexing uses sequential numbers; noise group appears as the last numbered cluster instead of `-1`.
- Renamed the target-agent LLM environment variables (`RITS_*`) to `INFERENCE_MODEL`/`INFERENCE_BASE_URL`/`INFERENCE_API_KEY` across `.env_template`, examples, and documentation. `OLLAMA_BASE_URL` (no `/v1` suffix) is now reserved solely for promptfoo's native ollama provider, resolving the previous duplicate-variable collision.
- Updated example configurations (call-for-papers, car-price, RagChatbot) with revised system variables and regenerated smith outputs.
- Converted Promptfoo test cases now live in `references/test_cases/disallow/` (removed separate `promptfoo_malicious/` folder).
- `test_case_translation` skips cases that already carry an `arguments` block (already translated), making translation re-runnable and avoiding a full-corpus re-translation when only newly-added bypass cases need it.
- Reset `assets/policy.rego` to empty as a fresh starting point for policy creation.
- `get_tool_definitions()` helper in `cli.py` to deduplicate MCP tool extraction across `test_generation`, `bypass_case_generation`, and `get_mcp_parameter` flags.
- `make ci` is now `lint + license-check + unit` (was `lint + lint-policy + license-check`). `make lint-policy` is no longer in the gate and has no CI job, so run it locally when changing a `.rego` file. 


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

[Unreleased]: https://github.com/IBM/smith/compare/0.1.1...HEAD
[0.1.1]: https://github.com/IBM/smith/compare/0.1.0...0.1.1
[0.1.0]: https://github.com/IBM/smith/releases/tag/0.1.0
