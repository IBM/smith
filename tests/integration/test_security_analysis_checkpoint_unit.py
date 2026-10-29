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
    PHASES,
    _is_emitted_verdict,
    _surface_ids,
    _validate_addendum_contract,
    _validate_enforcement,
    _validate_questionnaire,
    _snapshot_errors,
    _validate_threat_model,
    _verdict_tokens,
    checkpoint,
    prepare_phase,
)
from smith.tools.security_catalog import load_catalog

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


def write_catalog(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "threats": [
                    {"id": f"ASI{number:02d}", "attack_scenarios": ["scenario"]}
                    for number in range(1, 11)
                ]
            }
        )
    )
    return path


def catalog_input(path: Path) -> dict:
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def architecture() -> dict:
    return {
        "schema": "architecture-v2",
        "status": "PASS",
        "title": "Architecture: sample",
        "sections": {
            "Run Context": "- Target agent: sample",
            "Trust Boundaries": "Runtime context and arguments are separate.",
            "Data Flow": "caller → tool",
        },
        "tables": {
            "Layers": [
                {
                    "Layer": "MCP",
                    "File": "server.py",
                    "Role": "tools",
                    "Inputs": "args",
                    "Outputs": "result",
                    "Current enforcement": "none",
                }
            ],
            "Runtime Subject Context": [],
            "Tool Arguments": [
                {
                    "Field": "`input.args.role`",
                    "Tool": "set_role",
                    "Origin / influence": "Caller-influenced",
                    "Disposition": "Acts on",
                }
            ],
            "Prompt Inputs": [],
            "External Data": [],
            "Enforcement Points": [
                {
                    "Layer": "MCP",
                    "Current": "none",
                    "Available (OPA-interceptable)": "tool call",
                    "Blind spots": "none",
                }
            ],
            "Undeclared Fields": [],
        },
        "handoff": {"Status": "PASS", "Artifact schema": "architecture-v2"},
    }


def test_checkpoint_writes_one_compact_machine_readable_state(tmp_path: Path):
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    source = analysis_dir / "architecture.json"
    source.write_text(json.dumps(architecture()))
    state_path = analysis_dir / "analysis_state.json"
    tools = tmp_path / "tools.json"
    tools.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "set_role",
                        "input_schema": {"properties": {"role": {"type": "string"}}},
                    },
                    {"name": "audit", "input_schema": {"properties": {}}},
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
    artifact = analysis_dir / "architecture.md"
    rendered = artifact.read_text()
    assert rendered.startswith("# Architecture: sample")
    assert "## Run Context" not in rendered
    assert "## Trust Boundaries" not in rendered
    assert "## Data Flow" not in rendered
    assert "Runtime context and arguments are separate." not in rendered
    assert "## Phase Handoff\n\n- Status: PASS" in rendered
    assert state["latest_phase"] == "A"
    assert state["phases"]["A"]["tables"]["Tool Arguments"][0]["Tool"] == "set_role"
    assert (
        state["phases"]["A"]["sha256"]
        == hashlib.sha256(artifact.read_bytes()).hexdigest()
    )


def test_checkpoint_rejects_failed_handoff_without_writing_state(tmp_path: Path):
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    failed = architecture()
    failed["status"] = "FAIL"
    failed["handoff"]["Status"] = "FAIL"
    (analysis_dir / "architecture.json").write_text(json.dumps(failed))
    state_path = analysis_dir / "analysis_state.json"
    state_path.write_text(json.dumps({"latest_phase": "D", "phases": {}}))
    stale_markdown = analysis_dir / "architecture.md"
    stale_markdown.write_text("stale successful result")
    stale_later_markdown = analysis_dir / "threat_model.md"
    stale_later_markdown.write_text("stale later result")

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
    assert not stale_markdown.exists()
    assert not stale_later_markdown.exists()


def test_prepare_phase_creates_structured_template(tmp_path: Path):
    result = prepare_phase("A", tmp_path)

    draft = json.loads((tmp_path / "architecture.json").read_text())
    assert result.startswith("Security analysis phase A draft:")
    assert draft["status"] == "DRAFT"
    assert "Tool Arguments" in draft["tables"]
    assert draft["columns"]["Tool Arguments"] == [
        "Field",
        "Tool",
        "Origin / influence",
        "Disposition",
    ]
    assert not (tmp_path / "architecture.md").exists()


