# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration test for ``smith --flag reset_policy``.

STEPS COVERED (all from the single run)
--------------------------------------
STEP 1  the flag resolves the managed policy from ``.env``
        (``POLICY_DIR`` + ``POLICY_PATH``) via the real ``BlueAgent.__init__``
STEP 2  it truncates that file to zero bytes, creating it if absent
STEP 3  it removes the CPEX-translated sibling (``<policy>_cpex.rego``),
        but only when one exists

This is deterministic, filesystem-only work — no LLM, no OPA, no Docker — so
per the guide its output is asserted exactly.

NEVER DAMAGES THE WORKING TREE
-------------------------------
``reset_policy`` empties the real, tracked ``assets/policy.rego``, so every
test here goes through ``backup_working_tree`` (via the ``stage`` fixture, or
directly) to restore it on teardown.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


# ===========================================================================
# STEPS 1 + 2 — the managed policy is emptied
# ===========================================================================


def test_a_populated_policy_is_emptied(stage, smith_cli):
    stage.stage_policy()
    env = stage.env
    assert env.policy.read_text().strip(), "fixture policy must be non-empty to test truncation"

    result = smith_cli("reset_policy")

    assert result.returncode == 0, result.stdout + result.stderr
    assert env.policy.exists()
    assert env.policy.read_text() == ""


def test_a_missing_policy_is_created_empty(backup_working_tree, smith_cli):
    env = backup_working_tree
    if env.policy.exists():
        env.policy.unlink()
    assert not env.policy.exists()

    result = smith_cli("reset_policy")

    assert result.returncode == 0, result.stdout + result.stderr
    assert env.policy.exists()
    assert env.policy.read_text() == ""


def test_the_flag_reports_what_it_emptied(stage, smith_cli):
    stage.stage_policy()
    env = stage.env

    result = smith_cli("reset_policy")

    assert result.returncode == 0, result.stdout + result.stderr
    assert str(env.policy) in result.stdout, (
        "the flag should name the file it emptied, so a run's log is auditable"
    )


# ===========================================================================
# STEP 3 — the CPEX sibling
# ===========================================================================


def test_an_existing_cpex_sibling_is_removed(stage, backup_file, smith_cli):
    stage.stage_policy()
    env = stage.env
    cpex_path = env.policy.with_name(env.policy.stem + "_cpex.rego")
    backup_file(cpex_path)
    cpex_path.write_text("package mcp.policies\n\nsubject := input.subject\n")

    result = smith_cli("reset_policy")

    assert result.returncode == 0, result.stdout + result.stderr
    assert not cpex_path.exists(), "the CPEX-translated sibling must not survive a reset"
    assert str(cpex_path) in result.stdout


def test_a_missing_cpex_sibling_is_not_reported_or_an_error(stage, smith_cli):
    stage.stage_policy()
    env = stage.env
    cpex_path = env.policy.with_name(env.policy.stem + "_cpex.rego")
    if cpex_path.exists():
        cpex_path.unlink()

    result = smith_cli("reset_policy")

    assert result.returncode == 0, result.stdout + result.stderr
    assert str(cpex_path) not in result.stdout
