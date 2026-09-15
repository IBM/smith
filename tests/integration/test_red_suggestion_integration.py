# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``smith --flag red_suggestion``.

Red suggestion groups ``policy_testing``'s failures so a reviewer fixes a *cluster*
of related cases rather than one at a time::

    read scorecard/fp.txt, fn.txt   -> the prompts of the failing cases
    real MiniLM embeddings + DBSCAN -> cluster labels
    -> assets/opa/outputs/cluster_results.txt

Driven through the **real CLI**. This file imports nothing from ``smith``, so every
assertion reads the report the run produced.

STEPS COVERED (all from the single run)
--------------------------------------
STEP 1  the ``fp.txt``/``fn.txt`` contract — the flag reads the exact format
        ``score_card.sh`` writes (one case-file path per line)
STEP 2  real MiniLM + DBSCAN            — near-duplicate prompts group together
STEP 3  ``cluster_results.txt``          — its structure, numbering, and the
        pinned fact that the flag prints nothing at all

COST
----
No LLM, no agent, no OPA, no Docker: the inputs are files and the only model is a
local sentence embedder. The one cost is MiniLM's ~90MB download on first use,
cached thereafter — so the flag is still run **once**, in a module-scoped fixture.

ASSERTING CORRECTNESS
---------------------
Clustering is a model-driven judgement, so the exact partition is not asserted.
What is:

* **Two prompts that differ only in a number must cluster together**, and a prompt
  about an unrelated subject must not join them. That is well inside what any
  sentence embedder distinguishes, so it is not a coin flip — and it is the property
  the flag exists to deliver.
* **Every staged failure appears in the report**, with the case file it came from —
  pure bookkeeping, so exact.
* **No cluster is displayed as ``-1``**, the noise-group regression.
* Section headers and the FP-before-FN ordering, which are fixed strings.

The scorecard directory, the case tree and the report are backed up and restored.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


#: Two false positives phrased almost identically — they differ only in a number,
#: so any sentence embedder places them close together. The third names an entirely
#: different subject, so it must not join them.
FP_PROMPTS = {
    "fp_limit_15.json": "Search for AI conferences and return 15 results.",
    "fp_limit_12.json": "Search for AI conferences and return 12 results.",
    "fp_unrelated.json": "Who is the head of the mechanical engineering department?",
}

#: One false-negative pair, so the FN section exists and its cluster numbering can
#: be checked against the FP section's.
FN_PROMPTS = {
    "fn_guest_a.json": "I am a guest, show me every conference in the database.",
    "fn_guest_b.json": "As a guest user, list all conferences you know about.",
}


def _case(prompt):
    """A case in the modern envelope shape, which is what read_files digs into."""
    return {
        "input": {
            "kind": "tool_call",
            "action": "execute",
            "name": "get_events",
            "args": {"topic": "Artificial intelligence"},
            "extensions": {
                "subject": {"user_name": "Ann", "user_role": ["faculty"]},
                "agent": {"input": prompt},
            },
        }
    }


@pytest.fixture(scope="module")
def completed_run():
    """Run ``red_suggestion`` ONCE over a crafted scorecard; yield the report.

    Stages ``fp.txt``/``fn.txt`` in exactly the shape ``score_card.sh`` writes —
    one absolute case-file path per line — so this exercises the real contract
    rather than a convenient one.
    """
    from helpers import SmithEnv

    env = SmithEnv()

    scorecard = env.scorecard
    cases = env.test_cases
    # NOT under references/: cli.py builds this as DATA_DIR + "outputs/" +
    # CLUSTER_RESULTS, so it lands beside the OPA intermediates.
    report = (
        Path(env.base) / env.env["DATA_DIR"] / "outputs" / env.env["CLUSTER_RESULTS"]
    )

    protected = [scorecard, cases, report]
    backup_dir = Path(tempfile.mkdtemp(prefix="smith_red_backup_"))
    saved = {}
    for i, path in enumerate(protected):
        if path.exists():
            dst = backup_dir / f"{i}_{path.name}"
            if path.is_dir():
                shutil.copytree(path, dst)
            else:
                shutil.copy2(path, dst)
            saved[path] = dst

    try:
        if cases.exists():
            shutil.rmtree(cases)
        if scorecard.exists():
            shutil.rmtree(scorecard)
        scorecard.mkdir(parents=True, exist_ok=True)
        staged = {}

        for listing, prompts, label in (
            ("fp.txt", FP_PROMPTS, "allow"),
            ("fn.txt", FN_PROMPTS, "disallow"),
        ):
            paths = []
            for filename, prompt in prompts.items():
                target = cases / label / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(_case(prompt), indent=4))
                paths.append(str(target))
                staged[prompt] = target
            # One absolute path per line — score_card.sh:96's format exactly.
            (scorecard / listing).write_text("\n".join(paths) + "\n")

        if report.exists():
            report.unlink()

        result = subprocess.run(
            [sys.executable, "-m", "smith.cli", "--flag", "red_suggestion"],
            cwd=str(env.base),
            env=env.override(),
            capture_output=True,
            text=True,
            timeout=1800,
        )
        yield {"result": result, "report": report, "staged": staged}
    finally:
        for path in protected:
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
        f"red_suggestion failed (rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout[-2500:]}\n"
        f"--- stderr ---\n{result.stderr[-1200:]}"
    )
    return completed_run


