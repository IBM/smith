# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the ``cpex_translate`` flag.

``cpex_translate`` -> ``translate_policy_to_cpex(src, dest)`` rewrites a policy
into the CPEX input shape:
  - ``package mcp.policies`` -> ``package authz``
  - ``input.extensions.subject`` -> ``input.subject`` (the ``extensions`` layer
    is dropped, ``subject`` kept under the input root)
  - envelope / tool-name guards are dropped
and writes the result next to the original (``<name>_cpex.rego`` by default). It
is a deterministic, line-preserving text transform followed by an ``opa fmt`` +
validate pass, so we test it directly on crafted policies. Needs the ``opa``
binary (``requires_opa_binary``); never touches repo files (works in tmp_path).
"""

from __future__ import annotations

import subprocess

import pytest

from helpers import BASE_URL
from smith.policy_generation.translate_cpex import translate_policy_to_cpex

pytestmark = pytest.mark.integration

CPEX_INPUT = (
    "package mcp.policies\n\n"
    "default allow := false\n\n"
    "subject := input.extensions.subject\n\n"
    "allow if {\n"
    '\tinput.name == "get_events"\n'
    '\tsubject.user_role[_] == "faculty"\n'
    "}\n"
)


def test_cpex_translate_rewrites_shape(requires_opa_binary, tmp_path):
    src = tmp_path / "policy.rego"
    src.write_text(CPEX_INPUT)
    dest = tmp_path / "policy_cpex.rego"

    ok = translate_policy_to_cpex(str(src), str(dest))
    assert ok is True
    assert dest.exists()

    out = dest.read_text()
    # package renamed to the CPEX package.
    assert "package authz" in out
    assert "package mcp.policies" not in out
    # extensions layer dropped from the subject accessor.
    assert "input.subject" in out
    assert "input.extensions.subject" not in out
    # The original file is left untouched.
    assert src.read_text() == CPEX_INPUT


def test_cpex_translate_missing_source_returns_false(requires_opa_binary, tmp_path):
    ok = translate_policy_to_cpex(str(tmp_path / "nope.rego"), str(tmp_path / "o.rego"))
    assert ok is False


def test_cpex_translate_cli_default_dest(requires_opa_binary, tmp_path):
    # Via the CLI: `--policy_path X` with no --dest writes X_cpex.rego alongside.
    src = tmp_path / "mypolicy.rego"
    src.write_text(CPEX_INPUT)
    result = subprocess.run(
        ["smith", "--flag", "cpex_translate", "--policy_path", str(src)],
        cwd=BASE_URL,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "mypolicy_cpex.rego").exists()
