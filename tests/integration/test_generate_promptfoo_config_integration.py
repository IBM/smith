# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``smith --flag generate_promptfoo_config``.

The flag turns Smith's guidance + system variables into a promptfoo redteam
config, via MCP tool extraction and one LLM call::

    get_tool_definitions()        spawn the MCP server, list its tools
    generate_promptfoo_config()   template + LLM -> purpose, vars, contexts,
                                  policy text, tool-parameter instructions

Driven through the **real CLI** with a real model. This file imports nothing from
``smith``, so every assertion reads the config the run produced.

STEPS COVERED (all from the single run)
--------------------------------------
STEP 0  MCP tool extraction — the tool-parameter block proves it reached the config
STEP 1  the template skeleton survives (targets / prompts)
STEP 2  the model's purpose and contexts are filled in
STEP 3  the policy text comes from the real guidance file
STEP 4  the output is valid YAML promptfoo can load

COST: THE FLAG IS RUN ONCE
--------------------------
It spawns an MCP server and makes one LLM call over the full guidance. So the flag
runs **exactly once** in a module-scoped fixture and every test inspects that run's
config.

The **update** path — a second run against an existing config, which regenerates
contexts while preserving ``purpose`` — would cost a second call to observe, so it
is covered in the unit lane where it is free. Same for the tool-block idempotency
across runs.

WHAT IS ASSERTED, AND WHY THAT MUCH
-----------------------------------
The model writes ``purpose`` and invents ``contexts``, so per the guide neither is
asserted verbatim. What is asserted:

* **The guidance reaches the policy plugin verbatim.** That is a file copy, not a
  model decision, so an exact substring check is safe — and it is the field
  promptfoo red-teams against, so a stale or empty one would silently test nothing.
* **Every context is structurally usable** and carries no Smith-internal vars.
  Those keys would otherwise flow into every generated test case.
* **The tool-parameter block names a real extracted tool** with its required
  arguments — the seam proving STEP 0's output reached the config.
* **Negative assertions** on the fields a degraded run leaves empty, which is what
  silent failure looks like here.

The output path is redirected to a throwaway file, so the example's committed
``promptfooconfig.yaml`` is never touched.

Requires an LLM (``OPENAI_*``/``MODEL_SONNET``) and the MCP server's ``python``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.integration


#: Keys every context must carry for promptfoo to render it.
REQUIRED_CONTEXT_FIELDS = {"id", "purpose", "vars"}

#: Smith-internal plumbing that must never reach a red-teaming config.
INTERNAL_VARS = {"action_list", "action_description"}


@pytest.fixture(scope="module")
def completed_run(tmp_path_factory):
    """Run the flag ONCE; yield the config it produced."""
    import subprocess
    import sys

    from helpers import SmithEnv, which

    env = SmithEnv()
    missing = env.missing("OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL_SONNET")
    if missing:
        pytest.skip(f"Smith LLM not configured (missing {', '.join(missing)})")
    if not which("python"):
        pytest.skip("python not on PATH (the MCP server is spawned over stdio)")

    # A throwaway output path. This override is what protects the example's
    # COMMITTED promptfooconfig.yaml, which is what PROMPTFOO_CONFIG_FILE points
    # at by default — the flag would otherwise regenerate a tracked file in place.
    out_rel = "references/__test_promptfooconfig__.yaml"
    out_path = Path(env.base) / out_rel
    if out_path.exists():
        out_path.unlink()

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "smith.cli",
                "--flag",
                "generate_promptfoo_config",
            ],
            cwd=str(env.base),
            env=env.override(PROMPTFOO_CONFIG_FILE=out_rel),
            capture_output=True,
            text=True,
            timeout=1800,
        )
        yield {"result": result, "path": out_path, "guidance": env.guidance_file}
    finally:
        if out_path.exists():
            out_path.unlink()


@pytest.fixture(scope="module")
def run_ok(completed_run):
    """The run must have succeeded before any artifact assertion is meaningful."""
    result = completed_run["result"]
    assert result.returncode == 0, (
        f"generate_promptfoo_config failed (rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout[-2500:]}\n"
        f"--- stderr ---\n{result.stderr[-1200:]}"
    )
    return completed_run


