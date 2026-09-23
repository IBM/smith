# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Offline tests for deterministic security-analysis checkpoints and merging."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from smith.tools.guidance_merge import merge_guidance, validate_addendum
from smith.tools.guidance_reconciliation import ReconciliationError
from smith.tools.security_analysis_checkpoint import (
    _validate_questionnaire,
    _validate_threat_model,
    checkpoint,
)

pytestmark = pytest.mark.unit


def table(headers: list[str], rows: list[list[str]]) -> str:
    return (
        "| "
        + " | ".join(headers)
        + " |\n|"
        + "|".join("---" for _ in headers)
        + "|\n"
        + "".join("| " + " | ".join(row) + " |\n" for row in rows)
    )


def architecture() -> str:
    return """\
# Architecture: sample
## Run Context
- Target agent: sample
## Layers
| Layer | File | Role | Inputs | Outputs | Current enforcement |
|---|---|---|---|---|---|
| MCP | server.py | tools | args | result | none |
## Trust Boundaries
## Runtime Subject Context
none
## Tool Arguments
| Field | Tool | Origin / influence | Disposition |
|---|---|---|---|
| `input.args.role` | set_role | Caller-influenced | Acts on |
## Prompt Inputs
none
## External Data
none
## Data Flow
caller → tool
## Enforcement Points
| Layer | Current | Available (OPA-interceptable) | Blind spots |
|---|---|---|---|
| MCP | none | tool call | none |
## Undeclared Fields
| Field | Referenced by guidance rule # | Declared by | Consequence |
|---|---|---|---|
## Phase Handoff
- Status: PASS
- Artifact schema: architecture-v2
"""


def test_checkpoint_writes_one_compact_machine_readable_state(tmp_path: Path):
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    artifact = analysis_dir / "architecture.md"
    artifact.write_text(architecture())
    state_path = analysis_dir / "analysis_state.json"
    tools = tmp_path / "tools.json"
    tools.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "set_role",
                        "input_schema": {"properties": {"role": {"type": "string"}}},
                    }
                ]
            }
        )
    )
    subjects = tmp_path / "subjects.json"
    subjects.write_text("{}")

    result = checkpoint(
        "A",
        analysis_dir,
        tools,
        subjects,
        tmp_path / "unused-catalog.json",
        state_path,
    )

    state = json.loads(state_path.read_text())
    assert result.startswith("Security analysis checkpoint A: PASS")
    assert state["latest_phase"] == "A"
    assert state["phases"]["A"]["tables"]["Tool Arguments"][0]["Tool"] == "set_role"
    assert (
        state["phases"]["A"]["sha256"]
        == hashlib.sha256(artifact.read_bytes()).hexdigest()
    )


def test_checkpoint_rejects_failed_handoff_without_writing_state(tmp_path: Path):
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    (analysis_dir / "architecture.md").write_text(
        architecture().replace("- Status: PASS", "- Status: FAIL")
    )
    state_path = analysis_dir / "analysis_state.json"

    with pytest.raises(ReconciliationError, match="status is not PASS"):
        checkpoint(
            "A",
            analysis_dir,
            tmp_path / "unused-tools.json",
            tmp_path / "unused-subjects.json",
            tmp_path / "unused-catalog.json",
            state_path,
        )

    assert not state_path.exists()


def test_questionnaire_requires_q1_through_q22_and_q13b():
    rows = [{"Q": f"Q{number}"} for number in range(1, 23)] + [{"Q": "Q13b"}]
    assert _validate_questionnaire({"tables": {"Answer Register": rows}}) == []

    errors = _validate_questionnaire(
        {"tables": {"Answer Register": [row for row in rows if row["Q"] != "Q13b"]}}
    )
    assert errors == ["Questionnaire is missing answers: Q13b"]


