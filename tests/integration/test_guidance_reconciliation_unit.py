# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Offline unit tests for guidance candidate reconciliation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from smith.tools.guidance_reconciliation import (
    ReconciliationError,
    analyze_existing_relationships,
    analyze_relationships,
    load_subject_schema,
    load_tool_schema,
    parse_candidate_table,
    parse_existing_guidance_table,
    reconcile,
    suggest_exact_unions,
    validate_candidates,
)

pytestmark = pytest.mark.unit


HEADER = """\
# Assessment

## Existing Guidance Normalization

| Existing ID | Rule number | Tool | Subject scope | Field expression | Operator | Values | Action |
|---|---|---|---|---|---|---|---|

## Candidate Reconciliation

| Candidate ID | Tool | Subject scope | Field expression | Operator | Values | Action | Sources | Related rule | Verdict |
|---|---|---|---|---|---|---|---|---|---|
"""


def row(
    candidate_id: str,
    *,
    tool: str = "set_user_role",
    scope: str = "all",
    field: str = "input.args.user_role",
    operator: str = "eq",
    values: str = "manager",
    action: str = "deny",
) -> str:
    return (
        f"| {candidate_id} | {tool} | {scope} | `{field}` | {operator} | "
        f"{values} | {action} | T01 | — | Novel |\n"
    )


@pytest.fixture
def schemas(tmp_path: Path):
    tools_path = tmp_path / "tool_definitions.json"
    tools_path.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "set_user_role",
                        "parameters": [
                            {
                                "name": "user_role",
                                "type": "string",
                                "enum": ["employee", "manager"],
                            }
                        ],
                        "input_schema": {
                            "properties": {
                                "user_role": {
                                    "type": "string",
                                    "enum": ["employee", "manager"],
                                }
                            }
                        },
                    },
                    {
                        "name": "view_team_compensation",
                        "input_schema": {
                            "properties": {"select_fields": {"type": "array"}}
                        },
                    },
                ]
            }
        )
    )
    subjects_path = tmp_path / "system_vars.json"
    subjects_path.write_text(
        json.dumps({"roles": ["employee", "manager"], "user_id": "Bob"})
    )
    return load_tool_schema(tools_path), load_subject_schema(subjects_path)


def test_parses_normalized_markdown_table():
    candidates = parse_candidate_table(
        HEADER
        + row("C01", values="{manager, employee}", operator="in")
        + "\n## Phase Handoff\n"
    )
    assert len(candidates) == 1
    assert candidates[0].candidate_id == "C01"
    assert candidates[0].values == ("employee", "manager")
    assert candidates[0].subject_scope is None


def test_parses_grouped_candidate_table_rendered_by_checkpoint():
    markdown = HEADER.replace(
        "Related rule | Verdict",
        "Related rule | Guidance group | Verdict",
    ).replace(
        "|---|---|---|---|---|---|---|---|---|---|",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    )
    markdown += (
        "| C01 | set_user_role | all | `input.args.user_role` | eq | manager | "
        "deny | T01 | — | G01 | Novel |\n"
    )

    candidates = parse_candidate_table(markdown)

    assert candidates[0].guidance_group == "G01"


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("# No table", "section is missing"),
        (
            "## Candidate Reconciliation\n\n| Candidate ID | Tool |\n|---|---|\n",
            "table is missing or malformed",
        ),
    ],
)
def test_rejects_missing_or_malformed_candidate_table(content, message):
    with pytest.raises(ReconciliationError, match=message):
        parse_candidate_table(content)


def test_detects_exact_duplicates_and_coverage(schemas):
    candidates = parse_candidate_table(
        HEADER
        + row("C01", operator="in", values="{employee, manager}")
        + row("C02", operator="eq", values="manager")
        + row("C03", operator="eq", values="manager")
    )
    tools, subjects = schemas
    assert all(item.valid for item in validate_candidates(candidates, tools, subjects))
    relationships = analyze_relationships(candidates)
    assert any(
        item.verdict == "Covered" and item.left == "C01" and item.right == "C02"
        for item in relationships
    )
    assert any(
        item.verdict == "Duplicate" and {item.left, item.right} == {"C02", "C03"}
        for item in relationships
    )


