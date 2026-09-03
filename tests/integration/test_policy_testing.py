# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration test for ``smith --flag policy_testing`` — the deterministic anchor.

Stages the frozen fixture policy + test cases into the real locations, runs the
real CLI (which starts OPA in Docker via ``make test`` and scores every case),
and asserts the exact scorecard the frozen inputs must produce — confusion
counts, per-experiment totals, coverage, and policy line count. Because both
the policy and the cases are frozen, every one of these numbers is deterministic
(see ``EXPECTED`` in helpers.py).

The session backup fixture restores the developer's real policy/test_cases
afterwards. Requires Docker + make (no LLM, no target agent).
"""

from __future__ import annotations

import shutil

import pytest

from helpers import (
    EXPECTED,
    FIXTURE_POLICY,
    SCORECARD,
    SCORECARD_SUMMARY,
    count_lines,
    parse_scorecard_summary,
    run_smith,
)

pytestmark = pytest.mark.integration


def test_policy_testing_exact_scorecard(
    stage, requires_docker, requires_make, backup_file
):
    # Arrange: install the frozen policy + the frozen test-case set.
    stage.stage_policy()
    counts = stage.stage_test_cases()
    assert counts == {
        "allow": EXPECTED["allow_total"],
        "disallow": EXPECTED["disallow_total"],
    }

    # The harness writes the whole scorecard dir (score_card.sh) and the session
    # backup does not cover it, so register it: without this, running the suite
    # destroys the developer's real scorecard from their last policy_testing run.
    backup_file(SCORECARD)
    # Remove it outright so the assertions below cannot possibly read STALE files
    # from a previous run. This matters because run_policy_evaluation.py catches
    # CalledProcessError from `make test` and still reads the summary, so the CLI
    # exits 0 even when scoring failed — leaving old numbers to assert against.
    if SCORECARD.exists():
        shutil.rmtree(SCORECARD)

    # Act: run the real CLI stage (starts OPA in Docker, scores all cases).
    result = run_smith("policy_testing", timeout=600)
    assert result.returncode == 0, f"policy_testing failed:\n{result.stderr}"

    # The scorecard must have been (re)created by THIS run — guards against the
    # swallowed `make test` failure described above.
    assert SCORECARD.is_dir(), (
        "policy_testing exited 0 but wrote no scorecard directory — `make test` "
        f"likely failed and the error was swallowed.\n{result.stdout[-1500:]}"
    )

    # Assert: exact confusion counts for the frozen inputs. The directory comes
    # from TEST_OUTPUT_DIR via helpers.SCORECARD; these five filenames are
    # hardcoded in src/smith/policy_testing/score_card.sh:48 (no env var), so they
    # stay literal here to match.
    tp = count_lines(SCORECARD / "tp.txt")
    fp = count_lines(SCORECARD / "fp.txt")
    tn = count_lines(SCORECARD / "tn.txt")
    fn = count_lines(SCORECARD / "fn.txt")
    assert (tn, fp, tp, fn) == (
        EXPECTED["tn"],
        EXPECTED["fp"],
        EXPECTED["tp"],
        EXPECTED["fn"],
    ), f"confusion mismatch: got tn={tn} fp={fp} tp={tp} fn={fn}"

    # And no OPA request errors (all cases were actually scored).
    assert count_lines(SCORECARD / "errors.txt") == 0

    # Assert the SUMMARY's own numbers, not just the tp/fp/tn/fn files.
    summary_text = SCORECARD_SUMMARY.read_text()
    assert "Scorecard Summary" in summary_text
    parsed = parse_scorecard_summary(summary_text)

    by_dir = {
        e["directory"].rstrip("/").split("/")[-1]: e for e in parsed["experiments"]
    }
    assert set(by_dir) == {"allow", "disallow"}, parsed["experiments"]

    # allow experiment: Allowed=tn, Denied=fp, Total=allow_total.
    assert by_dir["allow"]["allowed"] == EXPECTED["tn"]
    assert by_dir["allow"]["denied"] == EXPECTED["fp"]
    assert by_dir["allow"]["total"] == EXPECTED["allow_total"]

    # disallow experiment: Allowed=fn, Denied=tp, Total=disallow_total.
    assert by_dir["disallow"]["allowed"] == EXPECTED["fn"]
    assert by_dir["disallow"]["denied"] == EXPECTED["tp"]
    assert by_dir["disallow"]["total"] == EXPECTED["disallow_total"]

    # Summary must agree with the tp/fp/tn/fn file partition.
    assert by_dir["allow"]["allowed"] == tn
    assert by_dir["allow"]["denied"] == fp
    assert by_dir["disallow"]["denied"] == tp
    assert by_dir["disallow"]["allowed"] == fn

    # Coverage: exact values the frozen policy + suite produce.
    assert parsed["coverage"] == pytest.approx(EXPECTED["coverage"])
    assert parsed["covered_lines"] == EXPECTED["covered_lines"]
    assert parsed["not_covered_lines"] == EXPECTED["not_covered_lines"]

    # Policy line count: the summary reports `wc -l` (newline count); it must
    # match both the recorded expectation and the fixture file itself.
    assert parsed["policy_lines"] == EXPECTED["policy_lines"]
    assert parsed["policy_lines"] == FIXTURE_POLICY.read_text().count("\n")
