# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Validate and explicitly merge a pending guidance addendum."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from smith.tools.guidance_reconciliation import ReconciliationError
from smith.tools.security_catalog import CATALOG_PATH

RULE = re.compile(r"^(\d+)\.\s+(\S.*)$")
BULLET_RULE = re.compile(r"^[-*+]\s+(\S.*)$")
HEADING = re.compile(r"^#{1,6}\s+\S")
HEADING_LEVEL = re.compile(r"^(#{1,6})\s")
NUMBERED_HEADING = re.compile(r"^(#{1,6})\s+(\d+)[.)]\s+(\S.*)$")


def _numbered_rules(text: str, label: str) -> list[tuple[int, str]]:
    rules: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            if label == "guidance_updated.txt":
                raise ReconciliationError(
                    f"{label} contains a blank line at line {line_number}"
                )
            continue
        match = RULE.fullmatch(line)
        if match:
            rules.append((int(match.group(1)), match.group(2)))
        elif label == "guidance_updated.txt":
            raise ReconciliationError(
                f"{label} line {line_number} is not '<number>. <single-line rule>'"
            )
    return rules


def _guidance_style(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    if any(NUMBERED_HEADING.match(line) for line in lines):
        return "numbered_sections"
    if any(HEADING.match(line) for line in lines):
        return "markdown"
    if lines and all(RULE.fullmatch(line) for line in lines):
        return "numbered"
    return "plain"


def _markdown_rules(text: str, label: str) -> list[tuple[int, str]]:
    rules: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        if HEADING.match(line):
            raise ReconciliationError(
                f"{label} must contain only rule bullets, without headings or "
                "phase metadata"
            )
        if RULE.fullmatch(line):
            raise ReconciliationError(
                f"{label} must preserve the sectioned Markdown style of guidance.txt"
            )
        match = BULLET_RULE.match(line)
        if match:
            rules.append((line_number, match.group(1)))
            continue
        if line[:1].isspace() and rules:
            continue
        raise ReconciliationError(
            f"{label} line {line_number} is not a top-level rule bullet or "
            "indented continuation"
        )
    return rules


def _section_level(text: str) -> int:
    """Heading level of the numbered rule sections in guidance.txt."""
    for line in text.splitlines():
        if match := NUMBERED_HEADING.match(line):
            return len(match.group(1))
    raise ReconciliationError("guidance.txt contains no numbered rule sections")


def _existing_sections(text: str) -> list[tuple[int, str]]:
    return [
        (int(match.group(2)), match.group(3))
        for line in text.splitlines()
        if (match := NUMBERED_HEADING.match(line))
    ]


def _section_rules(text: str, label: str, level: int) -> list[tuple[int, str]]:
    """Parse an addendum of ``<level> <number>. <title>`` sections.

    Each section is one rule: its heading, then a body in any form the
    existing sections use. Headings deeper than ``level`` may appear inside a
    section; any other heading would break the guidance's structure.
    """
    rules: list[tuple[int, str]] = []
    expected = f"'{'#' * level} <number>. <title>'"
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        match = NUMBERED_HEADING.match(line)
        if match and len(match.group(1)) == level:
            rules.append((int(match.group(2)), match.group(3)))
            continue
        heading = HEADING_LEVEL.match(line)
        if not rules:
            raise ReconciliationError(
                f"{label} must start with a {expected} section, as guidance.txt does"
            )
        if heading and len(heading.group(1)) <= level:
            raise ReconciliationError(
                f"{label} line {line_number} is a heading other than a {expected} "
                "section, which guidance.txt does not use for rules"
            )
    return rules


def _plain_rules(text: str, label: str) -> list[tuple[int, str]]:
    rules: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        if (
            RULE.fullmatch(stripped)
            or HEADING.match(stripped)
            or BULLET_RULE.match(stripped)
        ):
            raise ReconciliationError(
                f"{label} must preserve the plain one-rule-per-line style of "
                "guidance.txt"
            )
        rules.append((line_number, stripped))
    return rules


def _existing_rule_entries(text: str, style: str) -> list[tuple[int, str]]:
    if style == "numbered":
        return _numbered_rules(text, "guidance.txt")
    if style == "numbered_sections":
        return _existing_sections(text)
    if style == "markdown":
        return [
            (line_number, match.group(1))
            for line_number, line in enumerate(text.splitlines(), 1)
            if (match := BULLET_RULE.match(line))
        ]
    return [
        (line_number, line.strip())
        for line_number, line in enumerate(text.splitlines(), 1)
        if line.strip()
    ]


def _rule_duplicates(
    existing: list[tuple[int, str]], proposed: list[tuple[int, str]]
) -> list[tuple[int, int]]:
    normalized_existing: dict[str, list[int]] = {}
    for line_number, rule in existing:
        normalized = " ".join(rule.casefold().split())
        normalized_existing.setdefault(normalized, []).append(line_number)
    return [
        (existing_line, proposed_line)
        for proposed_line, rule in proposed
        for existing_line in normalized_existing.get(
            " ".join(rule.casefold().split()), []
        )
    ]


def validate_addendum(guidance: Path, addendum: Path) -> list[tuple[int, str]]:
    if not guidance.is_file():
        raise ReconciliationError(f"guidance file is missing: {guidance}")
    if not addendum.is_file():
        raise ReconciliationError(f"no guidance addendum is pending: {addendum}")
    guidance_text = guidance.read_text(encoding="utf-8")
    addendum_text = addendum.read_text(encoding="utf-8")
    if not addendum_text:
        raise ReconciliationError("guidance_updated.txt is empty")
    style = _guidance_style(guidance_text)
    if style in ("numbered", "numbered_sections"):
        if style == "numbered":
            existing = _numbered_rules(guidance_text, "guidance.txt")
            proposed = _numbered_rules(addendum_text, "guidance_updated.txt")
        else:
            existing = _existing_sections(guidance_text)
            proposed = _section_rules(
                addendum_text, "guidance_updated.txt", _section_level(guidance_text)
            )
        if not proposed:
            raise ReconciliationError("guidance_updated.txt contains no numbered rules")
        start = max(number for number, _ in existing) + 1
        expected = list(range(start, start + len(proposed)))
        actual = [number for number, _ in proposed]
        if actual != expected:
            raise ReconciliationError(
                f"guidance_updated.txt numbering is {actual}; expected {expected}"
            )
    elif style == "markdown":
        proposed = _markdown_rules(addendum_text, "guidance_updated.txt")
    else:
        proposed = _plain_rules(addendum_text, "guidance_updated.txt")
    if not proposed:
        raise ReconciliationError("guidance_updated.txt contains no guidance rules")
    duplicates = _rule_duplicates(
        _existing_rule_entries(guidance_text, style), proposed
    )
    if duplicates:
        raise ReconciliationError(
            "guidance_updated.txt repeats existing guidance at line pairs "
            + ", ".join(f"{left}/{right}" for left, right in duplicates)
        )
    normalized = [" ".join(rule.casefold().split()) for _, rule in proposed]
    if len(normalized) != len(set(normalized)):
        raise ReconciliationError(
            "guidance_updated.txt contains duplicate proposed rules"
        )
    return proposed


def _verify_checkpoint(
    state_path: Path,
    enforcement_path: Path,
    guidance: Path,
    addendum: Path,
    catalog: Path,
) -> None:
    if not state_path.is_file():
        raise ReconciliationError(
            "security analysis checkpoint is missing; run "
            "smith --flag security_analysis_checkpoint --phase D"
        )
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        phase = state["phases"]["D"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ReconciliationError(
            f"security analysis checkpoint is malformed: {exc}"
        ) from exc
    if state.get("schema") != "security-analysis-state-v1":
        raise ReconciliationError(
            "security analysis checkpoint has an unsupported schema"
        )
    if state.get("latest_phase") != "D" or phase.get("status") != "PASS":
        raise ReconciliationError(
            "security analysis does not have a passing Phase D checkpoint"
        )
    actual_hash = hashlib.sha256(enforcement_path.read_bytes()).hexdigest()
    if (
        phase.get("artifact") != str(enforcement_path)
        or phase.get("sha256") != actual_hash
    ):
        raise ReconciliationError(
            "owasp_policy_guidelines.md changed after its Phase D checkpoint"
        )
    for name, path in (
        ("guidance", guidance),
        ("guidance_updated", addendum),
        ("owasp_catalog", catalog),
    ):
        recorded = state.get("inputs", {}).get(name)
        actual = (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        )
        if (
            not recorded
            or recorded.get("path") != str(path)
            or recorded.get("sha256") != actual
        ):
            raise ReconciliationError(
                f"{path.name} changed after its Phase D checkpoint"
            )


def merge_guidance(
    guidance: Path,
    addendum: Path,
    state_path: Path,
    enforcement_path: Path,
    catalog: Path = CATALOG_PATH,
) -> str:
    """Append a verified addendum atomically, then remove the pending file."""
    _verify_checkpoint(state_path, enforcement_path, guidance, addendum, catalog)
    proposed = validate_addendum(guidance, addendum)
    original = guidance.read_bytes()
    addition = addendum.read_bytes()
    if _guidance_style(original.decode("utf-8")) in ("markdown", "numbered_sections"):
        separator = (
            b""
            if not original or original.endswith(b"\n\n")
            else b"\n" if original.endswith(b"\n") else b"\n\n"
        )
    else:
        separator = b"" if not original or original.endswith(b"\n") else b"\n"
    merged = original + separator + addition
    temporary = guidance.with_name(f".{guidance.name}.merge.tmp")
    try:
        temporary.write_bytes(merged)
        if temporary.read_bytes() != merged or not merged.startswith(original):
            raise ReconciliationError("guidance merge read-back validation failed")
        temporary.replace(guidance)
        if guidance.read_bytes() != merged:
            raise ReconciliationError(
                "guidance merge final read-back validation failed"
            )
    finally:
        if temporary.exists():
            temporary.unlink()
    addendum.unlink()
    return f"Merged {len(proposed)} guidance rule(s); removed {addendum}"
