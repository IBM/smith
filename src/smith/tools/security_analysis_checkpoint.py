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
    analyze_existing_relationships,
    load_subject_schema,
    load_tool_schema,
    parse_candidate_rows,
    parse_existing_guidance_rows,
    validate_candidates,
    validate_existing_rule_numbers,
)

PHASES = {
    "A": ("architecture", "architecture-v2", "Architecture Analysis"),
    "B": (
        "policy_guidance_questionnaire",
        "questionnaire-v2",
        "OPA Policy Guidance Questionnaire",
    ),
    "C": ("threat_model", "threat-model-v3", "Threat Model"),
    "D": (
        "owasp_policy_guidelines",
        "enforcement-mapping-v8",
        "OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines",
    ),
}
BLOCKING_VERDICTS = {"overlap", "conflict", "contradictory correction"}
EMITTED_VERDICTS = {"novel", "additive"}
NON_EMITTED_VERDICTS = {"duplicate", "covered", "clarification"}

TABLE_COLUMNS = {
    "Layers": ["Layer", "File", "Role", "Inputs", "Outputs", "Current enforcement"],
    "Runtime Subject Context": [
        "Field",
        "Provider",
        "Provenance",
        "Verification / integrity",
        "OPA-visible?",
    ],
    "Tool Arguments": ["Field", "Tool", "Origin / influence", "Disposition"],
    "Prompt Inputs": ["Field or data", "Source", "Consumer", "Trust / influence"],
    "External Data": ["Data", "Source", "Verification / integrity", "Consumer"],
    "Enforcement Points": [
        "Layer",
        "Current",
        "Available (OPA-interceptable)",
        "Blind spots",
    ],
    "Undeclared Fields": [
        "Field",
        "Referenced by guidance rule #",
        "Declared by",
        "Consequence",
    ],
    "Answer Register": ["Q", "Required answer", "Answer", "Confidence"],
    "Parameter Details": ["Tool", "Policy path", "Type", "Required", "Valid values"],
    "Runtime Subject Details": [
        "Policy path",
        "Provider",
        "Provenance",
        "Verification / integrity mechanism",
    ],
    "Role Permissions": ["Tool", "Role", "Permission / scope", "guidance.txt rule"],
    "Approval Paths": ["Parameter condition", "Approval field", "guidance.txt rule"],
    "Rate Limits": ["Role", "Max calls per session"],
    "Severity Levels": ["Level", "Examples"],
    "Violation Codes": ["Existing code", "Meaning"],
    "Attack Surfaces": [
        "#",
        "Field or Data Point",
        "Source Layer",
        "Provenance / influence",
        "Enters where",
        "Threat IDs / N/A",
    ],
    "Evidence Index": ["ID", "Source", "Grounded fact"],
    "Category Assessment": [
        "ASI",
        "Name",
        "Applicability",
        "OWASP summary",
        "Boundary (optional)",
    ],
    "Threat Instances": [
        "ID",
        "ASI",
        "Severity",
        "Actor",
        "Surface",
        "Catalog basis",
        "Evidence",
        "Concrete threat",
    ],
    "Scenario Coverage": ["ASI", "Scenario", "Disposition"],
    "Threat Disposition": ["Threat ID", "Field / surface", "Owner", "Reason"],
    "OWASP Top 10 for Agentic AI Security — Scope Assessment": [
        "OWASP",
        "Scope",
        "OPA threat IDs",
        "Other-layer threat IDs",
        "Reason / owner",
    ],
    "Gap Register": ["Finding ID", "Layer", "Recommended action"],
    "Input Schema": ["Field", "Source"],
    "Rules": [
        "Code",
        "OWASP",
        "Threat IDs",
        "Severity",
        "Tool(s) / field",
        "Condition",
        "Matching",
    ],
    "Candidate Reconciliation": [
        "Candidate ID",
        "Tool",
        "Subject scope",
        "Field expression",
        "Operator",
        "Values",
        "Action",
        "Sources",
        "Related rule",
        "Guidance group",
        "Verdict",
    ],
    "Existing Guidance Normalization": [
        "Existing ID",
        "Rule number",
        "Tool",
        "Subject scope",
        "Field expression",
        "Operator",
        "Values",
        "Action",
    ],
    "Prior Proposal Reconciliation": [
        "Prior ID",
        "Original number",
        "Normalized rule",
        "Disposition",
        "Candidate / reason",
    ],
}

