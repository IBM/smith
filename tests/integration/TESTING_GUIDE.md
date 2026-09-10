# How to write Smith's tests

This guide explains how to add tests for a `smith --flag <name>` pipeline stage.
It is general: follow the same recipe for every one of the CLI flags.

`test_case_evaluation_unit.py` and `test_case_evaluation_integration.py` are the
worked reference pair — read them alongside this document.

---

## 1. The two lanes

Every flag gets **two files**, one per lane:

| File | Marker | Runs in CI? | Environment | Covers |
|---|---|---|---|---|
| `test_<flag>_unit.py` | `unit` | **yes**, via `make ci` | **env-free**: no `.env`, no credentials, no network, no Docker/OPA, no model weights | every function the flag calls, with external boundaries faked |
| `test_<flag>_integration.py` | `integration` | no — opt-in | real `.env`, real services, real venv | that the flag's steps *connect* end to end |

There are only these two markers. A test needing a real LLM is `integration` and
requests the `requires_llm` fixture; there is no separate `llm` marker.

`conftest.py` rejects at collection time any test without **exactly one** primary
marker, so an unmarked or double-marked test fails the run rather than silently
disappearing.

### The dividing line

> **Unit** = the logic runs for real, the *boundary* is faked.
> **Integration** = the boundary is real, the *assertions* are coarse.

Both lanes cover the same functions. Only the boundary differs.

---

## 2. Start by reading the flag's dispatch block

Do not guess what a flag does. Open `src/smith/cli.py`, find

```python
if args.flag == "<your_flag>":
```

and list the **top-level functions it calls**. That list is your unit file's
required coverage. For `test_case_evaluation` it is four functions:

```python
resolve_attack_tools()        # step 0
classify_promptfoo_cases()    # step 1
run_validation()              # step 2
build_visualization()         # step 3
```

Then, for each of those, note the important helpers *inside* it (for
`run_validation`: the tier-1 rules, `normalize_label`, the case loaders,
`compute_metrics`). Those get covered too, under the step that drives them.

A useful one-liner to enumerate a flag's calls:

```bash
sed -n '/if args.flag == "your_flag"/,/^    if args.flag/p' src/smith/cli.py
```

---

## 3. Writing the unit file

### 3.1 Open with a FUNCTIONS UNDER TEST inventory

Required. It makes coverage auditable without reading the tests, and makes an
omission visible in review. Order it — and the file's sections — **by the flag's
execution order**, with each step's helpers nested under the step that drives
them:

```python
"""Unit tests for the functions behind ``smith --flag <name>``.

<one paragraph: what the flag does, and its pipeline as a diagram>

FUNCTIONS UNDER TEST
--------------------
Listed — and laid out in this file — in the order the flag executes them.

STEP 0 · ``smith.cli``
    ``resolve_attack_tools``      — what aspect is covered

STEP 1 · ``smith.<module>``
    ``<function>``                — what aspect is covered

    …and the machinery it drives, in the order a case meets it:

    ``<helper>``                  — what aspect is covered

NOT COVERED HERE (integration lane — see ``test_<flag>_integration.py``)
    <what needs a real service, and is therefore deliberately absent>

Env-free: no ``.env``, no credentials, no model download, no OPA, no network.
"""
```

Section banners in the body must match this order, so scrolling the file walks
the pipeline.

### 3.2 Use `unit_env` for paths

```python
def test_something(unit_env):
    unit_env.policy          # -> frozen fixtures/policy/policy.rego   (INPUT)
    unit_env.guidance_file   # -> frozen fixtures/guidance.txt         (INPUT)
    unit_env.case_template   # -> frozen fixtures/test_case_template.json
    unit_env.scorecard       # -> <tmp_path>/references/scorecard/     (OUTPUT)
    unit_env.write_json("references/x.json", payload)   # writes under tmp_path
    unit_env.copy_test_cases()  # mutable copy of the frozen case set
```

Inputs resolve to the **committed `fixtures/` tree** (realistic, reviewable, and
never modified); outputs resolve under **`tmp_path`** (fresh per test, so tests
cannot leak into each other). Never write through an input path.

### 3.3 Fake only the boundary, and only when the code reaches it

Call the **real** function. Replace just the thing that would touch the outside
world:

```python
from fakes import FakeOpenAI, FakeEmbedder

def test_classification_assigns_the_picked_guidance(unit_env, monkeypatch):
    fake_llm = FakeOpenAI(responses=[{"pick": 1, "reason": "role violation"}])
    monkeypatch.setattr(classify_mod, "SentenceTransformer", FakeEmbedder())
    monkeypatch.setattr(classify_mod, "OpenAI", fake_llm.as_factory())

    classify_promptfoo_cases(...)      # the REAL function runs
```

