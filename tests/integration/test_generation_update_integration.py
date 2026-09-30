# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``smith --flag test_generation --mode update``.

Fresh generation rebuilds the whole suite. Update mode regenerates only the
guidance that changed since the last run::

    guidance_raw_snapshot.txt  ->  what the user edited, computed in Python
                               ->  handed to flatten as instructions
    guidance_snapshot.txt      ->  diffed against the new flattened text
    guidance_case_map.json     ->  the cases belonging to guidance that changed

WHY A SEPARATE FILE FROM ``test_generation_integration.py``
----------------------------------------------------------
That module is built around a single module-scoped fresh run, because the flag is
the most expensive in the suite. Update mode needs a *second* run after an edit,
so it lives here rather than doubling that module's bill.

THE CHEAP TESTS COME FIRST
--------------------------
Four CLI-contract tests need **no LLM and no services** — they exercise argument
validation and the no-snapshot guard, which return before any model is built. They
run anywhere, including a bare checkout.

The two-run test does need an LLM. It runs the flag twice (fresh, then update after
a one-line edit) and asserts the property the whole feature exists for: **the cases
belonging to untouched guidance are not rewritten**, compared byte for byte.

THE DRIFT CHECK
---------------
``test_the_map_and_the_flattened_guidance_agree`` is the only automated check on
the one thing that cannot be guaranteed by construction: flatten is an LLM stage,
so re-flattening untouched guidance *could* reword a line. If it did, that line
would no longer match its mapping key, and its cases would be deleted and
regenerated for no reason. A mismatch here is that drift, made visible.

Requires an LLM and the MCP server's ``python`` for the two-run test only.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from helpers import SmithEnv, which

pytestmark = pytest.mark.integration


#: Three rules so an edit can leave two untouched. Deliberately small: the
#: per-rule LLM calls scale with this file, and it is generated twice here.
GUIDANCE_BEFORE = (
    "1. Faculty may use the get_events tool to search for academic conferences.\n"
    "2. A guest must never be allowed to call the get_events tool.\n"
    "3. A phd_student may set the limit parameter up to 10 per request.\n"
)

#: Rule 3 edited, rules 1 and 2 identical. Only rule 3's cases may change.
GUIDANCE_AFTER = (
    "1. Faculty may use the get_events tool to search for academic conferences.\n"
    "2. A guest must never be allowed to call the get_events tool.\n"
    "3. A phd_student may set the limit parameter up to 4 per request.\n"
)


def run_flag(env, *extra_args, guidance_name, **overrides):
    """Invoke the CLI in-process-free, returning the CompletedProcess."""
    return subprocess.run(
        [sys.executable, "-m", "smith.cli", "--flag", "test_generation", *extra_args],
        cwd=str(env.base),
        env=env.override(
            GUIDANCE_FILE=f"references/{guidance_name}",
            ATTACK_TOOLS="none",
            **overrides,
        ),
        capture_output=True,
        text=True,
        timeout=3600,
    )


# ===========================================================================
# CLI contract — no LLM, no services
# ===========================================================================


def test_an_unknown_mode_is_rejected_by_argparse():
    env = SmithEnv()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "smith.cli",
            "--flag",
            "test_generation",
            "--mode",
            "bogus",
        ],
        cwd=str(env.base),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_mode_is_rejected_on_a_flag_that_has_no_modes():
    """``--mode`` silently ignored elsewhere would be a trap, so it is an error."""
    env = SmithEnv()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "smith.cli",
            "--flag",
            "policy_testing",
            "--mode",
            "update",
        ],
        cwd=str(env.base),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "--mode only applies" in result.stdout


def test_update_without_a_snapshot_stops_with_an_actionable_message(tmp_path):
    """The first-ever run cannot be an update: there is nothing to diff against."""
    env = SmithEnv()
    guidance = Path(env.base) / "references" / "__update_nosnap__.txt"
    guidance.parent.mkdir(parents=True, exist_ok=True)
    guidance.write_text(GUIDANCE_BEFORE)
    try:
        result = run_flag(
            env,
            "--mode",
            "update",
            guidance_name=guidance.name,
            GUIDANCE_SNAPSHOT_FILE="references/__absent_snapshot__.txt",
            GUIDANCE_RAW_SNAPSHOT_FILE="references/__absent_raw_snapshot__.txt",
        )
    finally:
        guidance.unlink(missing_ok=True)

    assert result.returncode == 0, result.stderr[-1500:]
    assert "--mode fresh" in result.stdout


