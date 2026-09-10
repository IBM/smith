# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the functions behind ``smith --flag policy_validation`` /
``--flag policy_validation_fix``.

Both flags are thin wrappers over ``smith.policy_generation.validate_policy``::

    policy_validation      -> validate_policy(path)           # check only
    policy_validation_fix  -> fix_and_validate_policy(path)   # rewrite, then check

Each composite shells out to the ``opa`` binary three times and folds the three
exit codes into one boolean:

    validate_policy       = fmt      + check + eval_smoke
    fix_and_validate      = fmt -w   + check + eval_smoke

FUNCTIONS UNDER TEST
--------------------
Listed — and laid out in this file — in the order the composites call them.

STEP 0 · ``smith.policy_generation.validate_policy``
    ``check_opa_installed``     — presence detection via ``shutil.which``

STEP 1 · ``run_opa_fmt``       — the read-back comparison: content-based, not
                                 path-based, plus the empty-stdout branch

STEP 2 · the composites
    ``validate_policy``        — guard order, three-into-one folding, no
                                 short-circuit, and that it never rewrites
    ``fix_and_validate_policy``— ``fmt -w`` replaces plain ``fmt``, a failed
                                 rewrite still runs the checks, and an absent OPA
                                 leaves the file untouched

Cross-cutting
    All four runners' containment contract — timeout and OSError — in one
    parametrized test.

NOT COVERED HERE (integration lane — see ``test_policy_validation_integration.py``)
    Everything about what a **real** ``opa`` build reports. The integration lane
    drives the CLI end to end against real OPA and asserts the exit code and
    stdout; it does not call these functions.