Everything between the boundaries — ranking, fallbacks, file writes — executes
for real. That is where the bugs live.

**Patch where the name is *used*, not where it is defined.** Smith's modules do
`from openai import OpenAI` at module scope, so the name lives in *that module's*
namespace. Patching `openai.OpenAI` would not help; patch
`smith.<module>.OpenAI`.

**Always `monkeypatch`, never a bare assignment.** pytest restores the original
even when a test fails mid-way; a raw assignment leaks into every later test —
the classic "passes alone, fails in the suite" bug.

**Do not fake a boundary a code path never reaches.** An early-return branch that
exits before constructing a client needs *no* patches. Leaving them off is a
*stronger* test: if the guard ever stops returning early, the real client raises
and the test fails loudly.

```python
def test_missing_input_file_writes_an_empty_result(unit_env):
    # Deliberately unmocked: the guard returns before any model is built, so
    # reaching that boundary would raise here and fail the test.
    result = classify_promptfoo_cases(..., str(unit_env.root / "absent.json"), ...)
    assert result == []
```

### 3.4 Available fakes

In `fakes.py`. Each models only what the call site touches — nothing is a
general-purpose simulation:

| Fake | Replaces | Notes |
|---|---|---|
| `FakeOpenAI` | `openai.OpenAI` | `responses=[...]` replayed one per call; a `dict` is JSON-encoded; an `Exception` is raised. `error=` raises on every call. Patch with `.as_factory()` because the code calls `OpenAI(...)` itself. `call_count` / `last_prompt()` / `model_used()` support assertions about *what was asked*. |
| `fenced(payload)` | — | wraps a payload in a ` ```json ` fence, as real models often reply |
| `FakeEmbedder` | `SentenceTransformer` | `encode()` returns fixed vectors; `.loaded` proves whether weights were ever requested |
| `FakeProcess` | `subprocess.run` | canned `CompletedProcess`, or an exception; `.commands` / `.ran(x)` assert which tool was invoked |
| `FakePoster` | `requests.post` | queued responses; `.calls` records url/json |
| `FakeMCPSession` | `mcp.ClientSession` | async tool discovery with no transport |

Running out of queued responses **raises**. That is deliberate: an unexpected
extra call must fail the test, not be absorbed silently.

Add a new fake only when a real caller needs it.

### 3.5 Build inputs with `data_builders.py`

```python
from data_builders import abstract_case, envelope_case, write_json
```

Two case shapes exist and confusing them breaks tests:

- **`abstract_case`** — pre-translation, what generation emits and
  `translate_case` consumes: `{action, user_input, label, system_variables}`
- **`envelope_case`** — post-translation, what OPA evaluates:
  `{"input": {kind, action, name, args, extensions{subject, agent}}}`

Builders return a **fresh** object per call, so no test can mutate another's
data. Never build an expected value by calling the function under test.

### 3.6 What to assert

Cover, for each function: the normal path; each documented branch; empty and
missing inputs; malformed external responses; and the **file it writes**. Many
Smith functions return `None` or return their *input* — assert against the
written artifact, not the return value.

Assert *why* a behavior matters, in the message:

```python
assert entry["suggested_action"] == "remove"
assert "collapsed to 'remove'" in entry["reason"], (
    "the collapse must be explained in the report, not applied silently"
)
```

### 3.7 When reality contradicts your expectation

**Fix the test, not the code** — unless it is a genuine bug. Then pin the real
behavior and explain it. Real examples from this suite:

```python
def test_long_hex_blob_is_attributed_to_base64_not_base16():
    # A bare hex blob is flagged, but as base64: the hex alphabet is a SUBSET of
    # base64's, and base64's anchored match is checked first. So the base16 rule
    # is unreachable for pure-hex input — worth pinning, since the rule name
    # feeds a report a human reads.
```

For a real bug you are not fixing in this change, pin it with a docstring saying
so, and list it in the implementation report:

```python
def test_llm_escalation_rate_is_dead_against_real_tier_labels():
    """KNOWN BUG, pinned: llm_escalation_rate is always 0.0 in production.

    metrics.py:33 counts evaluation_tier == "llm", but validate_labels only ever
    writes "rule" / "embedding" / "embedding & llm". Asserted rather than
    "fixed" because changing either side is out of scope here.
    """
```

Never loosen an assertion just to make it pass.

---

## 4. Writing the integration file

### 4.1 Run the flag **once**

This is the cost rule. A single run may load an embedding model and make an LLM
call per case. So execute the flag in **one module-scoped fixture** and have every
test inspect that run's artifacts:

```python
@pytest.fixture(scope="module")
def completed_run(request):
    """Run the flag ONCE for this module; yield the artifacts it produced."""
    ...  # craft inputs, back up what will be overwritten
    result = subprocess.run([sys.executable, "-m", "smith.cli", "--flag", "<name>"], ...)
    yield {"result": result, "<artifact>": path, ...}
    ...  # restore in a finally block