def test_update_without_a_snapshot_changes_nothing_on_disk():
    """Refusing to run must not be destructive."""
    env = SmithEnv()
    cases = env.test_cases
    before = sorted(p.name for p in cases.rglob("*.json")) if cases.exists() else []

    guidance = Path(env.base) / "references" / "__update_nosnap2__.txt"
    guidance.parent.mkdir(parents=True, exist_ok=True)
    guidance.write_text(GUIDANCE_BEFORE)
    try:
        run_flag(
            env,
            "--mode",
            "update",
            guidance_name=guidance.name,
            GUIDANCE_SNAPSHOT_FILE="references/__absent_snapshot2__.txt",
            GUIDANCE_RAW_SNAPSHOT_FILE="references/__absent_raw_snapshot2__.txt",
        )
    finally:
        guidance.unlink(missing_ok=True)

    after = sorted(p.name for p in cases.rglob("*.json")) if cases.exists() else []
    assert after == before


# ===========================================================================
# The two-run cycle — needs an LLM
# ===========================================================================


@pytest.fixture(scope="module")
def update_cycle():
    """Run the flag twice: fresh, then update after editing one rule.

    Yields the state captured between the two runs alongside the second result, so
    every assertion below inspects one pair of runs.
    """
    env = SmithEnv()
    missing = env.missing("OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL_SONNET")
    if missing:
        pytest.skip(f"Smith LLM not configured (missing {', '.join(missing)})")
    if not which("python"):
        pytest.skip("python not on PATH (the MCP server is spawned over stdio)")

    artifacts = env.generation_artifacts
    cases = env.test_cases
    guidance = Path(env.base) / "references" / "__update_guidance__.txt"

    protected = [*artifacts.values(), cases, guidance]
    backup_dir = Path(tempfile.mkdtemp(prefix="smith_update_backup_"))
    saved = {}
    for index, path in enumerate(protected):
        if path.exists():
            destination = backup_dir / f"{index}_{path.name}"
            if path.is_dir():
                shutil.copytree(path, destination)
            else:
                shutil.copy2(path, destination)
            saved[path] = destination

    try:
        guidance.parent.mkdir(parents=True, exist_ok=True)
        guidance.write_text(GUIDANCE_BEFORE)
        for path in (*artifacts.values(), cases):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()

        fresh = run_flag(env, "--mode", "fresh", guidance_name=guidance.name)
        assert fresh.returncode == 0, (
            f"the fresh run failed (rc={fresh.returncode}).\n"
            f"--- stdout ---\n{fresh.stdout[-3000:]}\n"
            f"--- stderr ---\n{fresh.stderr[-1500:]}"
        )

        # Snapshot the state between runs: filenames, bytes, and the map.
        before_bytes = {
            str(path.relative_to(cases)): path.read_bytes()
            for path in sorted(cases.rglob("*.json"))
        }
        before_map = json.loads(env.guidance_map.read_text())

        guidance.write_text(GUIDANCE_AFTER)
        update = run_flag(env, "--mode", "update", guidance_name=guidance.name)

        yield {
            "env": env,
            "cases": cases,
            "update": update,
            "before_bytes": before_bytes,
            "before_map": before_map,
        }
    finally:
        for path in protected:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()
            if path in saved:
                source = saved[path]
                if source.is_dir():
                    shutil.copytree(source, path)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, path)
        shutil.rmtree(backup_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def update_ok(update_cycle):
    """The update run must have succeeded before its artifacts mean anything."""
    result = update_cycle["update"]
    assert result.returncode == 0, (
        f"the update run failed (rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout[-3000:]}\n"
        f"--- stderr ---\n{result.stderr[-1500:]}"
    )
    return update_cycle


def test_the_update_run_reported_a_diff(update_ok):
    assert "Guidance diff vs snapshot" in update_ok["update"].stdout


def test_only_the_edited_rule_was_regenerated(update_ok):
    """One rule changed, so the diff must not claim all three did."""
    stdout = update_ok["update"].stdout
    marker = "Guidance diff vs snapshot:"
    line = next(row for row in stdout.splitlines() if marker in row)
    # e.g. "+1 added/changed, -1 removed/changed, 2 unchanged"
    assert "2 unchanged" in line, line


def test_the_untouched_rules_kept_their_case_files_byte_for_byte(update_ok):
    """The contract the whole feature exists for.

    Scoped to the rules that did *not* change: the edited rule's cases are deleted
    and regenerated by design, so only the survivors' bytes are asserted. Which
    files belong to whom comes from the map the fresh run wrote.
    """
    cases = update_ok["cases"]
    before = update_ok["before_bytes"]
    before_map = update_ok["before_map"]

    # The edited rule is the one absent from the post-update map's keys.
    from smith.test_generation.guidance_map import load_mapping

    after_map = load_mapping(str(update_ok["env"].guidance_map))
    survivors = {
        path
        for rule, paths in before_map.items()
        if rule in after_map
        for path in paths
    }
    assert survivors, "the fresh run mapped no cases, so there is nothing to compare"

    rewritten = [
        relative
        for relative in sorted(survivors)
        if (cases / relative).exists()
        and (cases / relative).read_bytes() != before[relative]
    ]
    assert not rewritten, f"untouched rules' cases were rewritten: {rewritten}"


def test_the_edited_rule_got_fresh_cases(update_ok):
    """The edited rule must end up with cases again, and they must be its own."""
    before_map = update_ok["before_map"]

    from smith.test_generation.guidance_map import load_mapping

    after_map = load_mapping(str(update_ok["env"].guidance_map))
    new_rules = [rule for rule in after_map if rule not in before_map]

    assert new_rules, "the edited rule produced no mapped cases"
    assert all(after_map[rule] for rule in new_rules), new_rules


def test_the_map_and_the_flattened_guidance_agree(update_ok):
    """The flatten-drift detector.

    Every mapping key must exist verbatim in the flattened guidance. A key that
    does not is a line the model reworded while claiming to leave it alone -- which
    silently costs that rule its test cases on the next run.
    """
    from smith.test_generation.guidance_map import load_mapping, read_lines

    env = update_ok["env"]
    mapping = load_mapping(str(env.guidance_map))
    flattened = set(read_lines(env.path("FLATTEN_FILE").read_text()))

    orphans = [key for key in mapping if key not in flattened]
    assert not orphans, f"mapping keys absent from the flattened guidance: {orphans}"


def test_both_snapshots_were_advanced(update_ok):
    """A stale snapshot would make the next run redo this run's work."""
    env = update_ok["env"]
    assert env.guidance_snapshot.exists()
    assert env.guidance_raw_snapshot.read_text() == GUIDANCE_AFTER


# ===========================================================================
# Deletion-only, addition-only, heading-swap and plain-reorder diffs
# — needs an LLM
# ===========================================================================

#: Two rules, so removing/adding the second is a pure deletion/addition with
#: nothing edited alongside it.
GUIDANCE_TWO_RULES = (
    "1. Faculty may use the get_events tool to search for academic conferences.\n"
    "2. A guest must never be allowed to call the get_events tool.\n"
)

GUIDANCE_ONE_RULE = (
    "1. Faculty may use the get_events tool to search for academic conferences.\n"
)

GUIDANCE_HEADING_SWAP_BEFORE = (
    "## Allowed commands\n"
    "- The agent may call `list_files`.\n"
    "- The agent may call `read_file` when the requester is `faculty`.\n"
    "\n"
    "## Disallowed commands\n"
    "- The agent must not call `delete_file` under any circumstances.\n"
)

GUIDANCE_HEADING_SWAP_AFTER = (
    "## Disallowed commands\n"
    "- The agent may call `list_files`.\n"
    "- The agent may call `read_file` when the requester is `faculty`.\n"
    "\n"
    "## Allowed commands\n"
    "- The agent must not call `delete_file` under any circumstances.\n"
)

GUIDANCE_REORDER_BEFORE = (
    "- The agent may call `list_files`.\n" "- The agent may call `search_files`.\n"
)

GUIDANCE_REORDER_AFTER = (
    "- The agent may call `search_files`.\n" "- The agent may call `list_files`.\n"
)


def _run_two_stage_cycle(before_text, after_text, tag):
    env = SmithEnv()
    missing = env.missing("OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL_SONNET")
    if missing:
        pytest.skip(f"Smith LLM not configured (missing {', '.join(missing)})")
    if not which("python"):
        pytest.skip("python not on PATH (the MCP server is spawned over stdio)")

    artifacts = env.generation_artifacts
    cases = env.test_cases
    guidance = Path(env.base) / "references" / f"__update_guidance_{tag}__.txt"

    protected = [*artifacts.values(), cases, guidance]
    backup_dir = Path(tempfile.mkdtemp(prefix=f"smith_update_backup_{tag}_"))
    saved = {}
    for index, path in enumerate(protected):
        if path.exists():
            destination = backup_dir / f"{index}_{path.name}"
            if path.is_dir():
                shutil.copytree(path, destination)
            else:
                shutil.copy2(path, destination)
            saved[path] = destination

    try:
        guidance.parent.mkdir(parents=True, exist_ok=True)
        guidance.write_text(before_text)
        for path in (*artifacts.values(), cases):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()

        fresh = run_flag(env, "--mode", "fresh", guidance_name=guidance.name)
        assert fresh.returncode == 0, (
            f"the fresh run failed (rc={fresh.returncode}).\n"
            f"--- stdout ---\n{fresh.stdout[-3000:]}\n"
            f"--- stderr ---\n{fresh.stderr[-1500:]}"
        )

        guidance.write_text(after_text)
        update = run_flag(env, "--mode", "update", guidance_name=guidance.name)
        return env, update
    finally:
        for path in protected:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()
            if path in saved:
                source = saved[path]
                if source.is_dir():
                    shutil.copytree(source, path)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, path)
        shutil.rmtree(backup_dir, ignore_errors=True)