def test_prepare_phase_replaces_an_existing_draft(tmp_path: Path):
    stale = architecture()
    stale["status"] = "PASS"
    stale["tables"]["Tool Arguments"] = [{"stale": "result"}]
    source = tmp_path / "architecture.json"
    source.write_text(json.dumps(stale))

    result = prepare_phase("A", tmp_path)

    draft = json.loads(source.read_text())
    assert result == f"Security analysis phase A draft: {source}"
    assert draft["status"] == "DRAFT"
    assert draft["tables"]["Tool Arguments"] == []


def test_prepare_phase_removes_current_and_later_outputs(tmp_path: Path):
    for phase, (stem, _, _) in PHASES.items():
        (tmp_path / f"{stem}.json").write_text(f"stale {phase} json")
        (tmp_path / f"{stem}.md").write_text(f"stale {phase} markdown")
        (tmp_path / f"{stem}.json.tmp").write_text("stale temporary")
        (tmp_path / f"{stem}.md.tmp").write_text("stale temporary")
    state_path = tmp_path / "analysis_state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema": "security-analysis-state-v1",
                "latest_phase": "D",
                "inputs": {"guidance_updated": {"sha256": "stale"}},
                "phases": {phase: {"phase": phase} for phase in PHASES},
            }
        )
    )

    prepare_phase("B", tmp_path)

    assert (tmp_path / "architecture.json").read_text() == "stale A json"
    assert (tmp_path / "architecture.md").read_text() == "stale A markdown"
    assert json.loads((tmp_path / "policy_guidance_questionnaire.json").read_text())[
        "status"
    ] == "DRAFT"
    for phase in ("B", "C", "D"):
        stem = PHASES[phase][0]
        assert not (tmp_path / f"{stem}.md").exists()
        assert not (tmp_path / f"{stem}.json.tmp").exists()
        assert not (tmp_path / f"{stem}.md.tmp").exists()
    assert not (tmp_path / "threat_model.json").exists()
    assert not (tmp_path / "owasp_policy_guidelines.json").exists()
    state = json.loads(state_path.read_text())
    assert state["latest_phase"] == "A"
    assert list(state["phases"]) == ["A"]
    assert state["inputs"]["guidance_updated"] is None


def test_prepare_phase_removes_stale_downstream_guidance_addendum(tmp_path: Path):
    guidance = tmp_path / "guidance.txt"
    addendum = tmp_path / "guidance_updated.txt"
    addendum.write_text("stale proposal")

    prepare_phase("B", tmp_path / "analysis", guidance)

    assert not addendum.exists()


def test_surface_ids_accept_numeric_and_hash_prefixed_forms():
    assert _surface_ids("1, #2") == {"#1", "#2"}


def test_compound_verdicts_preserve_blocking_and_emission_semantics():
    assert _verdict_tokens("Conflict / Additive") == {"conflict", "additive"}
    assert not _is_emitted_verdict("Conflict / Additive")
    assert _is_emitted_verdict("Novel / Additive")


def test_enforcement_accepts_compound_emission_and_blocks_compound_conflict(
    tmp_path: Path,
):
    tools = tmp_path / "tools.json"
    tools.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "send",
                        "input_schema": {
                            "properties": {
                                "format": {
                                    "type": "string",
                                    "enum": ["a", "b", "c", "d"],
                                }
                            }
                        },
                    }
                ]
            }
        )
    )
    subjects = tmp_path / "subjects.json"
    subjects.write_text("{}")
    base = {
        "Candidate ID": "C01",
        "Tool": "send",
        "Subject scope": "all",
        "Field expression": "input.args.format",
        "Operator": "in",
        "Values": "a, b",
        "Action": "deny",
        "Sources": "Q12",
        "Related rule": "—",
        "Verdict": "Novel / Additive",
    }
    existing = {
        "Existing ID": "E01",
        "Rule number": "1",
        "Tool": "send",
        "Subject scope": "all",
        "Field expression": "input.args.format",
        "Operator": "eq",
        "Values": "d",
        "Action": "deny",
    }
    state = {
        "tables": {
            "Threat Disposition": [],
            "Candidate Reconciliation": [base],
            "Existing Guidance Normalization": [existing],
            "Prior Proposal Reconciliation": [],
        }
    }
    threat_state = {"tables": {"Threat Instances": []}}

    assert _validate_enforcement(state, threat_state, tools, subjects, None) == []

    overlapping = dict(
        existing, **{"Existing ID": "E02", "Values": "b, c", "Operator": "in"}
    )
    state["tables"]["Existing Guidance Normalization"] = [existing, overlapping]
    state["tables"]["Candidate Reconciliation"][0]["Verdict"] = "Overlap / Additive"
    errors = _validate_enforcement(state, threat_state, tools, subjects, None)
    assert any("retains blocking verdict" in error for error in errors)


