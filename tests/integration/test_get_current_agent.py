# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration test for ``smith --flag get_current_agent``.

This flag is read-only and dependency-free: it prints the configured target
agent and the resolved guidance-file path from the environment, then exits 0.

"""

from __future__ import annotations

import os
import subprocess

import pytest

pytestmark = pytest.mark.integration


def _run(env: dict, cwd) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["smith", "--flag", "get_current_agent"],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _clean_env(**overrides) -> dict:
    """Process env minus the vars this flag reads, plus explicit overrides.

    (Dropping them from the dict is not enough on its own — load_dotenv would
    refill from .env — which is why callers also run from an .env-free cwd.)
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"BASE_URL", "TARGET_AGENT_PATH", "GUIDANCE_FILE"}
    }
    env.update({k: str(v) for k, v in overrides.items()})
    return env


def _lines(stdout: str) -> dict:
    return {
        line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip()
        for line in stdout.splitlines()
        if ":" in line
    }


def test_prints_configured_agent_and_guidance(tmp_path):
    env = _clean_env(
        BASE_URL="/tmp/skill/",
        TARGET_AGENT_PATH="examples/call-for-papers-mcp/",
        GUIDANCE_FILE="examples/call-for-papers-mcp/smith/guidance.txt",
    )
    result = _run(env, cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    lines = _lines(result.stdout)
    assert lines["target_agent"] == env["TARGET_AGENT_PATH"]
    assert lines["guidance_file"] == env["BASE_URL"] + env["GUIDANCE_FILE"]


def test_unset_target_agent_prints_unset(tmp_path):
    env = _clean_env(BASE_URL="/tmp/skill/", TARGET_AGENT_PATH="", GUIDANCE_FILE="")
    result = _run(env, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    assert lines["target_agent"] == "(unset)"
    assert lines["guidance_file"] == "(unset)"


def test_guidance_unset_but_agent_set(tmp_path):
    env = _clean_env(
        BASE_URL="/tmp/skill/",
        TARGET_AGENT_PATH="examples/hr-agent/",
        GUIDANCE_FILE="",
    )
    result = _run(env, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    # target_agent echoes the env value; guidance is "(unset)" (empty is falsy).
    assert lines["target_agent"] == env["TARGET_AGENT_PATH"]
    assert lines["guidance_file"] == "(unset)"