@pytest.fixture(scope="module")
def config(run_ok):
    """The generated config, parsed — the artifact every assertion reads."""
    path = run_ok["path"]
    assert (
        path.exists()
    ), f"no config written to {path}\n{run_ok['result'].stdout[-2000:]}"
    loaded = yaml.safe_load(path.read_text())
    assert isinstance(loaded, dict), "the config is not a YAML mapping"
    return loaded


@pytest.fixture(scope="module")
def redteam(config):
    assert "redteam" in config, f"config missing the redteam block: {list(config)}"
    return config["redteam"]


# ===========================================================================
# STEP 1 — the template skeleton survives
# ===========================================================================


def test_the_template_skeleton_is_preserved(config):
    # These come from the template, not the model. promptfoo needs both to run at
    # all, so regenerating the redteam block must not drop them.
    assert config.get("targets"), "config missing 'targets'"
    assert config.get("prompts"), "config missing 'prompts'"


# ===========================================================================
# STEP 2 — the model's contribution
# ===========================================================================


def test_the_purpose_is_populated(redteam):
    assert redteam.get("purpose", "").strip(), "redteam.purpose is empty"


def test_every_context_is_structurally_usable(redteam):
    contexts = redteam.get("contexts")
    assert contexts, "redteam.contexts is empty — no personas to red-team as"
    for entry in contexts:
        missing = REQUIRED_CONTEXT_FIELDS - entry.keys()
        assert not missing, f"context missing {missing}: {entry}"
        assert entry["purpose"].strip(), f"context {entry['id']} has no purpose"
        assert isinstance(entry["vars"], dict)


def test_no_internal_vars_leak_into_the_contexts(redteam):
    """CORRECTNESS: the leak is code-controlled, so this is asserted exactly."""
    for entry in redteam["contexts"]:
        leaked = INTERNAL_VARS & entry["vars"].keys()
        assert not leaked, f"context {entry['id']} leaked internal vars: {leaked}"


def test_the_vars_block_offers_values_to_vary(redteam):
    # Built in code from system_vars.json, not by the model. It is what makes
    # promptfoo vary personas, and internal keys must not appear here either.
    rendered = str(redteam.get("vars", ""))
    assert rendered.strip(), "redteam.vars is empty"
    for internal in INTERNAL_VARS:
        assert internal not in rendered, f"{internal} leaked into redteam.vars"


# ===========================================================================
# STEP 3 — the policy text comes from the real guidance
# ===========================================================================


def test_the_policy_plugin_carries_the_real_guidance(redteam, run_ok):
    """CORRECTNESS: a file copy, so exactly assertable."""
    plugins = redteam.get("plugins") or []
    policy = next(
        (p for p in plugins if isinstance(p, dict) and p.get("id") == "policy"), None
    )
    assert policy is not None, (
        f"no 'policy' plugin — that is what drives policy red-teaming: "
        f"{[p.get('id') if isinstance(p, dict) else p for p in plugins]}"
    )

    text = policy["config"]["policy"]["text"]
    first_rule = run_ok["guidance"].read_text().strip().splitlines()[0]
    assert (
        first_rule in text
    ), "the policy text does not match the guidance file it was generated from"


# ===========================================================================
# STEP 0 -> STEP 4 — extracted tools reach the generation instructions
# ===========================================================================


def test_the_extracted_tools_reach_the_generation_instructions(run_ok, redteam):
    tgi = str(redteam.get("testGenerationInstructions", ""))
    assert "[smith:tool-parameters]" in tgi, (
        "no tool-parameter block was appended, so MCP extraction did not reach "
        f"the config:\n{run_ok['result'].stdout[-1500:]}"
    )
    # The example agent exposes get_events; naming it ties this to a real tool
    # rather than to the marker alone.
    assert "get_events" in tgi, f"the extracted tool is not named in:\n{tgi[-800:]}"
    assert tgi.count("[smith:tool-parameters]") == 1, "the tool block was duplicated"


# ===========================================================================
# STEP 4 — the flag reports what it did
# ===========================================================================


def test_the_flag_reports_writing_and_validating_the_config(run_ok):
    stdout = run_ok["result"].stdout
    assert "Config written to:" in stdout
    # The flag validates its own output. Note it does NOT fail on a bad verdict —
    # see the pinned bug in the unit lane — so the message is the only signal.
    assert (
        "Validation passed" in stdout
    ), f"the generated config did not pass Smith's own validation:\n{stdout[-1500:]}"
