# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``smith --flag bypass_case_generation``.

The flag finds places the **policy diverges from the guidance**, then turns each
divergence into a concrete adversarial test case::

    detect_bypass_vectors    LLM #1: guidance vs policy -> bypass_report.{json,md}
    synthesize_bypass_cases  LLM #2: each vector -> bypass_cases.json
    convert_bypass_case      route by label -> bypass_test_case*.json under
                             test_cases/{allow,disallow}/

It is driven through the **real CLI** with a real LLM and a real MCP server. This
file imports nothing from ``smith``, so every assertion reads the artifacts one
run left behind.

STEPS COVERED (all from the single run)
--------------------------------------
STEP 0  MCP tool extraction — the flag pulls tool definitions before analyzing
STEP 1  ``bypass_report.{json,md}`` — divergences found in the staged policy
STEP 2  ``bypass_cases.json``       — abstract cases, each labelled by direction
STEP 3  ``bypass_test_case*.json``  — routed into allow/ and disallow/

COST: THE FLAG IS RUN ONCE
--------------------------
It spawns an MCP server, then makes **two** LLM calls with a 30k token budget each
(the second scaling with the number of divergences found). So the flag runs
**exactly once** in a module-scoped fixture and every assertion inspects that
run's artifacts.

WHAT IS ASSERTED, AND WHY THAT MUCH
-----------------------------------
Which divergences a model finds is a judgement call, so per the guide this file
does **not** demand a specific vector, category or count. What it does assert:

* **At least one divergence is found.** The staged policy has a *known,
  deterministic* gap — guidance rule 4 forbids arguments outside
  ``{keywords, topic, limit}``, and the policy declares ``allowed_arg_keys`` but
  never references it in any deny rule. A run finding nothing means the analysis
  degraded, which is exactly the silent failure this flag must not have.
* **Every vector's category and direction are in the schema's enums** — the code
  filters on these, so a value outside them proves the filter broke.
* **The label a case carries matches the bucket it landed in.** That mapping is
  pure code, not a model decision, so it is asserted exactly. It is also the
  security-relevant part: a malicious probe in ``allow/`` would teach the suite
  that an exploit is expected behaviour.
* **The ``bypass_test_case`` prefix**, which cross-validate's adversarial collapse
  keys on to refuse relabelling a malicious probe as benign.
* **The steps connect** — a vector reaches a case, and a case reaches a file.

Every file the flag writes is backed up and restored: the staged policy, the case
tree, ``references/bypass/`` and ``references/bypass_cases.json``.

Requires an LLM (``OPENAI_*``/``MODEL_SONNET``) and the MCP server's ``python``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from helpers import FIXTURE_POLICY, load_json

pytestmark = pytest.mark.integration


VALID_CATEGORIES = {
    "omitted_field",
    "type_confusion",
    "malformed_value",
    "keyword_evasion",
}
VALID_DIRECTIONS = {"guidance_deny_policy_allow", "guidance_allow_policy_deny"}

#: label -> the bucket that label must be written into. Pure code, so exact.
LABEL_BUCKET = {"bypass_malicious": "disallow", "bypass_benign": "allow"}