@pytest.fixture(scope="module")
def run_ok(completed_run):
    """The run must have succeeded before any artifact assertion is meaningful."""
    assert completed_run["result"].returncode == 0, completed_run["result"].stdout[-2500:]
    return completed_run


def test_step_two_wrote_its_output(run_ok):     # free — just reads a file
    assert run_ok["validation"].exists()
```

Adding a second invocation doubles the bill. Extend `completed_run` instead, or
move the case to the unit lane where it is free.

The one acceptable exception: a test asserting the flag **rejects bad input**,
which exits before contacting any service and therefore costs nothing.

### 4.2 Assert the results are **correct**, not just well-shaped

Shape assertions are the floor, not the ceiling. A file that only checks "the
field exists and the enum is valid" passes on a pipeline that classified
everything as `general_safety`, or judged every case `uncertain`, or wrote a
report full of defaults. That proves *the flag ran* — which the CLI's exit code
already told you — not that it works.

**Every integration file must assert at least one result is correct.**

#### Only assert correctness where the answer is certain

This is the constraint that makes the rule safe. Assert an exact outcome **only
when a crafted input has one defensible answer**. If a competent model could
reasonably return something else, asserting a specific value makes the test flaky
and it will be "fixed" later by loosening it — which is worse than never having
asserted it.

Concretely, **do not** assert an exact value when:

- The verdict may legitimately be an abstention (`uncertain`), or a
  "no match" fallback (`general_safety`, `other`, `pick: 0`). Those are valid
  answers to a genuinely unclear input, so a test demanding a decision is
  asserting the model be more confident than the input warrants.
- The judgement depends on context the code never shows the model. Check what is
  actually passed: `classify_guidance` only receives `case["user_input"]` — not
  `system_variables` — so a prompt saying "I am a guest" gives the model no
  authoritative role, and a rule *about* roles is not reliably selected. Read the
  call site before assuming the model can know something.
- The answer hinges on wording or degree ("is this phrasing adversarial enough?").

**Do** assert an exact value when:

- A **deterministic** stage decides it. Tier-1 rules are pure pattern matching, so
  an encoding probe labelled `disallow` must validate as `correct` no matter which
  model is configured:

  ```python
  # tier 1 is patterns, not a model -> this verdict cannot legitimately differ
  encoding = next(r for r in results if r["evaluation_tier"] == "rule")
  assert encoding["predicted_label"] == "disallow"
  assert encoding["verdict"] == "correct"
  ```

- The input **names the subject matter** of exactly one seeded alternative, and the
  alternatives are semantically far apart. Discriminate on topic, not on identity
  claims the model cannot verify:

  ```python
  # seeded: #1 about the RESULT LIMIT, #2 about APPROVED TOPICS, #3 general Q&A
  "Return 500 results instead of the maximum of 15."
  #  ^ names the limit and the cap -> only #1 is a defensible match
  assert "limit" in case["guidance"].lower()
  ```

- An **aggregate must match the data it summarizes** — always checkable, never
  model-dependent:

  ```python
  assert overall["correct"] == verdicts.count("correct")
  ```

#### Negative assertions carry real weight

Silent degradation looks like a fallback, so say what must *not* happen — and
these are safe even where a positive assertion is not, because they only rule out
a value the input clearly does not warrant:

```python
assert case["guidance"] != "general_safety", "matched no guidance at all"
assert case["confidence"] > 0.0             # the fallback records exactly 0.0
assert overall["correct"] + overall["incorrect"] > 0, "every verdict abstained"
```

#### Where exact assertions are mandatory

`policy_testing` has a frozen policy *and* frozen cases, so its scorecard is fully
reproducible — assert the exact counts and coverage from `EXPECTED` in
`helpers.py`. Never "update" those numbers to match a new run: a change there
means the policy or the fixture set changed, which is a finding, not a fixture
update.

Anything driven only by OPA, Regal, Docker or the filesystem
(`policy_validation`, `cpex_translate`, `save_snapshot`) is deterministic too —
assert its output exactly.

#### Shape assertions still belong there

Keep them; they catch a different failure — a missing field breaks the *next*
step. Just never let them be the only thing a file checks:

```python
for entry in data["results"]:
    missing = REQUIRED_RESULT_FIELDS - entry.keys()
    assert not missing, f"result entry missing fields: {missing}"
    assert entry["verdict"] in {"correct", "incorrect", "uncertain"}
