# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the functions behind ``smith --flag save_snapshot``.

STEP 1 · ``smith.tools.save_snapshot`` — the whole snapshot
    ``save_snapshot``     — canonical destination names, nested case buckets,
                            absent/None sources, an entirely empty snapshot, the
                            returned destination, and preservation of the sources

STEP 2 · the copy helpers it drives, in the order it calls them
    ``_copy_file``        — rename-on-copy, basename fallback, missing-source
                            return value
    ``_copy_case_dir``    — file counting, sorted order, directory skipping,
                            absent bucket

NOT COVERED HERE (integration lane — see ``test_save_snapshot_integration.py``)
    The CLI's ``--dest`` requirement and its BASE_URL-derived path assembly.

Env-free: every path is under ``tmp_path``; no configuration is read.
"""

from __future__ import annotations

import pytest

from smith.tools.save_snapshot import _copy_case_dir, _copy_file, save_snapshot

pytestmark = pytest.mark.unit


@pytest.fixture
def artifacts(unit_env):
    """A source tree with every artifact present, under the temp root."""
    root = unit_env.root / "src"
    (root / "assets").mkdir(parents=True, exist_ok=True)
    (root / "smithinputs").mkdir(parents=True, exist_ok=True)
    cases = root / "test_cases"
    (cases / "allow").mkdir(parents=True, exist_ok=True)
    (cases / "disallow").mkdir(parents=True, exist_ok=True)

    (root / "assets" / "policy.rego").write_text("package mcp.policies\n")
    (root / "assets" / "policy_cpex.rego").write_text("package authz\n")
    (root / "smithinputs" / "guidance.txt").write_text("1. rule\n")
    (root / "tool_definitions.json").write_text('{"tools": []}')
    (root / "promptfooconfig.yaml").write_text("redteam: {}\n")
    for i in range(2):
        (cases / "allow" / f"test_case{i}.json").write_text("{}")
    (cases / "disallow" / "test_case0.json").write_text("{}")

    return {
        "policy": str(root / "assets" / "policy.rego"),
        "policy_cpex": str(root / "assets" / "policy_cpex.rego"),
        "guidance": str(root / "smithinputs" / "guidance.txt"),
        "tool_definitions": str(root / "tool_definitions.json"),
        "promptfoo_config": str(root / "promptfooconfig.yaml"),
        "test_case_path": str(cases),
    }


# ===========================================================================
# STEP 1 · save_snapshot — the whole artifact set
# ===========================================================================


def test_every_artifact_lands_under_its_canonical_name(unit_env, artifacts):
    # The destination names are a contract: an archived snapshot is read back by
    # name, regardless of what the source file happened to be called.
    dest = unit_env.root / "snap"
    save_snapshot(str(dest), artifacts)

    assert (dest / "policy.rego").read_text() == "package mcp.policies\n"
    assert (dest / "policy_cpex.rego").read_text() == "package authz\n"
    assert (dest / "guidance.txt").read_text() == "1. rule\n"
    assert (dest / "tool_definitions.json").read_text() == '{"tools": []}'


def test_promptfoo_config_keeps_its_own_basename(unit_env, artifacts):
    # The only artifact NOT renamed: _copy_file is called without a dst_name, so
    # the original filename is preserved.
    dest = unit_env.root / "snap"
    save_snapshot(str(dest), artifacts)
    assert (dest / "promptfooconfig.yaml").exists()


def test_test_cases_are_copied_into_nested_buckets(unit_env, artifacts):
    dest = unit_env.root / "snap"
    save_snapshot(str(dest), artifacts)
    assert len(list((dest / "test_cases" / "allow").glob("*.json"))) == 2
    assert len(list((dest / "test_cases" / "disallow").glob("*.json"))) == 1


def test_sources_are_left_untouched(unit_env, artifacts):
    # A snapshot copies; it must never move or alter the working artifacts.
    dest = unit_env.root / "snap"
    save_snapshot(str(dest), artifacts)
    from pathlib import Path

    for key in ("policy", "guidance", "tool_definitions"):
        assert Path(artifacts[key]).exists(), f"{key} disappeared from the source"
    assert Path(artifacts["policy"]).read_text() == "package mcp.policies\n"


def test_returns_the_absolute_destination(unit_env, artifacts):
    dest = unit_env.root / "snap"
    returned = save_snapshot(str(dest), artifacts)
    import os

    assert returned == os.path.abspath(str(dest))


def test_destination_is_created_when_absent(unit_env, artifacts):
    dest = unit_env.root / "deeply" / "nested" / "snap"
    save_snapshot(str(dest), artifacts)
    assert dest.is_dir()


# ===========================================================================
# The best-effort contract: missing sources must not be fatal
# ===========================================================================


def test_missing_sources_are_skipped_not_fatal(unit_env, artifacts):
    # A snapshot taken before cpex translation / promptfoo generation still
    # succeeds, carrying whatever exists.
    partial = dict(artifacts)
    partial["policy_cpex"] = str(unit_env.root / "src" / "assets" / "absent.rego")
    partial["promptfoo_config"] = None

    dest = unit_env.root / "snap"
    save_snapshot(str(dest), partial)

    assert (dest / "policy.rego").exists(), "present artifacts still copied"
    assert not (dest / "policy_cpex.rego").exists()
    assert not (dest / "promptfooconfig.yaml").exists()


def test_all_sources_missing_still_creates_the_destination(unit_env):
    dest = unit_env.root / "snap"
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
    assert list(dest.iterdir()) == [], "nothing to copy -> an empty snapshot"


def test_an_empty_paths_dict_is_accepted(unit_env):
    # Every key is read with .get(), so omitting them entirely behaves the same
    # as passing None — worth pinning, since the CLI builds this dict piecemeal.
    dest = unit_env.root / "snap"
    assert save_snapshot(str(dest), {}) is not None
    assert dest.is_dir()


def test_absent_case_buckets_are_skipped(unit_env, artifacts):
    # test_case_path set, but the allow/disallow subdirs do not exist.
    partial = dict(artifacts)
    partial["test_case_path"] = str(unit_env.root / "src" / "no_such_cases")
    dest = unit_env.root / "snap"
    save_snapshot(str(dest), partial)
    assert not (dest / "test_cases" / "allow").exists()
    # The rest of the snapshot is unaffected.
    assert (dest / "policy.rego").exists()


# ===========================================================================
# STEP 2 · the copy helpers
# ===========================================================================


def test_copy_file_renames_and_reports_the_new_name(unit_env):
    src = unit_env.root / "original.rego"
    src.write_text("x")
    dest = unit_env.root / "out"
    assert _copy_file(str(src), str(dest), "renamed.rego") == "renamed.rego"
    assert (dest / "renamed.rego").read_text() == "x"


def test_copy_file_falls_back_to_the_source_basename(unit_env):
    src = unit_env.root / "keepme.yaml"
    src.write_text("y")
    dest = unit_env.root / "out"
    assert _copy_file(str(src), str(dest)) == "keepme.yaml"
    assert (dest / "keepme.yaml").exists()


@pytest.mark.parametrize("missing", [None, "", "/definitely/not/here.rego"])
def test_copy_file_returns_none_for_a_missing_source(unit_env, missing):
    assert _copy_file(missing, str(unit_env.root / "out")) is None


def test_copy_file_ignores_a_directory_source(unit_env):
    # It guards on isfile, so a directory is treated as "not found" rather than
    # raising partway through a snapshot.
    a_dir = unit_env.root / "adir"
    a_dir.mkdir()
    assert _copy_file(str(a_dir), str(unit_env.root / "out")) is None


def test_copy_case_dir_counts_the_files_copied(unit_env):
    src = unit_env.root / "allow"
    src.mkdir()
    for i in range(3):
        (src / f"test_case{i}.json").write_text("{}")
    dest = unit_env.root / "out" / "allow"
    assert _copy_case_dir(str(src), str(dest), "allow") == 3
    assert len(list(dest.glob("*.json"))) == 3


def test_copy_case_dir_skips_subdirectories(unit_env):
    # wrong_cases/ nests under a bucket during translation; the snapshot copies
    # files only, and does not recurse.
    src = unit_env.root / "allow"
    (src / "nested").mkdir(parents=True)
    (src / "case.json").write_text("{}")
    (src / "nested" / "deep.json").write_text("{}")

    dest = unit_env.root / "out" / "allow"
    assert _copy_case_dir(str(src), str(dest), "allow") == 1
    assert (dest / "case.json").exists()
    assert not (dest / "nested").exists()


def test_copy_case_dir_copies_every_file_regardless_of_extension(unit_env):
    # Despite the docstring saying "JSON test cases", there is no extension
    # filter. Pinned so the count is predictable if a stray file appears.
    src = unit_env.root / "allow"
    src.mkdir()
    (src / "case.json").write_text("{}")
    (src / "notes.txt").write_text("hi")
    assert _copy_case_dir(str(src), str(unit_env.root / "out"), "allow") == 2


@pytest.mark.parametrize("missing", [None, "", "/definitely/not/here"])
def test_copy_case_dir_returns_zero_for_a_missing_bucket(unit_env, missing):
    assert _copy_case_dir(missing, str(unit_env.root / "out"), "allow") == 0


# ===========================================================================
# A realistic end-to-end snapshot, from the frozen fixtures
# ===========================================================================


def test_snapshot_of_the_frozen_fixture_artifacts(unit_env):
    # Uses the committed fixture policy + case set as sources, which is the
    # shape a real snapshot takes.
    dest = unit_env.root / "snap"
    save_snapshot(
        str(dest),
        {
            "policy": str(unit_env.policy),
            "guidance": str(unit_env.guidance_file),
            "test_case_path": str(unit_env.test_cases),
        },
    )
    assert (dest / "policy.rego").exists()
    assert (dest / "guidance.txt").exists()
    allow = list((dest / "test_cases" / "allow").glob("*.json"))
    disallow = list((dest / "test_cases" / "disallow").glob("*.json"))
    assert len(allow) == 35 and len(disallow) == 80, (
        "the frozen fixture set is 35 allow / 80 disallow cases"
    )