@pytest.fixture(scope="module")
def completed_run():
    """Run ``bypass_case_generation`` ONCE; yield the artifacts it produced.

    Module-scoped because the flag spawns an MCP server and makes two LLM calls.
    Function-scoped helpers like ``backup_file`` are unavailable here, so the
    backup/restore is done by hand in a ``try/finally``.
    """
    import shutil
    import subprocess
    import sys
    import tempfile

    from helpers import SmithEnv, which

    env = SmithEnv()
    missing = env.missing("OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL_SONNET")
    if missing:
        pytest.skip(f"Smith LLM not configured (missing {', '.join(missing)})")
    if not which("python"):
        pytest.skip("python not on PATH (the MCP server is spawned over stdio)")

    policy = env.policy
    cases = env.test_cases
    report_dir = env.bypass_report_dir
    cases_file = env.bypass_cases_file

    backup_dir = Path(tempfile.mkdtemp(prefix="smith_bypass_backup_"))
    saved = {}
    for i, path in enumerate((policy, cases, report_dir, cases_file)):
        if path.exists():
            dst = backup_dir / f"{i}_{path.name}"
            if path.is_dir():
                shutil.copytree(path, dst)
            else:
                shutil.copy2(path, dst)
            saved[path] = dst

    try:
        # Stage the frozen fixture policy: it is non-empty (so the guard passes)
        # and carries the known rule-4 gap the assertions below rely on.
        policy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(FIXTURE_POLICY, policy)

        # Start from a clean slate so nothing pre-existing can be mistaken for
        # this run's output.
        for path in (cases, report_dir):
            if path.exists():
                shutil.rmtree(path)
        if cases_file.exists():
            cases_file.unlink()

        result = subprocess.run(
            [sys.executable, "-m", "smith.cli", "--flag", "bypass_case_generation"],
            cwd=str(env.base),
            env=env.override(),
            capture_output=True,
            text=True,
            timeout=1800,
        )
        yield {
            "result": result,
            "report_dir": report_dir,
            "cases_file": cases_file,
            "cases": cases,
        }
    finally:
        for path in (policy, cases, report_dir, cases_file):
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
        f"bypass_case_generation failed (rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout[-2500:]}\n"
        f"--- stderr ---\n{result.stderr[-1200:]}"
    )
    return completed_run


@pytest.fixture(scope="module")
def report(run_ok):
    """The parsed divergence report — the artifact STEP 1 produces."""
    path = run_ok["report_dir"] / "bypass_report.json"
    assert path.exists(), f"no bypass_report.json at {path}"
    return load_json(path)


@pytest.fixture(scope="module")
def synthesized(run_ok):
    """The abstract cases STEP 2 wrote."""
    path = run_ok["cases_file"]
    assert path.exists(), f"no bypass_cases.json at {path}"
    return load_json(path)


# ===========================================================================
# STEP 0 — tool definitions are pulled before any analysis
# ===========================================================================


def test_the_flag_extracts_tool_definitions_first(run_ok):
    # The tool shapes tell the model what input.args.* a request may carry;
    # without them the analysis cannot propose a concrete exploit payload.
    #
    # The CLI reports a COUNT rather than the tool names, so that is what is
    # asserted — and it is the stronger check: "Extracted 0 tools" would mean the
    # server answered but exposed nothing, which a name-based assertion on the
    # whole stdout could not distinguish from a name mentioned elsewhere.
    stdout = run_ok["result"].stdout
    match = re.search(r"Extracted (\d+) tools? from MCP server", stdout)
    assert match, f"no tool extraction reported:\n{stdout[-1500:]}"
    assert int(match.group(1)) > 0, "the MCP server exposed no tools to analyze"


# ===========================================================================
# STEP 1 — the divergence report
# ===========================================================================


def test_at_least_one_divergence_is_found(report, run_ok):
    """CORRECTNESS: the staged policy has a known, deterministic gap.

    Guidance rule 4 forbids arguments outside ``{keywords, topic, limit}``. The
    fixture policy declares ``allowed_arg_keys`` but never references it in a deny
    rule, so an extra argument key is accepted — a real divergence, independently
    confirmed with ``opa eval`` in the cross-validate work.

    A run finding *nothing* therefore means the analysis silently degraded, which
    on a security check reads as a false all-clear. Which vectors are found is left
    to the model; that there is at least one is not.
    """
    assert report["vectors"], (
        "no divergences found, but the staged policy has an unenforced "
        f"allowed_arg_keys declaration.\n{run_ok['result'].stdout[-2000:]}"
    )


def test_every_vector_uses_the_schema_enums(report):
    # The code filters on both fields, so a value outside these sets proves the
    # filter stopped working rather than the model misbehaving.
    for vector in report["vectors"]:
        assert vector["category"] in VALID_CATEGORIES, f"bad category: {vector}"
        assert vector["direction"] in VALID_DIRECTIONS, f"bad direction: {vector}"


