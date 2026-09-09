# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the function behind ``smith --flag regal_suggestion``.

The flag asks the Styra **Regal** linter what is stylistically wrong with the policy
and hands the report to the refinement loop::

    BlueAgent.get_regal_feedback()
        -> create_regal_suggestion(policy_path, regal_suggestion_path)
               regal lint <policy>          (invoked directly, no shell)
               strip ANSI escapes in Python
               write the report, return its text

SCOPE: THIS IS A THIN WRAPPER, SO THIS FILE IS SHORT
----------------------------------------------------
Whether Regal correctly flags an unused rule is **Regal's** correctness, trusted
here rather than re-verified. What belongs to Smith is:

1. **Reading the exit code correctly.** ``regal lint`` returns 0 for "no
   violations" and **3** for "violations found" — so 3 is a normal, expected result,
   not a failure. Anything else (notably 127, binary not found) means the linter did
   not run, and must be reported rather than passed off as a clean policy.
2. **Stripping ANSI escapes**, since the report is printed *and* fed to an LLM.
3. **Writing and returning** the same text.

No per-rule tests: asserting that a fake echoing "unused-rule" comes back as
"unused-rule" would test the fake and a file read.

FUNCTIONS UNDER TEST
--------------------
STEP 1 · ``smith.policy_agent.policy_analysis.regal.regal_finder``
    ``create_regal_suggestion``  — the argv it builds, the exit-code classification,
                                   the ANSI strip, the written artifact, and the
                                   failure paths

NOT COVERED HERE (integration lane — see ``test_regal_suggestion_integration.py``)
    The real ``regal`` binary's findings on a real policy, that it genuinely
    colourises its output, and the CLI wiring.

Env-free: ``subprocess.run`` is patched, so the ``regal`` binary is never invoked.
"""

from __future__ import annotations

import subprocess

import pytest

from smith.policy_agent.policy_analysis.regal import regal_finder as regal_mod
from smith.policy_agent.policy_analysis.regal.regal_finder import (
    create_regal_suggestion,
)

from data_builders import minimal_policy, write_text
from fakes import FakeProcess

pytestmark = pytest.mark.unit


#: A colourised finding, as Regal really emits it (yellow label, cyan location).
COLOURISED = (
    "\x1b[33mRule:\x1b[0m         \tunused-rule\n"
    "\x1b[33mLocation:\x1b[0m     \t\x1b[36mpolicy.rego:9:1\x1b[0m\n"
)

#: Regal's own exit codes.
NO_VIOLATIONS = 0
VIOLATIONS_FOUND = 3


@pytest.fixture
def policy(unit_env):
    return write_text(unit_env.root / "policy.rego", minimal_policy())


@pytest.fixture
def report(unit_env):
    return unit_env.root / "outputs" / "regal_suggestion.txt"


def _fake_regal(monkeypatch, returncode, stdout="", stderr=""):
    fake = FakeProcess(results=[(returncode, stdout, stderr)])
    monkeypatch.setattr(regal_mod.subprocess, "run", fake)
    return fake


# ===========================================================================
# STEP 1 · create_regal_suggestion
# ===========================================================================


def test_regal_is_invoked_directly_on_the_policy(monkeypatch, policy, report):
    fake = _fake_regal(monkeypatch, NO_VIOLATIONS)

    create_regal_suggestion(str(policy), str(report))

    assert fake.calls[0] == ["regal", "lint", str(policy)]
    assert fake.calls[0][0] == "regal", "regal must be argv[0], not part of a string"


def test_violations_found_is_a_normal_result_not_a_failure(monkeypatch, policy, report):
    _fake_regal(monkeypatch, VIOLATIONS_FOUND, stdout="Rule:\tunused-rule\n")

    result = create_regal_suggestion(str(policy), str(report))

    assert "unused-rule" in result
    assert "failed" not in result


def test_a_clean_policy_reports_regals_own_summary(monkeypatch, policy, report):
    _fake_regal(
        monkeypatch, NO_VIOLATIONS, stdout="1 file linted. No violations found.\n"
    )

    result = create_regal_suggestion(str(policy), str(report))

    assert result == "1 file linted. No violations found.\n"
    assert "failed" not in result and "could not be run" not in result


def test_a_linter_that_did_not_run_is_reported_not_silently_empty(
    monkeypatch, policy, report
):
    _fake_regal(monkeypatch, 127, stderr="regal: command not found\n")

    result = create_regal_suggestion(str(policy), str(report))

    assert "regal lint failed (exit 127)" in result
    assert "Is Regal installed?" in result, "the message must say how to fix it"
    # And the diagnostic is not mistakable for findings.
    assert "Rule:" not in result


@pytest.mark.parametrize("returncode", [1, 2, 4, 127], ids=lambda c: f"exit-{c}")
def test_any_unrecognised_exit_code_is_treated_as_a_failure(
    monkeypatch, policy, report, returncode
):
    # Only 0 and 3 mean the linter ran. Guarding on a whitelist rather than a
    # blacklist means a future Regal error code is reported, not misread as success.
    _fake_regal(monkeypatch, returncode, stdout="partial output")

    result = create_regal_suggestion(str(policy), str(report))

    assert f"exit {returncode}" in result


def test_ansi_escapes_are_stripped_from_the_report(monkeypatch, policy, report):
    _fake_regal(monkeypatch, VIOLATIONS_FOUND, stdout=COLOURISED)

    result = create_regal_suggestion(str(policy), str(report))

    assert "\x1b[" not in result, f"escape codes survived: {result!r}"
    # The content survives the strip — only the colour bytes go.
    assert "unused-rule" in result
    assert "policy.rego:9:1" in result


def test_the_report_is_both_written_and_returned(monkeypatch, policy, report):
    # The CLI prints the return value; the file is what a reviewer keeps. They must
    # not diverge.
    _fake_regal(monkeypatch, VIOLATIONS_FOUND, stdout=COLOURISED)

    result = create_regal_suggestion(str(policy), str(report))

    assert report.read_text() == result


def test_the_report_directory_is_created_on_demand(monkeypatch, policy, unit_env):
    # `assets/opa/outputs/` may not exist in a fresh checkout, and the previous
    # shell redirect would have failed there.
    nested = unit_env.root / "does" / "not" / "exist" / "regal.txt"
    _fake_regal(monkeypatch, NO_VIOLATIONS, stdout="clean\n")

    create_regal_suggestion(str(policy), str(nested))

    assert nested.read_text() == "clean\n"


def test_a_failure_to_launch_is_contained(monkeypatch, policy, report):
    # An OSError (a vanished binary, a permissions problem) must become a reported
    # result rather than a traceback: this is called from a CLI flag whose contract
    # is an exit code.
    monkeypatch.setattr(
        regal_mod.subprocess,
        "run",
        FakeProcess(default=OSError("permission denied")),
    )

    result = create_regal_suggestion(str(policy), str(report))

    assert "could not be run" in result
    assert "permission denied" in result
    assert report.read_text() == result, "the failure is recorded in the file too"


def test_a_hung_linter_is_contained(monkeypatch, policy, report):
    # The call is bounded by a timeout; the expiry must surface as a normal failure
    # so a wedged Regal cannot hang the flag indefinitely.
    monkeypatch.setattr(
        regal_mod.subprocess,
        "run",
        FakeProcess(default=subprocess.TimeoutExpired(cmd="regal", timeout=120)),
    )

    result = create_regal_suggestion(str(policy), str(report))

    assert "could not be run" in result
