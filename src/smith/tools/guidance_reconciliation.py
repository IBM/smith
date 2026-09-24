# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Read-only validation and reconciliation for Step D guidance candidates."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

HEADERS = (
    "candidate id",
    "tool",
    "subject scope",
    "field expression",
    "operator",
    "values",
    "action",
    "sources",
    "related rule",
    "verdict",
)
GROUPED_HEADERS = HEADERS[:-1] + ("guidance group", "verdict")
EXISTING_HEADERS = (
    "existing id",
    "rule number",
    "tool",
    "subject scope",
    "field expression",
    "operator",
    "values",
    "action",
)
OPERATORS = {
    "eq",
    "neq",
    "in",
    "not_in",
    "contains_any",
    "lt",
    "lte",
    "gt",
    "gte",
    "missing/null/empty",
}
FIELD_PATTERN = re.compile(
    r"input\.(?:args|extensions\.subject)\.[A-Za-z_][A-Za-z0-9_.]*"
)


class ReconciliationError(ValueError):
    """An input required for deterministic reconciliation is unusable."""


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    tool: str
    subject_scope: frozenset[str] | None
    fields: tuple[str, ...]
    operator: str
    values: tuple[str, ...]
    action: str
    sources: tuple[str, ...]
    related_rule: str
    verdict: str
    guidance_group: str

    @property
    def group(self) -> tuple[str, tuple[str, ...], str]:
        return self.tool, self.fields, self.action

    @property
    def exact_key(self) -> tuple[Any, ...]:
        return (
            self.group,
            self.subject_scope,
            self.operator,
            self.values,
        )


@dataclass(frozen=True)
class ValidationFinding:
    candidate_id: str
    messages: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.messages


@dataclass(frozen=True)
class Relationship:
    verdict: str
    left: str
    right: str
    detail: str


@dataclass(frozen=True)
class UnionSuggestion:
    candidate_ids: tuple[str, ...]
    operator: str
    values: tuple[str, ...]


def _split_markdown_row(line: str) -> list[str]:
    """Split a pipe table row while retaining escaped pipes inside cells."""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if escaped:
        current.append("\\")
    cells.append("".join(current).strip())
    return cells


def _plain(value: str) -> str:
    return value.strip().strip("`").strip()


def _split_values(value: str) -> tuple[str, ...]:
    text = _plain(value)
    if text in {"", "—", "-"}:
        return ()
    text = text.strip("{}[]()")
    parts = re.split(r"\s*,\s*|\s*;\s*", text)
    normalized = {
        part.strip().strip("`\"'").strip()
        for part in parts
        if part.strip().strip("`\"'").strip()
    }
    return tuple(sorted(normalized, key=str.casefold))


def _parse_scope(value: str) -> frozenset[str] | None:
    text = _plain(value).casefold()
    if text in {"all", "every role", "all roles", "*"}:
        return None
    return frozenset(_split_values(value))


def _row_value(row: dict[str, Any], name: str) -> str:
    for key, value in row.items():
        if str(key).casefold() == name.casefold():
            return _plain(str(value))
    return ""


def parse_candidate_rows(rows: Iterable[dict[str, Any]]) -> list[Candidate]:
    """Parse normalized candidates from structured phase state."""
    candidates: list[Candidate] = []
    seen_ids: set[str] = set()
    for row in rows:
        candidate_id = _row_value(row, "Candidate ID")
        tool = _row_value(row, "Tool")
        scope = _row_value(row, "Subject scope")
        expression = _row_value(row, "Field expression")
        operator = _row_value(row, "Operator").casefold()
        values = _row_value(row, "Values")
        action = _row_value(row, "Action")
        sources = _row_value(row, "Sources")
        related = _row_value(row, "Related rule")
        verdict = _row_value(row, "Verdict")
        guidance_group = _row_value(row, "Guidance group") or candidate_id
        if not candidate_id or not tool or not expression or not action:
            raise ReconciliationError("Candidate row has an empty required field")
        if candidate_id in seen_ids:
            raise ReconciliationError(f"Duplicate Candidate ID: {candidate_id}")
        seen_ids.add(candidate_id)
        if operator not in OPERATORS:
            raise ReconciliationError(
                f"{candidate_id} uses unsupported operator {operator!r}"
            )
        fields = tuple(sorted(set(FIELD_PATTERN.findall(expression))))
        if not fields:
            raise ReconciliationError(
                f"{candidate_id} has no canonical input.args.* or "
                "input.extensions.subject.* field"
            )
        candidates.append(
            Candidate(
                candidate_id=candidate_id,
                tool=tool,
                subject_scope=_parse_scope(scope),
                fields=fields,
                operator=operator,
                values=_split_values(values),
                action=action.casefold(),
                sources=_split_values(sources),
                related_rule=related,
                verdict=verdict,
                guidance_group=guidance_group,
            )
        )
    return candidates