def test_the_human_readable_report_is_written_too(run_ok, report):
    # The Markdown is what a reviewer reads before accepting the generated cases,
    # so it must exist and reflect the same run rather than a stale one.
    md = (run_ok["report_dir"] / "bypass_report.md").read_text()
    assert "# Policy Bypass Analysis Report" in md
    assert "No bypass vectors detected" not in md, (
        "the markdown says no vectors, but the JSON reported "
        f"{len(report['vectors'])}"
    )


# ===========================================================================
# STEP 2 — synthesized cases
# ===========================================================================


def test_vectors_reach_the_synthesis_step(report, synthesized):
    # STEPS 1 -> 2: a report full of divergences that yields no cases means the
    # expensive second call produced nothing usable.
    assert synthesized, (
        f"{len(report['vectors'])} divergence(s) were found but no cases were "
        "synthesized from them"
    )


def test_every_synthesized_case_is_labelled_and_complete(synthesized):
    # The label is derived in code from the vector's direction, and the four
    # required fields are indexed directly by the conversion step.
    for case in synthesized:
        assert case["label"] in LABEL_BUCKET, f"unexpected label: {case.get('label')}"
        for field in ("action", "condition", "user_input", "system_variables"):
            assert field in case, f"case missing {field}: {case}"
        assert isinstance(case["system_variables"], dict)


# ===========================================================================
# STEP 3 — conversion into the case tree
# ===========================================================================


def test_cases_reach_the_case_tree(run_ok, synthesized):
    # STEPS 2 -> 3: the flag's whole purpose is new case FILES; a populated
    # bypass_cases.json that produced none would be a silent dead end.
    produced = list(run_ok["cases"].rglob("bypass_test_case*.json"))
    assert produced, (
        f"{len(synthesized)} case(s) were synthesized but no "
        "bypass_test_case*.json files were written"
    )


def test_every_written_case_lands_in_the_bucket_its_label_demands(run_ok, synthesized):
    """CORRECTNESS: label -> bucket is pure code, so it is asserted exactly.

    ``bypass_malicious`` is a request the guidance forbids, so it must sit in
    ``disallow/`` where the policy is expected to deny it. ``bypass_benign`` is a
    legitimate request the policy over-blocks, so it belongs in ``allow/``.
    Getting this backwards would encode an exploit as expected behaviour.
    """
    expected = {LABEL_BUCKET[c["label"]] for c in synthesized}
    for bucket in expected:
        assert list(
            (run_ok["cases"] / bucket).glob("bypass_test_case*.json")
        ), f"cases were labelled for {bucket}/ but none were written there"

    # And nothing appeared in a bucket no case was labelled for.
    for bucket in set(LABEL_BUCKET.values()) - expected:
        directory = run_ok["cases"] / bucket
        if directory.exists():
            assert not list(directory.glob("bypass_test_case*.json")), (
                f"a bypass case landed in {bucket}/ though no synthesized case "
                "carried that label"
            )


def test_written_cases_keep_the_bypass_prefix(run_ok):
    # The prefix is load-bearing: cross-validate's adversarial collapse matches on
    # `bypass_test_case*` to refuse relabelling a malicious probe as benign. A case
    # written under the plain `test_case` prefix would silently lose that shield.
    for path in run_ok["cases"].rglob("bypass_test_case*.json"):
        assert path.name.startswith("bypass_test_case")


def test_written_cases_are_valid_opa_envelopes(run_ok):
    # STEP 3 -> policy_testing: OPA evaluates these bytes directly, so a missing
    # field would fail the whole scorecard rather than one case.
    for path in run_ok["cases"].rglob("bypass_test_case*.json"):
        case = json.loads(path.read_text())
        assert "input" in case, f"{path.name} has no input envelope"
        inner = case["input"]
        assert inner.get("kind") == "tool_call"
        assert inner.get("name"), f"{path.name} names no tool"
        assert inner["extensions"]["agent"]["input"], f"{path.name} carries no prompt"


def test_the_flag_reports_what_it_produced(run_ok, report):
    # The summary line is how a user decides whether to review the new cases, so
    # its count must match the report rather than being a fixed string.
    stdout = run_ok["result"].stdout
    assert "Bypass case generation complete" in stdout
    assert f"{len(report['vectors'])} divergence(s) found" in stdout
