# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``smith --flag test_generation``.

Smith's largest pipeline: guidance text in, ready-to-evaluate OPA test cases out.
Driven through the **real CLI** with a real model and a real MCP server. This file
imports nothing from ``smith``, so every assertion reads an artifact the run left
behind.

STEPS COVERED (all from the single run)
--------------------------------------
STEP 0  MCP tool extraction     — the tools generation targets
STEP 1  ``decomp_file.json``    — guidance lines -> per-rule records
STEP 2  ``grey_guidance.json``  — edge conditions per tool
STEP 3  ``vars_file.json``      — system/prompt variables per rule
STEP 4  ``test_cases.json``     — abstract cases with labels
STEP 5  promptfoo attack file   — the optional red-team source
STEP 6  ``test_cases/{allow,disallow}/`` — translated OPA envelopes

COST: THE FLAG IS RUN ONCE
--------------------------
This is the most expensive flag in the suite: it spawns an MCP server, runs the
promptfoo redteam CLI, and makes **at least four** LLM calls whose count scales
with the number of guidance rules. So it runs **exactly once** in a module-scoped
fixture and every assertion inspects that run's artifacts.

Two things keep the bill down. A **crafted two-rule guidance** is staged rather
than the example's full file, so the per-rule calls stay at two. And
``ATTACK_TOOLS=promptfoo`` omits ARES, which would otherwise need a separate
install plus its plugins — that path is exercised nowhere in this lane and is
noted below.

ASSERTING CORRECTNESS, NOT JUST SHAPE
-------------------------------------
The model writes the rules, the conditions and the prompts, so none of that is
asserted verbatim. What is asserted:

* **Every stage's artifact is chained to the previous one.** Rule counts must
  agree across decomposition and variable extraction, and every generated case
  must name a tool the MCP server actually exposes. That is what makes this a
  pipeline test rather than six independent file-exists checks.
* **Labels route to buckets exactly.** ``allow`` -> ``allow/``, ``disallow`` ->
  ``disallow/`` is pure code, and it defines what the scorecard counts as a pass.
* **Both directions are generated.** A run producing only ``allow`` cases would
  score 100% against any policy at all, so the absence of one bucket is a silent
  failure this checks for.
* **Every written case is a valid OPA envelope**, since policy_testing feeds these
  bytes straight to OPA.

The crafted guidance and every generated artifact are backed up and restored, and
the example's own files are never written.

Requires an LLM, the promptfoo CLI, and the MCP server's ``python``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from helpers import load_json

pytestmark = pytest.mark.integration


#: Two rules, one clearly permissive and one clearly restrictive, so the pipeline
#: has a reason to emit both an allow and a disallow case. Deliberately small: the
#: per-rule LLM calls scale with this file.
CRAFTED_GUIDANCE = (
    "1. Faculty may use the get_events tool to search for academic conferences.\n"
    "2. A guest must never be allowed to call the get_events tool.\n"
)

#: Labels the pipeline may emit, mapped to the bucket each must land in.
LABEL_BUCKET = {"allow": "allow", "disallow": "disallow"}


