# Contributing to Smith

Smith welcomes external contributions. If you have an itch, please feel free to
scratch it.

To contribute code or documentation, submit a [pull request](https://github.com/IBM/smith/pulls).
A good way to get familiar with the codebase is to tackle low-hanging fruit in
the [issue tracker](https://github.com/IBM/smith/issues). Before a more ambitious
contribution, please [open an issue](https://github.com/IBM/smith/issues) first
so the approach can be discussed.

## Prerequisites

- **Python 3.11+** — the CLI and pipelines target 3.11 and 3.12.
- **OPA** and **[Regal](https://github.com/StyraInc/regal#getting-started)** —
  required to lint, run, and test Rego policies.
- **[ARES](https://github.com/IBM/ares)** and **[Promptfoo](https://www.promptfoo.dev/)**
  — required only for adversarial test generation (install separately; see the
  [README](README.md)).

## Development workflow

The [`Makefile`](Makefile) mirrors CI — a green `make ci` locally means a green
pipeline:

```bash
make install         # create a uv venv and install Smith (editable) + [dev] extras
make lint            # ruff check + black --check over src/ (read-only)
make format          # ruff --fix + black (apply formatting)
make lint-policy     # Regal/OPA lint of assets/policy.rego (NOT part of `make ci`)
make license-check   # verify every in-scope file carries the SPDX header
make test            # policy scorecard (needs Docker + the OPA server)
make unit            # env-free offline pytest subset (part of `make ci`)
make integration     # the live suite: real CLI against real services (opt-in)
make ci              # the gate: lint + license-check + unit
```

Package management uses [`uv`](https://docs.astral.sh/uv/). Build and publish
with `make package` / `make publish` (`uv build` / `uv publish`).

## Before you open a PR

Run **both** of these, and paste the results in the PR description:

```bash
make ci            # the gate: lint (ruff + black) + license-check + unit
make integration   # the live suite, one test module per `smith --flag`
```

`make ci` is read-only, it reports problems rather than fixing them. Run
`make format` to apply the ruff/black fixes and `make license` to insert missing
SPDX headers, then re-run `make ci`. 

### What `make integration` covers

It is one pytest module per **`smith --flag <stage>`** — the tests run the real
CLI (`python -m smith.cli --flag <stage>`) against the real services and then
assert the artifacts that stage wrote. So "integration passed" means every
pipeline stage still starts, connects to its neighbours, and produces the files
the next stage reads. Currently covered flags:

`get_current_agent` · `get_mcp_parameter` · `test_generation` ·
`bypass_case_generation` · `generate_promptfoo_config` · `test_case_evaluation` ·
`test_case_translation` · `policy_testing` · `policy_validation` (+ `_fix`) ·
`cross_validate` (+ `apply_cross_validate`) · `red_suggestion` ·
`regal_suggestion` · `duplication_suggestion` · `cpex_translate` ·
`save_snapshot` · `classify_guidance` · `open_explorer`

Two things to know before you run it:

- **Nothing is required.** Each module *skips cleanly* when its dependency is
  absent — Docker/OPA, an LLM (`OPENAI_*` / `MODEL_SONNET`), the example agent,
  ARES, Promptfoo. A bare run on a fresh laptop is safe and will mostly skip.
  Read the skip reasons (`-ra` is on by default): a stage you touched that
  *skipped* was not actually tested.

### Running one stage's integration test by hand

`make integration` runs everything; while iterating, run just the file for the
stage you changed:

```bash
# one stage, verbose, with skip reasons
source .venv/bin/activate 
python pytest tests/integration/test_policy_testing_integration.py -m integration -v -ra

# a single test inside that file
python pytest \
  tests/integration/test_policy_testing_integration.py::test_the_confusion_matrix_matches_the_frozen_expectation \
  -m integration -v

# the matching unit file — offline, no .env, fast
.venv/bin/python -m pytest tests/integration/test_policy_testing_unit.py -m unit

# see what would run without running it
.venv/bin/python -m pytest tests/integration --collect-only -m integration
```

The file for a flag is `tests/integration/test_<flag>_integration.py`, with a few
historical names: `test_generation_integration.py` (`test_generation`),
`test_translation_integration.py` (`test_case_translation`), and
`test_case_evaluation_integration.py` (`test_case_evaluation`).

### If you add a new CLI flag

A new `smith --flag <name>` is not done until it has **both** test lanes:

| File | Marker | Runs in CI | Boundary |
|---|---|---|---|
| `tests/integration/test_<flag>_unit.py` | `unit` | yes (`make ci`) | faked — env-free, offline, no Docker/LLM |
| `tests/integration/test_<flag>_integration.py` | `integration` | no (opt-in) | real services, coarse assertions |

Follow [`tests/integration/TESTING_GUIDE.md`](tests/integration/TESTING_GUIDE.md) to create additional tests
— it is the normative document and gives the recipe plus a worked reference pair
(`test_case_evaluation_{unit,integration}.py`). 

## If you change the skill files

The markdown under [`SKILL.md`](SKILL.md), [`opa_policy/`](opa_policy), and
[`test_generation/`](test_generation) is *not* code — it is the instructions a
coding agent follows. `make ci` and `make integration` cannot test it: they
exercise the CLI stages behind the flags, never the orchestration that decides
which flag to run when. **A change to any of those files has to be validated by
actually running the skill end to end** against one example agent.

### Setup

**1. Place the skill where your agent finds it**

Claude Code resolve `/smith` against `.claude/skills/` under
their own working directory, Bob uses `.bob/skills/`:

```
<workspace>/                         # the agent's cwd
└── .claude/skills/smith/            # this repo
```

**2. Python environment + the Smith CLI**

```bash
cd .claude/skills/smith
make install                 # uv venv + editable install; provides the `smith` CLI
source .venv/bin/activate
```

**3. `.env`**

```bash
cp .env_template .env
```

Paths are relative to `BASE_URL`, which is the absolute path to the skill folder
**with a trailing slash**. For the `hr-agent` example:

```dotenv
BASE_URL=/absolute/path/to/<workspace>/.claude/skills/smith/

# the LLM Smith's own pipelines use
OPENAI_API_KEY=<your key>
OPENAI_BASE_URL=<your endpoint>
MODEL_SONNET=<model>

# the target agent
AGENT_URL=http://localhost:9000
TARGET_AGENT_PATH=examples/hr-agent/
GUIDANCE_FILE=examples/hr-agent/smith/guidance.txt
SYSTEM_VAR_FILE=examples/hr-agent/smith/system_vars.json
PROMPTFOO_CONFIG_FILE=examples/hr-agent/smith/promptfooconfig.yaml
PROMPTFOO_OUTPUT_FILE=examples/hr-agent/smith/redteam.yaml

# hr-agent serves its tool definitions at GET /tool_definitions — no MCP server
MCP_TRANSPORT=http
MCP_URL=http://localhost:9000/tool_definitions

ATTACK_TOOLS=promptfoo    # or `ares,promptfoo`, or `none`
```

Confirm it resolved: `smith --flag get_current_agent` should print the
`target_agent` path and the resolved guidance file.

**4. Adversarial tooling** (optional — needed only for red-team coverage; set
`ATTACK_TOOLS=none` to skip)

```bash
npm install -g promptfoo
export PROMPTFOO_DISABLE_TELEMETRY=1
export PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION=true
export PROMPTFOO_DISABLE_SHARING=true
```

ARES installs under `src/smith/test_generation/ares/` in its **own** venv:

```bash
cd src/smith/test_generation/ares
python -m venv .venv && source .venv/bin/activate
curl https://raw.githubusercontent.com/IBM/ares/refs/heads/main/install.sh | bash
ares install-plugin ares-autodan
ares install-plugin ares-human-jailbreak
ares install-plugin ares-garak
cp ../ares_config/qwen-owasp-llm-01.yaml ./example_configs
cp ../ares_config/human_jailbreaks.json ./assets
export ARES_HOME=/absolute/path/to/smith/src/smith/test_generation/ares
deactivate && cd ../../../../ && source .venv/bin/activate
```

**5. Start the target agent and OPA**

```bash
cd examples/hr-agent
pip install -r requirements.txt
ollama pull qwen3.5                                     # the example's local model
uvicorn server:app --host 0.0.0.0 --port 9100  &        # MCP server (own terminal)
uvicorn agent:app  --host 0.0.0.0 --port 9000  &        # the agent  (own terminal)
```

**6. Start Claude Code**
```bash
# From `<workspace>` (not the skill directory — that's where `/smith` resolves)
claude --model "model name" # claude code
```

### Test sentences

These prompts are optional, you can run all of them, or run each independantly to test a specific part. 

#### Overall checking
When running a prompt, at the end, it should prompt you next steps as well. 

#### Checking for each steps
| # | Prompt | Check it passed |
|---|---|---|
| 1 | `/smith create an opa policy for target agent` | `assets/policy.rego` is non-empty and `make lint-policy` is clean, remember to check if the generated policy makes sense. |
| 2 | `/smith generate test cases, generate both guidance targeted cases and policy bypass cases` | `references/test_cases/allow/` and `.../disallow/` are populated (adversarial cases land in `disallow/` as `promptfoo_test_case*.json` / `bypass_test_case*.json`); the CLI names which attack tools ran vs were skipped. It equals to `smith --flag test_generation` and `smith --flag bypass_case_generation` |
| 3 | `/smith translate test cases` | the cases carry an `input.args` envelope resolved via the agent's `/extract_tool_call`. It equals to `smith --flag test_case_translation` |
| 4 | `/smith test my policy` | `FP/FN listed, and seems reasonable (test case number is larger than 0, some tests pass, and some might fail.) |
| 5 | `/smith cross validate checking test cases` | cross validation results seem reasonable |
| 6 | `/smith patch the failed test cases` | policy edited; the final result shows **fewer failures** and no new ones, and fixing processes/reasons are reasonable |
| 7 | `/smith get regal suggestions and fix the problems` | The suggestions and fixing seems reasonable, FP and FN are not changed |
| 8 | `/smith get duplication suggestions and fix the problems` | The suggestions and fixing seems reasonable, FP and FN are not changed |
| 9 | `/smith test my policy` | final scorecard: failures at or below step 4's, total cases not reduced |

## Documentation conventions

There are three kinds of prose in this repo, and they are maintained differently:

- **The Hugo site**, [`docs/content/docs/`](docs/content/docs) — published to
  <https://IBM.github.io/smith/> by `.github/workflows/docs-deploy.yaml` on every
  push to `main` that touches `docs/**`. One page per workflow stage, ordered by
  the `weight:` in each page's front matter. Images go in `docs/static/images/`
  and are referenced by relative path. Build it locally with `hugo server` from
  `docs/` before pushing; `docs/public/` and `docs/resources/` are build output —
  don't hand-edit them.
- **The skill guides**, [`SKILL.md`](SKILL.md) and the markdown under
  [`opa_policy/`](opa_policy) / [`test_generation/`](test_generation) — these are
  *executable* in the sense that an agent follows them literally. Changing them
  changes behavior, so they get validated by an end-to-end run (see above), not
  just proofread.
- **The root documents** — [`README.md`](README.md), this file,
  [`CLAUDE.md`](CLAUDE.md). Note that `docs/content/docs/contributing.md`
  deliberately *summarizes* and links to this file rather than duplicating it; if
  you change the commands here, keep that page's command list in step.

## Changelog

We keep a [`CHANGELOG.md`](CHANGELOG.md). When your change
is user-visible — a new feature, a behavior change, a deprecation/removal, a bug
fix, or a security fix — add an entry under the `## [Unreleased]` section in the
appropriate group (**Added**, **Changed**, **Deprecated**, **Removed**,
**Fixed**, **Security**). Maintainers promote the `Unreleased` entries under a new
dated version heading when cutting a release tag.

## Legal — Developer Certificate of Origin

Contributions are accepted under the [Developer Certificate of Origin (DCO) 1.1](https://developercertificate.org/).
Sign off every commit to certify you wrote the patch or otherwise have the right
to submit it under the project's license:

```bash
git commit -s
```

This adds a `Signed-off-by` trailer:

```text
Signed-off-by: Jane Doe <jane.doe@example.com>
```

## Security

Do not report security vulnerabilities through public issues or PRs. See
[SECURITY.md](SECURITY.md) for private disclosure via GitHub's vulnerability
reporting.

## Communication

Connect with us through the [issue tracker](https://github.com/IBM/smith/issues).
