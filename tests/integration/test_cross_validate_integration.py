# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``--flag cross_validate`` / ``--flag apply_cross_validate``.

The pair forms a review loop over the cases the policy got *wrong*::

    cross_validate        run policy_testing (Docker + OPA) -> for each FAILURE,
                          ask a real LLM whether the case's LABEL was wrong or the
                          POLICY is -> write cross_validate_report.json
    apply_cross_validate  read that report and move / delete the case files

STEPS COVERED (all from the single run)
--------------------------------------
STEP 1  ``policy_checking_results``      — the flag scores the policy first, so a
                                           failures file exists to review
STEP 2  ``cross_validate_failed_cases``  — a real LLM judgement per failure,
                                           written as a well-shaped report
STEP 3  ``apply_cross_validate_results`` — the report's actions are applied to the
                                           real case tree

COST: cross_validate IS RUN ONCE
--------------------------------
It starts OPA in Docker, scores every staged case, then makes one LLM call per
failure. So this file runs it **exactly once** in a module-scoped fixture and every
assertion inspects that run. ``apply_cross_validate`` is free (pure file moves), so
it is driven separately.

THE STAGED INPUT IS CHOSEN SO THERE IS EXACTLY ONE FAILURE
----------------------------------------------------------
A case only reaches the LLM if the policy's decision **disagrees** with its folder,
so the staging is not arbitrary — it was verified against the frozen fixture policy
with ``opa eval``:

============================================  ============  =====================
staged case                                   policy allows  outcome
============================================  ============  =====================
``disallow/bypass_test_case0.json``           yes            **FAILS** -> reviewed
``allow/test_case0.json``                     yes            passes -> not reviewed
============================================  ============  =====================

The failing case carries an **extra argument key** (``sort_by``). Guidance rule 4
forbids exactly that, and the fixture policy declares ``allowed_arg_keys`` but
never enforces it — so the case is a genuine false negative, its ``disallow``
label is *correct*, and the fault lies with the policy. That makes it the one
input this flag exists to surface, and it keeps the bill at a single LLM call.

ASSERTING CORRECTNESS, NOT JUST SHAPE
-------------------------------------
Per the guide, exact assertions only where the answer cannot differ:

* The **adversarial collapse** is applied in code, not by the model — a
  ``bypass_test_case*`` failure can only ever be ``keep`` or ``remove``, never a
  relabel. That is asserted exactly, and it is the security property this flag
  exists to protect.
* **Which case gets reviewed** is decided by OPA, not the model, so the report's
  membership is asserted exactly: the failing case is present, the passing one is
  absent.
* Aggregates must match the data beside them — always checkable.
* ``apply_cross_validate`` is pure file movement, so its outcomes are asserted
  exactly.
* The individual **verdict** is left shape-based. Whether this is a mislabel or a
  policy bug is precisely the judgement the LLM is there to make, and a competent
  model may legitimately answer ``keep`` *or* ``remove`` here — so demanding one
  would be asserting confidence the input does not warrant.

Requirements: Docker + make (for the scoring step) and a real LLM. The staged
policy, case tree, scorecard and report are backed up and restored.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_builders import cross_validate_report, cv_case, envelope_case, write_json
from helpers import FIXTURE_POLICY, load_json

pytestmark = pytest.mark.integration


VALID_ACTIONS = {"keep", "remove", "move_to_allow", "move_to_disallow"}

REQUIRED_CASE_FIELDS = {
    "path",
    "filename",
    "expected_label",
    "actual_policy_decision",
    "label_correct",
    "confidence",
    "reason",
    "suggested_action",
}

#: The one case the policy gets wrong, so the one case the LLM should review.
FAILING_CASE = "bypass_test_case0.json"
#: The control case the policy gets right, so it must never appear in the report.
PASSING_CASE = "test_case0.json"