PHASE_LAYOUT = {
    "A": [
        ("Run Context", 2, "section"),
        ("Layers", 2, "table"),
        ("Trust Boundaries", 2, "section"),
        ("Runtime Subject Context", 3, "table"),
        ("Tool Arguments", 3, "table"),
        ("Prompt Inputs", 3, "table"),
        ("External Data", 3, "table"),
        ("Data Flow", 2, "section"),
        ("Enforcement Points", 2, "table"),
        ("Undeclared Fields", 2, "table"),
        ("Phase Handoff", 2, "handoff"),
    ],
    "B": [
        ("Answer Register", 2, "table"),
        ("Parameter Details", 2, "table"),
        ("Runtime Subject Details", 2, "table"),
        ("Role Permissions", 2, "table"),
        ("Approval Paths", 2, "table"),
        ("Rate Limits", 2, "table"),
        ("Severity Levels", 2, "table"),
        ("Violation Logging", 2, "section"),
        ("Violation Codes", 2, "table"),
        ("Phase Handoff", 2, "handoff"),
    ],
    "C": [
        ("Attack Surfaces", 2, "table"),
        ("Evidence Index", 2, "table"),
        ("Category Assessment", 2, "table"),
        ("Threat Instances", 2, "table"),
        ("Scenario Coverage", 2, "table"),
        ("Phase Handoff", 2, "handoff"),
    ],
    "D": [
        ("Architecture Summary", 2, "section"),
        ("Threat Disposition", 2, "table"),
        ("OWASP Top 10 for Agentic AI Security — Scope Assessment", 2, "table"),
        ("Gap Register", 2, "table"),
        ("Policy Rules (OPA scope only)", 2, "section"),
        ("Input Schema", 3, "table"),
        ("Known values", 3, "section"),
        ("Rules", 3, "table"),
        ("Candidate Reconciliation", 2, "table"),
        ("Existing Guidance Normalization", 2, "table"),
        ("Prior Proposal Reconciliation", 2, "table"),
        ("Phase Handoff", 2, "handoff"),
    ],
}

QUESTIONNAIRE_PROMPTS = {
    "Q1": "Tool names and one-sentence purposes",
    "Q2": "External systems: protocol, authentication, and read/write behavior",
    "Q3": "Whether each tool reads, writes, or both",
    "Q4": "Parameters; use Parameter Details",
    "Q5": "Every user role",
    "Q6": "Runtime subject provenance and integrity; use Runtime Subject Details",
    "Q7": "User ID canonical path, provider, and use",
    "Q8": "Whether simultaneous roles are supported",
    "Q9": "Tool permissions and scope per role; use Role Permissions",
    "Q10": "Role-specific topics, values, or parameter combinations",
    "Q11": "Roles with no restrictions",
    "Q12": "Globally blocked enumerable values, formats, domains, or flags",
    "Q13": "Numeric hard caps",
    "Q13b": "Conditional approval paths; use Approval Paths",
    "Q14": "Rejected patterns and their input source",
    "Q15": "Per-session call limits; use Rate Limits",
    "Q16": "Counter owner, mechanism, and canonical policy path",
    "Q17": "Post-response filtering",
    "Q18": "Response fields suppressed by role",
    "Q19": "Conditions making a result actionable",
    "Q20": "Silent rejection or user explanation",
    "Q21": "Hard-block and soft-block meanings; use Severity Levels",
    "Q22": "Denial logging and existing violation-code scheme",
}


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


def _surface_ids(value: str) -> set[str]:
    """Normalize attack-surface references written as either `1` or `#1`."""
    return {
        f"#{match}" for match in re.findall(r"(?<![A-Za-z0-9])#?(\d+)\b", str(value))
    }


def _verdict_tokens(value: str) -> frozenset[str]:
    """Return every recognized verdict in a simple or compound cell."""
    normalized = value.casefold()
    labels = BLOCKING_VERDICTS | EMITTED_VERDICTS | NON_EMITTED_VERDICTS
    return frozenset(
        label
        for label in labels
        if re.search(rf"(?<![a-z]){re.escape(label)}(?![a-z])", normalized)
    )


def _is_emitted_verdict(value: str) -> bool:
    verdicts = _verdict_tokens(value)
    return bool(verdicts) and verdicts <= EMITTED_VERDICTS


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", r"\|").replace("\n", "<br>")