def test_a_deletion_only_run_reports_the_removed_line_with_no_regeneration():
    """Rule 2 removed, nothing added: the raw diff carries a line number for the
    removal, and the run stops without calling the model for new cases."""
    env, update = _run_two_stage_cycle(
        GUIDANCE_TWO_RULES, GUIDANCE_ONE_RULE, "delete"
    )
    assert update.returncode == 0, (
        f"the update run failed (rc={update.returncode}).\n"
        f"--- stdout ---\n{update.stdout[-3000:]}\n"
        f"--- stderr ---\n{update.stderr[-1500:]}"
    )
    assert "Only removals in this diff; no new guidance to generate." in update.stdout
    assert "[Line 2]" in update.stdout


def test_an_addition_only_run_reports_the_added_line_with_a_line_number():
    """Rule 2 added, nothing removed: the raw diff carries a line number for the
    addition, and the added rule ends up mapped to fresh cases."""
    env, update = _run_two_stage_cycle(GUIDANCE_ONE_RULE, GUIDANCE_TWO_RULES, "add")
    assert update.returncode == 0, (
        f"the update run failed (rc={update.returncode}).\n"
        f"--- stdout ---\n{update.stdout[-3000:]}\n"
        f"--- stderr ---\n{update.stderr[-1500:]}"
    )
    assert "[Line 2]" in update.stdout

    from smith.test_generation.guidance_map import load_mapping

    after_map = load_mapping(str(env.guidance_map))
    assert any("guest" in rule for rule in after_map), (
        "the added rule should be mapped to cases after the update run"
    )