def test_threat_validation_checks_scenarios_citations_and_fields(tmp_path: Path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "threats": [
                    {"id": f"ASI{number:02d}", "attack_scenarios": ["scenario"]}
                    for number in range(1, 11)
                ]
            }
        )
    )
    tools = tmp_path / "tools.json"
    tools.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "set_role",
                        "input_schema": {"properties": {"role": {"type": "string"}}},
                    }
                ]
            }
        )
    )
    subjects = tmp_path / "subjects.json"
    subjects.write_text(json.dumps({"user_id": "Bob"}))
    state = {
        "tables": {
            "Attack Surfaces": [
                {"#": "#1", "Threat IDs / N/A": "T01"},
            ],
            "Evidence Index": [
                {"ID": "E01", "Source": "questionnaire Q1"},
            ],
            "Category Assessment": [
                {"ASI": f"ASI{number:02d}"} for number in range(1, 11)
            ],
            "Threat Instances": [
                {
                    "ID": "T01",
                    "ASI": "ASI01",
                    "Surface": "#1",
                    "Catalog basis": "1",
                    "Evidence": "E01",
                    "Concrete threat": "set_role input.args.role misuse",
                }
            ],
            "Scenario Coverage": [
                {
                    "ASI": f"ASI{number:02d}",
                    "Scenario": "1",
                    "Disposition": "T01" if number == 1 else "N/A — no substrate",
                }
                for number in range(1, 11)
            ],
        }
    }
    questionnaire_state = {
        "tables": {
            "Answer Register": [
                {"Q": "Q1", "Answer": "set_role", "Confidence": "confirmed"}
            ]
        }
    }

    assert (
        _validate_threat_model(state, catalog, questionnaire_state, tools, subjects)
        == []
    )

    state["tables"]["Scenario Coverage"].pop()
    errors = _validate_threat_model(
        state, catalog, questionnaire_state, tools, subjects
    )
    assert "Scenario Coverage is missing 1 catalog scenarios" in errors


def test_validate_addendum_checks_numbering_and_duplicates(tmp_path: Path):
    guidance = tmp_path / "guidance.txt"
    addendum = tmp_path / "guidance_updated.txt"
    guidance.write_text("1. Existing rule\n")
    addendum.write_text("3. New rule\n")
    with pytest.raises(ReconciliationError, match="numbering"):
        validate_addendum(guidance, addendum)

    addendum.write_text("2. existing rule\n")
    with pytest.raises(ReconciliationError, match="repeats existing guidance"):
        validate_addendum(guidance, addendum)


def test_explicit_merge_preserves_original_bytes_and_removes_addendum(tmp_path: Path):
    guidance = tmp_path / "guidance.txt"
    addendum = tmp_path / "guidance_updated.txt"
    enforcement = tmp_path / "owasp_policy_guidelines.md"
    state = tmp_path / "analysis_state.json"
    guidance.write_bytes(b"1. Existing rule")
    addendum.write_bytes(b"2. New rule\n")
    enforcement.write_text("validated")
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
                        "path": str(addendum),
                        "sha256": hashlib.sha256(addendum.read_bytes()).hexdigest(),
                    },
                },
                "phases": {
                    "D": {
                        "artifact": str(enforcement),
                        "status": "PASS",
                        "sha256": hashlib.sha256(enforcement.read_bytes()).hexdigest(),
                    }
                },
            }
        )
    )

    result = merge_guidance(guidance, addendum, state, enforcement)

    assert result.startswith("Merged 1 guidance rule")
    assert guidance.read_bytes() == b"1. Existing rule\n2. New rule\n"
    assert not addendum.exists()


def test_merge_rejects_a_stale_checkpoint_without_changes(tmp_path: Path):
    guidance = tmp_path / "guidance.txt"
    addendum = tmp_path / "guidance_updated.txt"
    enforcement = tmp_path / "owasp_policy_guidelines.md"
    state = tmp_path / "analysis_state.json"
    guidance.write_text("1. Existing rule\n")
    addendum.write_text("2. New rule\n")
    enforcement.write_text("changed")
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
                        "path": str(addendum),
                        "sha256": hashlib.sha256(addendum.read_bytes()).hexdigest(),
                    },
                },
                "phases": {
                    "D": {
                        "artifact": str(enforcement),
                        "status": "PASS",
                        "sha256": "stale",
                    }
                },
            }
        )
    )
    before = guidance.read_bytes(), addendum.read_bytes()

    with pytest.raises(ReconciliationError, match="changed after"):
        merge_guidance(guidance, addendum, state, enforcement)

    assert (guidance.read_bytes(), addendum.read_bytes()) == before