def test_addendum_counts_consolidated_guidance_groups(tmp_path: Path):
    guidance = tmp_path / "guidance.txt"
    guidance.write_text("1. Existing rule\n")
    guidance.with_name("guidance_updated.txt").write_text("2. Consolidated rule\n")
    candidate = {
        "Subject scope": "all",
        "Field expression": "input.args.value",
        "Operator": "eq",
        "Values": "blocked",
        "Action": "deny",
        "Sources": "Q12",
        "Related rule": "—",
        "Guidance group": "G01",
        "Verdict": "Novel / Additive",
    }
    state = {
        "tables": {
            "Candidate Reconciliation": [
                dict(candidate, **{"Candidate ID": "C01", "Tool": "tool_a"}),
                dict(candidate, **{"Candidate ID": "C02", "Tool": "tool_b"}),
            ]
        }
    }

    assert _validate_addendum_contract(state, guidance) == []


def checkpointed_through_c(tmp_path: Path, applicable: tuple[str, ...] = ()) -> dict:
    """Prepare and checkpoint Phases A-C; return the paths later steps need."""
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    (analysis_dir / "architecture.json").write_text(json.dumps(architecture()))
    catalog = write_catalog(tmp_path / "catalog.json")
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

    prepare_phase("B", analysis_dir)
    questionnaire_path = analysis_dir / "policy_guidance_questionnaire.json"
    questionnaire = json.loads(questionnaire_path.read_text())
    questionnaire["status"] = "PASS"
    questionnaire["handoff"]["Status"] = "PASS"
    for row in questionnaire["tables"]["Answer Register"]:
        row["Answer"] = "none"
        row["Confidence"] = "[derived from guidance.txt]"
    questionnaire_path.write_text(json.dumps(questionnaire))

    prepare_phase("C", analysis_dir, catalog=catalog)
    threat_path = analysis_dir / "threat_model.json"
    threat = json.loads(threat_path.read_text())
    threat["status"] = "PASS"
    threat["handoff"]["Status"] = "PASS"
    threat["tables"]["Category Assessment"] = [
        {
            "ASI": f"ASI{number:02d}",
            "Name": f"Category {number}",
            "Applicability": "Yes" if f"ASI{number:02d}" in applicable else "No",
            "OWASP summary": "Not applicable",
            "Boundary (optional)": "—",
        }
        for number in range(1, 11)
    ]
    threat["tables"]["Scenario Coverage"] = [
        {
            "ASI": f"ASI{number:02d}",
            "Scenario": "1",
            "Disposition": "N/A — no substrate",
        }
        for number in range(1, 11)
    ]
    threat_path.write_text(json.dumps(threat))
    paths = {
        "analysis_dir": analysis_dir,
        "catalog": catalog,
        "tools": tools,
        "subjects": subjects,
        "state": analysis_dir / "analysis_state.json",
    }
    run_checkpoint("C", paths)
    return paths


def run_checkpoint(phase: str, paths: dict, guidance: Path | None = None) -> str:
    return checkpoint(
        phase,
        paths["analysis_dir"],
        paths["tools"],
        paths["subjects"],
        paths["catalog"],
        paths["state"],
        guidance,
    )


def prepare_passing_d(paths: dict) -> Path:
    prepare_phase("D", paths["analysis_dir"], catalog=paths["catalog"])
    enforcement_path = paths["analysis_dir"] / "owasp_policy_guidelines.json"
    enforcement = json.loads(enforcement_path.read_text())
    enforcement["status"] = "PASS"
    enforcement["handoff"]["Status"] = "PASS"
    enforcement_path.write_text(json.dumps(enforcement))
    guidance = paths["analysis_dir"].parent / "guidance.txt"
    guidance.write_text("1. Existing rule\n")
    return guidance