def _render_table(columns: list[str], rows: list[dict[str, str]]) -> str:
    header = "| " + " | ".join(columns) + " |"
    separator = "|" + "|".join("---" for _ in columns) + "|"
    body = [
        "| "
        + " | ".join(_markdown_cell(row.get(column, "")) for column in columns)
        + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def _render_phase(phase: str, state: dict[str, Any]) -> str:
    lines = [f"# {state['title']}", ""]
    for name, level, kind in PHASE_LAYOUT[phase]:
        if phase == "A" and kind == "section":
            continue
        lines.extend([f"{'#' * level} {name}", ""])
        if kind == "table":
            lines.extend(
                [_render_table(TABLE_COLUMNS[name], state["tables"].get(name, [])), ""]
            )
        elif kind == "handoff":
            lines.extend(
                [
                    f"- {key}: {_markdown_cell(value)}"
                    for key, value in state["handoff"].items()
                ]
            )
            lines.append("")
        else:
            lines.extend([state["sections"].get(name, "") or "none", ""])
    return "\n".join(lines).rstrip() + "\n"


def _structured_phase(
    phase: str, source: Path, artifact: Path, expected_schema: str
) -> tuple[dict[str, Any], list[str]]:
    if not source.is_file():
        return {}, [f"Phase {phase} structured artifact is missing: {source}"]
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"Phase {phase} structured artifact is malformed: {source}: {exc}"]
    if not isinstance(data, dict):
        return {}, [f"Phase {phase} structured artifact must be a JSON object"]

    errors: list[str] = []
    sections = data.get("sections")
    tables = data.get("tables")
    handoff = data.get("handoff")
    if not isinstance(sections, dict):
        sections = {}
        errors.append(f"Phase {phase} sections must be an object")
    if not isinstance(tables, dict):
        tables = {}
        errors.append(f"Phase {phase} tables must be an object")
    if not isinstance(handoff, dict):
        handoff = {}
        errors.append(f"Phase {phase} handoff must be an object")

    allowed_sections = {
        name for name, _, kind in PHASE_LAYOUT[phase] if kind == "section"
    }
    allowed_tables = {name for name, _, kind in PHASE_LAYOUT[phase] if kind == "table"}
    unknown_sections = sorted(set(sections) - allowed_sections)
    unknown_tables = sorted(set(tables) - allowed_tables)
    if unknown_sections:
        errors.append(
            f"Phase {phase} has unknown sections: {', '.join(unknown_sections)}"
        )
    if unknown_tables:
        errors.append(f"Phase {phase} has unknown tables: {', '.join(unknown_tables)}")

    present = set(sections) | set(tables)
    if handoff:
        present.add("Phase Handoff")
    expected_sections = allowed_sections | allowed_tables | {"Phase Handoff"}
    missing_sections = sorted(expected_sections - present)
    if missing_sections:
        errors.append(
            f"Phase {phase} required sections are missing: {', '.join(missing_sections)}"
        )
    normalized_tables: dict[str, list[dict[str, str]]] = {}
    for name, rows in tables.items():
        if isinstance(rows, list):
            normalized_tables[str(name)] = [
                {str(key): str(value) for key, value in row.items()}
                for row in rows
                if isinstance(row, dict)
            ]
    for name in allowed_tables:
        rows = tables.get(name)
        if not isinstance(rows, list):
            errors.append(f"Phase {phase} required table {name!r} is missing")
            continue
        expected_columns = TABLE_COLUMNS[name]
        for index, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                errors.append(
                    f"Phase {phase} table {name!r} row {index} is not an object"
                )
                continue
            missing = [column for column in expected_columns if column not in row]
            extra = [column for column in row if column not in expected_columns]
            if missing:
                errors.append(
                    f"Phase {phase} table {name!r} row {index} is missing columns: "
                    + ", ".join(missing)
                )
            if extra:
                errors.append(
                    f"Phase {phase} table {name!r} row {index} has unknown columns: "
                    + ", ".join(extra)
                )

    status = str(data.get("status", handoff.get("Status", "missing")))
    schema = str(data.get("schema", handoff.get("Artifact schema", "missing")))
    if status != "PASS" or str(handoff.get("Status", "")) != "PASS":
        errors.append(f"Phase {phase} handoff status is not PASS")
    if (
        schema != expected_schema
        or str(handoff.get("Artifact schema", "")) != expected_schema
    ):
        errors.append(
            f"Phase {phase} schema is {schema!r}; expected {expected_schema!r}"
        )
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append(f"Phase {phase} title is missing")
        title = PHASES[phase][2]

    normalized = {
        "artifact": str(artifact),
        "source": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "schema": expected_schema,
        "status": status,
        "handoff": {str(key): str(value) for key, value in handoff.items()},
        "sections": {str(key): str(value) for key, value in sections.items()},
        "tables": normalized_tables,
        "title": title,
    }
    markdown = _render_phase(phase, normalized)
    normalized["sha256"] = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    normalized["_markdown"] = markdown
    return normalized, errors


