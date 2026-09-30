# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the method behind ``smith --flag reset_policy``.

The flag clears the managed policy before a new target agent's policy is
generated, so a stale policy from a previously configured agent can never leak
into a fresh run::

    BlueAgent.reset_policy()
        truncate policy_path to zero bytes   (created if it did not exist)
        <policy>.rego -> <policy>_cpex.rego   (the CPEX-translated sibling)
        remove the CPEX sibling, but only if it exists

FUNCTIONS UNDER TEST
--------------------
STEP 1 · ``smith.cli``
    ``BlueAgent.reset_policy`` — the truncation, the CPEX-sibling name
                                 derivation, and the exists-before-remove guard

NOT COVERED HERE (integration lane — see ``test_reset_policy_integration.py``)
    Resolving ``policy_path`` from a real ``.env`` via ``BlueAgent.__init__``,
    and the CLI's ``sys.exit(0)`` after the call.

Env-free: no ``.env``, no credentials, no network, no OPA.
"""

from __future__ import annotations

import pytest

from smith.cli import BlueAgent

pytestmark = pytest.mark.unit


def _agent(policy_path) -> BlueAgent:
    agent = object.__new__(BlueAgent)
    agent.policy_path = str(policy_path)
    return agent


# ===========================================================================
# STEP 1 · reset_policy
# ===========================================================================


def test_a_policy_with_content_is_truncated_to_empty(tmp_path):
    policy = tmp_path / "policy.rego"
    policy.write_text("package mcp.policies\n\ndefault allow := false\n")

    _agent(policy).reset_policy()

    assert policy.exists()
    assert policy.read_text() == ""


def test_a_missing_policy_file_is_created_empty(tmp_path):
    # A fresh checkout, or a target agent switch where the policy was never
    # written yet — reset_policy must not require the file to pre-exist.
    policy = tmp_path / "policy.rego"
    assert not policy.exists()

    _agent(policy).reset_policy()

    assert policy.exists()
    assert policy.read_text() == ""


def test_an_existing_cpex_sibling_is_removed(tmp_path):
    policy = tmp_path / "policy.rego"
    policy.write_text("package mcp.policies\n")
    cpex = tmp_path / "policy_cpex.rego"
    cpex.write_text("package mcp.policies\n\nsubject := input.subject\n")

    _agent(policy).reset_policy()

    assert not cpex.exists(), "the CPEX-translated sibling must not survive a reset"
    assert policy.read_text() == ""


def test_a_missing_cpex_sibling_is_not_an_error(tmp_path):
    policy = tmp_path / "policy.rego"
    policy.write_text("package mcp.policies\n")

    _agent(policy).reset_policy()  # must not raise

    assert policy.read_text() == ""
    assert not (tmp_path / "policy_cpex.rego").exists()


def test_only_the_matching_cpex_sibling_name_is_removed(tmp_path):
    policy = tmp_path / "policy.rego"
    policy.write_text("package mcp.policies\n")
    unrelated = tmp_path / "policy.rego.bak"
    unrelated.write_text("kept")

    _agent(policy).reset_policy()

    assert unrelated.exists()
    assert unrelated.read_text() == "kept"


def test_reset_is_idempotent(tmp_path):
    policy = tmp_path / "policy.rego"
    agent = _agent(policy)

    agent.reset_policy()
    agent.reset_policy()

    assert policy.read_text() == ""


def test_only_the_policy_files_are_touched(tmp_path):
    policy = tmp_path / "policy.rego"
    policy.write_text("package mcp.policies\n")
    guidance = tmp_path / "guidance.txt"
    guidance.write_text("1. Some rule.\n")

    _agent(policy).reset_policy()

    assert guidance.read_text() == "1. Some rule.\n"