@pytest.fixture(scope="module")
def completed_run():
    """Run ``test_generation`` ONCE; yield every artifact it produced."""
    import shutil
    import subprocess
    import sys
    import tempfile

    from helpers import SmithEnv, which

    env = SmithEnv()
    missing = env.missing("OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL_SONNET")
    if missing:
        pytest.skip(f"Smith LLM not configured (missing {', '.join(missing)})")
    if not which("promptfoo"):
        pytest.skip("promptfoo CLI not found (ATTACK_TOOLS=promptfoo)")
    if not which("python"):
        pytest.skip("python not on PATH (the MCP server is spawned over stdio)")

    artifacts = env.generation_artifacts
    cases = env.test_cases
    # A throwaway guidance file, so the example's own guidance.txt is never touched.
    crafted_guidance = Path(env.base) / "references" / "__test_guidance__.txt"

    protected = [*artifacts.values(), cases, crafted_guidance]
    backup_dir = Path(tempfile.mkdtemp(prefix="smith_gen_backup_"))
    saved = {}
    for i, path in enumerate(protected):
        if path.exists():
            dst = backup_dir / f"{i}_{path.name}"
            if path.is_dir():
                shutil.copytree(path, dst)
            else:
                shutil.copy2(path, dst)
            saved[path] = dst

    try:
        crafted_guidance.parent.mkdir(parents=True, exist_ok=True)
        crafted_guidance.write_text(CRAFTED_GUIDANCE)
        # Start clean so nothing pre-existing is mistaken for this run's output.
        for path in (*artifacts.values(), cases):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()

        result = subprocess.run(
            [sys.executable, "-m", "smith.cli", "--flag", "test_generation"],
            cwd=str(env.base),
            env=env.override(
                GUIDANCE_FILE=f"references/{crafted_guidance.name}",
                # ARES omitted: it needs a separate install plus its plugins.
                ATTACK_TOOLS="promptfoo",
            ),
            capture_output=True,
            text=True,
            timeout=3600,
        )
        yield {"result": result, "artifacts": artifacts, "cases": cases}
    finally:
        for path in protected:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()
            if path in saved:
                src = saved[path]
                if src.is_dir():
                    shutil.copytree(src, path)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, path)
        shutil.rmtree(backup_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def run_ok(completed_run):
    """The run must have succeeded before any artifact assertion is meaningful."""
    result = completed_run["result"]
    assert result.returncode == 0, (
        f"test_generation failed (rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout[-3000:]}\n"
        f"--- stderr ---\n{result.stderr[-1500:]}"
    )
    return completed_run


@pytest.fixture(scope="module")
def decomposed(run_ok):
    """STEP 1's artifact — the rule records every later stage builds on."""
    path = run_ok["artifacts"]["decomp"]
    assert path.exists(), f"no decomposition written to {path}"
    return load_json(path)


@pytest.fixture(scope="module")
def variables(run_ok):
    """STEP 3's artifact."""
    path = run_ok["artifacts"]["vars"]
    assert path.exists(), f"no variables file written to {path}"
    return load_json(path)


@pytest.fixture(scope="module")
def generated_cases(run_ok):
    """STEP 4's artifact — the abstract cases, before translation."""
    path = run_ok["artifacts"]["cases"]
    assert path.exists(), f"no cases file written to {path}"
    return load_json(path)


@pytest.fixture(scope="module")
def written_cases(run_ok):
    """STEP 6's artifacts — the OPA envelopes on disk, by bucket."""
    root = run_ok["cases"]
    assert root.exists(), f"no case tree written to {root}"
    return {
        bucket: sorted((root / bucket).glob("*.json"))
        for bucket in ("allow", "disallow")
        if (root / bucket).exists()
    }


# ===========================================================================
# STEP 1 — guidance becomes structured rules
# ===========================================================================


def test_both_crafted_rules_are_decomposed(decomposed):
    # Two guidance lines in, two rule records out. Losing a rule means silently
    # generating no cases for it, which no later stage can detect.
    assert len(decomposed) == 2, f"expected 2 rules, got {len(decomposed)}"


def test_every_rule_names_a_tool_and_carries_both_directions(decomposed):
    # allow_conditions and disallow_conditions are what case_generation turns into
    # the two case kinds, so a rule missing either can only produce half a test.
    for rule in decomposed:
        assert rule["action"], f"rule has no action: {rule}"
        assert "allow_conditions" in rule, f"rule missing allow_conditions: {rule}"
        assert (
            "disallow_conditions" in rule
        ), f"rule missing disallow_conditions: {rule}"
        assert rule["guidance"].strip(), "the source guidance text was lost"


# ===========================================================================
# STEP 2 — grey conditions
# ===========================================================================


def test_the_grey_condition_stage_produced_its_artifact(run_ok):
    path = run_ok["artifacts"]["grey"]
    assert path.exists(), f"no grey guidance written to {path}"
    assert load_json(path), "the grey guidance file is empty"


# ===========================================================================
# STEP 3 — variables attached to every rule
# ===========================================================================


def test_variables_are_attached_to_every_decomposed_rule(decomposed, variables):
    """``variable_extraction`` """
    assert len(variables) == len(decomposed)
    for rule in variables:
        assert "system_variables" in rule, f"rule missing system_variables: {rule}"
        assert "prompt_variables" in rule, f"rule missing prompt_variables: {rule}"


# ===========================================================================
# STEP 4 — abstract cases, and STEP 0 -> 4 tool agreement
# ===========================================================================


def test_cases_were_generated(generated_cases):
    assert generated_cases, "the pipeline generated no abstract cases at all"


def test_every_generated_case_is_complete(generated_cases):
    # translate_case indexes each of these directly, so a partial case would crash
    # STEP 6 rather than degrade it.
    for case in generated_cases:
        for field in ("action", "user_input", "label", "system_variables"):
            assert field in case, f"case missing {field}: {case}"
        assert case["user_input"].strip(), "a case with no prompt cannot be evaluated"


def test_generated_cases_target_a_tool_the_mcp_server_exposes(run_ok, generated_cases):
    actions = {case["action"] for case in generated_cases}
    assert (
        "get_events" in actions
    ), f"no case targets the extracted tool; got actions {actions}"


def test_both_label_directions_are_generated(generated_cases):
    labels = {case["label"] for case in generated_cases}
    assert "allow" in labels, f"no allow cases generated; labels were {labels}"
    assert "disallow" in labels, f"no disallow cases generated; labels were {labels}"


# ===========================================================================
# STEP 5 — the promptfoo red-team source
# ===========================================================================


def test_the_promptfoo_attack_file_was_produced(run_ok):
    # ATTACK_TOOLS=promptfoo, so this path must have run. Its absence would mean
    # the adversarial half of the suite is silently missing.
    path = run_ok["artifacts"]["promptfoo_attack"]
    assert (
        path.exists()
    ), f"no promptfoo attack file at {path}\n{run_ok['result'].stdout[-2000:]}"


def test_the_flag_reports_which_attack_tools_ran(run_ok):
    # The gate is env-driven, so the log line is how a user confirms what they got.
    stdout = run_ok["result"].stdout
    assert "ATTACK_TOOLS: promptfoo enabled" in stdout
    assert "ATTACK_TOOLS: ares skipped" in stdout


# ===========================================================================
# STEP 6 — translation into the case tree
# ===========================================================================


def test_cases_reach_the_case_tree(generated_cases, written_cases):
    # STEPS 4 -> 6: abstract cases that never become files are a dead end — the
    # scorecard only ever reads the tree.
    total = sum(len(paths) for paths in written_cases.values())
    assert total, (
        f"{len(generated_cases)} abstract case(s) were generated but none were "
        "written to the case tree"
    )


def test_every_label_landed_in_the_bucket_it_names(generated_cases, written_cases):
    expected = {
        LABEL_BUCKET[c["label"]] for c in generated_cases if c["label"] in LABEL_BUCKET
    }
    for bucket in expected:
        assert written_cases.get(
            bucket
        ), f"cases were labelled for {bucket}/ but none were written there"


def test_every_written_case_is_a_valid_opa_envelope(written_cases):
    # STEP 6 -> policy_testing: OPA evaluates these bytes, so one malformed file
    # breaks the whole scorecard rather than a single case.
    for bucket, paths in written_cases.items():
        for path in paths:
            case = json.loads(path.read_text())
            assert "input" in case, f"{bucket}/{path.name} has no input envelope"
            inner = case["input"]
            assert inner.get("kind") == "tool_call", f"{path.name}: wrong kind"
            assert inner.get("name"), f"{path.name} names no tool"
            assert inner["extensions"]["agent"][
                "input"
            ], f"{path.name} carries no prompt"
            assert inner["extensions"]["subject"], f"{path.name} carries no subject"


def test_the_promptfoo_attacks_reach_the_disallow_bucket(written_cases):
    # STEPS 5 -> 6: promptfoo attacks are merged into the same translation, and
    # land under their own prefix — which cross_validate's adversarial collapse
    # matches on to refuse relabelling an attack as benign.
    disallow = written_cases.get("disallow", [])
    promptfoo_cases = [p for p in disallow if p.name.startswith("promptfoo_test_case")]
    assert promptfoo_cases, (
        "no promptfoo_test_case*.json in disallow/ — the red-team cases did not "
        f"survive translation; found {[p.name for p in disallow]}"
    )
