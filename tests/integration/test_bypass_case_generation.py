# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration test for ``smith --flag bypass_case_generation``.

Bypass generation analyzes the *current policy* against the guidance to find
divergences (``bypass_report.{json,md}``), synthesizes adversarial cases
(``bypass_cases.json``), and converts them into ``bypass_test_case*.json`` under
``references/test_cases/{allow,disallow}/``. It first pulls MCP tool definitions
(so the example agent must be up) and then requires a NON-EMPTY policy at
``assets/policy.rego`` — a missing/empty policy makes it skip cleanly.

Two paths are covered:
  1. Guard: with an empty policy, the flag prints a skip message and produces no
     bypass artifacts (no LLM work).
  2. Happy path: with the fixture policy staged, it produces a well-formed
     divergence report and bypass_test_case files.

Every file the flag touches is protected and restored:
  - ``assets/policy.rego`` and ``references/test_cases/`` (where the
    ``bypass_test_case*.json`` land) — by the session-scoped ``_backup_working_tree``.
  - ``references/bypass/`` (the whole dir, so both ``bypass_report.json`` and
    ``bypass_report.md``) and ``references/bypass_cases.json`` — by ``backup_file``
    (directory-aware: restores prior content, or removes them if they were absent).

Requires the example agent (``agent_server``); the happy path also requires an
LLM (``requires_llm``).
"""

from __future__ import annotations

import os
import shutil

import pytest

from helpers import (
    BYPASS_CASES_FILE,
    BYPASS_REPORT_DIR,
    EXAMPLE,
    REAL_POLICY,
    REAL_TEST_CASES,
    env_rel,
    load_json,
    run_smith,
)

pytestmark = pytest.mark.integration

BYPASS_REPORT_JSON = BYPASS_REPORT_DIR / "bypass_report.json"

VALID_CATEGORIES = {
    "omitted_field",
    "type_confusion",
    "malformed_value",
    "keyword_evasion",
}


def _bypass_env() -> dict:
    env = dict(os.environ)
    rel = env_rel(EXAMPLE)
    env.update(
        {
            "GUIDANCE_FILE": f"{rel}smith/guidance.txt",
            "SYSTEM_VAR_FILE": f"{rel}smith/system_vars.json",
            "MCP_TRANSPORT": "stdio",
            "MCP_COMMAND": "python",
            "MCP_ARGS": "server.py",
            "MCP_CWD": rel,
            "BYPASS_REPORT_DIR": env_rel(BYPASS_REPORT_DIR, is_dir=True),
            "BYPASS_CASE_FILE": env_rel(BYPASS_CASES_FILE),
            "SESSION_CONFIG_FILE": "references/__no_session_config__.json",
        }
    )
    return env


def _protect_bypass_artifacts(backup_file):
    backup_file(BYPASS_REPORT_DIR)
    backup_file(BYPASS_CASES_FILE)


def test_bypass_skips_on_empty_policy(agent_server, backup_file):
    # Empty policy -> the flag should skip (no error, no bypass cases).
    _protect_bypass_artifacts(backup_file)
    REAL_POLICY.write_text("")  # staged/restored by session
    if REAL_TEST_CASES.exists():
        shutil.rmtree(REAL_TEST_CASES)

    result = run_smith("bypass_case_generation", timeout=300, env=_bypass_env())
    assert result.returncode == 0, f"unexpected failure:\n{result.stderr}"
    assert "skipped" in result.stdout.lower()
    # No bypass_test_case files were produced.
    produced = (
        list(REAL_TEST_CASES.rglob("bypass_test_case*.json"))
        if REAL_TEST_CASES.exists()
        else []
    )
    assert not produced, f"empty policy should yield no bypass cases, got {produced}"


def test_bypass_generates_report_and_cases(
    requires_llm, agent_server, stage, backup_file
):
    _protect_bypass_artifacts(backup_file)
    # Stage a real, non-empty policy so divergence analysis has something to do.
    stage.stage_policy()
    if REAL_TEST_CASES.exists():
        shutil.rmtree(REAL_TEST_CASES)
    if BYPASS_REPORT_DIR.exists():
        shutil.rmtree(BYPASS_REPORT_DIR)

    result = run_smith("bypass_case_generation", timeout=900, env=_bypass_env())
    assert result.returncode == 0, (
        f"bypass_case_generation failed (rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout[-1500:]}\n--- stderr ---\n{result.stderr[-1000:]}"
    )
    assert "complete" in result.stdout.lower()

    # A divergence report was written and is a well-formed BypassReport.
    assert BYPASS_REPORT_JSON.exists(), "bypass_report.json not produced"
    report = load_json(BYPASS_REPORT_JSON)
    assert "vectors" in report, f"report missing 'vectors': {report}"
    for v in report["vectors"]:
        assert v["category"] in VALID_CATEGORIES, f"bad category: {v.get('category')}"
        assert v["direction"] in {
            "guidance_deny_policy_allow",
            "guidance_allow_policy_deny",
        }
    assert report["vectors"], (
        "no divergence vectors found for the staged fixture policy — bypass "
        f"analysis produced nothing to synthesize from.\n{result.stdout[-1500:]}"
    )

    # Converted bypass_test_case files exist and carry the OPA input envelope.
    produced = (
        list(REAL_TEST_CASES.rglob("bypass_test_case*.json"))
        if REAL_TEST_CASES.exists()
        else []
    )
    assert produced, "divergences found but no bypass_test_case files written"
    case = load_json(produced[0])
    assert "input" in case and "name" in case["input"]