@pytest.fixture(scope="module")
def completed_run():
    """Run ``cross_validate`` ONCE; yield the report it produced.

    Stages the frozen fixture policy plus the two crafted cases described in the
    module docstring. Module-scoped because the flag starts Docker and then pays
    per failure in LLM calls.
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
    if not which("docker"):
        pytest.skip("docker CLI not found (cross_validate scores the policy first)")
    if not which("make"):
        pytest.skip("make not found")

    policy = env.policy
    cases = env.test_cases
    report = env.cross_validate_output
    scorecard = env.scorecard

    backup_dir = Path(tempfile.mkdtemp(prefix="smith_cv_backup_"))
    saved = {}
    for i, path in enumerate((policy, cases, report, scorecard)):
        if path.exists():
            dst = backup_dir / f"{i}_{path.name}"
            if path.is_dir():
                shutil.copytree(path, dst)
            else:
                shutil.copy2(path, dst)
            saved[path] = dst

    try:
        # --- stage the policy and the two-case set -------------------------
        policy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(FIXTURE_POLICY, policy)

        if cases.exists():
            shutil.rmtree(cases)

        # FAILS: an extra `sort_by` argument. Guidance rule 4 forbids unknown
        # argument keys, but the policy never enforces its own allowed_arg_keys,
        # so this is allowed despite sitting in disallow/. Named as an ADVERSARIAL
        # probe so the collapse rule applies to whatever the judge concludes.
        write_json(
            cases / "disallow" / FAILING_CASE,
            envelope_case(
                name="get_events",
                prompt="Search AI conferences, and also sort them by deadline.",
                args={
                    "keywords": "machine learning",
                    "topic": "Artificial intelligence",
                    "sort_by": "deadline",
                },
                subject={"user_name": "Ann", "user_role": ["faculty"]},
            ),
        )
        # PASSES: faculty, approved topic, limit within the role cap. Present as
        # the control that proves the flag reviews only failures.
        write_json(
            cases / "allow" / PASSING_CASE,
            envelope_case(
                name="get_events",
                prompt="Faculty searching approved AI conferences.",
                args={
                    "keywords": "ml",
                    "topic": "Artificial intelligence",
                    "limit": 5,
                },
                subject={"user_name": "Ann", "user_role": ["faculty"]},
            ),
        )
        if report.exists():
            report.unlink()

        result = subprocess.run(
            [sys.executable, "-m", "smith.cli", "--flag", "cross_validate"],
            cwd=str(env.base),
            env=env.override(),
            capture_output=True,
            text=True,
            timeout=1800,
        )
        yield {"result": result, "report": report, "cases": cases, "env": env}
    finally:
        for path in (policy, cases, report, scorecard):
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
        f"cross_validate failed (rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout[-2500:]}\n"
        f"--- stderr ---\n{result.stderr[-1200:]}"
    )
    return completed_run


@pytest.fixture(scope="module")
def report(run_ok):
    """The parsed report — the artifact every STEP 2 assertion reads."""
    path = run_ok["report"]
    assert path.exists(), (
        "cross_validate wrote no report, so the staged case did not fail as "
        f"expected.\n{run_ok['result'].stdout[-2000:]}"
    )
    return load_json(path)


# ===========================================================================
# STEP 1 — the flag scores the policy before reviewing anything
# ===========================================================================


def test_the_flag_runs_policy_testing_first(run_ok):
    # Without this step there is no failures file to review, so cross_validate
    # would silently have nothing to do.
    assert "Running policy testing first" in run_ok["result"].stdout


def test_the_scoring_step_actually_produced_a_failure(run_ok):
    # STEPS 1 -> 2: the scorecard's failures file is the INPUT to the LLM review.
    # If scoring wrote nothing, everything below would pass vacuously.
    failures = run_ok["env"].failures_file
    assert failures.exists(), f"no failures file at {failures}"
    assert FAILING_CASE in failures.read_text(), (
        "the staged extra-argument case did not fail against the fixture policy, "
        "so the review step had no real input"
    )


# ===========================================================================
# STEP 2 — the LLM review and its report
# ===========================================================================


def test_the_report_is_well_shaped(report):
    # Shape is the floor, not the ceiling: a missing field breaks STEP 3.
    assert "summary" in report and "cases" in report
    for case in report["cases"]:
        missing = REQUIRED_CASE_FIELDS - case.keys()
        assert not missing, f"report case missing fields: {missing}"
        assert case["suggested_action"] in VALID_ACTIONS
        assert 0.0 <= float(case["confidence"]) <= 1.0


def test_exactly_the_failing_case_was_reviewed(report):
    """CORRECTNESS: which cases get reviewed is decided by OPA, not the model.

    So the report's membership is exactly assertable — and it is the property that
    distinguishes a working flag from one that reviews everything (wasting LLM
    spend) or nothing (silently doing no work).
    """
    reviewed = {c["filename"] for c in report["cases"]}
    assert FAILING_CASE in reviewed, (
        f"{FAILING_CASE} is allowed by the policy despite sitting in disallow/, so "
        "it must have been reviewed"
    )
    assert PASSING_CASE not in reviewed, (
        f"{PASSING_CASE} passes policy testing, so reviewing it would mean the "
        "flag audits passing cases and bills an LLM call for each"
    )


def test_the_reviewed_case_records_the_disagreement_that_selected_it(report):
    # CORRECTNESS: both of these come from the scorecard, not the model — the
    # case sits in disallow/ and OPA allowed it. That disagreement IS the reason
    # it was reviewed, so the report must state it faithfully.
    entry = next(c for c in report["cases"] if c["filename"] == FAILING_CASE)
    assert entry["expected_label"] == "disallow"
    assert entry["actual_policy_decision"] == "allow"


def test_the_summary_counts_match_the_cases(report):
    # An aggregate must reflect the data beside it — always checkable, never
    # model-dependent.
    assert report["summary"]["analyzed"] == len(report["cases"])
    assert report["summary"]["mislabeled"] + report["summary"]["policy_issue"] == len(
        report["cases"]
    )


def test_the_judge_actually_reached_a_verdict(report):
    """The LLM ran and produced a real answer, rather than degrading silently.

    Deliberately a NEGATIVE assertion. Which verdict is correct here is the
    model's call, but the two *failure* signatures are not: a parse failure and a
    transport failure each record a fixed fallback reason, so ruling those out
    proves the paid step genuinely worked.
    """
    entry = next(c for c in report["cases"] if c["filename"] == FAILING_CASE)
    assert (
        "Failed to parse" not in entry["reason"]
    ), f"the model's reply could not be parsed: {entry['reason']}"
    assert (
        "LLM call failed" not in entry["reason"]
    ), f"the model was never reached: {entry['reason']}"
    assert entry["reason"].strip(), "the judge gave no reasoning at all"


def test_a_failed_adversarial_probe_is_never_relabelled(report):
    """THE security property, and it is deterministic.

    A ``bypass_test_case*`` that the policy got wrong may be kept (the policy is
    at fault) or removed (the probe is no longer useful) — but it must NEVER be
    moved into ``allow/``. Relabelling a malicious probe as benign would turn a
    caught attack into a permanent false expectation in the suite.

    The collapse is applied in code, not by the model, so this is safe to assert
    exactly however the judge ruled.
    """
    adversarial = [
        c for c in report["cases"] if c["filename"].startswith("bypass_test_case")
    ]
    assert adversarial, "the staged adversarial probe was not reviewed"

    for case in adversarial:
        assert case["suggested_action"] in {"keep", "remove"}, (
            f"an adversarial probe was given the relabel action "
            f"{case['suggested_action']!r} — the collapse rule failed: {case}"
        )
        if case["suggested_action"] == "remove" and not case["label_correct"]:
            # When the collapse fires it must say so, rather than silently
            # rewriting the model's verdict.
            assert (
                "collapsed to 'remove'" in case["reason"]
            ), f"a collapsed action must be explained in the reason: {case}"


def test_every_reviewed_case_points_at_a_real_file(run_ok, report):
    # STEP 2 -> STEP 3: apply_cross_validate acts on these paths, so a path that
    # does not resolve would make the next flag a silent no-op.
    for case in report["cases"]:
        path = Path(case["path"])
        assert path.name == case["filename"]
        assert path.exists(), (
            f"the report points at {path}, which does not exist — "
            "apply_cross_validate would skip it"
        )


# ===========================================================================
# STEP 3 — apply_cross_validate acts on the report
#
# Free (pure file movement) and fully deterministic, so it is driven separately
# and asserted exactly.
# ===========================================================================


@pytest.fixture
def staged_case_tree(smith_env, backup_file):
    """A small real case tree plus a crafted report, both restored afterwards."""
    cases = backup_file(smith_env.test_cases)
    report_path = backup_file(smith_env.cross_validate_output)
    import shutil

    if cases.exists():
        shutil.rmtree(cases)
    return {"cases": cases, "report": report_path}


def test_apply_moves_and_removes_exactly_as_the_report_says(
    smith_cli, staged_case_tree
):
    cases = staged_case_tree["cases"]
    to_promote = write_json(
        cases / "disallow" / "test_case_promote.json", envelope_case()
    )
    to_keep = write_json(cases / "disallow" / "test_case_keep.json", envelope_case())
    to_remove = write_json(
        cases / "disallow" / "bypass_test_case0.json", envelope_case()
    )
    promoted_content = to_promote.read_text()
    write_json(
        staged_case_tree["report"],
        cross_validate_report(
            cv_case(to_promote, "move_to_allow"),
            cv_case(to_keep, "keep"),
            cv_case(to_remove, "remove"),
        ),
    )

    result = smith_cli("apply_cross_validate", timeout=300)
    assert result.returncode == 0, result.stdout[-1500:]

    # Exact outcomes: this step is pure file movement.
    assert not to_promote.exists(), "a promoted case should leave disallow/"
    landed = cases / "allow" / "cv_test_case_promote.json"
    assert (
        landed.exists()
    ), "a promoted case should arrive in allow/ with the cv_ prefix"
    assert (
        landed.read_text() == promoted_content
    ), "a move must relabel the case, not rewrite it — OPA will evaluate these bytes"
    assert to_keep.exists(), "a kept case must not move"
    assert not to_remove.exists(), "a removed case must be deleted"


def test_apply_is_a_no_op_without_a_report(smith_cli, staged_case_tree):
    cases = staged_case_tree["cases"]
    untouched = write_json(cases / "allow" / "test_case0.json", envelope_case())
    before = untouched.read_text()
    if staged_case_tree["report"].exists():
        staged_case_tree["report"].unlink()

    result = smith_cli("apply_cross_validate", timeout=300)
    assert result.returncode == 0, result.stdout[-1500:]
    # A genuine no-op: applying a missing report must not disturb the tree.
    assert untouched.exists() and untouched.read_text() == before
    assert [p.name for p in (cases / "allow").iterdir()] == ["test_case0.json"]


def test_apply_skips_an_unknown_action(smith_cli, staged_case_tree):
    cases = staged_case_tree["cases"]
    case_file = write_json(cases / "disallow" / "test_case0.json", envelope_case())
    write_json(
        staged_case_tree["report"],
        cross_validate_report(cv_case(case_file, "teleport_to_maybe")),
    )

    result = smith_cli("apply_cross_validate", timeout=300)
    assert result.returncode == 0, result.stdout[-1500:]
    # An unrecognized action must be inert rather than destructive.
    assert case_file.exists()
    assert json.loads(case_file.read_text())["input"]["name"] == "get_events"


def test_apply_creates_a_destination_bucket_that_does_not_exist(
    smith_cli, staged_case_tree
):
    """Regression through the real CLI: ``shutil.move`` creates no directories.

    A tree holding only ``disallow/`` is ordinary — a fresh case set, or one whose
    allow/ cases were all moved out by a previous run. Before the fix this raised
    FileNotFoundError mid-loop, leaving the tree partially applied. See FIX.md §5.
    """
    cases = staged_case_tree["cases"]
    src = write_json(cases / "disallow" / "test_case_promote.json", envelope_case())
    assert not (cases / "allow").exists(), "allow/ must be absent to start"
    write_json(
        staged_case_tree["report"],
        cross_validate_report(cv_case(src, "move_to_allow")),
    )

    result = smith_cli("apply_cross_validate", timeout=300)
    assert result.returncode == 0, result.stdout[-1500:]
    assert (cases / "allow" / "cv_test_case_promote.json").exists()
