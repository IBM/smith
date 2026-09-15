# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``smith --flag policy_testing``.

The scoring stage. It runs the packaged OPA harness over every staged case and
writes the scorecard the whole refinement loop keys on::

    run_policy_evaluation -> make test -> score_card.sh
        start OPA in Docker with the staged policy
        curl every case under test_cases/{allow,disallow}/
        classify each: allow-allowed=tn, allow-denied=fp,
                       disallow-denied=tp, disallow-allowed=fn
        -> scorecard/{scorecard_summary.txt, score_test_failures.txt,
                      tp,fp,tn,fn}.txt
        + `opa test --coverage` over the policy

Driven through the **real CLI** against **real OPA in Docker**. This file imports
nothing from ``smith``, so every assertion reads an artifact the run produced.

STEPS COVERED (all from the single run)
--------------------------------------
STEP 1  the harness runs      — Docker, OPA, and a curl per case
STEP 2  ``scorecard_summary`` — the per-experiment totals and coverage
STEP 3  the bucket files      — every case classified into exactly one of
                                ``tp/fp/tn/fn``
STEP 4  ``score_test_failures`` — the failure list ``red_suggestion`` and
                                ``cross_validate`` consume

COST: THE FLAG IS RUN ONCE
--------------------------
It starts a Docker container and issues one HTTP request per staged case (115 of
them). No LLM. The flag runs **exactly once** in a module-scoped fixture and every
assertion inspects that run's artifacts.

ASSERTING CORRECTNESS: THIS FILE IS THE EXACT-NUMBERS CASE
----------------------------------------------------------
Per the guide, ``policy_testing`` has a **frozen policy and frozen cases**, so its
scorecard is fully reproducible — no model, no ordering, no wall-clock. The exact
counts and coverage from ``helpers.EXPECTED`` are therefore asserted:

    tn=30  fp=5  tp=70  fn=10      coverage 86.49%  (64 covered / 10 uncovered)

**Never "update" these numbers to match a new run.** A change here means the fixture
policy or the case set changed, which is a finding to investigate — not a fixture to
refresh. The guide says so explicitly, and the ``arguments`` -> ``args`` rename
earlier in this refactor is exactly why: renaming only one side of it silently moved
tn=30 to tn=35, which these numbers caught.

The staged policy and case tree are backed up and restored, along with every
scorecard artifact.

