# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the function behind ``smith --flag policy_testing``.

Policy testing is the scoring stage: it runs every staged test case through OPA and
writes a scorecard of true/false positives and negatives. The flag is a thin
wrapper::

    BlueAgent.policy_checking_results()
        -> run_policy_evaluation(base_url, test_result_path)
               validate base_url                 -> ValueError
               locate <base_url>/Makefile        -> FileNotFoundError
               subprocess.run(["make", "test"])  -> the OPA harness (Docker + curl)
               read test_result_path             -> return the scorecard text

SCOPE: WHAT IS COVERED HERE
---------------------------
The ``make test`` target is the real work — it starts OPA in Docker and curls every
case — and that belongs entirely to the integration lane. What is *this* function's
own logic is the wrapper around it: two guards, the failure handling, and the
read-back. So ``subprocess.run`` is faked and those four paths run for real.

That is a small surface deliberately. A test asserting "the faked make was invoked"
would be testing the fake; what is asserted instead is **which guards fire before
any subprocess is launched**, and **what happens when the harness fails** — the
branch a developer actually hits when Docker is not running.

This is the coverage deliberately excluded from ``test_cross_validate_unit.py``,
where ``run_policy_evaluation`` is only a preliminary step. Here it is the flag's
own top-level function.

FUNCTIONS UNDER TEST
--------------------
Listed — and laid out in this file — in the order the flag executes them.

STEP 1 · ``smith.policy_agent.policy_evaluation.run_policy_evaluation``
    ``run_policy_evaluation``  — the empty-``base_url`` guard and the missing-
                                 ``Makefile`` guard, both before any subprocess

STEP 2 · invoking the harness
    ``run_policy_evaluation``  — the argv and working directory it runs ``make``
                                 in, since the harness is path-sensitive

STEP 3 · the result
    ``run_policy_evaluation``  — the scorecard is read and returned on success,
                                 **and also after a failed run**; plus the pinned
                                 case where that read-back masks the real error

NOT COVERED HERE (integration lane — see ``test_policy_testing_integration.py``)
    The ``make test`` harness itself: real OPA in Docker, the frozen scorecard
    numbers in ``helpers.EXPECTED``, and the per-bucket ``fp/fn/tp/tn`` files.