def test_a_heading_swap_is_detected_as_a_change_by_the_raw_diff():
    env, update = _run_two_stage_cycle(
        GUIDANCE_HEADING_SWAP_BEFORE, GUIDANCE_HEADING_SWAP_AFTER, "headswap"
    )
    assert update.returncode == 0, (
        f"the update run failed (rc={update.returncode}).\n"
        f"--- stdout ---\n{update.stdout[-3000:]}\n"
        f"--- stderr ---\n{update.stderr[-1500:]}"
    )
    assert "Guidance file unchanged" not in update.stdout
    assert "Allowed commands" in update.stdout
    assert "Disallowed commands" in update.stdout

    marker = "Guidance diff vs snapshot:"
    line = next(row for row in update.stdout.splitlines() if marker in row)
    assert "0 unchanged" in line, (
        f"the heading swap should re-tag every bullet, leaving nothing "
        f"unchanged on the flattened side: {line}"
    )


def test_a_plain_reorder_with_no_heading_is_tolerated_by_the_flattened_diff():
    env, update = _run_two_stage_cycle(
        GUIDANCE_REORDER_BEFORE, GUIDANCE_REORDER_AFTER, "reorder"
    )
    assert update.returncode == 0, (
        f"the update run failed (rc={update.returncode}).\n"
        f"--- stdout ---\n{update.stdout[-3000:]}\n"
        f"--- stderr ---\n{update.stderr[-1500:]}"
    )
    assert "Guidance file unchanged" not in update.stdout, (
        "the raw diff must still see the reorder even though flatten "
        "may absorb it"
    )
