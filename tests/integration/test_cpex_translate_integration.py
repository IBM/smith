# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``smith --flag cpex_translate``.

STEPS COVERED (all from the single run)
--------------------------------------
STEP 1  the shape rewrite — package rename, ``extensions`` collapse, and removal
        of the constructs CPEX has no equivalent for
STEP 2  ``opa fmt -w``    — the delivered file is canonically formatted
STEP 3  ``validate_policy`` — the rewritten policy is still valid rego, which is
        the property only a real OPA can confirm
CLI     the destination contract and the exit code

COST: THE FLAG IS RUN ONCE
--------------------------
Every assertion inspects one run's artifacts, from a module-scoped fixture. 

ASSERTING CORRECTNESS
---------------------
This flag is fully deterministic — a text transform plus OPA — so per the guide
its output is asserted exactly: the rewritten text, the per-transform counts the
CLI reports, and OPA's own verdict on the result.

Requires the ``opa`` binary.
"""

from __future__ import annotations

import subprocess

import pytest

from data_builders import write_text
from helpers import FIXTURE_POLICY

pytestmark = pytest.mark.integration


# A policy carrying every construct the translation must rewrite or drop, so the
# assertions below are meaningful rather than trivially satisfied. The
# `input.name` guard is the only condition of no rule here, so the empty-body
# repair is exercised too.
FULL_POLICY = (
    "package mcp.policies\n\n"
    "import rego.v1\n\n"
    "default allow := false\n\n"
    "# === Envelope Validation ===\n"
    "valid_envelope if {\n"
    '\tinput.kind == "tool_call"\n'
    "}\n\n"
    "# === Tool Argument Keys ===\n"
    'allowed_arg_keys := {"get_events": {"keywords", "topic", "limit"}}\n\n'
    "subject := input.extensions.subject\n\n"
    "allow if {\n"
    "\tvalid_envelope\n"
    '\tinput.name == "get_events"\n'
    '\tsubject.user_role[_] == "faculty"\n'
    '\tinput.args.topic == "Artificial intelligence"\n'
    "}\n\n"
    "tool_only if {\n"
    '\tinput.name == "get_events"\n'
    "}\n"
)


@pytest.fixture(scope="module")
def completed_run(tmp_path_factory):
    """Run the flag ONCE for this module; yield the artifacts it produced.

    Everything happens in a temp directory, so no checkout file is touched and no
    backup is needed.
    """
    import sys

    from helpers import SmithEnv, which

    if not which("opa"):
        pytest.skip("opa binary not found on PATH")

    env = SmithEnv()
    work = tmp_path_factory.mktemp("cpex")
    src = write_text(work / "policy.rego", FULL_POLICY)
    dest = work / "policy_cpex.rego"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "smith.cli",
            "--flag",
            "cpex_translate",
            "--policy_path",
            str(src),
            "--dest",
            str(dest),
        ],
        cwd=str(env.base),
        env=env.override(),
        capture_output=True,
        text=True,
        timeout=300,
    )
    return {"result": result, "src": src, "dest": dest}


@pytest.fixture(scope="module")
def run_ok(completed_run):
    """The run must have succeeded before any artifact assertion is meaningful."""
    result = completed_run["result"]
    assert result.returncode == 0, (
        f"cpex_translate failed (rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout[-2000:]}\n"
        f"--- stderr ---\n{result.stderr[-1000:]}"
    )
    return completed_run


@pytest.fixture(scope="module")
def translated_text(run_ok):
    return run_ok["dest"].read_text()


# ===========================================================================
# STEP 1 — the shape rewrite
# ===========================================================================


def test_the_package_is_renamed_and_extensions_collapsed(translated_text):
    assert "package authz" in translated_text
    assert "package mcp.policies" not in translated_text
    # subject survives; the extensions layer around it does not.
    assert "input.subject" in translated_text
    assert "input.extensions" not in translated_text


def test_constructs_cpex_cannot_express_are_removed(translated_text):
    # Each of these would be a dangling reference in the CPEX shape.
    assert "valid_envelope" not in translated_text
    assert "allowed_arg_keys" not in translated_text
    assert "Envelope Validation" not in translated_text


def test_the_authorization_logic_survives(translated_text):
    # Arguments already live under input.args, so they must pass through
    # untouched — otherwise the translation would silently drop the access-control
    # check it exists to preserve.
    assert 'input.args.topic == "Artificial intelligence"' in translated_text
    assert 'subject.user_role[_] == "faculty"' in translated_text


def test_the_source_policy_is_left_untouched(run_ok):
    assert run_ok["src"].read_text() == FULL_POLICY


def test_the_cli_reports_every_transform_count(run_ok):
    # The per-label counts are how a user confirms the translation did what they
    # expected, so they must reach stdout.
    stdout = run_ok["result"].stdout
    assert "package mcp.policies -> package authz" in stdout
    assert "valid_envelope rule removed" in stdout
    assert "allowed_arg_keys block removed" in stdout


# ===========================================================================
# STEPS 2 + 3 — canonically formatted, and still valid rego
#
# Asserted against the ARTIFACT using the opa binary directly, rather than by
# calling Smith's wrappers — those are the unit lane's subject.
# ===========================================================================


def test_the_delivered_file_is_canonically_formatted(run_ok):
    # The flag runs `opa fmt -w` itself, so re-formatting must be a no-op.
    result = subprocess.run(
        ["opa", "fmt", str(run_ok["dest"])], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == run_ok["dest"].read_text(), (
        "the delivered file is not canonically formatted"
    )


def test_the_translated_policy_type_checks(run_ok):
    # THE property only this lane can establish: dropping the envelope rule and
    # the allowed_arg_keys block could leave a dangling reference or an empty rule
    # body, and a text transform cannot know. Real OPA is the judge.
    result = subprocess.run(
        ["opa", "check", str(run_ok["dest"])],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"the translated policy is not valid rego:\n{result.stderr}"
    )


def test_the_flag_reports_that_validation_passed(run_ok):
    # The CLI prints OPA's verdict; a silent success would hide a skipped check.
    stdout = run_ok["result"].stdout
    assert "opa fmt -w" in stdout
    assert "All validation checks passed" in stdout, stdout[-1500:]


# ===========================================================================
# CLI — the argument contract
#
# These invoke the CLI separately because they exercise ARGUMENT handling, which
# needs different arguments by definition.
# ===========================================================================


def test_the_destination_defaults_beside_the_source(
    smith_cli, unit_env, requires_opa_binary
):
    # `--policy_path X` with no --dest writes X_cpex.rego alongside X.
    src = write_text(unit_env.root / "mypolicy.rego", FULL_POLICY)
    result = smith_cli("cpex_translate", "--policy_path", str(src), timeout=180)
    assert result.returncode == 0, result.stdout[-1500:]
    assert (unit_env.root / "mypolicy_cpex.rego").exists()


def test_a_missing_source_exits_nonzero(smith_cli, unit_env):
    # No OPA needed: the existence check comes first, so this is the cheapest
    # test in the file.
    result = smith_cli(
        "cpex_translate",
        "--policy_path",
        str(unit_env.root / "nope.rego"),
        timeout=120,
    )
    assert result.returncode == 1


def test_the_frozen_fixture_policy_translates_to_valid_rego(
    smith_cli, unit_env, requires_opa_binary
):
    # A guard on the fixture itself: the policy every scorecard expectation is
    # built on must survive translation, or the CPEX path is broken for the one
    # policy shape Smith actually ships.
    dest = unit_env.root / "fixture_cpex.rego"
    result = smith_cli(
        "cpex_translate",
        "--policy_path",
        str(FIXTURE_POLICY),
        "--dest",
        str(dest),
        timeout=180,
    )
    assert result.returncode == 0, result.stdout[-1500:]
    assert "All validation checks passed" in result.stdout, result.stdout[-1500:]
    out = dest.read_text()
    assert "package authz" in out
    assert "input.extensions" not in out
