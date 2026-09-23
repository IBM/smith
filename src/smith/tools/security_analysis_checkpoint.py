# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Validate security-analysis artifacts and persist a compact phase handoff."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from smith.tools.guidance_reconciliation import (
    ReconciliationError,
    _split_markdown_row,
    analyze_existing_relationships,
    load_subject_schema,
    load_tool_schema,
    parse_candidate_table,
    parse_existing_guidance_table,
    validate_candidates,
    validate_existing_rule_numbers,
)

PHASES = {
    "A": ("architecture.md", "architecture-v2"),
    "B": ("policy_guidance_questionnaire.md", "questionnaire-v2"),
    "C": ("threat_model.md", "threat-model-v3"),
    "D": ("owasp_policy_guidelines.md", "enforcement-mapping-v8"),
}
REQUIRED_TABLES = {
    "A": {
        "Layers",
        "Tool Arguments",
        "Enforcement Points",
    },
    "B": {"Answer Register"},
    "C": {
        "Attack Surfaces",
        "Evidence Index",
        "Category Assessment",
        "Threat Instances",
        "Scenario Coverage",
    },
    "D": {
        "Threat Disposition",
        "OWASP Top 10 for Agentic AI Security — Scope Assessment",
        "Gap Register",
        "Input Schema",
        "Rules",
        "Candidate Reconciliation",
        "Existing Guidance Normalization",
        "Prior Proposal Reconciliation",
    },
}
REQUIRED_SECTIONS = {
    "A": {
        "Run Context",
        "Layers",
        "Trust Boundaries",
        "Runtime Subject Context",
        "Tool Arguments",
        "Prompt Inputs",
        "External Data",
        "Data Flow",
        "Enforcement Points",
        "Undeclared Fields",
        "Phase Handoff",
    },
    "B": REQUIRED_TABLES["B"] | {"Phase Handoff"},
    "C": REQUIRED_TABLES["C"] | {"Phase Handoff"},
    "D": REQUIRED_TABLES["D"]
    | {"Architecture Summary", "Policy Rules (OPA scope only)", "Phase Handoff"},
}
BLOCKING_VERDICTS = {"overlap", "conflict", "contradictory correction"}


