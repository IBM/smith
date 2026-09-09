# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``smith --flag policy_validation`` /
``--flag policy_validation_fix``.

Both flags are driven through the **real CLI** against the **real ``opa``
binary**. This file imports nothing from ``smith``, so no sub-function can be
reached even accidentally — every assertion reads a completed run's exit code, its
stdout, or the file it left on disk.

STEPS COVERED (all from the single ``policy_validation`` run)
-----------------------------------------------------------
STEP 1  ``opa fmt``          — reports a formatting difference, and passes anyway
STEP 2  ``opa check``        — rejects a policy that parses but does not type-check
STEP 3  ``opa eval`` (smoke) — the third check still runs after an earlier failure
CLI     the exit code, the diagnostic on stdout, and that the file is not modified

COST: THE FLAG IS RUN ONCE
--------------------------
Every assertion below inspects one run's output, from a module-scoped fixture.

WHAT ONLY THIS LANE CAN PROVE
-----------------------------
The unit lane fakes ``subprocess`` and therefore *encodes* an assumption about
what OPA reports for each policy shape. Only a real binary confirms it:

* A policy calling an undefined function is accepted by ``opa fmt`` and caught
  only by ``opa check``. That is the entire reason Smith runs both — if it ever
  stopped being true, the extra check would be dead weight and Smith would report
  a broken policy as valid.
* ``opa fmt -w`` really does normalize the file, and the result really is
  canonical — a property Smith delegates and never verifies itself.

ASSERTING CORRECTNESS
---------------------
This flag is deterministic — OPA plus the filesystem, no model — so per the guide
its outcomes are asserted exactly: the exit code, the per-check PASS/FAIL lines,
OPA's own diagnostic text, and the bytes on disk.

Everything happens under ``tmp_path``, so no repo file is touched and no backup is
needed. Requires the ``opa`` binary.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from data_builders import write_text
from helpers import SmithEnv, which

pytestmark = pytest.mark.integration


#: Staged input for the one validation run: 4-space indent and doubled blank lines
#: (so ``opa fmt`` would rewrite it) *and* a call to a function that does not exist
#: (so ``opa check`` rejects it). One run therefore exercises a PASS-with-note, a
#: hard FAIL, and the fold of both into a nonzero exit.
UNFORMATTED_AND_BROKEN = (
    "package mcp.policies\n\n\n\n"
    "default allow := false\n"
    "allow if {\n"
    "    not_a_builtin(input.name)\n"
    "}\n"
)

#: Staged input for the fix run: valid rego, but not canonically formatted. Valid
#: so that a successful rewrite is observable as an exit-0 run; unformatted so
#: there is genuinely something for ``opa fmt -w`` to change.
UNFORMATTED_BUT_VALID = (
    "package mcp.policies\n\n\n\n"
    "default allow := false\n"
    "allow if {\n"
    '    input.name == "get_events"\n'
    "}\n"
)


def _run_flag(work, flag, content):
    """Invoke one CLI flag against a crafted policy under ``work``."""
    env = SmithEnv()
    path = write_text(work / "policy.rego", content)
    result = subprocess.run(
        [sys.executable, "-m", "smith.cli", "--flag", flag, "--policy_path", str(path)],
        cwd=str(env.base),
        env=env.override(),
        capture_output=True,
        text=True,
        timeout=300,
    )
    return {"result": result, "path": path, "before": content}


@pytest.fixture(scope="module")
def opa_available():
    if not which("opa"):
        pytest.skip("opa binary not found on PATH")


@pytest.fixture(scope="module")
def completed_run(tmp_path_factory, opa_available):
    """Run ``policy_validation`` ONCE; yield the run and the file it was given."""
    work = tmp_path_factory.mktemp("policy_validation")
    return _run_flag(work, "policy_validation", UNFORMATTED_AND_BROKEN)


@pytest.fixture(scope="module")
def stdout(completed_run):
    """The run's combined output — the artifact every assertion below reads."""
    result = completed_run["result"]
    return result.stdout + result.stderr


# ===========================================================================
# STEP 1 — opa fmt reports the formatting difference, and passes anyway
# ===========================================================================


def test_the_formatting_difference_is_reported_but_does_not_fail(stdout):
    # Real `opa fmt` reports a difference, and Smith turns that into a PASS with a
    # note. Both halves matter: the note tells the user `_fix` would help, and the
    # PASS keeps a merely-unformatted policy from blocking a pipeline on style.
    assert "would rewrite" in stdout
    assert "[PASS] opa fmt" in stdout, "formatting must be advisory, not fatal"


