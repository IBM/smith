# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""CLI integration tests for ``smith --flag guidance_reconciliation``."""

from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


TABLE = """\
## Existing Guidance Normalization

| Existing ID | Rule number | Tool | Subject scope | Field expression | Operator | Values | Action |
|---|---|---|---|---|---|---|---|

## Candidate Reconciliation

| Candidate ID | Tool | Subject scope | Field expression | Operator | Values | Action | Sources | Related rule | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| C01 | set_user_role | all | `input.args.user_role` | eq | manager | deny | T01 | — | Novel |
| C02 | set_user_role | all | `input.args.user_role` | not_in | {employee, manager} | deny | T02 | — | Novel |
"""


def cli_environment(tmp_path: Path) -> tuple[dict[str, str], tuple[Path, ...]]:
    target = tmp_path / "agent"
    smith = target / "smith"
    analysis_dir = smith / "guidelines-security-analysis"
    analysis_dir.mkdir(parents=True)
    analysis = analysis_dir / "owasp_policy_guidelines.md"
    tools = smith / "tool_definitions.json"
    guidance = smith / "guidance.txt"
    updated = smith / "guidance_updated.txt"
    system_vars = smith / "system_vars.json"
    analysis.write_text(TABLE)
    tools.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "set_user_role",
                        "input_schema": {
                            "properties": {
                                "user_role": {
                                    "type": "string",
                                    "enum": ["employee", "manager"],
                                }
                            }
                        },
                    }
                ]
            }
        )
    )
    guidance.write_text("1. Existing rule\n")
    updated.write_text("2. existing rule\n")
    system_vars.write_text(json.dumps({"roles": ["employee", "manager"]}))
    env = dict(os.environ)
    env.update(
        {
            "BASE_URL": str(tmp_path) + os.sep,
            "TARGET_AGENT_PATH": "agent",
            "GUIDANCE_FILE": "agent/smith/guidance.txt",
            "SYSTEM_VAR_FILE": "agent/smith/system_vars.json",
        }
    )
    return env, (analysis, tools, guidance, updated, system_vars)


def run_cli(env: dict[str, str]):
    return subprocess.run(
        [sys.executable, "-m", "smith.cli", "--flag", "guidance_reconciliation"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def test_cli_prints_deterministic_report_without_modifying_inputs(tmp_path):
    env, paths = cli_environment(tmp_path)
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}

    result = run_cli(env)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert result.stdout == (
        "Guidance reconciliation (read-only)\n"
        "Candidates: 2 | Valid: 2 | Invalid: 0\n"
        "Existing normalized rules: 0\n"
        "\n"
        "Validation\n"
        "- C01: PASS\n"
        "- C02: PASS\n"
        "\n"
        "Relationships\n"
        "- Additive: C01 / C02 — deny conditions add distinct values or ranges\n"
        "\n"
        "Existing guidance relationships\n"
        "- None.\n"
        "\n"
        "Exact union simplifications\n"
        "- C01, C02 -> neq {employee}\n"
        "\n"
        "Exact normalized-text duplicates\n"
        "- guidance.txt:1 = guidance_updated.txt:1\n"
        "\n"
        "Result: findings are suggestions; no files were modified.\n"
    )
    assert before == {
        path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths
    }


def test_cli_returns_nonzero_for_missing_candidate_table(tmp_path):
    env, paths = cli_environment(tmp_path)
    paths[0].write_text("# Assessment without reconciliation\n")

    result = run_cli(env)

    assert result.returncode == 1
    assert result.stdout == ""
    assert "ERROR: Candidate Reconciliation section is missing" in result.stderr


def test_cli_compares_candidates_with_normalized_existing_guidance(tmp_path):
    env, paths = cli_environment(tmp_path)
    analysis = paths[0]
    analysis.write_text(
        analysis.read_text().replace(
            "|---|---|---|---|---|---|---|---|\n\n## Candidate Reconciliation",
            "|---|---|---|---|---|---|---|---|\n"
            "| E01 | 1 | set_user_role | all | `input.args.user_role` | eq | manager | deny |\n\n"
            "## Candidate Reconciliation",
        )
    )

    result = run_cli(env)

    assert result.returncode == 0, result.stderr
    assert "Existing normalized rules: 1" in result.stdout
    assert "Duplicate: C01 / E01" in result.stdout
    assert "Additive: C02 / E01" in result.stdout


def test_checkpoint_cli_requires_an_explicit_phase():
    result = subprocess.run(
        [sys.executable, "-m", "smith.cli", "--flag", "security_analysis_checkpoint"],
        capture_output=True,
        text=True,
        env=dict(os.environ),
        timeout=30,
    )
    assert result.returncode == 1
    assert "requires --phase A, B, C, or D" in result.stderr


def test_guidance_merge_cli_uses_a_current_phase_d_checkpoint(tmp_path):
    env, paths = cli_environment(tmp_path)
    analysis, _, guidance, updated, _ = paths
    guidance.write_bytes(b"1. Existing rule")
    updated.write_bytes(b"2. New rule\n")
    state = analysis.parent / "analysis_state.json"
    state.write_text(
        json.dumps(
            {
                "schema": "security-analysis-state-v1",
                "latest_phase": "D",
                "inputs": {
                    "guidance": {
                        "path": str(guidance),
                        "sha256": hashlib.sha256(guidance.read_bytes()).hexdigest(),
                    },
                    "guidance_updated": {
                        "path": str(updated),
                        "sha256": hashlib.sha256(updated.read_bytes()).hexdigest(),
                    },
                },
                "phases": {
                    "D": {
                        "artifact": str(analysis),
                        "status": "PASS",
                        "sha256": hashlib.sha256(analysis.read_bytes()).hexdigest(),
                    }
                },
            }
        )
    )

    result = subprocess.run(
        [sys.executable, "-m", "smith.cli", "--flag", "guidance_merge"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert guidance.read_bytes() == b"1. Existing rule\n2. New rule\n"
    assert not updated.exists()