Env-free: ``subprocess.run`` is patched, so no Docker, no OPA, no ``make``.
"""

from __future__ import annotations

import subprocess

import pytest

from smith.policy_agent.policy_evaluation import run_policy_evaluation as rpe_mod
from smith.policy_agent.policy_evaluation.run_policy_evaluation import (
    run_policy_evaluation,
)

from data_builders import write_text

pytestmark = pytest.mark.unit


SCORECARD_TEXT = "Scorecard Summary\n===================\ntn: 30\nfp: 5\n"


@pytest.fixture
def project(unit_env):
    """A project root with a Makefile and a scorecard, as a real run would have."""

    class Project:
        root = unit_env.root
        makefile = write_text(unit_env.root / "Makefile", "test:\n\t@true\n")
        summary = write_text(
            unit_env.root / "references" / "scorecard" / "scorecard_summary.txt",
            SCORECARD_TEXT,
        )

    return Project()


def _fake_make(monkeypatch, result=(0, "", "")):
    from fakes import FakeProcess

    fake = FakeProcess(results=[result])
    monkeypatch.setattr(rpe_mod.subprocess, "run", fake)
    return fake


# ===========================================================================
# STEP 1 · the guards, both before any subprocess
# ===========================================================================


@pytest.mark.parametrize("base_url", ["", None], ids=["empty", "none"])
def test_a_missing_base_url_is_rejected_before_launching_anything(
    monkeypatch, base_url
):
    fake = _fake_make(monkeypatch)

    with pytest.raises(ValueError, match="BASE_URL not provided"):
        run_policy_evaluation(base_url, "/nonexistent/summary.txt")

    assert fake.call_count == 0, "no subprocess should run without a project root"


def test_a_project_without_a_makefile_is_rejected_before_launching_anything(
    unit_env, monkeypatch
):
    # The harness IS the Makefile's `test` target, so its absence means there is
    # nothing to run. Failing here names the problem; letting `make` fail would
    # surface as a generic non-zero exit.
    fake = _fake_make(monkeypatch)

    with pytest.raises(FileNotFoundError, match="Makefile not found"):
        run_policy_evaluation(str(unit_env.root), "/nonexistent/summary.txt")

    assert fake.call_count == 0


def test_the_guard_names_the_path_it_looked_in(unit_env, monkeypatch):
    # The error must be actionable: a wrong BASE_URL is the likeliest cause, so the
    # message has to show where it searched.
    _fake_make(monkeypatch)

    with pytest.raises(FileNotFoundError) as excinfo:
        run_policy_evaluation(str(unit_env.root), "/nonexistent/summary.txt")

    assert str(unit_env.root) in str(excinfo.value)


# ===========================================================================
# STEP 2 · how the harness is invoked
# ===========================================================================


def test_make_test_is_run_from_the_project_root(project, monkeypatch):
    """The harness is path-sensitive, so ``cwd`` is part of the contract."""
    fake = _fake_make(monkeypatch)

    run_policy_evaluation(str(project.root), str(project.summary))

    assert fake.calls[0] == ["make", "test"]
    assert fake.commands[0] == "make test"


def test_a_relative_base_url_is_resolved_to_an_absolute_root(project, monkeypatch):
    # `os.path.abspath` — the CLI passes BASE_URL straight through, and `make` is
    # given `cwd`, so a relative value must be anchored before use.
    import os

    fake = _fake_make(monkeypatch)
    relative = os.path.relpath(project.root, os.getcwd())

    run_policy_evaluation(relative, str(project.summary))

    assert fake.call_count == 1


# ===========================================================================
# STEP 3 · the scorecard is read back — on success and on failure
# ===========================================================================


def test_the_scorecard_text_is_returned_on_success(project, monkeypatch, capsys):
    # The return value is what the refinement loop reads, and it is also printed so
    # a user running the flag sees the scorecard without opening the file.
    result = run_policy_evaluation(str(project.root), str(project.summary))

    assert result == SCORECARD_TEXT
    out = capsys.readouterr().out
    assert "completed successfully" in out
    assert "tn: 30" in out, "the scorecard must reach stdout, not only the return value"


def test_a_failed_harness_run_still_returns_the_scorecard(project, monkeypatch, capsys):
    """CORRECTNESS: a non-zero ``make test`` is reported but not fatal.

    ``score_card.sh`` exits non-zero when cases fail — which is the *normal* state
    of a policy under refinement, not an error. So the exception is caught and the
    scorecard is still read: suppressing it would hide the very failures the flag
    exists to surface.
    """
    from fakes import FakeProcess

    monkeypatch.setattr(
        rpe_mod.subprocess,
        "run",
        FakeProcess(results=[subprocess.CalledProcessError(2, ["make", "test"])]),
    )

    result = run_policy_evaluation(str(project.root), str(project.summary))

    assert result == SCORECARD_TEXT, "the scorecard must be read even after a failure"
    assert "tests failed" in capsys.readouterr().out


def test_a_failed_run_with_no_scorecard_raises_about_the_wrong_thing(
    project, monkeypatch, capsys
):
    from fakes import FakeProcess

    monkeypatch.setattr(
        rpe_mod.subprocess,
        "run",
        FakeProcess(results=[subprocess.CalledProcessError(2, ["make", "test"])]),
    )
    absent = project.root / "references" / "scorecard" / "never_written.txt"

    with pytest.raises(FileNotFoundError) as excinfo:
        run_policy_evaluation(str(project.root), str(absent))

    # The exception is about the scorecard, NOT about the harness that failed.
    assert "never_written.txt" in str(excinfo.value)
    assert "make" not in str(excinfo.value)
    # The real cause was printed, so it is recoverable from the logs.
    assert "tests failed" in capsys.readouterr().out


def test_a_successful_run_with_no_scorecard_also_raises(project, monkeypatch):
    # The same unguarded read on the success path. Here it is arguably right: `make`
    # exited zero yet wrote nothing, which means the harness is broken rather than
    # the policy failing.
    _fake_make(monkeypatch)
    absent = project.root / "references" / "scorecard" / "never_written.txt"

    with pytest.raises(FileNotFoundError):
        run_policy_evaluation(str(project.root), str(absent))