def reword_scenario(catalog: Path, asi: str, text: str) -> None:
    data = json.loads(catalog.read_text())
    for entry in data["threats"]:
        if entry["id"] == asi:
            entry["attack_scenarios"][0] = text
    catalog.write_text(json.dumps(data))


def test_checkpoint_runs_all_phases_from_structured_sources(tmp_path: Path):
    paths = checkpointed_through_c(tmp_path)
    guidance = prepare_passing_d(paths)

    result = run_checkpoint("D", paths, guidance)

    analysis_dir = paths["analysis_dir"]
    assert result.startswith("Security analysis checkpoint D: PASS")
    for name in (
        "architecture.md",
        "policy_guidance_questionnaire.md",
        "threat_model.md",
        "owasp_policy_guidelines.md",
    ):
        assert (analysis_dir / name).is_file()
    inputs = json.loads(paths["state"].read_text())["inputs"]
    assert inputs["owasp_catalog"] == catalog_input(paths["catalog"]), (
        "the run must record which catalog bytes it validated against"
    )
    for phase in ("C", "D"):
        snapshot = analysis_dir / f"owasp_catalog_{phase}.json"
        assert inputs[f"owasp_catalog_{phase}"] == catalog_input(snapshot)


# --- catalog snapshots and freshness ------------------------------------------


def test_prepare_c_snapshot_has_discovery_fields_only(tmp_path: Path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "threats": [
                    {
                        "id": f"ASI{number:02d}",
                        "name": f"Category {number}",
                        "attack_scenarios": ["scenario"],
                        "mitigations": ["secret mitigation"],
                        "impact": "secret impact",
                    }
                    for number in range(1, 11)
                ]
            }
        )
    )

    result = prepare_phase("C", tmp_path, catalog=catalog)

    snapshot = json.loads((tmp_path / "owasp_catalog_C.json").read_text())
    assert "OWASP catalog snapshot:" in result
    assert [entry["id"] for entry in snapshot["threats"]] == [
        f"ASI{number:02d}" for number in range(1, 11)
    ]
    assert "secret" not in json.dumps(snapshot), (
        "Phase C must not be able to read mitigations or impact"
    )


def test_prepare_d_snapshot_holds_exactly_the_applicable_categories(tmp_path: Path):
    paths = checkpointed_through_c(tmp_path, applicable=("ASI02", "ASI06"))

    prepare_phase("D", paths["analysis_dir"], catalog=paths["catalog"])

    snapshot = json.loads(
        (paths["analysis_dir"] / "owasp_catalog_D.json").read_text()
    )
    assert [entry["id"] for entry in snapshot["threats"]] == ["ASI02", "ASI06"]
    assert "attack_scenarios" not in snapshot["threats"][0]


def test_prepare_d_requires_a_checkpointed_phase_c(tmp_path: Path):
    catalog = write_catalog(tmp_path / "catalog.json")

    with pytest.raises(ReconciliationError, match="passing Phase C checkpoint"):
        prepare_phase("D", tmp_path / "analysis", catalog=catalog)

    assert not (tmp_path / "analysis" / "owasp_catalog_D.json").exists()


def test_reworded_scenario_fails_the_phase_d_checkpoint(tmp_path: Path):
    """Acceptance test: the per-ASI count check alone passes this edit."""
    paths = checkpointed_through_c(tmp_path)
    guidance = prepare_passing_d(paths)
    reword_scenario(paths["catalog"], "ASI03", "reworded")

    with pytest.raises(
        ReconciliationError, match=r"since Phase C was prepared \(ASI03#1\)"
    ):
        run_checkpoint("D", paths, guidance)

    assert not (paths["analysis_dir"] / "owasp_policy_guidelines.md").exists(), (
        "a stale run must not render artifacts"
    )


def test_catalog_edit_between_prepare_and_checkpoint_fails(tmp_path: Path):
    catalog = write_catalog(tmp_path / "catalog.json")
    analysis_dir = tmp_path / "analysis"
    prepare_phase("C", analysis_dir, catalog=catalog)
    reword_scenario(catalog, "ASI01", "edited mid-phase")
    snapshot = load_catalog(catalog)

    errors = _snapshot_errors(["A", "B", "C"], analysis_dir, snapshot, {})

    assert len(errors) == 1 and "ASI01#1" in errors[0]