Requires Docker, ``make``, and the ``opa`` binary.
"""

from __future__ import annotations

import pytest

from helpers import EXPECTED, parse_scorecard_summary

pytestmark = pytest.mark.integration


#: The four confusion-matrix buckets, each written as its own file of case paths.
BUCKETS = ("tp", "fp", "tn", "fn")


@pytest.fixture(scope="module")
def completed_run():
    """Run ``policy_testing`` ONCE over the frozen fixtures; yield its artifacts.

    Stages the frozen policy and the frozen 115-case tree, so the scorecard is the
    reproducible one ``EXPECTED`` records. Module-scoped because the run starts
    Docker and issues one request per case.
    """
    import shutil
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    from helpers import FIXTURE_POLICY, FIXTURE_TEST_CASES, SmithEnv, which

    env = SmithEnv()
    if not which("docker"):
        pytest.skip("docker CLI not found (the harness runs OPA in a container)")
    if not which("make"):
        pytest.skip("make not found (the harness is a Makefile target)")

    policy = env.policy
    cases = env.test_cases
    scorecard = env.scorecard

    backup_dir = Path(tempfile.mkdtemp(prefix="smith_scorecard_backup_"))
    saved = {}
    for i, path in enumerate((policy, cases, scorecard)):
        if path.exists():
            dst = backup_dir / f"{i}_{path.name}"
            if path.is_dir():
                shutil.copytree(path, dst)
            else:
                shutil.copy2(path, dst)
            saved[path] = dst

    try:
        # Stage the frozen inputs: EXPECTED is only meaningful against these.
        policy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(FIXTURE_POLICY, policy)
        if cases.exists():
            shutil.rmtree(cases)
        shutil.copytree(FIXTURE_TEST_CASES, cases)
        if scorecard.exists():
            shutil.rmtree(scorecard)

        result = subprocess.run(
            [sys.executable, "-m", "smith.cli", "--flag", "policy_testing"],
            cwd=str(env.base),
            env=env.override(),
            capture_output=True,
            text=True,
            timeout=1800,
        )
        yield {
            "result": result,
            "scorecard": scorecard,
            "summary": env.scorecard_summary,
            "failures": env.failures_file,
            "cases": cases,
        }
    finally:
        for path in (policy, cases, scorecard):
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
        f"policy_testing failed (rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout[-3000:]}\n"
        f"--- stderr ---\n{result.stderr[-1500:]}"
    )
    return completed_run


@pytest.fixture(scope="module")
def summary(run_ok):
    """The parsed scorecard summary — the artifact the exact numbers come from."""
    path = run_ok["summary"]
    assert (
        path.exists()
    ), f"no scorecard summary at {path}\n{run_ok['result'].stdout[-2000:]}"
    return parse_scorecard_summary(path.read_text())


@pytest.fixture(scope="module")
def buckets(run_ok):
    """``{bucket: [case paths]}`` from the four confusion-matrix files."""
    out = {}
    for name in BUCKETS:
        path = run_ok["scorecard"] / f"{name}.txt"
        lines = (
            [ln.strip() for ln in path.read_text().splitlines() if ln.strip()]
            if path.exists()
            else []
        )
        out[name] = lines
    return out


# ===========================================================================
# STEP 1 — the harness actually ran
# ===========================================================================


def test_the_harness_reports_running_and_prints_the_scorecard(run_ok):
    # The flag prints the summary it read back, so a user sees the result without
    # opening the file. That echo is also how the refinement loop consumes it.
    stdout = run_ok["result"].stdout
    assert "Running policy evaluation tests via Makefile" in stdout
    assert (
        "Scorecard Summary" in stdout
    ), "the scorecard was not echoed, so the read-back step did not run"


# ===========================================================================
# STEP 2 — the frozen scorecard numbers
#
# THE exact-assertion case. Do not update these to match a new run.
# ===========================================================================


def test_the_confusion_matrix_matches_the_frozen_expectation(buckets):
    """CORRECTNESS, exactly: frozen policy + frozen cases = one reproducible answer."""
    actual = {name: len(paths) for name, paths in buckets.items()}
    expected = {name: EXPECTED[name] for name in BUCKETS}

    assert actual == expected, (
        f"the scorecard moved: {actual} != {expected}. Something changed in the "
        "fixture policy or the case set — that is a finding, not a number to update."
    )


def test_the_per_experiment_totals_match(summary):
    # The two experiments are the allow/ and disallow/ directories. Their totals are
    # the case counts, so a drift here means cases were added or lost.
    by_total = sorted(exp["total"] for exp in summary["experiments"])
    assert by_total == sorted(
        [EXPECTED["allow_total"], EXPECTED["disallow_total"]]
    ), f"experiment totals changed: {[e['total'] for e in summary['experiments']]}"


def test_each_experiment_splits_into_allowed_plus_denied(summary):
    # An aggregate that must match the data beside it — always checkable, and it
    # catches a case that OPA errored on rather than decided.
    for experiment in summary["experiments"]:
        assert experiment["allowed"] + experiment["denied"] == experiment["total"], (
            f"{experiment['experiment']}: allowed+denied != total, so some case was "
            f"not scored: {experiment}"
        )


def test_the_policy_coverage_matches_the_frozen_expectation(summary):
    """CORRECTNESS: ``opa test --coverage`` over a frozen policy is deterministic."""
    assert summary["coverage"] == pytest.approx(EXPECTED["coverage"])
    assert summary["covered_lines"] == EXPECTED["covered_lines"]
    assert summary["not_covered_lines"] == EXPECTED["not_covered_lines"]


def test_the_scored_policy_is_the_frozen_one(summary):
    # Guards the staging itself: if a different policy were scored, every number
    # above would be measuring the wrong file.
    assert (
        summary["policy_lines"] == EXPECTED["policy_lines"]
    ), "the scored policy is not the frozen fixture policy"


# ===========================================================================
# STEP 3 — every case is classified exactly once
# ===========================================================================


def test_every_staged_case_was_scored(buckets, run_ok):
    staged = list(run_ok["cases"].rglob("*.json"))
    scored = sum(len(paths) for paths in buckets.values())

    assert scored == len(staged), (
        f"{len(staged)} cases were staged but {scored} were scored — "
        f"{len(staged) - scored} went unclassified"
    )
    assert scored == sum(EXPECTED[name] for name in BUCKETS)


def test_no_case_lands_in_two_buckets(buckets):
    # The four buckets are mutually exclusive by construction, so an overlap would
    # mean a case was scored twice and double-counted in the totals.
    seen = {}
    for name, paths in buckets.items():
        for path in paths:
            assert path not in seen, f"{path} appears in both {seen[path]} and {name}"
            seen[path] = name


def test_the_buckets_agree_with_the_directory_each_case_came_from(buckets):
    for name in ("tp", "fn"):
        for path in buckets[name]:
            assert (
                "/disallow/" in path
            ), f"{name}.txt lists an allow/ case, so the labels are crossed: {path}"
    for name in ("tn", "fp"):
        for path in buckets[name]:
            assert (
                "/allow/" in path
            ), f"{name}.txt lists a disallow/ case, so the labels are crossed: {path}"


def test_every_scored_case_points_at_a_real_file(buckets):
    # red_suggestion and cross_validate open these paths, so one that does not
    # resolve makes the next stage a silent no-op.
    from pathlib import Path

    for name, paths in buckets.items():
        for path in paths:
            assert Path(path).is_file(), f"{name}.txt points at a missing file: {path}"


# ===========================================================================
# STEP 4 — the failures file the next stages consume
# ===========================================================================


def test_the_failures_file_holds_exactly_the_misclassified_cases(run_ok, buckets):
    path = run_ok["failures"]
    assert path.exists(), f"no failures file at {path}"

    text = path.read_text()
    for name in ("fp", "fn"):
        for case in buckets[name]:
            assert (
                case in text
            ), f"a {name} case is missing from the failures file: {case}"


def test_the_failure_count_matches_the_confusion_matrix(run_ok, buckets):
    # An aggregate check: the failures file must not contain a case the buckets call
    # correct, which would send refinement after a non-problem.
    text = run_ok["failures"].read_text()
    for name in ("tp", "tn"):
        for case in buckets[name]:
            assert (
                case not in text
            ), f"a correctly-scored {name} case was listed as a failure: {case}"
