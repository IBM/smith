# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the ``save_snapshot`` flag.

``save_snapshot`` -> ``save_snapshot(dest, paths)`` copies the named Smith
artifacts (policy, cpex policy, guidance, tool definitions, promptfoo config,
and the ``test_cases/{allow,disallow}`` buckets) into a flat ``dest`` directory,
skipping any source that is missing (the snapshot still succeeds). We test the
function directly with crafted source files copied into a ``tmp_path`` dest, so
no repo files are involved, plus the CLI ``--dest`` requirement.
"""

from __future__ import annotations

import subprocess

import pytest

from helpers import BASE_URL
from smith.tools.save_snapshot import save_snapshot

pytestmark = pytest.mark.integration


def test_save_snapshot_copies_present_and_skips_missing(tmp_path):
    # Craft a source tree with some artifacts present, some absent.
    srcdir = tmp_path / "src"
    (srcdir / "assets").mkdir(parents=True)
    (srcdir / "smithinputs").mkdir(parents=True)
    tc = srcdir / "test_cases"
    (tc / "allow").mkdir(parents=True)
    (tc / "disallow").mkdir(parents=True)

    policy = srcdir / "assets" / "policy.rego"
    policy.write_text("package mcp.policies\n")
    guidance = srcdir / "smithinputs" / "guidance.txt"
    guidance.write_text("1. rule\n")
    (tc / "allow" / "a0.json").write_text("{}")
    (tc / "allow" / "a1.json").write_text("{}")
    (tc / "disallow" / "d0.json").write_text("{}")

    dest = tmp_path / "snap"
    save_snapshot(
        str(dest),
        {
            "policy": str(policy),
            "policy_cpex": str(srcdir / "assets" / "missing_cpex.rego"),  # missing
            "guidance": str(guidance),
            "tool_definitions": str(srcdir / "missing_tools.json"),  # missing
            "promptfoo_config": None,  # missing
            "test_case_path": str(tc),
        },
    )

    # Present sources copied (flat), with the canonical destination names.
    assert (dest / "policy.rego").read_text() == "package mcp.policies\n"
    assert (dest / "guidance.txt").read_text() == "1. rule\n"
    # Missing sources are simply skipped, not fatal.
    assert not (dest / "policy_cpex.rego").exists()
    assert not (dest / "tool_definitions.json").exists()
    # Test cases copied under test_cases/{allow,disallow}/ with the right counts.
    assert len(list((dest / "test_cases" / "allow").glob("*.json"))) == 2
    assert len(list((dest / "test_cases" / "disallow").glob("*.json"))) == 1


def test_save_snapshot_empty_paths_still_creates_dest(tmp_path):
    # All sources missing/None -> nothing copied, but dest is created and the
    # call succeeds (snapshot of "whatever exists", which is nothing here).
    dest = tmp_path / "snap"
    save_snapshot(
        str(dest),
        {
            "policy": None,
            "policy_cpex": None,
            "guidance": None,
            "tool_definitions": None,
            "promptfoo_config": None,
            "test_case_path": None,
        },
    )
    assert dest.is_dir()
    assert list(dest.iterdir()) == []


def test_save_snapshot_cli_requires_dest():
    result = subprocess.run(
        ["smith", "--flag", "save_snapshot"],
        cwd=BASE_URL,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 1
    assert "requires --dest" in (result.stdout + result.stderr)