def _sections(markdown: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^#{2,3}\s+(.+?)\s*$", markdown))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        result[match.group(1).strip()] = markdown[match.end() : end]
    return result


def _table(section: str) -> list[dict[str, str]] | None:
    lines = [line for line in section.splitlines() if line.strip()]
    for index in range(len(lines) - 1):
        if not lines[index].lstrip().startswith("|"):
            continue
        headers = _split_markdown_row(lines[index])
        separators = _split_markdown_row(lines[index + 1])
        if len(headers) != len(separators) or not all(
            re.fullmatch(r":?-{3,}:?", cell) for cell in separators
        ):
            continue
        rows: list[dict[str, str]] = []
        for line in lines[index + 2 :]:
            if not line.lstrip().startswith("|"):
                break
            cells = _split_markdown_row(line)
            if len(cells) != len(headers):
                raise ReconciliationError("Markdown table has an inconsistent row")
            if any("<" in cell and ">" in cell for cell in cells):
                continue
            rows.append(dict(zip(headers, cells)))
        return rows
    return None


def _handoff(section: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in section.splitlines():
        match = re.match(r"\s*-\s*([^:]+):\s*(.+?)\s*$", line)
        if match:
            result[match.group(1).strip()] = match.group(2).strip()
    return result


def _column(row: dict[str, str], name: str) -> str:
    for key, value in row.items():
        if key.casefold() == name.casefold():
            return value
    return ""


def _ids(value: str, prefix: str) -> set[str]:
    if prefix == "#":
        return set(re.findall(r"(?<!\d)#\d+\b", value))
    if prefix == "Q":
        return set(re.findall(r"\bQ\d+b?\b", value))
    return set(re.findall(rf"\b{re.escape(prefix)}\d+\b", value))


def _validate_phase_shape(
    phase: str, path: Path, expected_schema: str
) -> tuple[dict[str, Any], list[str]]:
    if not path.is_file():
        return {}, [f"Phase {phase} artifact is missing: {path}"]
    text = path.read_text(encoding="utf-8")
    sections = _sections(text)
    errors: list[str] = []
    handoff = _handoff(sections.get("Phase Handoff", ""))
    missing_sections = sorted(REQUIRED_SECTIONS[phase] - set(sections))
    if missing_sections:
        errors.append(
            f"Phase {phase} required sections are missing: {', '.join(missing_sections)}"
        )
    if handoff.get("Status") != "PASS":
        errors.append(f"Phase {phase} handoff status is not PASS")
    if handoff.get("Artifact schema") != expected_schema:
        errors.append(
            f"Phase {phase} schema is {handoff.get('Artifact schema', 'missing')!r}; "
            f"expected {expected_schema!r}"
        )
    tables: dict[str, list[dict[str, str]]] = {}
    for name, content in sections.items():
        rows = _table(content)
        if rows is not None:
            tables[name] = rows
    for name in REQUIRED_TABLES[phase] - set(tables):
        errors.append(f"Phase {phase} required table {name!r} is missing")
    return {
        "artifact": str(path),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "schema": expected_schema,
        "status": handoff.get("Status", "missing"),
        "handoff": handoff,
        "tables": tables,
    }, errors


def _validate_questionnaire(state: dict[str, Any]) -> list[str]:
    rows = state["tables"].get("Answer Register", [])
    ids = [_column(row, "Q") or _column(row, "ID") for row in rows]
    found = set(ids)
    expected = {f"Q{number}" for number in range(1, 23)} | {"Q13b"}
    missing = sorted(
        expected - found,
        key=lambda item: (int(re.match(r"Q(\d+)", item).group(1)), item),
    )
    extra = sorted(found - expected)
    errors = []
    if missing:
        errors.append(f"Questionnaire is missing answers: {', '.join(missing)}")
    if extra:
        errors.append(f"Questionnaire has unknown answer IDs: {', '.join(extra)}")
    if len(ids) != len(found):
        errors.append("Questionnaire contains duplicate answer IDs")
    return errors


def _canonical_field(value: str) -> str:
    match = re.search(
        r"input\.(?:args|extensions\.subject)\.[A-Za-z_][A-Za-z0-9_.]*", value
    )
    return match.group(0) if match else ""


def _validate_architecture(
    state: dict[str, Any], tools_path: Path, subjects_path: Path
) -> list[str]:
    tools = load_tool_schema(tools_path)
    subjects = load_subject_schema(subjects_path)
    errors: list[str] = []
    for row in state["tables"].get("Tool Arguments", []):
        field = _canonical_field(_column(row, "Field"))
        tool = _column(row, "Tool").strip("`")
        name = field.removeprefix("input.args.").split(".", 1)[0]
        if tool not in tools:
            errors.append(f"Architecture Tool Arguments cites unknown tool {tool!r}")
        elif not field.startswith("input.args.") or name not in tools[tool]:
            errors.append(
                f"Architecture cites undeclared argument {field or _column(row, 'Field')}"
            )
    for row in state["tables"].get("Runtime Subject Context", []):
        field = _canonical_field(_column(row, "Field"))
        name = field.removeprefix("input.extensions.subject.").split(".", 1)[0]
        if not field.startswith("input.extensions.subject.") or name not in subjects:
            errors.append(
                f"Architecture cites undeclared subject field {field or _column(row, 'Field')}"
            )
    return errors


def _catalog_scenario_counts(path: Path) -> dict[str, int]:
    if not path.is_file():
        raise ReconciliationError(f"OWASP catalog is missing: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        threats = data["threats"]
        return {
            entry["id"]: len(entry.get("attack_scenarios", [])) for entry in threats
        }
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ReconciliationError(f"OWASP catalog is malformed: {path}: {exc}") from exc


def _validate_threat_model(
    state: dict[str, Any],
    catalog: Path,
    questionnaire_state: dict[str, Any],
    tools_path: Path,
    subjects_path: Path,
) -> list[str]:
    tables = state["tables"]
    errors: list[str] = []
    surfaces = tables.get("Attack Surfaces", [])
    evidence = tables.get("Evidence Index", [])
    categories = tables.get("Category Assessment", [])
    threats = tables.get("Threat Instances", [])
    coverage = tables.get("Scenario Coverage", [])
    surface_ids = {_column(row, "#") for row in surfaces}
    surfaces_by_id = {_column(row, "#"): row for row in surfaces}
    evidence_ids = {_column(row, "ID") for row in evidence}
    threat_ids = {_column(row, "ID") for row in threats}
    category_ids = {_column(row, "ASI") for row in categories}
    expected_categories = {f"ASI{number:02d}" for number in range(1, 11)}
    if category_ids != expected_categories:
        errors.append(
            "Category Assessment must contain ASI01 through ASI10 exactly once"
        )
    if len(categories) != len(category_ids):
        errors.append("Category Assessment contains duplicate ASI rows")
    if len(evidence) != len(evidence_ids):
        errors.append("Evidence Index contains duplicate IDs")
    if len(threats) != len(threat_ids):
        errors.append("Threat Instances contains duplicate IDs")
    if len(surfaces) != len(surface_ids):
        errors.append("Attack Surfaces contains duplicate IDs")
    scenario_counts = _catalog_scenario_counts(catalog)
    answer_rows = questionnaire_state["tables"].get("Answer Register", [])
    answers = {_column(row, "Q"): row for row in answer_rows}
    tools = load_tool_schema(tools_path)
    subjects = load_subject_schema(subjects_path)
    for row in evidence:
        evidence_id = _column(row, "ID") or "unknown evidence"
        source = _column(row, "Source")
        for question in _ids(source, "Q"):
            answer = answers.get(question)
            if not answer:
                errors.append(
                    f"{evidence_id} cites missing questionnaire answer {question}"
                )
            elif (
                not _column(answer, "Answer").strip()
                or "low confidence" in _column(answer, "Confidence").casefold()
            ):
                errors.append(
                    f"{evidence_id} cites unusable questionnaire answer {question}"
                )
    for row in threats:
        threat_id = _column(row, "ID") or "unknown threat"
        unknown_surfaces = _ids(_column(row, "Surface"), "#") - surface_ids
        unknown_evidence = _ids(_column(row, "Evidence"), "E") - evidence_ids
        if unknown_surfaces:
            errors.append(
                f"{threat_id} cites unknown surfaces: {sorted(unknown_surfaces)}"
            )
        if unknown_evidence:
            errors.append(
                f"{threat_id} cites unknown evidence: {sorted(unknown_evidence)}"
            )
        if not _ids(_column(row, "Evidence"), "E"):
            errors.append(f"{threat_id} has no Evidence Index citation")
        asi = _column(row, "ASI")
        scenario_indexes = {
            int(value)
            for value in re.findall(r"\b\d+\b", _column(row, "Catalog basis"))
        }
        if scenario_indexes and any(
            value < 1 or value > scenario_counts.get(asi, 0)
            for value in scenario_indexes
        ):
            errors.append(f"{threat_id} cites an unknown {asi} catalog scenario")
        cited_surface_rows = [
            surfaces_by_id[surface_id]
            for surface_id in _ids(_column(row, "Surface"), "#")
            if surface_id in surfaces_by_id
        ]
        row_text = (
            " ".join(row.values())
            + " "
            + " ".join(
                value for surface in cited_surface_rows for value in surface.values()
            )
        )
        tool_names = {
            name for name in tools if re.search(rf"\b{re.escape(name)}\b", row_text)
        }
        for field in re.findall(r"input\.args\.([A-Za-z_][A-Za-z0-9_]*)", row_text):
            if not tool_names:
                errors.append(
                    f"{threat_id} cites input.args.{field} without a governing tool"
                )
            elif any(field not in tools[name] for name in tool_names):
                errors.append(
                    f"{threat_id} cites undeclared tool argument input.args.{field}"
                )
        for field in re.findall(
            r"input\.extensions\.subject\.([A-Za-z_][A-Za-z0-9_]*)", row_text
        ):
            if field not in subjects:
                errors.append(
                    f"{threat_id} cites undeclared subject field input.extensions.subject.{field}"
                )
    for row in surfaces:
        surface_id = _column(row, "#")
        disposition = _column(row, "Threat IDs / N/A")
        referenced = any(
            surface_id in _ids(_column(item, "Surface"), "#") for item in threats
        )
        if not referenced and not disposition.casefold().startswith("n/a"):
            errors.append(
                f"Attack surface {surface_id} has no threat or N/A disposition"
            )
    actual: dict[tuple[str, int], int] = {}
    for row in coverage:
        asi = _column(row, "ASI")
        try:
            scenario = int(_column(row, "Scenario"))
        except ValueError:
            errors.append(
                f"Scenario Coverage has invalid index for {asi or 'unknown ASI'}"
            )
            continue
        actual[(asi, scenario)] = actual.get((asi, scenario), 0) + 1
        disposition = _column(row, "Disposition")
        unknown = _ids(disposition, "T") - threat_ids
        if unknown:
            errors.append(
                f"{asi} scenario {scenario} cites unknown threats: {sorted(unknown)}"
            )
        if not _ids(disposition, "T") and not disposition.casefold().startswith("n/a"):
            errors.append(
                f"{asi} scenario {scenario} lacks a threat or N/A disposition"
            )
    expected = {
        (asi, scenario)
        for asi, count in scenario_counts.items()
        for scenario in range(1, count + 1)
    }
    missing = sorted(expected - set(actual))
    duplicate = sorted(key for key, count in actual.items() if count != 1)
    extra = sorted(set(actual) - expected)
    if missing:
        errors.append(f"Scenario Coverage is missing {len(missing)} catalog scenarios")
    if duplicate:
        errors.append(f"Scenario Coverage repeats entries: {duplicate}")
    if extra:
        errors.append(f"Scenario Coverage has unknown entries: {extra}")
    return errors


def _validate_enforcement(
    state: dict[str, Any],
    threat_state: dict[str, Any],
    tools_path: Path,
    subjects_path: Path,
    guidance: Path | None,
) -> list[str]:
    tables = state["tables"]
    errors: list[str] = []
    threat_ids = {
        _column(row, "ID") for row in threat_state["tables"].get("Threat Instances", [])
    }
    disposition_ids = [
        _column(row, "Threat ID") for row in tables.get("Threat Disposition", [])
    ]
    if set(disposition_ids) != threat_ids or len(disposition_ids) != len(
        set(disposition_ids)
    ):
        errors.append("Threat Disposition must map every threat ID exactly once")
    candidates = parse_candidate_table(
        Path(state["artifact"]).read_text(encoding="utf-8")
    )
    existing_rules = parse_existing_guidance_table(
        Path(state["artifact"]).read_text(encoding="utf-8")
    )
    validations = validate_candidates(
        candidates, load_tool_schema(tools_path), load_subject_schema(subjects_path)
    )
    for finding in validations:
        for message in finding.messages:
            errors.append(f"{finding.candidate_id}: {message}")
    existing_validations = validate_candidates(
        existing_rules, load_tool_schema(tools_path), load_subject_schema(subjects_path)
    )
    for finding in existing_validations:
        for message in finding.messages:
            errors.append(f"{finding.candidate_id}: existing guidance: {message}")
    if guidance is not None and guidance.is_file():
        for finding in validate_existing_rule_numbers(
            existing_rules, guidance.read_text(encoding="utf-8")
        ):
            for message in finding.messages:
                errors.append(f"{finding.candidate_id}: existing guidance: {message}")
    relationships = analyze_existing_relationships(candidates, existing_rules)
    by_candidate: dict[str, list[str]] = {}
    for relationship in relationships:
        by_candidate.setdefault(relationship.left, []).append(relationship.verdict)
    for candidate in candidates:
        unknown_threats = {
            source for source in candidate.sources if source.startswith("T")
        } - threat_ids
        allowed_questions = {f"Q{number}" for number in range(1, 23)} | {"Q13b"}
        unknown_questions = {
            source
            for source in candidate.sources
            if source.startswith("Q") and source not in allowed_questions
        }
        if unknown_threats:
            errors.append(
                f"{candidate.candidate_id} cites unknown threats: {sorted(unknown_threats)}"
            )
        if unknown_questions:
            errors.append(
                f"{candidate.candidate_id} cites unknown questions: {sorted(unknown_questions)}"
            )
        if candidate.verdict.casefold() in BLOCKING_VERDICTS:
            errors.append(
                f"{candidate.candidate_id} retains blocking verdict {candidate.verdict!r}"
            )
        detected = set(by_candidate.get(candidate.candidate_id, []))
        if detected & {"Duplicate", "Covered"}:
            allowed_verdicts = {"duplicate", "covered", "clarification"}
        elif detected & {"Conflict", "Overlap"}:
            allowed_verdicts = {"conflict", "overlap", "contradictory correction"}
        elif "Additive" in detected:
            allowed_verdicts = {"additive", "clarification"}
        else:
            allowed_verdicts = {"novel"}
        if candidate.verdict.casefold() not in allowed_verdicts:
            errors.append(
                f"{candidate.candidate_id} verdict {candidate.verdict!r} conflicts "
                f"with existing-guidance relationship {sorted(detected) or ['Novel']}"
            )
    prior_rows = tables.get("Prior Proposal Reconciliation", [])
    prior_ids = [_column(row, "Prior ID") for row in prior_rows]
    if len(prior_ids) != len(set(prior_ids)):
        errors.append("Prior Proposal Reconciliation contains duplicate Prior IDs")
    for row in prior_rows:
        prior_id = _column(row, "Prior ID") or "unknown prior proposal"
        disposition = _column(row, "Disposition").casefold()
        reason = _column(row, "Candidate / reason")
        if disposition not in {"proposed", "merged", "dropped"}:
            errors.append(f"{prior_id} has invalid prior-proposal disposition")
        if not reason or reason in {"—", "-"}:
            errors.append(f"{prior_id} has no candidate link or drop reason")
    return errors


def _validate_addendum_contract(state: dict[str, Any], guidance: Path) -> list[str]:
    from smith.tools.guidance_merge import validate_addendum

    analysis = Path(state["artifact"]).read_text(encoding="utf-8")
    candidates = parse_candidate_table(analysis)
    emitted = [
        candidate
        for candidate in candidates
        if candidate.verdict.casefold() in {"novel", "additive"}
    ]
    addendum = guidance.with_name("guidance_updated.txt")
    if not emitted:
        return (
            ["guidance_updated.txt exists although no Novel/Additive candidate remains"]
            if addendum.exists()
            else []
        )
    try:
        proposed = validate_addendum(guidance, addendum)
    except ReconciliationError as exc:
        return [str(exc)]
    if len(proposed) != len(emitted):
        return [
            "guidance_updated.txt rule count does not match Novel/Additive "
            f"candidates ({len(proposed)} != {len(emitted)})"
        ]
    return []


def checkpoint(
    phase: str,
    analysis_dir: Path,
    tool_definitions: Path,
    system_vars: Path,
    catalog: Path,
    state_path: Path,
    guidance: Path | None = None,
) -> str:
    phase = phase.upper()
    if phase not in PHASES:
        raise ReconciliationError("phase must be one of A, B, C, or D")
    selected = list(PHASES)[: list(PHASES).index(phase) + 1]
    states: dict[str, Any] = {}
    errors: list[str] = []
    for current in selected:
        filename, schema = PHASES[current]
        states[current], shape_errors = _validate_phase_shape(
            current, analysis_dir / filename, schema
        )
        errors.extend(shape_errors)
        if shape_errors:
            continue
        if current == "A":
            errors.extend(
                _validate_architecture(states[current], tool_definitions, system_vars)
            )
        elif current == "B":
            errors.extend(_validate_questionnaire(states[current]))
        elif current == "C":
            errors.extend(
                _validate_threat_model(
                    states[current],
                    catalog,
                    states["B"],
                    tool_definitions,
                    system_vars,
                )
            )
        elif current == "D" and states.get("C"):
            errors.extend(
                _validate_enforcement(
                    states[current],
                    states["C"],
                    tool_definitions,
                    system_vars,
                    guidance,
                )
            )
            if guidance is None:
                errors.append("GUIDANCE_FILE is required for Phase D validation")
            else:
                errors.extend(_validate_addendum_contract(states[current], guidance))
    if errors:
        raise ReconciliationError(
            "checkpoint validation failed:\n- " + "\n- ".join(errors)
        )
    input_paths = {
        "tool_definitions": tool_definitions,
        "system_vars": system_vars,
        "guidance": guidance,
        "guidance_updated": (
            guidance.with_name("guidance_updated.txt") if guidance else None
        ),
    }
    payload = {
        "schema": "security-analysis-state-v1",
        "latest_phase": phase,
        "inputs": {
            name: (
                {
                    "path": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                if path is not None and path.is_file()
                else None
            )
            for name, path in input_paths.items()
        },
        "phases": states,
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = state_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(state_path)
    return f"Security analysis checkpoint {phase}: PASS\nState: {state_path}"


def checkpoint_from_environment(
    phase: str, environment: dict[str, str] | None = None
) -> str:
    env = os.environ if environment is None else environment
    base = Path(env.get("BASE_URL") or ".")
    if not base.is_absolute():
        base = Path.cwd() / base
    target_value = env.get("TARGET_AGENT_PATH")
    system_value = env.get("SYSTEM_VAR_FILE")
    guidance_value = env.get("GUIDANCE_FILE")
    if not target_value:
        raise ReconciliationError("TARGET_AGENT_PATH is not configured")
    if not system_value:
        raise ReconciliationError("SYSTEM_VAR_FILE is not configured")
    if phase.upper() == "D" and not guidance_value:
        raise ReconciliationError("GUIDANCE_FILE is not configured")
    target = Path(target_value)
    target = target if target.is_absolute() else base / target
    system_vars = Path(system_value)
    system_vars = system_vars if system_vars.is_absolute() else base / system_vars
    guidance = Path(guidance_value) if guidance_value else None
    if guidance is not None and not guidance.is_absolute():
        guidance = base / guidance
    analysis_dir = target / "smith" / "guidelines-security-analysis"
    catalog = Path(__file__).resolve().parents[1] / "data" / "owasp_10_ai_catalog.json"
    return checkpoint(
        phase,
        analysis_dir,
        target / "smith" / "tool_definitions.json",
        system_vars,
        catalog,
        analysis_dir / "analysis_state.json",
        guidance,
    )
