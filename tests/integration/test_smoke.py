# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Dependency-free smoke tests for the ``smith`` CLI contract.

These need no OPA, LLM, or agent, so they always run. They guard the invariant
from CLAUDE.md: ``smith --help`` and a bare ``smith`` must work without a
populated ``.env`` (args are parsed before any env-derived path assembly).
"""

from __future__ import annotations

import os
import subprocess

import pytest

from helpers import BASE_URL

pytestmark = pytest.mark.integration


def _run(*args, env=None):
    return subprocess.run(
        ["smith", *args],
        cwd=BASE_URL,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_help_exits_zero():
    result = _run("--help")
    assert result.returncode == 0
    assert "flag" in result.stdout.lower()


def test_bare_smith_prints_help_and_exits_zero():
    # A bare invocation should print help and exit 0 (no flag given).
    result = _run()
    assert result.returncode == 0


def test_help_works_without_env():
    # Strip Smith's env-derived vars; --help must still succeed because argparse
    # runs before any BASE_URL + os.getenv path assembly.
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"BASE_URL", "OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL_SONNET"}
    }
    result = _run("--help", env=env)
    assert result.returncode == 0


def test_unknown_flag_is_rejected():
    # An unrecognized --flag must exit 1 and name both the bad flag and the
    # allowed set (cli.py's allowed_flags guard). This is the CLI's only input
    # validation on --flag, so it belongs in the dependency-free smoke lane.
    result = _run("--flag", "definitely_not_a_flag")
    assert result.returncode == 1, result.stdout + result.stderr
    out = result.stdout + result.stderr
    assert "definitely_not_a_flag" in out
    assert "is not a valid flag" in out
    # The error lists the valid alternatives, so a user can self-correct.
    assert "Allowed flags:" in out
    assert "policy_testing" in out