def test_mitigation_edit_fails_phase_d_but_not_phase_c(tmp_path: Path):
    paths = checkpointed_through_c(tmp_path, applicable=("ASI02",))
    prepare_passing_d(paths)
    data = json.loads(paths["catalog"].read_text())
    data["threats"][1]["mitigations"] = ["new mitigation"]
    paths["catalog"].write_text(json.dumps(data))
    catalog = load_catalog(paths["catalog"])
    threat_state = json.loads(paths["state"].read_text())["phases"]

    errors = _snapshot_errors(
        ["A", "B", "C", "D"], paths["analysis_dir"], catalog, threat_state
    )

    assert errors == [
        "OWASP catalog changed since Phase D was prepared (ASI02 mitigations); "
        "re-run smith --flag security_analysis_checkpoint --phase D --prepare "
        "and redo the phase"
    ]


def test_edit_outside_the_applicable_set_does_not_fail_phase_d(tmp_path: Path):
    paths = checkpointed_through_c(tmp_path, applicable=("ASI02",))
    guidance = prepare_passing_d(paths)
    data = json.loads(paths["catalog"].read_text())
    data["threats"][2]["mitigations"] = ["ASI03 is not applicable"]
    paths["catalog"].write_text(json.dumps(data))

    assert run_checkpoint("D", paths, guidance).startswith(
        "Security analysis checkpoint D: PASS"
    )


def test_missing_snapshot_names_the_prepare_remediation(tmp_path: Path):
    paths = checkpointed_through_c(tmp_path)
    (paths["analysis_dir"] / "owasp_catalog_C.json").unlink()

    with pytest.raises(ReconciliationError, match="--phase C --prepare"):
        run_checkpoint("C", paths)


def test_reset_removes_current_and_later_catalog_snapshots(tmp_path: Path):
    paths = checkpointed_through_c(tmp_path)
    prepare_passing_d(paths)
    analysis_dir = paths["analysis_dir"]

    prepare_phase("C", analysis_dir)

    assert not (analysis_dir / "owasp_catalog_C.json").exists()
    assert not (analysis_dir / "owasp_catalog_D.json").exists()


def test_questionnaire_requires_q1_through_q22_and_q13b():
    rows = [{"Q": f"Q{number}"} for number in range(1, 23)] + [{"Q": "Q13b"}]
    assert _validate_questionnaire({"tables": {"Answer Register": rows}}) == []

    errors = _validate_questionnaire(
        {"tables": {"Answer Register": [row for row in rows if row["Q"] != "Q13b"]}}
    )
    assert errors == ["Questionnaire is missing answers: Q13b"]


