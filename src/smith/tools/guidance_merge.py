# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Validate and explicitly merge a pending guidance addendum."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from smith.tools.guidance_reconciliation import ReconciliationError

RULE = re.compile(r"^(\d+)\.\s+(\S.*)$")
BULLET_RULE = re.compile(r"^[-*+]\s+(\S.*)$")
HEADING = re.compile(r"^#{1,6}\s+\S")


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
    if any(HEADING.match(line) for line in lines):
        return "markdown"
    if lines and all(RULE.fullmatch(line) for line in lines):
        return "numbered"
    return "plain"


def _markdown_rules(text: str, label: str) -> list[tuple[int, str]]:
    rules: list[tuple[int, str]] = []
    saw_heading = False
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        if HEADING.match(line):
            saw_heading = True
            continue
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
            f"{label} line {line_number} is not a heading, top-level bullet, "
            "or indented continuation"
        )
    if not saw_heading:
        raise ReconciliationError(
            f"{label} must preserve the sectioned Markdown style of guidance.txt"
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
    if style == "numbered":
        existing = _numbered_rules(guidance_text, "guidance.txt")
        proposed = _numbered_rules(addendum_text, "guidance_updated.txt")
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
    state_path: Path, enforcement_path: Path, guidance: Path, addendum: Path
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
    for name, path in (("guidance", guidance), ("guidance_updated", addendum)):
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
) -> str:
    """Append a verified addendum atomically, then remove the pending file."""
    _verify_checkpoint(state_path, enforcement_path, guidance, addendum)
    proposed = validate_addendum(guidance, addendum)
    original = guidance.read_bytes()
    addition = addendum.read_bytes()
    if _guidance_style(original.decode("utf-8")) == "markdown":
        separator = (
            b""
            if not original or original.endswith(b"\n\n")
            else b"\n"
            if original.endswith(b"\n")
            else b"\n\n"
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


def merge_from_environment(environment: dict[str, str] | None = None) -> str:
    env = os.environ if environment is None else environment
    base = Path(env.get("BASE_URL") or ".")
    if not base.is_absolute():
        base = Path.cwd() / base
    target_value = env.get("TARGET_AGENT_PATH")
    guidance_value = env.get("GUIDANCE_FILE")
    if not target_value:
        raise ReconciliationError("TARGET_AGENT_PATH is not configured")
    if not guidance_value:
        raise ReconciliationError("GUIDANCE_FILE is not configured")
    target = Path(target_value)
    target = target if target.is_absolute() else base / target
    guidance = Path(guidance_value)
    guidance = guidance if guidance.is_absolute() else base / guidance
    analysis_dir = target / "smith" / "guidelines-security-analysis"
    return merge_guidance(
        guidance,
        guidance.with_name("guidance_updated.txt"),
        analysis_dir / "analysis_state.json",
        analysis_dir / "owasp_policy_guidelines.md",
    )
