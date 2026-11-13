# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for ``smith --flag test_generation --mode update``.

Fresh generation rebuilds the whole suite. Update mode regenerates only the
guidance that changed since the last run::

    guidance_raw_snapshot.txt  ->  what the user edited, computed in Python
                               ->  handed to flatten as instructions
    guidance_snapshot.txt      ->  diffed against the new flattened text
    guidance_case_map.json     ->  the cases belonging to guidance that changed

Requires an LLM and the MCP server's ``python`` for the two-run fixture only.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from helpers import STDIO_MCP, SmithEnv, which

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

CRAFTED_SYSTEM_VARS = {
    "action_list": ["get_events", "other"],
    "action_description": {
        "get_events": (
            "Search for upcoming academic conferences and calls for papers."
        ),
        "other": "General Q&A not backed by a specific tool.",
    },
    "user_name": "Alice",
    "user_role": ["faculty", "phd_student", "guest"],
}

#: Written beside each run's guidance, so no example's own file is touched.
SYSTEM_VARS_NAME = "__update_system_vars__.json"


@pytest.fixture(scope="module", autouse=True)
def _remove_crafted_system_vars():
    yield
    from helpers import SmithEnv

    (Path(SmithEnv().base) / "references" / SYSTEM_VARS_NAME).unlink(
        missing_ok=True
    )


def run_flag(env, *extra_args, guidance_name, **overrides):
    """Invoke the CLI in-process-free, returning the CompletedProcess."""
    system_vars = Path(env.base) / "references" / SYSTEM_VARS_NAME
    system_vars.parent.mkdir(parents=True, exist_ok=True)
    system_vars.write_text(json.dumps(CRAFTED_SYSTEM_VARS, indent=2))
    overrides.setdefault("SYSTEM_VAR_FILE", f"references/{SYSTEM_VARS_NAME}")
    return subprocess.run(
        [sys.executable, "-m", "smith.cli", "--flag", "test_generation", *extra_args],
        cwd=str(env.base),
        env=env.override(
            # The flag extracts tool definitions; stdio is the transport this
            # test can satisfy on its own.
            **STDIO_MCP,
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
        from smith.test_generation.guidance_map import read_lines

        before_lines = read_lines(GUIDANCE_BEFORE)
        assert len(before_lines) == 3, before_lines

        env.guidance_raw_snapshot.parent.mkdir(parents=True, exist_ok=True)
        env.guidance_raw_snapshot.write_text(GUIDANCE_BEFORE)
        env.guidance_snapshot.write_text(GUIDANCE_BEFORE)

        # One stub case per rule, so the map points at files that exist and the
        # survivors' bytes are known exactly -- the update run must not touch them.
        before_bytes = {}
        before_map = {}
        for position, line in enumerate(before_lines, start=1):
            bucket = "allow" if position != 2 else "disallow"
            relative = f"{bucket}/test_case{position}.json"
            target = cases / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(
                {
                    "input": {
                        "kind": "tool_call",
                        "name": "get_events",
                        "args": {"limit": position},
                        "extensions": {
                            "agent": {"input": f"staged case for rule {position}"},
                            "subject": {"role": "faculty"},
                        },
                    }
                },
                indent=4,
            )
            target.write_text(payload)
            before_bytes[relative] = target.read_bytes()
            before_map[line] = [relative]

        env.guidance_map.write_text(json.dumps(before_map, indent=4))

        guidance.write_text(GUIDANCE_AFTER)
        update = run_flag(env, "--mode", "update", guidance_name=guidance.name)
        after_map = json.loads(env.guidance_map.read_text())
        flattened_text = env.path("FLATTEN_FILE").read_text()
        raw_snapshot_text = env.guidance_raw_snapshot.read_text()
        snapshot_exists = env.guidance_snapshot.exists()
        after_bytes = {
            str(path.relative_to(cases)): path.read_bytes()
            for path in sorted(cases.rglob("*.json"))
        }

        yield {
            "env": env,
            "cases": cases,
            "update": update,
            "before_bytes": before_bytes,
            "before_map": before_map,
            "after_map": after_map,
            "after_bytes": after_bytes,
            "flattened_text": flattened_text,
            "raw_snapshot_text": raw_snapshot_text,
            "snapshot_exists": snapshot_exists,
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
    before = update_ok["before_bytes"]
    after = update_ok["after_bytes"]
    before_map = update_ok["before_map"]
    after_map = update_ok["after_map"]

    # The edited rule is the one absent from the post-update map's keys.
    survivors = {
        path
        for rule, paths in before_map.items()
        if rule in after_map
        for path in paths
    }
    assert survivors, "the staged map held no cases, so there is nothing to compare"

    rewritten = [
        relative
        for relative in sorted(survivors)
        if relative in after and after[relative] != before[relative]
    ]
    assert not rewritten, f"untouched rules' cases were rewritten: {rewritten}"


def test_the_edited_rule_got_fresh_cases(update_ok):
    """The edited rule must end up with cases again, and they must be its own."""
    before_map = update_ok["before_map"]
    after_map = update_ok["after_map"]
    new_rules = [rule for rule in after_map if rule not in before_map]

    assert new_rules, "the edited rule produced no mapped cases"
    assert all(after_map[rule] for rule in new_rules), new_rules


def test_the_map_and_the_flattened_guidance_agree(update_ok):
    from smith.test_generation.guidance_map import read_lines

    flattened = set(read_lines(update_ok["flattened_text"]))

    orphans = [key for key in update_ok["after_map"] if key not in flattened]
    assert not orphans, f"mapping keys absent from the flattened guidance: {orphans}"


def test_both_snapshots_were_advanced(update_ok):
    """A stale snapshot would make the next run redo this run's work."""
    assert update_ok["snapshot_exists"]
    assert update_ok["raw_snapshot_text"] == GUIDANCE_AFTER