# ===========================================================================
# STEP 2 — opa check rejects what opa fmt accepted
#
# THE property only this lane can establish.
# ===========================================================================


def test_the_type_error_passes_fmt_but_fails_check(stdout):
    assert "[PASS] opa fmt" in stdout, "a type error still parses, so fmt succeeds"
    assert "[FAIL] opa check" in stdout, "only opa check catches an undefined function"


def test_opas_own_diagnostic_reaches_the_user(stdout):
    # The message is the actionable part of a rejection; an exit code alone does
    # not tell the user which rule is wrong.
    assert "rego_type_error" in stdout
    assert "not_a_builtin" in stdout, "the offending symbol must be named"


# ===========================================================================
# STEP 3 — the run does not stop at the first failure
# ===========================================================================


def test_every_check_runs_even_though_one_failed(stdout):
    # All three lines present: the user sees every problem in one round trip
    # instead of re-running after each fix. This is the composite's fold observed
    # end to end, against real OPA rather than a fake.
    for check in ("opa fmt", "opa check", "opa eval (smoke)"):
        assert f"] {check}" in stdout, f"{check} did not run: {stdout[-1500:]}"


# ===========================================================================
# CLI — the exit code and the read-only contract
# ===========================================================================


def test_a_broken_policy_exits_nonzero(completed_run):
    # The exit code is the contract a CI pipeline and the refinement loop key on.
    assert completed_run["result"].returncode == 1
    assert "Some validation checks failed" in completed_run["result"].stdout


def test_validation_does_not_modify_the_policy(completed_run):
    # The read-only contract, observed on disk through the real CLI. SKILL.md
    # forbids modifying a policy without explicit human approval, so a check flag
    # that quietly reformatted — even a broken file — would violate it.
    assert completed_run["path"].read_text() == completed_run["before"]


# ===========================================================================
# policy_validation_fix — a DIFFERENT flag, so one run of its own
# ===========================================================================


@pytest.fixture(scope="module")
def fixed_run(tmp_path_factory, opa_available):
    """Run ``policy_validation_fix`` ONCE on a valid-but-unformatted policy."""
    work = tmp_path_factory.mktemp("policy_validation_fix")
    return _run_flag(work, "policy_validation_fix", UNFORMATTED_BUT_VALID)


def test_the_fix_flag_rewrites_the_file_and_exits_zero(fixed_run):
    result = fixed_run["result"]
    assert result.returncode == 0, result.stdout[-2000:]
    assert (
        fixed_run["path"].read_text() != fixed_run["before"]
    ), "the fix flag must actually rewrite an unformatted policy"
    assert "[PASS] opa fmt -w" in result.stdout
    assert "All validation checks passed" in result.stdout


def test_the_fixed_file_is_canonical_according_to_opa_itself(fixed_run):
    result = subprocess.run(
        ["opa", "fmt", str(fixed_run["path"])],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert (
        result.stdout == fixed_run["path"].read_text()
    ), "the file the fix flag delivered is still not canonically formatted"


def test_the_fix_preserves_the_authorization_logic(fixed_run):
    # A formatter must not change meaning. Reformatting that dropped the rule's
    # condition would turn a restrictive policy into an open one.
    text = fixed_run["path"].read_text()
    assert "package mcp.policies" in text
    assert "default allow := false" in text
    assert 'input.name == "get_events"' in text


# ===========================================================================
# CLI argument contract
#
# The guide's acceptable exception to the single-run rule: these exit before
# contacting any tool, so they cost nothing and need no opa binary.
# ===========================================================================


@pytest.mark.parametrize("flag", ["policy_validation", "policy_validation_fix"])
def test_the_cli_requires_a_policy_path(smith_cli, flag):
    result = smith_cli(flag, timeout=120)
    assert result.returncode == 1
    assert "--policy_path is required" in (result.stdout + result.stderr)


@pytest.mark.parametrize("flag", ["policy_validation", "policy_validation_fix"])
def test_a_nonexistent_policy_path_is_rejected_clearly(smith_cli, tmp_path, flag):
    # A typo'd path must name the problem rather than surfacing an opaque OPA error.
    missing = tmp_path / "does_not_exist.rego"
    result = smith_cli(flag, "--policy_path", str(missing), timeout=120)
    assert result.returncode == 1
    assert "not found" in (result.stdout + result.stderr)