def parse_existing_guidance_rows(rows: Iterable[dict[str, Any]]) -> list[Candidate]:
    """Parse normalized existing guidance from structured phase state."""
    existing: list[Candidate] = []
    seen_ids: set[str] = set()
    for row in rows:
        existing_id = _row_value(row, "Existing ID")
        rule_number = _row_value(row, "Rule number")
        tool = _row_value(row, "Tool")
        scope = _row_value(row, "Subject scope")
        expression = _row_value(row, "Field expression")
        operator = _row_value(row, "Operator").casefold()
        values = _row_value(row, "Values")
        action = _row_value(row, "Action")
        if (
            not existing_id
            or not rule_number
            or not tool
            or not expression
            or not action
        ):
            raise ReconciliationError(
                "Existing Guidance Normalization row has an empty required field"
            )
        if existing_id in seen_ids:
            raise ReconciliationError(f"Duplicate Existing ID: {existing_id}")
        seen_ids.add(existing_id)
        if operator not in OPERATORS:
            raise ReconciliationError(
                f"{existing_id} uses unsupported operator {operator!r}"
            )
        fields = tuple(sorted(set(FIELD_PATTERN.findall(expression))))
        if not fields:
            raise ReconciliationError(
                f"{existing_id} has no canonical input.args.* or "
                "input.extensions.subject.* field"
            )
        existing.append(
            Candidate(
                candidate_id=existing_id,
                tool=tool,
                subject_scope=_parse_scope(scope),
                fields=fields,
                operator=operator,
                values=_split_values(values),
                action=action.casefold(),
                sources=(rule_number,),
                related_rule="",
                verdict="Existing",
                guidance_group=existing_id,
            )
        )
    return existing


def _markdown_table_rows(
    markdown: str, section_name: str, headers: tuple[str, ...]
) -> list[dict[str, str]]:
    heading = re.search(rf"(?im)^##\s+{re.escape(section_name)}\s*$", markdown)
    if not heading:
        raise ReconciliationError(f"{section_name} section is missing")
    section = markdown[heading.end() :]
    next_heading = re.search(r"(?m)^#{1,2}\s+", section)
    if next_heading:
        section = section[: next_heading.start()]
    lines = [line for line in section.splitlines() if line.strip()]
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if tuple(cell.casefold() for cell in _split_markdown_row(line)) == headers
        ),
        None,
    )
    if header_index is None or header_index + 1 >= len(lines):
        raise ReconciliationError(f"{section_name} table is missing or malformed")
    separator = _split_markdown_row(lines[header_index + 1])
    if len(separator) != len(headers) or not all(
        re.fullmatch(r":?-{3,}:?", cell) for cell in separator
    ):
        raise ReconciliationError(f"{section_name} separator is malformed")
    rows: list[dict[str, str]] = []
    for line in lines[header_index + 2 :]:
        if not line.lstrip().startswith("|"):
            break
        cells = _split_markdown_row(line)
        if len(cells) != len(headers):
            raise ReconciliationError(
                f"{section_name} row has {len(cells)} cells; expected {len(headers)}"
            )
        if all(cell.startswith("<") and cell.endswith(">") for cell in cells[:2]):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def parse_candidate_table(markdown: str) -> list[Candidate]:
    """Parse Step D's normalized Candidate Reconciliation Markdown table."""
    try:
        rows = _markdown_table_rows(
            markdown, "Candidate Reconciliation", GROUPED_HEADERS
        )
    except ReconciliationError:
        rows = _markdown_table_rows(markdown, "Candidate Reconciliation", HEADERS)
    return parse_candidate_rows(rows)