def test_threat_validation_handles_numeric_surfaces_and_multi_tool_fields(
    tmp_path: Path,
):
    catalog = load_catalog(write_catalog(tmp_path / "catalog.json"))
    tools = tmp_path / "tools.json"
    tools.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "set_role",
                        "input_schema": {"properties": {"role": {"type": "string"}}},
                    },
                    {"name": "audit", "input_schema": {"properties": {}}},
                ]
            }
        )
    )
    subjects = tmp_path / "subjects.json"
    subjects.write_text(json.dumps({"user_id": "Bob"}))
    state = {
        "tables": {
            "Attack Surfaces": [
                {"#": "1", "Threat IDs / N/A": "T01"},
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
                    "Surface": "1",
                    "Catalog basis": "1",
                    "Evidence": "E01",
                    "Concrete threat": "set_role input.args.role misuse before audit",
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


def test_validate_addendum_preserves_sectioned_markdown_style(tmp_path: Path):
    guidance = tmp_path / "guidance.txt"
    addendum = tmp_path / "guidance_updated.txt"
    guidance.write_text("# Scenario\n\n## Rules\n\n- Existing rule\n")
    addendum.write_text("- First new rule\n- Second new rule\n")

    assert validate_addendum(guidance, addendum) == [
        (1, "First new rule"),
        (2, "Second new rule"),
    ]

    addendum.write_text("2. Numbered rule\n")
    with pytest.raises(ReconciliationError, match="sectioned Markdown style"):
        validate_addendum(guidance, addendum)

    addendum.write_text("## Addendum — Enforcement Mapping (Phase D)\n\n- New rule\n")
    with pytest.raises(ReconciliationError, match="without headings or phase metadata"):
        validate_addendum(guidance, addendum)


def test_validate_addendum_preserves_plain_line_style(tmp_path: Path):
    guidance = tmp_path / "guidance.txt"
    addendum = tmp_path / "guidance_updated.txt"
    guidance.write_text("Existing rule one.\nExisting rule two.\n")
    addendum.write_text("New rule one.\nNew rule two.\n")

    assert validate_addendum(guidance, addendum) == [
        (1, "New rule one."),
        (2, "New rule two."),
    ]

    addendum.write_text("- Bulleted rule\n")
    with pytest.raises(ReconciliationError, match="plain one-rule-per-line style"):
        validate_addendum(guidance, addendum)


def test_explicit_merge_preserves_original_bytes_and_removes_addendum(tmp_path: Path):
    guidance = tmp_path / "guidance.txt"
    addendum = tmp_path / "guidance_updated.txt"
    enforcement = tmp_path / "owasp_policy_guidelines.md"
    state = tmp_path / "analysis_state.json"
    catalog = write_catalog(tmp_path / "catalog.json")
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
                    "owasp_catalog": catalog_input(catalog),
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

    result = merge_guidance(guidance, addendum, state, enforcement, catalog)

    assert result.startswith("Merged 1 guidance rule")
    assert guidance.read_bytes() == b"1. Existing rule\n2. New rule\n"
    assert not addendum.exists()


def test_explicit_merge_separates_markdown_addendum(tmp_path: Path):
    guidance = tmp_path / "guidance.txt"
    addendum = tmp_path / "guidance_updated.txt"
    enforcement = tmp_path / "owasp_policy_guidelines.md"
    state = tmp_path / "analysis_state.json"
    catalog = write_catalog(tmp_path / "catalog.json")
    guidance.write_text("# Scenario\n\n## Rules\n\n- Existing rule\n")
    addendum.write_text("- New rule\n")
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
                    "owasp_catalog": catalog_input(catalog),
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

    result = merge_guidance(guidance, addendum, state, enforcement, catalog)

    assert result.startswith("Merged 1 guidance rule")
    assert guidance.read_text() == (
        "# Scenario\n\n## Rules\n\n- Existing rule\n\n- New rule\n"
    )
    assert not addendum.exists()


def test_merge_rejects_a_stale_checkpoint_without_changes(tmp_path: Path):
    guidance = tmp_path / "guidance.txt"
    addendum = tmp_path / "guidance_updated.txt"
    enforcement = tmp_path / "owasp_policy_guidelines.md"
    state = tmp_path / "analysis_state.json"
    catalog = write_catalog(tmp_path / "catalog.json")
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
                    "owasp_catalog": catalog_input(catalog),
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
        merge_guidance(guidance, addendum, state, enforcement, catalog)

    assert (guidance.read_bytes(), addendum.read_bytes()) == before


def test_merge_rejects_guidance_derived_from_an_older_catalog(tmp_path: Path):
    guidance = tmp_path / "guidance.txt"
    addendum = tmp_path / "guidance_updated.txt"
    enforcement = tmp_path / "owasp_policy_guidelines.md"
    state = tmp_path / "analysis_state.json"
    catalog = write_catalog(tmp_path / "catalog.json")
    guidance.write_text("1. Existing rule\n")
    addendum.write_text("2. New rule\n")
    enforcement.write_text("validated")
    state.write_text(
        json.dumps(
            {
                "schema": "security-analysis-state-v1",
                "latest_phase": "D",
                "inputs": {
                    "guidance": catalog_input(guidance),
                    "guidance_updated": catalog_input(addendum),
                    "owasp_catalog": catalog_input(catalog),
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
    reword_scenario(catalog, "ASI01", "reworded after Phase D")
    before = guidance.read_bytes(), addendum.read_bytes()

    with pytest.raises(ReconciliationError, match="catalog.json changed after"):
        merge_guidance(guidance, addendum, state, enforcement, catalog)

    assert (guidance.read_bytes(), addendum.read_bytes()) == before