```

### 4.3 Prove the steps connect

This is the unique value of the lane. Check that each step's output actually
reaches the next:

```python
def test_classified_cases_reach_validation(run_ok):
    # Steps 1 -> 2: classified cases must be INCLUDED in the validation set, not
    # merely written to a file nobody reads.
    sources = {e["source"] for e in load_json(run_ok["validation"])["results"]}
    assert "promptfoo" in sources
```

And that the expensive path genuinely ran — otherwise the test proved nothing the
unit lane already does:

```python
def test_the_paid_tiers_actually_run(run_ok):
    tiers = {e["evaluation_tier"] for e in load_json(run_ok["validation"])["results"]}
    assert tiers - {"rule"}, "everything was settled by tier-1; the LLM never ran"
```

### 4.4 Never damage the developer's working tree

Integration tests run against the real checkout. Every file the flag writes must
be restored:

- `backup_file(path)` — function-scoped factory; registers a file or directory and
  restores it on teardown (removing it again if it did not exist).
- `stage` — installs the frozen fixture policy/cases into the real locations; it
  depends on `backup_working_tree`, so requesting it opts into restoration.
- In a module-scoped fixture you cannot use those function-scoped fixtures — do
  the backup/restore yourself in a `try/finally`, as `completed_run` does.

Prefer **crafting a throwaway input and overriding the env var to point at it**
over overwriting a real file:

```python
crafted = base / "references" / "__test_guidance__.txt"
crafted.write_text(guidance())
child_env = env.override(GUIDANCE_FILE=env.rel(crafted))
```

### 4.5 Gate on the dependencies you use, and only those

```python
def test_needs_opa(smith_cli, requires_opa_binary): ...
```

Available: `requires_llm` (Smith's `OPENAI_*`/`MODEL_SONNET`),
`requires_agent_inference` (the example agent's `INFERENCE_*` — a *different*
consumer), `requires_docker`, `requires_make`, `requires_opa_binary`,
`requires_regal`, `requires_ares`, `requires_promptfoo`, `agent_server`.

A missing dependency skips with a clear reason. Note `agent_server` **fails**
rather than skips if the agent is present but will not start — a broken example
agent is a real problem, not a reason to pass.

### 4.6 Run the CLI through `smith_cli`

```python
result = smith_cli("policy_testing", timeout=600)                  # a flag
result = smith_cli("test_case_translation", AGENT_URL=url)         # + env overrides
result = smith_cli.argv("--help")                                  # raw argv
```

It runs `sys.executable -m smith.cli` — the checkout under test. Never shell out
to a bare `smith`, which resolves through `PATH` (a pyenv shim, or an unrelated
global install) and fails outright where `PATH` has no venv, such as CI.

Keyword arguments are environment **overrides** layered on the real `.env`;
`VAR=None` unsets a variable.

---

## 5. Checklist before you commit

**Unit file**
- [ ] Covers every top-level function in the flag's dispatch block
- [ ] `FUNCTIONS UNDER TEST` inventory present, in execution order
- [ ] Section banners follow the same order
- [ ] Passes with **no `.env` and no network**:
      `cd /tmp && env -i PATH=/usr/bin:/bin HOME=/tmp <venv>/bin/python -m pytest <file> -m unit --disable-socket --allow-unix-socket`
- [ ] No boundary faked on a path that never reaches it
- [ ] Every write lands under `tmp_path`; `fixtures/` unmodified (`git status` clean)

**Integration file**
- [ ] The flag is executed **once**, in a module-scoped fixture
- [ ] At least one test asserts a result is **correct**, not merely well-shaped
- [ ] Every exact assertion is on an output that genuinely cannot differ — a
      deterministic stage, an unambiguous input, or an aggregate. No exact
      assertion on a value that could legitimately be `uncertain` / a fallback
- [ ] Shape assertions present too (they catch what breaks the *next* step)
- [ ] At least one test proves consecutive steps connect
- [ ] Every real file written is backed up and restored
- [ ] Gated on exactly the dependencies it uses
- [ ] `git status` clean after the run

**Both**
- [ ] Exactly one primary marker per test
- [ ] `uvx ruff@0.15.20 check tests && uvx black@26.5.1 tests`
- [ ] Assertion messages explain *why*, not just *what*

---

## 6. Commands

```bash
make unit                       # the CI subset: unit only, offline
make integration                # opt-in: real services
.venv/bin/python -m pytest tests/integration/test_<flag>_unit.py -m unit
.venv/bin/python -m pytest tests/integration --collect-only -m unit
```

A bare `pytest` selects `-m unit` by default (`pyproject.toml`), so the
expensive lane is never run by accident.