def parse_existing_guidance_table(markdown: str) -> list[Candidate]:
    """Parse existing guidance normalized by Step D into candidate tuples."""
    return parse_existing_guidance_rows(
        _markdown_table_rows(
            markdown, "Existing Guidance Normalization", EXISTING_HEADERS
        )
    )


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ReconciliationError(f"{label} is missing: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReconciliationError(f"{label} is malformed: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ReconciliationError(f"{label} must contain a JSON object: {path}")
    return data


def load_tool_schema(path: Path) -> dict[str, dict[str, Any]]:
    data = _read_json(path, "tool_definitions.json")
    tools = data.get("tools")
    if not isinstance(tools, list):
        raise ReconciliationError("tool_definitions.json must contain a tools array")
    result: dict[str, dict[str, Any]] = {}
    for tool in tools:
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
            raise ReconciliationError("tool_definitions.json contains an invalid tool")
        fields: dict[str, Any] = {}
        properties = tool.get("input_schema", {}).get("properties", {})
        if isinstance(properties, dict):
            fields.update(properties)
        parameters = tool.get("parameters", [])
        if isinstance(parameters, list):
            for parameter in parameters:
                if isinstance(parameter, dict) and isinstance(
                    parameter.get("name"), str
                ):
                    fields.setdefault(parameter["name"], parameter)
        result[tool["name"]] = fields
    return result


def load_subject_schema(path: Path) -> dict[str, Any]:
    return _read_json(path, "system_vars.json")


def _domain_from_schema(schema: Any) -> frozenset[str] | None:
    if isinstance(schema, dict):
        enum = schema.get("enum")
        if isinstance(enum, list):
            return frozenset(str(value) for value in enum)
    if isinstance(schema, list):
        return frozenset(str(value) for value in schema)
    if isinstance(schema, str) and "|" in schema:
        return frozenset(part.strip() for part in schema.split("|") if part.strip())
    return None


def field_domain(
    candidate: Candidate,
    tools: dict[str, dict[str, Any]],
    subjects: dict[str, Any],
) -> frozenset[str] | None:
    if len(candidate.fields) != 1:
        return None
    field = candidate.fields[0]
    if field.startswith("input.args."):
        name = field.removeprefix("input.args.").split(".", 1)[0]
        return _domain_from_schema(tools.get(candidate.tool, {}).get(name))
    name = field.removeprefix("input.extensions.subject.").split(".", 1)[0]
    return _domain_from_schema(subjects.get(name))


def validate_candidates(
    candidates: Iterable[Candidate],
    tools: dict[str, dict[str, Any]],
    subjects: dict[str, Any],
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for candidate in candidates:
        messages: list[str] = []
        if candidate.subject_scope == frozenset():
            messages.append("subject scope is empty")
        if candidate.tool not in tools:
            messages.append(f"unknown tool {candidate.tool!r}")
        for field in candidate.fields:
            if field.startswith("input.args."):
                name = field.removeprefix("input.args.").split(".", 1)[0]
                if candidate.tool in tools and name not in tools[candidate.tool]:
                    messages.append(
                        f"{field} is not declared for tool {candidate.tool!r}"
                    )
            else:
                name = field.removeprefix("input.extensions.subject.").split(".", 1)[0]
                if name not in subjects:
                    messages.append(f"{field} is not declared in system_vars.json")
        if candidate.action != "deny":
            messages.append(f"unsupported action {candidate.action!r}; expected 'deny'")
        if (
            candidate.operator in {"eq", "neq", "lt", "lte", "gt", "gte"}
            and len(candidate.values) != 1
        ):
            messages.append(
                f"operator {candidate.operator!r} requires exactly one value"
            )
        if (
            candidate.operator in {"in", "not_in", "contains_any"}
            and not candidate.values
        ):
            messages.append(
                f"operator {candidate.operator!r} requires at least one value"
            )
        if candidate.operator in {"lt", "lte", "gt", "gte"} and candidate.values:
            try:
                float(candidate.values[0])
            except ValueError:
                messages.append(
                    f"operator {candidate.operator!r} requires a numeric value"
                )
        domain = field_domain(candidate, tools, subjects)
        if domain and candidate.operator in {
            "eq",
            "neq",
            "in",
            "not_in",
            "contains_any",
        }:
            invalid = sorted(set(candidate.values) - set(domain), key=str.casefold)
            if invalid:
                messages.append(
                    f"values {invalid!r} are outside the declared domain {sorted(domain)!r}"
                )
        findings.append(ValidationFinding(candidate.candidate_id, tuple(messages)))
    return findings


def _scope_covers(
    covering: frozenset[str] | None, covered: frozenset[str] | None
) -> bool:
    if covering is None:
        return True
    if covered is None:
        return False
    return covering.issuperset(covered)


def _set_condition(
    operator: str, values: tuple[str, ...]
) -> tuple[str, set[str]] | None:
    if operator == "eq":
        return "positive", set(values[:1])
    if operator == "in":
        return "positive", set(values)
    if operator == "neq":
        return "negative", set(values[:1])
    if operator == "not_in":
        return "negative", set(values)
    if operator == "contains_any":
        return "contains", set(values)
    return None


def _numeric_bound(candidate: Candidate) -> float | None:
    if (
        candidate.operator not in {"lt", "lte", "gt", "gte"}
        or len(candidate.values) != 1
    ):
        return None
    try:
        return float(candidate.values[0])
    except ValueError:
        return None


def _condition_covers(covering: Candidate, covered: Candidate) -> bool:
    if covering.operator == covered.operator and covering.values == covered.values:
        return True
    left = _set_condition(covering.operator, covering.values)
    right = _set_condition(covered.operator, covered.values)
    if left and right:
        left_kind, left_values = left
        right_kind, right_values = right
        if left_kind == right_kind == "positive":
            return left_values.issuperset(right_values)
        if left_kind == right_kind == "negative":
            return left_values.issubset(right_values)
        if left_kind == right_kind == "contains":
            return left_values.issuperset(right_values)
        if left_kind == "negative" and right_kind == "positive":
            return left_values.isdisjoint(right_values)
    left_bound = _numeric_bound(covering)
    right_bound = _numeric_bound(covered)
    if left_bound is None or right_bound is None:
        return False
    if covering.operator in {"gt", "gte"} and covered.operator in {"gt", "gte"}:
        if left_bound < right_bound:
            return True
        return left_bound == right_bound and (
            covering.operator == "gte" or covered.operator == "gt"
        )
    if covering.operator in {"lt", "lte"} and covered.operator in {"lt", "lte"}:
        if left_bound > right_bound:
            return True
        return left_bound == right_bound and (
            covering.operator == "lte" or covered.operator == "lt"
        )
    return False


def _conditions_overlap(left: Candidate, right: Candidate) -> bool:
    left_set = _set_condition(left.operator, left.values)
    right_set = _set_condition(right.operator, right.values)
    if left_set and right_set:
        left_kind, left_values = left_set
        right_kind, right_values = right_set
        if left_kind == right_kind == "positive":
            return bool(left_values & right_values)
        if left_kind == right_kind == "contains":
            return bool(left_values & right_values)
        if left_kind == right_kind == "negative":
            return True
        if left_kind == "negative" and right_kind == "positive":
            return bool(right_values - left_values)
        if left_kind == "positive" and right_kind == "negative":
            return bool(left_values - right_values)
    if _numeric_bound(left) is not None and _numeric_bound(right) is not None:
        if left.operator in {"gt", "gte"} and right.operator in {"lt", "lte"}:
            return _numeric_ranges_overlap(left, right)
        if right.operator in {"gt", "gte"} and left.operator in {"lt", "lte"}:
            return _numeric_ranges_overlap(right, left)
        return True
    return left.operator == right.operator and left.values == right.values


def _numeric_ranges_overlap(lower: Candidate, upper: Candidate) -> bool:
    low = _numeric_bound(lower)
    high = _numeric_bound(upper)
    assert low is not None and high is not None
    if low < high:
        return True
    return low == high and lower.operator == "gte" and upper.operator == "lte"


def analyze_relationships(candidates: list[Candidate]) -> list[Relationship]:
    relationships: list[Relationship] = []
    for index, left in enumerate(candidates):
        for right in candidates[index + 1 :]:
            if left.tool != right.tool or left.fields != right.fields:
                continue
            scopes_overlap = (
                left.subject_scope is None
                or right.subject_scope is None
                or bool(left.subject_scope & right.subject_scope)
            )
            if not scopes_overlap:
                continue
            if left.action != right.action:
                if _conditions_overlap(left, right):
                    relationships.append(
                        Relationship(
                            "Conflict",
                            left.candidate_id,
                            right.candidate_id,
                            "overlapping conditions have different actions",
                        )
                    )
                continue
            if left.exact_key == right.exact_key:
                relationships.append(
                    Relationship(
                        "Duplicate",
                        left.candidate_id,
                        right.candidate_id,
                        f"{right.candidate_id} repeats {left.candidate_id}",
                    )
                )
                continue
            left_covers = _scope_covers(
                left.subject_scope, right.subject_scope
            ) and _condition_covers(left, right)
            right_covers = _scope_covers(
                right.subject_scope, left.subject_scope
            ) and _condition_covers(right, left)
            if left_covers or right_covers:
                covering, covered = (left, right) if left_covers else (right, left)
                relationships.append(
                    Relationship(
                        "Covered",
                        covering.candidate_id,
                        covered.candidate_id,
                        f"{covered.candidate_id} is covered by {covering.candidate_id}",
                    )
                )
            elif _conditions_overlap(left, right):
                relationships.append(
                    Relationship(
                        "Overlap",
                        left.candidate_id,
                        right.candidate_id,
                        "deny conditions overlap but neither covers the other",
                    )
                )
            else:
                relationships.append(
                    Relationship(
                        "Additive",
                        left.candidate_id,
                        right.candidate_id,
                        "deny conditions add distinct values or ranges",
                    )
                )
    return relationships


def analyze_existing_relationships(
    candidates: list[Candidate], existing_rules: list[Candidate]
) -> list[Relationship]:
    """Compare candidates with normalized existing guidance behavior."""
    relationships: list[Relationship] = []
    for candidate in candidates:
        for existing in existing_rules:
            if candidate.tool != existing.tool or candidate.fields != existing.fields:
                continue
            scopes_overlap = (
                candidate.subject_scope is None
                or existing.subject_scope is None
                or bool(candidate.subject_scope & existing.subject_scope)
            )
            if not scopes_overlap:
                continue
            if candidate.action != existing.action:
                if _conditions_overlap(candidate, existing):
                    relationships.append(
                        Relationship(
                            "Conflict",
                            candidate.candidate_id,
                            existing.candidate_id,
                            "candidate and existing rule have overlapping conditions with different actions",
                        )
                    )
                continue
            if candidate.exact_key == existing.exact_key:
                relationships.append(
                    Relationship(
                        "Duplicate",
                        candidate.candidate_id,
                        existing.candidate_id,
                        f"{candidate.candidate_id} repeats existing {existing.candidate_id}",
                    )
                )
                continue
            existing_covers = _scope_covers(
                existing.subject_scope, candidate.subject_scope
            ) and _condition_covers(existing, candidate)
            candidate_covers = _scope_covers(
                candidate.subject_scope, existing.subject_scope
            ) and _condition_covers(candidate, existing)
            if existing_covers:
                relationships.append(
                    Relationship(
                        "Covered",
                        candidate.candidate_id,
                        existing.candidate_id,
                        f"{candidate.candidate_id} is already covered by existing {existing.candidate_id}",
                    )
                )
            elif candidate_covers:
                relationships.append(
                    Relationship(
                        "Additive",
                        candidate.candidate_id,
                        existing.candidate_id,
                        f"{candidate.candidate_id} broadens existing {existing.candidate_id}; emit only the uncovered difference or recommend replacement",
                    )
                )
            elif _conditions_overlap(candidate, existing):
                relationships.append(
                    Relationship(
                        "Overlap",
                        candidate.candidate_id,
                        existing.candidate_id,
                        "candidate and existing rule overlap but neither covers the other",
                    )
                )
            else:
                relationships.append(
                    Relationship(
                        "Additive",
                        candidate.candidate_id,
                        existing.candidate_id,
                        "candidate adds a distinct condition in an existing tool/field group",
                    )
                )
    return relationships


def suggest_exact_unions(candidates: list[Candidate]) -> list[UnionSuggestion]:
    """Return safe single-condition unions for identical candidate groups."""
    grouped: dict[tuple[Any, ...], list[Candidate]] = {}
    for candidate in candidates:
        key = (
            candidate.tool,
            candidate.subject_scope,
            candidate.fields,
            candidate.action,
        )
        grouped.setdefault(key, []).append(candidate)
    suggestions: list[UnionSuggestion] = []
    for group in grouped.values():
        if len(group) < 2:
            continue
        conditions = [_set_condition(item.operator, item.values) for item in group]
        if any(condition is None for condition in conditions):
            continue
        typed = [condition for condition in conditions if condition is not None]
        kinds = {kind for kind, _ in typed}
        operator: str | None = None
        values: set[str] = set()
        if kinds == {"positive"}:
            values = set().union(*(item for _, item in typed))
            operator = "eq" if len(values) == 1 else "in"
        elif kinds == {"contains"}:
            values = set().union(*(item for _, item in typed))
            operator = "contains_any"
        elif kinds == {"negative"}:
            values = set.intersection(*(item for _, item in typed))
            if values:
                operator = "neq" if len(values) == 1 else "not_in"
        elif kinds == {"positive", "negative"}:
            positives = set().union(
                *(item for kind, item in typed if kind == "positive")
            )
            negatives = set.intersection(
                *(item for kind, item in typed if kind == "negative")
            )
            if positives.issubset(negatives):
                values = negatives - positives
                if values:
                    operator = "neq" if len(values) == 1 else "not_in"
        if operator is None:
            continue
        normalized_values = tuple(sorted(values, key=str.casefold))
        if any(
            item.operator == operator and item.values == normalized_values
            for item in group
        ):
            continue
        suggestions.append(
            UnionSuggestion(
                tuple(item.candidate_id for item in group), operator, normalized_values
            )
        )
    return suggestions


def find_normalized_text_duplicates(
    guidance_text: str, updated_text: str
) -> list[tuple[int, int]]:
    def normalized_lines(text: str) -> dict[str, list[int]]:
        result: dict[str, list[int]] = {}
        for line_number, line in enumerate(text.splitlines(), 1):
            line = re.sub(r"^\s*\d+[.)]\s*", "", line)
            normalized = " ".join(line.casefold().split()).strip()
            if normalized:
                result.setdefault(normalized, []).append(line_number)
        return result

    original = normalized_lines(guidance_text)
    updated = normalized_lines(updated_text)
    return [
        (source_line, updated_line)
        for text, source_lines in original.items()
        for source_line in source_lines
        for updated_line in updated.get(text, [])
    ]


def validate_existing_rule_numbers(
    existing_rules: list[Candidate], guidance_text: str
) -> list[ValidationFinding]:
    numbered = {
        int(match.group(1))
        for line in guidance_text.splitlines()
        if (match := re.match(r"^\s*(\d+)[.)]\s+", line))
    }
    findings: list[ValidationFinding] = []
    for rule in existing_rules:
        raw_number = rule.sources[0] if rule.sources else ""
        match = re.search(r"\d+", raw_number)
        messages: tuple[str, ...] = ()
        if not match or int(match.group(0)) not in numbered:
            messages = (f"references missing guidance rule {raw_number!r}",)
        findings.append(ValidationFinding(rule.candidate_id, messages))
    return findings


def render_report(
    candidates: list[Candidate],
    existing_rules: list[Candidate],
    validations: list[ValidationFinding],
    relationships: list[Relationship],
    existing_relationships: list[Relationship],
    unions: list[UnionSuggestion],
    text_duplicates: list[tuple[int, int]],
) -> str:
    candidate_ids = {candidate.candidate_id for candidate in candidates}
    invalid_count = sum(
        not item.valid and item.candidate_id in candidate_ids for item in validations
    )
    lines = [
        "Guidance reconciliation (read-only)",
        f"Candidates: {len(candidates)} | Valid: {len(candidates) - invalid_count} | Invalid: {invalid_count}",
        f"Existing normalized rules: {len(existing_rules)}",
        "",
        "Validation",
    ]
    if not validations:
        lines.append("- No candidates found.")
    for finding in validations:
        if finding.valid:
            lines.append(f"- {finding.candidate_id}: PASS")
        else:
            lines.append(
                f"- {finding.candidate_id}: INVALID — {'; '.join(finding.messages)}"
            )
    lines.extend(["", "Relationships"])
    if relationships:
        for item in relationships:
            lines.append(
                f"- {item.verdict}: {item.left} / {item.right} — {item.detail}"
            )
    else:
        lines.append("- None.")
    lines.extend(["", "Existing guidance relationships"])
    if existing_relationships:
        for item in existing_relationships:
            lines.append(
                f"- {item.verdict}: {item.left} / {item.right} — {item.detail}"
            )
    else:
        lines.append("- None.")
    lines.extend(["", "Exact union simplifications"])
    if unions:
        for item in unions:
            values = "{" + ", ".join(item.values) + "}"
            lines.append(
                f"- {', '.join(item.candidate_ids)} -> {item.operator} {values}"
            )
    else:
        lines.append("- None.")
    lines.extend(["", "Exact normalized-text duplicates"])
    if text_duplicates:
        for guidance_line, updated_line in text_duplicates:
            lines.append(
                f"- guidance.txt:{guidance_line} = guidance_updated.txt:{updated_line}"
            )
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "Result: findings are suggestions; no files were modified.",
        ]
    )
    return "\n".join(lines)


