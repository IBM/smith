# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``smith --flag regal_suggestion``.

The flag runs the Styra **Regal** linter over the policy under management and prints
its report, which the refinement loop then acts on::

    create_regal_suggestion(policy_path, regal_suggestion_path)
        regal lint <policy>          (invoked directly, no shell)
        classify the exit code: 0 = clean, 3 = violations, else = did not run
        strip ANSI escapes, write <out>
        -> the report text, printed on stdout

Driven through the **real CLI** against the **real ``regal`` binary**. This file
imports nothing from ``smith``, so every assertion reads the run's stdout or the
report file it left behind.

STEPS COVERED (all from the single run)
--------------------------------------
STEP 1  ``regal lint`` runs against the staged policy
STEP 2  the ANSI escapes Regal emits are stripped from the report
STEP 3  the report is written to ``REGAL_SUGGESTION_PATH`` and echoed on stdout

COST
----
No LLM, no Docker, no agent — one local ``regal`` invocation. The flag still runs
**once**, in a module-scoped fixture.

ASSERTING CORRECTNESS
---------------------
Regal is deterministic — a fixed linter over a frozen policy — so per the guide its
output is asserted exactly. The frozen fixture policy genuinely violates several
Regal rules, verified with the binary directly:

    default-over-else, directory-package-mismatch, line-length,
    messy-rule, opa-fmt, redundant-existence-check

Two of those are asserted by name (``opa-fmt`` and ``messy-rule``) because they
follow from properties of the file that are visible on inspection — it is not
canonically formatted, and it interleaves rule bodies. Asserting *all six* would
break on a Regal upgrade that renames or adds a rule, which is not a Smith
regression, so the rest is covered by "the report is non-empty and well-formed".

The staged policy and the report file are backed up and restored.

Requires the ``regal`` binary.
"""

from __future__ import annotations

import re

import pytest

pytestmark = pytest.mark.integration


#: Regal rule names the frozen fixture policy genuinely violates. Both follow from
#: inspectable properties of the file rather than from linter fashion: it is not
#: ``opa fmt``-clean, and it interleaves rule bodies (``messy-rule``).
EXPECTED_RULES = ("opa-fmt", "messy-rule")

#: Any CSI escape sequence — what the ANSI filter is there to remove.
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

#: Pulls the rule names out of a report, for a failure message that lists what
#: Regal *did* find. Precompiled rather than inlined because a backslash inside an
#: f-string requires Python 3.12, and this project targets 3.11.
RULE_NAME = re.compile(r"Rule:\s+(\S+)")


@pytest.fixture(scope="module")
def completed_run():
    """Run ``regal_suggestion`` ONCE over the frozen fixture policy."""
    import shutil
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    from helpers import FIXTURE_POLICY, SmithEnv, which

    env = SmithEnv()
    if not which("regal"):
        pytest.skip("regal binary not found (it installs separately from opa)")

    policy = env.policy
    report = (
        Path(env.base)
        / env.env["DATA_DIR"]
        / "outputs"
        / env.env["REGAL_SUGGESTION_PATH"]
    )

    backup_dir = Path(tempfile.mkdtemp(prefix="smith_regal_backup_"))
    saved = {}
    for i, path in enumerate((policy, report)):
        if path.exists():
            saved[path] = backup_dir / f"{i}_{path.name}"
            shutil.copy2(path, saved[path])

    try:
        policy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(FIXTURE_POLICY, policy)
        if report.exists():
            report.unlink()

        result = subprocess.run(
            [sys.executable, "-m", "smith.cli", "--flag", "regal_suggestion"],
            cwd=str(env.base),
            env=env.override(),
            capture_output=True,
            text=True,
            timeout=600,
        )
        yield {"result": result, "report": report, "policy": policy}
    finally:
        for path in (policy, report):
            if path.exists():
                path.unlink()
            if path in saved:
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(saved[path], path)
        shutil.rmtree(backup_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def run_ok(completed_run):
    """The run must have succeeded before any artifact assertion is meaningful."""
    result = completed_run["result"]
    assert result.returncode == 0, (
        f"regal_suggestion failed (rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout[-2500:]}\n"
        f"--- stderr ---\n{result.stderr[-1200:]}"
    )
    return completed_run


@pytest.fixture(scope="module")
def report(run_ok):
    """The report file's text — the artifact the flag both writes and returns."""
    path = run_ok["report"]
    assert (
        path.exists()
    ), f"no regal report at {path}\n{run_ok['result'].stdout[-2000:]}"
    return path.read_text()