def test_detects_additive_values_and_suggests_union():
    candidates = parse_candidate_table(
        HEADER + row("C01", values="employee") + row("C02", values="manager")
    )
    relationships = analyze_relationships(candidates)
    assert [(item.verdict, item.left, item.right) for item in relationships] == [
        ("Additive", "C01", "C02")
    ]
    assert suggest_exact_unions(candidates)[0].operator == "in"
    assert suggest_exact_unions(candidates)[0].values == ("employee", "manager")


def test_detects_overlap_and_conflict():
    overlapping = parse_candidate_table(
        HEADER
        + row("C01", operator="in", values="{employee, manager}")
        + row("C02", operator="in", values="{manager, guest}")
    )
    assert analyze_relationships(overlapping)[0].verdict == "Overlap"

    conflicting = parse_candidate_table(
        HEADER
        + row("C01", values="manager")
        + row("C02", values="manager", action="allow")
    )
    assert analyze_relationships(conflicting)[0].verdict == "Conflict"


def test_simplifies_documented_eq_and_not_in_union():
    candidates = parse_candidate_table(
        HEADER
        + row("C01", operator="eq", values="manager")
        + row("C02", operator="not_in", values="{employee, manager}")
    )
    suggestion = suggest_exact_unions(candidates)
    assert len(suggestion) == 1
    assert suggestion[0].candidate_ids == ("C01", "C02")
    assert suggestion[0].operator == "neq"
    assert suggestion[0].values == ("employee",)


def test_detects_candidate_that_broadens_an_existing_rule():
    markdown = HEADER.replace(
        "\n## Candidate Reconciliation",
        "\n| E01 | 2 | set_user_role | all | `input.args.user_role` | eq | employee | deny |\n\n## Candidate Reconciliation",
    ) + row("C01", operator="not_in", values="manager")
    existing = parse_existing_guidance_table(markdown)
    candidates = parse_candidate_table(markdown)

    relationships = analyze_existing_relationships(candidates, existing)

    assert len(relationships) == 1
    assert relationships[0].verdict == "Additive"
    assert "emit only the uncovered difference" in relationships[0].detail


def test_rejects_unknown_tool_and_tool_specific_argument(schemas):
    candidates = parse_candidate_table(
        HEADER
        + row("C01", tool="missing_tool")
        + row(
            "C02",
            tool="view_team_compensation",
            field="input.args.user_role",
        )
    )
    findings = validate_candidates(candidates, *schemas)
    assert "unknown tool" in findings[0].messages[0]
    assert "not declared for tool" in findings[1].messages[0]


def test_validates_subject_fields_against_system_vars(schemas):
    candidates = parse_candidate_table(
        HEADER
        + row("C01", field="input.extensions.subject.roles", values="manager")
        + row("C02", field="input.extensions.subject.undeclared", values="manager")
    )
    findings = validate_candidates(candidates, *schemas)
    assert findings[0].valid
    assert not findings[1].valid
    assert "system_vars.json" in findings[1].messages[0]


def test_reconcile_is_read_only_and_reports_text_duplicate(tmp_path: Path, schemas):
    analysis = tmp_path / "owasp_policy_guidelines.md"
    tools_path = tmp_path / "tool_definitions.json"
    subjects_path = tmp_path / "system_vars.json"
    guidance = tmp_path / "guidance.txt"
    updated = tmp_path / "guidance_updated.txt"
    analysis.write_text(HEADER + row("C01"))
    tools, subjects = schemas
    tools_path.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": name,
                        "input_schema": {"properties": fields},
                    }
                    for name, fields in tools.items()
                ]
            }
        )
    )
    subjects_path.write_text(json.dumps(subjects))
    guidance.write_text("1. Block role escalation\n")
    updated.write_text("15. block role escalation\n")
    paths = (analysis, tools_path, subjects_path, guidance, updated)
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}

    report = reconcile(analysis, tools_path, subjects_path, guidance, updated)

    assert "guidance.txt:1 = guidance_updated.txt:1" in report
    assert "no files were modified" in report
    assert before == {
        path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths
    }