def reconcile(
    analysis_path: Path,
    tool_definitions_path: Path,
    system_vars_path: Path,
    guidance_path: Path,
    guidance_updated_path: Path | None = None,
) -> str:
    if not analysis_path.is_file():
        raise ReconciliationError(f"Step D artifact is missing: {analysis_path}")
    if not guidance_path.is_file():
        raise ReconciliationError(f"guidance file is missing: {guidance_path}")
    try:
        analysis = analysis_path.read_text(encoding="utf-8")
        guidance = guidance_path.read_text(encoding="utf-8")
        updated = (
            guidance_updated_path.read_text(encoding="utf-8")
            if guidance_updated_path and guidance_updated_path.is_file()
            else ""
        )
    except OSError as exc:
        raise ReconciliationError(
            f"could not read reconciliation input: {exc}"
        ) from exc
    candidates = parse_candidate_table(analysis)
    existing_rules = parse_existing_guidance_table(analysis)
    tools = load_tool_schema(tool_definitions_path)
    subjects = load_subject_schema(system_vars_path)
    validations = validate_candidates(candidates, tools, subjects)
    existing_validations = validate_candidates(existing_rules, tools, subjects)
    number_validations = validate_existing_rule_numbers(existing_rules, guidance)
    invalid_numbers = {
        item.candidate_id: item.messages
        for item in number_validations
        if not item.valid
    }
    existing_validations = [
        ValidationFinding(
            item.candidate_id,
            item.messages + invalid_numbers.get(item.candidate_id, ()),
        )
        for item in existing_validations
    ]
    for finding in existing_validations:
        if not finding.valid:
            validations.append(
                ValidationFinding(
                    finding.candidate_id,
                    tuple(
                        f"existing guidance: {message}" for message in finding.messages
                    ),
                )
            )
    valid_ids = {item.candidate_id for item in validations if item.valid}
    valid_candidates = [
        candidate for candidate in candidates if candidate.candidate_id in valid_ids
    ]
    valid_existing_ids = {
        item.candidate_id for item in existing_validations if item.valid
    }
    valid_existing = [
        rule for rule in existing_rules if rule.candidate_id in valid_existing_ids
    ]
    return render_report(
        candidates,
        existing_rules,
        validations,
        analyze_relationships(valid_candidates),
        analyze_existing_relationships(valid_candidates, valid_existing),
        suggest_exact_unions(valid_candidates),
        find_normalized_text_duplicates(guidance, updated),
    )


def _resolve(base: Path, value: str, label: str) -> Path:
    if not value:
        raise ReconciliationError(f"{label} is not configured")
    path = Path(value)
    return path if path.is_absolute() else base / path


def reconcile_from_environment(environment: dict[str, str] | None = None) -> str:
    env = os.environ if environment is None else environment
    base = Path(env.get("BASE_URL") or ".")
    if not base.is_absolute():
        base = Path.cwd() / base
    target = _resolve(base, env.get("TARGET_AGENT_PATH", ""), "TARGET_AGENT_PATH")
    guidance = _resolve(base, env.get("GUIDANCE_FILE", ""), "GUIDANCE_FILE")
    system_vars = _resolve(base, env.get("SYSTEM_VAR_FILE", ""), "SYSTEM_VAR_FILE")
    return reconcile(
        target
        / "smith"
        / "guidelines-security-analysis"
        / "owasp_policy_guidelines.md",
        target / "smith" / "tool_definitions.json",
        system_vars,
        guidance,
        guidance.with_name("guidance_updated.txt"),
    )