Env-free: ``shutil.which`` and ``subprocess.run`` are patched, so these tests give
the same answer whether or not OPA is installed.
"""

from __future__ import annotations

import subprocess

import pytest

from smith.policy_generation import validate_policy as vp_mod
from smith.policy_generation.validate_policy import (
    check_opa_installed,
    fix_and_validate_policy,
    run_opa_check,
    run_opa_eval_smoke,
    run_opa_fmt,
    run_opa_fmt_write,
    validate_policy,
)

from data_builders import minimal_policy, write_text
from fakes import FakeProcess

pytestmark = pytest.mark.unit


#: The two commands whose result is a plain pass-through, with "success" values.
#: ``opa fmt``'s stdout is compared against the file, so it is filled in per-test
#: with the policy's own text.
PASSING = {"opa check": (0, "", ""), "opa eval": (0, "{}", "")}


@pytest.fixture
def opa_present(monkeypatch):
    """Pretend the ``opa`` binary is on PATH."""
    monkeypatch.setattr(vp_mod.shutil, "which", lambda _name: "/usr/local/bin/opa")


@pytest.fixture
def opa_absent(monkeypatch):
    """Pretend the ``opa`` binary is missing."""
    monkeypatch.setattr(vp_mod.shutil, "which", lambda _name: None)


@pytest.fixture
def policy(unit_env):
    """A small valid policy on disk, under the temp root."""
    return write_text(unit_env.root / "policy.rego", minimal_policy())


def _fake_run(monkeypatch, fake: FakeProcess) -> FakeProcess:
    monkeypatch.setattr(vp_mod.subprocess, "run", fake)
    return fake


def _all_pass(policy) -> dict:
    """The by_command mapping where all three checks succeed for ``policy``."""
    return {"opa fmt": (0, policy.read_text(), ""), **PASSING}


# ===========================================================================
# STEP 0 · check_opa_installed
# ===========================================================================


def test_opa_absent_is_reported_false_rather_than_raising(opa_absent):
    # False rather than an exception: the callers turn this into a clean
    # "cannot validate" result instead of a crash.
    assert check_opa_installed() is False


def test_presence_is_decided_by_looking_up_opa_specifically(monkeypatch):
    # Guards against a `which` call that ignores its argument — which would
    # report OPA present whenever *any* binary resolves.
    looked_up = []
    monkeypatch.setattr(
        vp_mod.shutil, "which", lambda name: looked_up.append(name) or "/bin/opa"
    )
    assert check_opa_installed() is True
    assert looked_up == ["opa"]


# ===========================================================================
# STEP 1 · run_opa_fmt — the only runner with logic of its own
# ===========================================================================


def test_fmt_compares_against_the_file_on_disk_not_the_path(monkeypatch, unit_env):
    formatted = minimal_policy()
    same = write_text(unit_env.root / "same.rego", formatted)
    other = write_text(unit_env.root / "other.rego", minimal_policy(package="mcp.x"))

    _fake_run(monkeypatch, FakeProcess(default=(0, formatted, "")))

    assert "syntax is valid" in run_opa_fmt(str(same))[1]
    assert "would rewrite" in run_opa_fmt(str(other))[1]


def test_fmt_treats_empty_stdout_as_no_difference(monkeypatch, policy):
    # `if result.stdout and ...` — an empty stdout with a zero exit is read as
    # "nothing to say", not as "the formatted policy is the empty string".
    # Without that guard every silent success would be misreported as a rewrite.
    _fake_run(monkeypatch, FakeProcess(results=[(0, "", "")]))
    ok, msg = run_opa_fmt(str(policy))
    assert ok is True
    assert "syntax is valid" in msg


# ===========================================================================
# STEP 2 · validate_policy — folding three results into one verdict
# ===========================================================================


def test_a_missing_policy_file_fails_before_launching_any_tool(
    unit_env, monkeypatch, opa_present
):
    # Deliberate: the existence check precedes OPA, so a typo'd path gives a
    # clear error instead of an opaque tool failure — and costs no subprocess.
    fake = _fake_run(monkeypatch, FakeProcess())
    assert validate_policy(str(unit_env.root / "nope.rego")) is False
    assert fake.call_count == 0, "no tool should run for a nonexistent file"


def test_absent_opa_fails_before_launching_any_tool(monkeypatch, policy, opa_absent):
    fake = _fake_run(monkeypatch, FakeProcess())
    assert validate_policy(str(policy)) is False
    assert fake.call_count == 0


def test_all_three_checks_run_in_order_and_none_is_skipped(
    monkeypatch, policy, opa_present
):
    # fmt -> check -> eval, all three, even when all pass: the composite does not
    # stop early. Order is user-visible, since it is the order the report prints.
    fake = _fake_run(monkeypatch, FakeProcess(by_command=_all_pass(policy)))
    assert validate_policy(str(policy)) is True
    assert [c.split()[1] for c in fake.commands] == ["fmt", "check", "eval"]


def test_validation_never_rewrites_the_policy(monkeypatch, policy, opa_present):
    # The read-only contract: `policy_validation` must not be a silent formatter.
    # Only `policy_validation_fix` may pass -w. SKILL.md forbids modifying a policy
    # without explicit human approval, so a check flag that reformatted would
    # violate the skill's own rules.
    fake = _fake_run(monkeypatch, FakeProcess(by_command=_all_pass(policy)))
    validate_policy(str(policy))
    assert not fake.ran("-w"), f"validation must not rewrite the file: {fake.commands}"


@pytest.mark.parametrize("failing", ["opa fmt", "opa check", "opa eval"])
def test_any_single_check_failing_fails_the_whole_validation(
    monkeypatch, policy, opa_present, failing
):
    results = _all_pass(policy)
    results[failing] = (1, "", "boom")
    fake = _fake_run(monkeypatch, FakeProcess(by_command=results))

    assert validate_policy(str(policy)) is False
    # And it still runs every check, so the user sees ALL problems at once
    # rather than fixing them one round-trip at a time.
    assert fake.call_count == 3, fake.commands


def test_a_failure_is_explained_on_stdout_not_only_returned(
    monkeypatch, policy, opa_present, capsys
):
    # The boolean drives the exit code, but the printed diagnostic is what a human
    # — or the refinement loop reading stdout — acts on.
    results = _all_pass(policy)
    results["opa check"] = (1, "", "rego_type_error: undefined function frobnicate")
    _fake_run(monkeypatch, FakeProcess(by_command=results))

    assert validate_policy(str(policy)) is False
    out = capsys.readouterr().out
    assert "[FAIL] opa check" in out
    assert "frobnicate" in out, "the tool's diagnostic must reach stdout"
    assert "Some validation checks failed" in out


# ===========================================================================
# STEP 2 · fix_and_validate_policy — the composite that rewrites
# ===========================================================================


def test_fix_runs_fmt_write_instead_of_plain_fmt(monkeypatch, policy, opa_present):
    fake = _fake_run(
        monkeypatch, FakeProcess(by_command={"opa fmt -w": (0, "", ""), **PASSING})
    )
    assert fix_and_validate_policy(str(policy)) is True
    assert fake.call_count == 3, fake.commands
    assert "-w" in fake.commands[0], fake.commands
    assert [c.split()[1] for c in fake.commands] == ["fmt", "check", "eval"]

def test_fix_with_absent_opa_leaves_the_file_untouched(monkeypatch, policy, opa_absent):
    # Important for a *rewriting* flag: no OPA means the policy is left exactly as
    # it was, rather than half-processed.
    before = policy.read_text()
    fake = _fake_run(monkeypatch, FakeProcess())
    assert fix_and_validate_policy(str(policy)) is False
    assert fake.call_count == 0
    assert policy.read_text() == before


# ===========================================================================
# Cross-cutting — the containment contract shared by all four runners
# ===========================================================================


@pytest.mark.parametrize(
    "runner,label",
    [
        (run_opa_fmt, "opa fmt"),
        (run_opa_fmt_write, "opa fmt -w"),
        (run_opa_check, "opa check"),
        (run_opa_eval_smoke, "opa eval"),
    ],
)
@pytest.mark.parametrize(
    "raised,expected",
    [
        (OSError("permission denied"), "Error running {label}"),
        (subprocess.TimeoutExpired(cmd="opa", timeout=30), "timed out"),
    ],
    ids=["oserror", "timeout"],
)
def test_every_runner_contains_a_subprocess_failure(
    monkeypatch, policy, runner, label, raised, expected
):
    _fake_run(monkeypatch, FakeProcess(default=raised))
    ok, msg = runner(str(policy))
    assert ok is False
    assert expected.format(label=label) in msg