def prepare_phase(phase: str, analysis_dir: Path) -> str:
    """Create a structured phase template without replacing an existing draft."""
    phase = phase.upper()
    if phase not in PHASES:
        raise ReconciliationError("phase must be one of A, B, C, or D")
    stem, schema, title = PHASES[phase]
    path = analysis_dir / f"{stem}.json"
    if path.exists():
        return f"Security analysis phase {phase} draft already exists: {path}"
    layout = PHASE_LAYOUT[phase]
    payload = {
        "schema": schema,
        "status": "DRAFT",
        "title": title,
        "sections": {name: "" for name, _, kind in layout if kind == "section"},
        "columns": {
            name: TABLE_COLUMNS[name] for name, _, kind in layout if kind == "table"
        },
        "tables": {name: [] for name, _, kind in layout if kind == "table"},
        "handoff": {"Status": "DRAFT", "Artifact schema": schema},
    }
    if phase == "B":
        payload["tables"]["Answer Register"] = [
            {"Q": question, "Required answer": prompt, "Answer": "", "Confidence": ""}
            for question, prompt in QUESTIONNAIRE_PROMPTS.items()
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return f"Security analysis phase {phase} draft: {path}"


def _validate_phase_shape(
    phase: str, path: Path, expected_schema: str
) -> tuple[dict[str, Any], list[str]]:
    return _structured_phase(phase, path.with_suffix(".json"), path, expected_schema)


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
    surface_ids = {
        surface_id for row in surfaces for surface_id in _surface_ids(_column(row, "#"))
    }
    surfaces_by_id = {
        surface_id: row
        for row in surfaces
        for surface_id in _surface_ids(_column(row, "#"))
    }
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
        cited_surface_ids = _surface_ids(_column(row, "Surface"))
        unknown_surfaces = cited_surface_ids - surface_ids
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
            for surface_id in cited_surface_ids
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
            elif not any(field in tools[name] for name in tool_names):
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
        normalized_ids = _surface_ids(_column(row, "#"))
        surface_id = next(iter(normalized_ids), _column(row, "#"))
        disposition = _column(row, "Threat IDs / N/A")
        referenced = any(
            surface_id in _surface_ids(_column(item, "Surface")) for item in threats
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
    candidates = parse_candidate_rows(tables.get("Candidate Reconciliation", []))
    existing_rules = parse_existing_guidance_rows(
        tables.get("Existing Guidance Normalization", [])
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
        verdicts = _verdict_tokens(candidate.verdict)
        if verdicts & BLOCKING_VERDICTS:
            errors.append(
                f"{candidate.candidate_id} retains blocking verdict {candidate.verdict!r}"
            )
        detected = set(by_candidate.get(candidate.candidate_id, []))
        if detected & {"Conflict", "Overlap"}:
            allowed_verdicts = {"conflict", "overlap", "contradictory correction"}
        elif detected & {"Duplicate", "Covered"}:
            allowed_verdicts = {"duplicate", "covered", "clarification"}
        elif "Additive" in detected:
            allowed_verdicts = {"novel", "additive"}
        else:
            allowed_verdicts = {"novel", "additive"}
        if not verdicts or not verdicts <= allowed_verdicts:
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

    candidates = parse_candidate_rows(
        state["tables"].get("Candidate Reconciliation", [])
    )
    emitted = [
        candidate for candidate in candidates if _is_emitted_verdict(candidate.verdict)
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
    emitted_groups = {candidate.guidance_group for candidate in emitted}
    if len(proposed) != len(emitted_groups):
        return [
            "guidance_updated.txt rule count does not match Novel/Additive "
            f"guidance groups ({len(proposed)} != {len(emitted_groups)})"
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
        stem, schema, _ = PHASES[current]
        states[current], shape_errors = _validate_phase_shape(
            current, analysis_dir / f"{stem}.md", schema
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
    for current in selected:
        artifact = Path(states[current]["artifact"])
        temporary_artifact = artifact.with_suffix(".md.tmp")
        temporary_artifact.write_text(states[current]["_markdown"], encoding="utf-8")
        temporary_artifact.replace(artifact)
        del states[current]["_markdown"]
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


def prepare_from_environment(
    phase: str, environment: dict[str, str] | None = None
) -> str:
    env = os.environ if environment is None else environment
    base = Path(env.get("BASE_URL") or ".")
    if not base.is_absolute():
        base = Path.cwd() / base
    target_value = env.get("TARGET_AGENT_PATH")
    if not target_value:
        raise ReconciliationError("TARGET_AGENT_PATH is not configured")
    target = Path(target_value)
    target = target if target.is_absolute() else base / target
    return prepare_phase(phase, target / "smith" / "guidelines-security-analysis")