# ===========================================================================
# STEP 1 — the linter ran and found the policy's real problems
# ===========================================================================


def test_the_linter_produced_findings(report):
    # The flag now classifies Regal's exit code (0 = clean, 3 = violations, anything
    # else = did not run), so a failure to launch reports itself rather than looking
    # like a clean policy. Both halves are checked: real findings, and no diagnostic.
    assert report.strip(), "the report is empty"
    assert "Rule:" in report, f"unexpected report format: {report[:300]!r}"
    assert (
        "regal lint failed" not in report
    ), f"the linter did not run: {report[:300]!r}"
    assert "could not be run" not in report


@pytest.mark.parametrize("rule", EXPECTED_RULES)
def test_the_known_violations_are_reported(report, rule):
    reported = sorted(set(RULE_NAME.findall(report)))
    assert rule in report, (
        f"regal did not report {rule!r} for the fixture policy; the reported rules "
        f"were {reported}"
    )


def test_each_finding_names_a_location_in_the_staged_policy(report, run_ok):
    # A finding without a location is unusable — the refinement loop has to know
    # which line to patch. And the path must be the policy the flag was pointed at.
    locations = re.findall(r"Location:\s+(\S+)", report)
    assert locations, "no finding carried a location"
    for location in locations:
        assert location.startswith(
            str(run_ok["policy"])
        ), f"a finding points outside the staged policy: {location!r}"


# ===========================================================================
# STEP 2 — the ANSI escapes are stripped
# ===========================================================================


def test_the_report_carries_no_terminal_escape_codes(report):
    found = ANSI_ESCAPE.findall(report)
    assert not found, f"{len(found)} ANSI escape(s) survived the filter: {found[:5]}"


def test_regal_really_does_colourise_so_the_filter_is_not_dead_weight(run_ok):
    """The other half: confirm the raw output *would* contain escapes.

    Otherwise the assertion above passes trivially and the ANSI filter could be
    removed without any test noticing. Invoking the binary directly is the only way
    to see the raw output Smith filtered.
    """
    import subprocess

    raw = subprocess.run(
        ["regal", "lint", str(run_ok["policy"])],
        capture_output=True,
        text=True,
        timeout=120,
    )
    combined = raw.stdout + raw.stderr
    assert ANSI_ESCAPE.search(combined), (
        "regal no longer colourises its output, so the ANSI filter is now dead "
        "weight — worth removing deliberately rather than leaving unexplained"
    )


# ===========================================================================
# STEP 3 — the report reaches the user
# ===========================================================================


def test_the_report_is_echoed_on_stdout(run_ok, report):
    # Unlike red_suggestion, this flag does `print(results)`, so the findings reach
    # a user without opening the file. The refinement loop reads this stdout too.
    stdout = run_ok["result"].stdout
    assert "collecting regal feedbacks" in stdout
    for rule in EXPECTED_RULES:
        assert rule in stdout, f"{rule} was written to the file but not printed"


def test_the_printed_report_matches_the_written_one(run_ok, report):
    # The return value and the file must not diverge: a user reading stdout and a
    # tool reading the file have to see the same findings.
    assert report.strip() in run_ok["result"].stdout


def test_the_policy_is_not_modified(run_ok):
    from helpers import FIXTURE_POLICY

    assert run_ok["policy"].read_text() == FIXTURE_POLICY.read_text()
