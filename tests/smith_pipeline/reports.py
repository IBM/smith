# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
"""Per-stage evaluation tables, printed next to the token/cost table.

These are the tables `smith_evaluation_plan.md` asks for, emitted by the step
that produces the numbers so a run is transcribable without re-deriving
anything afterwards:

    generate test cases   -> RQ3 suite composition (by provenance)
    translate test cases  -> the translation half of RQ4's funnel
    cross-validate        -> the correction half of RQ4's funnel

Every reader is defensive: a stage that did not run, or an artifact a given
`ATTACK_TOOLS` setting never produces, is reported as absent rather than
raising. Each table is also written as CSV beside the run's logs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .console import out

# Case-file prefixes carry provenance: the generators name their output, and
# nothing inside a case file records where it came from.
BYPASS_PREFIX = "bypass_test_case"
CROSS_VALIDATED_PREFIX = "cv_test_case"


def _load(path: Path):
    """Parsed JSON, or None when the file is absent or unreadable."""
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None


def _count(value) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    return 0


def case_dir(root: Path, label: str) -> Path:
    return root / "references" / "test_cases" / label


def _cases(root: Path, label: str) -> list[Path]:
    d = case_dir(root, label)
    return sorted(d.glob("*.json")) if d.is_dir() else []


@dataclass
class SuiteComposition:
    """How many cases of each provenance the generation stage produced."""

    legit_allow: int = 0
    legit_disallow: int = 0
    bypass: int = 0
    promptfoo: int = 0
    ares: int = 0
    cross_validated: int = 0
    rows: list[tuple[str, int]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (self.legit_allow + self.legit_disallow + self.bypass
                + self.promptfoo + self.ares + self.cross_validated)


def read_suite(root: Path) -> SuiteComposition:
    """Partition the generated suite by provenance.

    Legitimate and adversarial-native cases share the plain `test_case`
    prefix, so the prompt-level counts come from the generators' own
    artifacts rather than from filenames.
    """
    comp = SuiteComposition()
    for label in ("allow", "disallow"):
        for path in _cases(root, label):
            name = path.name
            if name.startswith(BYPASS_PREFIX):
                comp.bypass += 1
            elif name.startswith(CROSS_VALIDATED_PREFIX):
                comp.cross_validated += 1
            elif label == "allow":
                comp.legit_allow += 1
            else:
                comp.legit_disallow += 1

    refs = root / "references"
    comp.promptfoo = _count(_load(refs / "decomp_attack_file_promptfoo.json"))
    comp.ares = _count(_load(refs / "decomp_attack_file.json"))
    return comp


def show_suite(root: Path, log_dir: Path) -> SuiteComposition:
    """RQ3: suite composition by provenance."""
    comp = read_suite(root)
    out.hdr("Test suite composition")
    if comp.total == 0:
        out.warn("No test cases under references/test_cases/.")
        return comp

    rows = [
        ("legitimate allow", comp.legit_allow),
        ("legitimate disallow", comp.legit_disallow),
        ("adversarial bypass", comp.bypass),
        ("adversarial promptfoo", comp.promptfoo),
        ("adversarial ARES (native)", comp.ares),
    ]
    if comp.cross_validated:
        # Present only on a re-run: apply_cross_validate renames corrected
        # cases, so they are no longer attributable to their original source.
        rows.append(("cross-validated (relabelled)", comp.cross_validated))

    width = max(len(name) for name, _ in rows)
    for name, value in rows:
        out.say(f"  {name:<{width}}  {value:>6,}")
    out.say(f"  {out.dim}{'-' * (width + 8)}{out.off}")
    out.say(f"  {'total cases on disk':<{width}}  "
            f"{comp.total - comp.promptfoo - comp.ares:>6,}")
    if comp.promptfoo or comp.ares:
        out.say(f"  {out.dim}prompt-level counts come from the generators' "
                f"artifacts, not from files on disk{out.off}")
    comp.rows = rows
    _write_csv(log_dir / "suite_composition.csv",
               ["partition", "cases"], rows)
    return comp


@dataclass
class TranslationFunnel:
    translated: int = 0
    mismatched: int = 0
    misclassified: int = 0

    @property
    def initial(self) -> int:
        return self.translated + self.mismatched + self.misclassified


def read_translation(root: Path) -> TranslationFunnel:
    """Counts for the translation stage.

    `translate_case` moves a case it cannot resolve to a tool into
    `test_cases/wrong_cases/`, naming it for the reason, so the removals are
    recoverable from that directory.
    """
    funnel = TranslationFunnel()
    funnel.translated = len(_cases(root, "allow")) + len(_cases(root,
                                                               "disallow"))
    # wrong_cases/ holds one SUBDIRECTORY per rejection reason, so the cases
    # are a level deeper than in allow/ and disallow/.
    wrong = case_dir(root, "wrong_cases")
    if wrong.is_dir():
        funnel.mismatched = len(list((wrong / "mcp_unrelated").rglob("*.json")))
        funnel.misclassified = sum(
            len(list(sub.rglob("*.json")))
            for sub in wrong.iterdir()
            if sub.is_dir() and sub.name != "mcp_unrelated"
        )
        # Any case files sitting directly in wrong_cases/ are counted too,
        # rather than silently dropped from the funnel.
        funnel.misclassified += len(list(wrong.glob("*.json")))
    return funnel


def show_translation(root: Path, log_dir: Path) -> TranslationFunnel:
    """RQ4 (first half): how many cases survived translation."""
    funnel = read_translation(root)
    out.hdr("Translation funnel")
    if funnel.initial == 0:
        out.warn("No test cases found — did generation run?")
        return funnel

    rows = [
        ("initial cases", funnel.initial),
        ("removed: tool-name mismatch", funnel.mismatched),
        ("removed: misclassified", funnel.misclassified),
        ("translated", funnel.translated),
    ]
    width = max(len(name) for name, _ in rows)
    for name, value in rows:
        out.say(f"  {name:<{width}}  {value:>6,}")
    if removed := funnel.mismatched + funnel.misclassified:
        out.say(f"  {out.dim}{removed} case(s) moved to "
                f"references/test_cases/wrong_cases/{out.off}")
    _write_csv(log_dir / "translation_funnel.csv",
               ["stage", "cases"], rows)
    return funnel


@dataclass
class CrossValidation:
    total_failed: int = 0
    analyzed: int = 0
    mislabeled: int = 0
    policy_issue: int = 0
    validated: int = 0
    present: bool = False


def read_cross_validation(root: Path) -> CrossValidation:
    """The cross-validate report's own summary, plus the resulting suite size."""
    cv = CrossValidation()
    report = _load(root / "references" / "cross_validate_report.json")
    if isinstance(report, dict):
        summary = report.get("summary") or {}
        cv.present = True
        cv.total_failed = int(summary.get("total_failed") or 0)
        cv.analyzed = int(summary.get("analyzed") or 0)
        cv.mislabeled = int(summary.get("mislabeled") or 0)
        cv.policy_issue = int(summary.get("policy_issue") or 0)
    cv.validated = len(_cases(root, "allow")) + len(_cases(root, "disallow"))
    return cv


