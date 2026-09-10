# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``smith --flag save_snapshot``.

STEPS COVERED (all from the single run)
--------------------------------------
STEP 1  the flag resolves every artifact path from ``.env``
        (``POLICY_DIR`` + ``POLICY_PATH``, ``GUIDANCE_FILE``,
        ``TARGET_AGENT_PATH``, ``PROMPTFOO_CONFIG_FILE``, ``TEST_CASE_PATH``)
STEP 2  it copies what exists into a flat destination under the canonical names,
        with the test cases nested under ``test_cases/{allow,disallow}/``
STEP 3  the sources are left untouched — a snapshot copies, never moves
CLI     the ``--dest`` requirement, and the best-effort skip for a missing source

COST: THE FLAG IS RUN ONCE
--------------------------
Every assertion inspects one run's artifacts, from a module-scoped fixture. File
copying is cheap, but the rule is the same one the other integration files follow:
drive the **flag** once and read what it produced. The two CLI-contract tests at
the bottom invoke it separately because they need *different arguments*.

ASSERTING CORRECTNESS
---------------------
This flag is pure file copying — fully deterministic — so per the guide its output
is asserted **exactly**: byte-for-byte equality with each source, not merely that
a file of the right name exists. A name-only check would pass on an empty or
truncated copy, and matching case *counts* would pass on the right number of the
wrong cases.

No LLM, no OPA. The destination is always under ``tmp_path``, so nothing in the
checkout is written.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


# The canonical flat names the snapshot writes. This IS the contract an archived
# snapshot is read back by, so an unexpected name is a failure.
CANONICAL_NAMES = {
    "policy.rego",
    "policy_cpex.rego",
    "guidance.txt",
    "tool_definitions.json",
}


@pytest.fixture(scope="module")
def completed_run(tmp_path_factory):
    """Run the flag ONCE for this module; yield the snapshot it produced."""
    import subprocess
    import sys

    from helpers import SmithEnv

    env = SmithEnv()
    dest = tmp_path_factory.mktemp("snapshot") / "snap"

    result = subprocess.run(
        [sys.executable, "-m", "smith.cli", "--flag", "save_snapshot", "--dest", str(dest)],
        cwd=str(env.base),
        env=env.override(),
        capture_output=True,
        text=True,
        timeout=300,
    )
    return {"result": result, "dest": dest, "env": env}


@pytest.fixture(scope="module")
def run_ok(completed_run):
    """The run must have succeeded before any artifact assertion is meaningful."""
    result = completed_run["result"]
    assert result.returncode == 0, (
        f"save_snapshot failed (rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout[-2000:]}\n"
        f"--- stderr ---\n{result.stderr[-1000:]}"
    )
    return completed_run


# ===========================================================================
# STEPS 1 + 2 — path resolution and the copies
# ===========================================================================


def test_the_snapshot_directory_is_created(run_ok):
    assert run_ok["dest"].is_dir()


def test_only_canonical_names_are_written(run_ok):
    # Anything else means the flag renamed an artifact wrongly, or copied
    # something it should not have.
    copied = {p.name for p in run_ok["dest"].iterdir() if p.is_file()}
    unexpected = {
        n for n in copied - CANONICAL_NAMES if not n.endswith((".yaml", ".yml"))
    }
    assert not unexpected, f"unexpected files in the snapshot: {unexpected}"


def test_each_copied_artifact_matches_its_source_byte_for_byte(run_ok):
    # Deterministic flag -> assert the bytes. A name-only check would pass on an
    # empty or truncated copy.
    env = run_ok["env"]
    expected = {
        "policy.rego": env.policy,
        "guidance.txt": env.guidance_file,
    }

    asserted = 0
    for name, source in expected.items():
        if not source.exists():
            continue  # not present in this checkout; the flag skips it
        asserted += 1
        target = run_ok["dest"] / name
        assert target.exists(), (
            f"{name} was not copied\n{run_ok['result'].stdout[-1500:]}"
        )
        assert target.read_text() == source.read_text(), (
            f"{name} differs from its source — the snapshot altered it"
        )

    assert asserted, (
        "no configured artifact was found in this checkout, so this test asserted "
        "nothing; check .env points at real files"
    )


def test_test_cases_are_copied_into_their_buckets_unaltered(run_ok):
    env = run_ok["env"]
    if not env.test_cases.exists():
        pytest.skip("no references/test_cases/ in this checkout to snapshot")

    checked_a_bucket = False
    for label in ("allow", "disallow"):
        source_bucket = env.test_cases / label
        if not source_bucket.is_dir():
            continue
        checked_a_bucket = True
        snapped = run_ok["dest"] / "test_cases" / label
        assert snapped.is_dir(), f"{label}/ bucket missing from the snapshot"

        # Contents, not counts: matching counts would pass on the right number of
        # the wrong cases, or on every case truncated to nothing.
        source_files = {p.name: p.read_text() for p in source_bucket.glob("*.json")}
        snapped_files = {p.name: p.read_text() for p in snapped.glob("*.json")}
        assert snapped_files.keys() == source_files.keys(), (
            f"{label}/ filenames differ: "
            f"missing={sorted(source_files.keys() - snapped_files.keys())} "
            f"extra={sorted(snapped_files.keys() - source_files.keys())}"
        )
        assert snapped_files == source_files, (
            f"{label}/ case contents were altered by the snapshot"
        )

    assert checked_a_bucket, "test_cases/ exists but has no allow/ or disallow/ bucket"


# ===========================================================================
# STEP 3 — the sources survive
# ===========================================================================


def test_the_snapshot_does_not_modify_its_sources(run_ok):
    env = run_ok["env"]

    checked = 0
    for name, source in (("policy.rego", env.policy), ("guidance.txt", env.guidance_file)):
        copy = run_ok["dest"] / name
        if not source.exists() or not copy.exists():
            continue
        checked += 1
        assert source.read_text() == copy.read_text(), (
            f"{source.name} no longer matches the snapshot taken from it, so the "
            "flag modified its source"
        )
    assert checked, "no source/copy pair was available to compare"


# ===========================================================================
# CLI — the argument contract
#
# These invoke the CLI separately because they exercise ARGUMENT handling, which
# needs different arguments by definition. Both are fast: neither copies a tree.
# ===========================================================================


def test_the_flag_requires_a_destination(smith_cli):
    # Fails on argument validation before touching any path.
    result = smith_cli("save_snapshot", timeout=120)
    assert result.returncode == 1
    assert "requires --dest" in (result.stdout + result.stderr)


def test_a_missing_artifact_is_skipped_rather_than_failing(smith_cli, unit_env):
    dest = unit_env.root / "snap"
    result = smith_cli(
        "save_snapshot",
        "--dest",
        str(dest),
        GUIDANCE_FILE="references/__definitely_absent__.txt",
        timeout=180,
    )
    assert result.returncode == 0, result.stdout[-1500:]
    assert "[skip]" in result.stdout, "a missing source should be reported as skipped"
    assert not (dest / "guidance.txt").exists()
    # The one missing input does not prevent the rest of the snapshot.
    assert dest.is_dir()