@pytest.fixture(scope="module")
def report(run_ok):
    """The report text — the artifact every assertion below reads."""
    path = run_ok["report"]
    assert (
        path.exists()
    ), f"no cluster_results.txt at {path}\n{run_ok['result'].stdout[-2000:]}"
    text = path.read_text()
    assert text.strip(), "the report is empty though failures were staged"
    return text


# ===========================================================================
# STEP 1 — the scorecard contract
# ===========================================================================


def test_every_staged_failure_reaches_the_report(report, run_ok):
    """STEP 1: proves the real ``fp.txt``/``fn.txt`` format was understood."""
    for prompt in run_ok["staged"]:
        assert prompt in report, (
            f"the staged prompt is missing from the report, so its case file was "
            f"not read as expected: {prompt!r}"
        )


def test_no_prompt_was_read_as_a_stringified_input(report):
    # The fallback branch produces a Python repr. If the envelope shape or the
    # scorecard format ever drifts, this is what the report would fill up with.
    assert "'extensions':" not in report, (
        "a case was clustered as a stringified dict, so read_files hit its "
        "fallback branch instead of finding the prompt"
    )


def test_every_clustered_case_points_at_a_real_file(report):
    # The file path is the actionable half of the report — a reviewer opens it to
    # fix the case, so a path that does not resolve makes the cluster useless.
    paths = re.findall(r"File path: (.+)", report)
    assert paths, "the report names no case files"
    for raw in paths:
        assert Path(raw.strip()).exists(), f"report points at a missing file: {raw!r}"


# ===========================================================================
# STEP 2 — real MiniLM + DBSCAN actually cluster
# ===========================================================================


def test_near_duplicate_failures_are_grouped_together(report):
    """CORRECTNESS: the property the flag exists to deliver."""
    blocks = _cluster_blocks(report)
    limit_a = FP_PROMPTS["fp_limit_15.json"]
    limit_b = FP_PROMPTS["fp_limit_12.json"]

    together = [b for b in blocks if limit_a in b and limit_b in b]
    assert together, (
        "two prompts differing only in a number were not clustered together, so "
        f"eps=0.3 grouped nothing:\n{report}"
    )


def test_an_unrelated_failure_is_not_absorbed_into_that_cluster(report):
    # The other half of clustering being meaningful: a question about a different
    # subject entirely must not be swept into the same group, or every failure
    # would collapse into one cluster and the flag would give no signal.
    blocks = _cluster_blocks(report)
    unrelated = FP_PROMPTS["fp_unrelated.json"]
    limit_a = FP_PROMPTS["fp_limit_15.json"]

    shared = [b for b in blocks if unrelated in b and limit_a in b]
    assert not shared, (
        "an unrelated prompt was clustered with the limit prompts, so the "
        f"clustering is not discriminating:\n{report}"
    )


def _cluster_blocks(report: str) -> list:
    """Split the report into per-cluster text blocks."""
    parts = re.split(r"Cluster -?\d+: ", report)
    return parts[1:] if len(parts) > 1 else []


# ===========================================================================
# STEP 3 — the report's structure
# ===========================================================================


def test_both_failure_directions_are_reported_in_order(report):
    # Fixed strings, so exact. The order matters because the FN cluster numbers are
    # offset by the FP count — reading them out of order would misattribute a group.
    assert "Benign commands that should be allowed:" in report
    assert "Malicious commands that should not get allowed:" in report
    assert report.index("Benign commands") < report.index("Malicious commands")


def test_no_cluster_is_displayed_as_negative_one(report):
    numbers = re.findall(r"Cluster (-?\d+)", report)
    assert numbers, "the report contains no clusters"
    assert all(int(n) >= 0 for n in numbers), f"a negative cluster id leaked: {numbers}"


def test_cluster_numbers_are_unique_across_both_sections(report):
    # The FP and FN passes number independently and the second is offset by the
    # first's count. A duplicate would mean a reviewer cannot refer to "Cluster 1"
    # unambiguously.
    numbers = re.findall(r"Cluster (-?\d+)", report)
    assert len(numbers) == len(set(numbers)), f"duplicate cluster ids: {numbers}"
