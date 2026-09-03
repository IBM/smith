# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the policy-validation functions (``policy_validation`` /
``policy_validation_fix`` flags).

The flags are thin wrappers over ``smith.policy_generation.validate_policy``:
``run_opa_fmt``, ``run_opa_fmt_write``, ``run_opa_check``, ``run_opa_eval_smoke``,
and the composites ``validate_policy`` / ``fix_and_validate_policy``. These are
pure ``(policy_path) -> (bool, msg)`` / ``-> bool`` functions over the local
``opa`` binary, so we unit-test them **directly** with a spread of crafted
policy inputs written into ``tmp_path``:

    valid+clean, valid+unformatted, type error (parses, fails opa check),
    parse error (broken syntax), empty file, and a nonexistent path.

A couple of CLI-contract cases (``--policy_path`` required) round it out.
Requires only the ``opa`` binary (``requires_opa_binary``); never touches repo
files.
"""

from __future__ import annotations

import subprocess

import pytest

from helpers import BASE_URL
from smith.policy_generation.validate_policy import (
    fix_and_validate_policy,
    run_opa_check,
    run_opa_fmt,
    run_opa_fmt_write,
    run_opa_eval_smoke,
    validate_policy,
)

pytestmark = pytest.mark.integration


# --- crafted policy inputs --------------------------------------------------

VALID_CLEAN = 'package mcp.policies\n\ndefault allow := false\n\nallow if {\n\tinput.name == "get_events"\n}\n'
# valid Rego, but 4-space indent + extra blank lines -> opa fmt would rewrite.
VALID_UNFORMATTED = 'package mcp.policies\n\n\n\ndefault allow := false\nallow if {\n    input.name == "get_events"\n}\n'
# parses fine, but references an undefined function -> opa check (type) error.
TYPE_ERROR = "package mcp.policies\n\nallow if {\n\tnot_a_builtin(input.name)\n}\n"
# unterminated expression -> opa parse error.
PARSE_ERROR = "package mcp.policies\n\nallow if {\n\tinput.name ==\n}\n"
EMPTY = ""


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content)
    return p


@pytest.fixture
def clean_policy(requires_opa_binary, tmp_path):
    """A valid policy normalized to canonical opa formatting."""
    p = _write(tmp_path, "clean.rego", VALID_CLEAN)
    subprocess.run(["opa", "fmt", "-w", str(p)], check=True, timeout=30)
    return p


# --- run_opa_fmt: only a syntax/format-parse failure returns False ----------


def test_fmt_clean_policy_is_valid(clean_policy):
    ok, msg = run_opa_fmt(str(clean_policy))
    assert ok is True
    assert "syntax is valid" in msg


def test_fmt_unformatted_policy_reports_rewrite_but_ok(requires_opa_binary, tmp_path):
    p = _write(tmp_path, "u.rego", VALID_UNFORMATTED)
    ok, msg = run_opa_fmt(str(p))
    assert ok is True  # unformatted is NOT a failure...
    assert "would rewrite" in msg  # ...just flagged


def test_fmt_type_error_still_parses_ok(requires_opa_binary, tmp_path):
    # A type error parses fine, so opa fmt succeeds (only opa check catches it).
    p = _write(tmp_path, "t.rego", TYPE_ERROR)
    ok, _ = run_opa_fmt(str(p))
    assert ok is True


def test_fmt_parse_error_fails(requires_opa_binary, tmp_path):
    p = _write(tmp_path, "b.rego", PARSE_ERROR)
    ok, msg = run_opa_fmt(str(p))
    assert ok is False
    assert "opa fmt failed" in msg


def test_fmt_empty_file_fails(requires_opa_binary, tmp_path):
    p = _write(tmp_path, "e.rego", EMPTY)
    ok, _ = run_opa_fmt(str(p))
    assert ok is False


# --- run_opa_check: catches type errors that fmt misses ---------------------


def test_check_passes_for_valid(clean_policy):
    ok, _ = run_opa_check(str(clean_policy))
    assert ok is True


def test_check_fails_for_type_error(requires_opa_binary, tmp_path):
    p = _write(tmp_path, "t.rego", TYPE_ERROR)
    ok, msg = run_opa_check(str(p))
    assert ok is False
    assert "opa check failed" in msg


def test_check_fails_for_parse_error(requires_opa_binary, tmp_path):
    p = _write(tmp_path, "b.rego", PARSE_ERROR)
    ok, _ = run_opa_check(str(p))
    assert ok is False


# --- run_opa_fmt_write: rewrites in place -----------------------------------


def test_fmt_write_reformats_in_place(requires_opa_binary, tmp_path):
    p = _write(tmp_path, "u.rego", VALID_UNFORMATTED)
    before = p.read_text()
    ok, _ = run_opa_fmt_write(str(p))
    assert ok is True
    assert p.read_text() != before  # file was rewritten to canonical form


def test_fmt_write_fails_on_parse_error(requires_opa_binary, tmp_path):
    p = _write(tmp_path, "b.rego", PARSE_ERROR)
    ok, _ = run_opa_fmt_write(str(p))
    assert ok is False


# --- run_opa_eval_smoke -----------------------------------------------------


def test_eval_smoke_loads_valid_policy(clean_policy):
    ok, _ = run_opa_eval_smoke(str(clean_policy))
    assert ok is True


# --- validate_policy (composite) --------------------------------------------


def test_validate_policy_true_for_clean(clean_policy):
    assert validate_policy(str(clean_policy)) is True


def test_validate_policy_true_for_unformatted(requires_opa_binary, tmp_path):
    # Composite passes because fmt "would rewrite" is not a failure and check/eval pass.
    p = _write(tmp_path, "u.rego", VALID_UNFORMATTED)
    assert validate_policy(str(p)) is True


def test_validate_policy_false_for_type_error(requires_opa_binary, tmp_path):
    p = _write(tmp_path, "t.rego", TYPE_ERROR)
    assert validate_policy(str(p)) is False


def test_validate_policy_false_for_parse_error(requires_opa_binary, tmp_path):
    p = _write(tmp_path, "b.rego", PARSE_ERROR)
    assert validate_policy(str(p)) is False


def test_validate_policy_false_for_missing_file(requires_opa_binary, tmp_path):
    assert validate_policy(str(tmp_path / "nope.rego")) is False


# --- fix_and_validate_policy (composite; rewrites) --------------------------


def test_fix_reformats_and_passes(requires_opa_binary, tmp_path):
    p = _write(tmp_path, "u.rego", VALID_UNFORMATTED)
    before = p.read_text()
    assert fix_and_validate_policy(str(p)) is True
    assert p.read_text() != before  # rewritten in place


def test_fix_false_for_parse_error(requires_opa_binary, tmp_path):
    p = _write(tmp_path, "b.rego", PARSE_ERROR)
    assert fix_and_validate_policy(str(p)) is False


def test_fix_false_for_missing_file(requires_opa_binary, tmp_path):
    assert fix_and_validate_policy(str(tmp_path / "nope.rego")) is False


# --- CLI-contract: --policy_path is required --------------------------------


@pytest.mark.parametrize("flag", ["policy_validation", "policy_validation_fix"])
def test_cli_requires_policy_path(flag):
    result = subprocess.run(
        ["smith", "--flag", flag],
        cwd=BASE_URL,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 1
    assert "--policy_path is required" in (result.stdout + result.stderr)