def show_cross_validation(root: Path, log_dir: Path) -> CrossValidation:
    """RQ4 (second half): corrections applied, and the validated suite size."""
    cv = read_cross_validation(root)
    out.hdr("Cross-validation")
    if not cv.present:
        out.warn("No references/cross_validate_report.json — "
                 "cross-validation did not run.")
        return cv

    rows = [
        ("failed cases examined", cv.total_failed),
        ("analyzed", cv.analyzed),
        ("corrected (mislabelled)", cv.mislabeled),
        ("kept as policy issues", cv.policy_issue),
        ("validated suite", cv.validated),
    ]
    width = max(len(name) for name, _ in rows)
    for name, value in rows:
        out.say(f"  {name:<{width}}  {value:>6,}")
    if cv.analyzed:
        share = 100.0 * cv.mislabeled / cv.analyzed
        out.say(f"  {out.dim}{share:.1f}% of examined failures were "
                f"mislabelled, not policy defects{out.off}")
    _write_csv(log_dir / "cross_validation.csv", ["metric", "cases"], rows)
    return cv


def _write_csv(path: Path, header: list[str],
               rows: list[tuple[str, int]]) -> None:
    lines = [",".join(header)]
    lines += [f"{name.replace(',', ' ')},{value}" for name, value in rows]
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out.say(f"  {out.dim}csv: {path}{out.off}")
    except OSError as exc:
        out.warn(f"Could not write {path.name}: {exc}")
