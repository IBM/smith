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
import re
from dataclasses import dataclass, field
from pathlib import Path

from .console import out

# Case-file prefixes carry provenance: the generators name their output, and
# nothing inside a case file records where it came from.
BYPASS_PREFIX = "bypass_test_case"
CROSS_VALIDATED_PREFIX = "cv_test_case"
PROMPTFOO_PREFIX = "promptfoo_test_case"


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
    #: Promptfoo cases present as files, counted separately from `promptfoo`
    #: (a prompt-level count read from the generator's own artifact).
    promptfoo_on_disk: int = 0
    rows: list[tuple[str, int]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (self.legit_allow + self.legit_disallow + self.bypass
                + self.promptfoo + self.ares + self.cross_validated)

    @property
    def on_disk(self) -> int:
        """Cases that exist as files under test_cases/{allow,disallow}/."""
        return (self.legit_allow + self.legit_disallow + self.bypass
                + self.promptfoo_on_disk + self.cross_validated)


def read_suite(root: Path) -> SuiteComposition:
    comp = SuiteComposition()
    for label in ("allow", "disallow"):
        for path in _cases(root, label):
            name = path.name
            if name.startswith(BYPASS_PREFIX):
                comp.bypass += 1
            elif name.startswith(CROSS_VALIDATED_PREFIX):
                comp.cross_validated += 1
            elif name.startswith(PROMPTFOO_PREFIX):
                comp.promptfoo_on_disk += 1
            elif label == "allow":
                comp.legit_allow += 1
            else:
                comp.legit_disallow += 1

    refs = root / "references"
    comp.promptfoo = _count(_load(refs / "decomp_attack_file_promptfoo.json"))
    comp.ares = _count(_load(refs / "decomp_attack_file.json"))
    return comp


def show_suite(root: Path, log_dir: Path) -> SuiteComposition:
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
        rows.append(("cross-validated (relabelled)", comp.cross_validated))

    width = max(len(name) for name, _ in rows)
    for name, value in rows:
        out.say(f"  {name:<{width}}  {value:>6,}")
    out.say(f"  {out.dim}{'-' * (width + 8)}{out.off}")
    out.say(f"  {'total cases on disk':<{width}}  {comp.on_disk:>6,}")
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
    """Counts for the translation stage. """
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
    """how many cases survived translation."""
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
    present: bool = False
    move_to_allow: int = 0
    move_to_disallow: int = 0
    removed: int = 0
    kept: int = 0
    removed_from_allow: int = 0
    removed_from_disallow: int = 0


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
        for case in report.get("cases") or []:
            action = case.get("suggested_action") or "keep"
            # `path` is the case's location at report time, i.e. before the
            # apply step moved anything, so it names the source bucket.
            source = "disallow" if "/disallow/" in (
                case.get("path") or "").replace("\\", "/") else "allow"
            if action == "move_to_allow":
                cv.move_to_allow += 1
            elif action == "move_to_disallow":
                cv.move_to_disallow += 1
            elif action == "remove":
                cv.removed += 1
                if source == "disallow":
                    cv.removed_from_disallow += 1
                else:
                    cv.removed_from_allow += 1
            else:
                cv.kept += 1
    return cv


def show_cross_validation(root: Path, log_dir: Path) -> CrossValidation:
    """what the audit decided, per action."""
    cv = read_cross_validation(root)
    out.hdr("Cross-validation")
    if not cv.present:
        out.warn("No references/cross_validate_report.json — "
                 "cross-validation did not run.")
        return cv

    rows = [
        ("failed cases examined", cv.total_failed),
        ("analyzed", cv.analyzed),
        ("moved allow -> disallow", cv.move_to_disallow),
        ("removed (moved disallow to allow)", cv.move_to_allow),
        ("removed (from disallow)", cv.removed_from_disallow),
        ("removed (from allow)", cv.removed_from_allow),
        ("kept as policy issues", cv.kept),
    ]
    width = max(len(name) for name, _ in rows)
    for name, value in rows:
        out.say(f"  {name:<{width}}  {value:>6,}")
    if cv.analyzed:
        corrected = cv.move_to_allow + cv.move_to_disallow + cv.removed
        share = 100.0 * corrected / cv.analyzed
        out.say(f"  {out.dim}{share:.1f}% of examined failures were "
                f"mislabelled, not policy defects{out.off}")
    _write_csv(log_dir / "cross_validation.csv", ["metric", "cases"], rows)
    return cv


@dataclass
class PolicyScore:
    """The confusion matrix and coverage a policy-testing run produced."""

    #: allow/ cases the policy allowed (correct) and denied (wrong).
    allow_allowed: int = 0
    allow_denied: int = 0
    #: disallow/ cases the policy allowed (wrong) and denied (correct).
    disallow_allowed: int = 0
    disallow_denied: int = 0
    covered_lines: int = 0
    not_covered_lines: int = 0
    coverage: float = 0.0
    policy_lines: int = 0
    errors: int = 0
    present: bool = False

    # The confusion matrix, under the convention recorded in
    # tests/integration/helpers.py: a deny is the positive prediction.
    @property
    def tp(self) -> int:
        return self.disallow_denied

    @property
    def fp(self) -> int:
        return self.allow_denied

    @property
    def tn(self) -> int:
        return self.allow_allowed

    @property
    def fn(self) -> int:
        return self.disallow_allowed

    @property
    def allow_total(self) -> int:
        return self.allow_allowed + self.allow_denied

    @property
    def disallow_total(self) -> int:
        return self.disallow_allowed + self.disallow_denied

    @property
    def scored(self) -> int:
        return self.allow_total + self.disallow_total

    @property
    def correct(self) -> int:
        return self.tp + self.tn

    @property
    def accuracy(self) -> float:
        return 100.0 * self.correct / self.scored if self.scored else 0.0

    @property
    def precision(self) -> float:
        hits = self.tp + self.fp
        return 100.0 * self.tp / hits if hits else 0.0

    @property
    def recall(self) -> float:
        actual = self.tp + self.fn
        return 100.0 * self.tp / actual if actual else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


#: `Allowed:`/`Denied:` lines, in the order the two experiments are written.
_DECISION_RE = re.compile(r"^\s*(Allowed|Denied):\s+(\d+)", re.M)
_COVERED_RE = re.compile(r'"covered_lines":\s*(\d+)')
_NOT_COVERED_RE = re.compile(r'"not_covered_lines":\s*(\d+)')
_COVERAGE_RE = re.compile(r'"coverage":\s*([\d.]+)')
_POLICY_LINES_RE = re.compile(
    r"The line number of current policy is:\s*\n\s*(\d+)", re.M)


def read_policy_score(root: Path) -> PolicyScore:
    """Parse references/scorecard/ into a confusion matrix. """
    score = PolicyScore()
    directory = root / "references" / "scorecard"
    summary_file = directory / "scorecard_summary.txt"
    if not summary_file.is_file():
        return score

    text = summary_file.read_text(encoding="utf-8", errors="replace")
    score.present = True
    pairs = [(kind, int(n)) for kind, n in _DECISION_RE.findall(text)]
    if len(pairs) == 4:
        score.allow_allowed, score.allow_denied = pairs[0][1], pairs[1][1]
        score.disallow_allowed, score.disallow_denied = pairs[2][1], pairs[3][1]

    if m := _COVERED_RE.search(text):
        score.covered_lines = int(m.group(1))
    if m := _NOT_COVERED_RE.search(text):
        score.not_covered_lines = int(m.group(1))
    if m := _COVERAGE_RE.search(text):
        score.coverage = float(m.group(1))
    if m := _POLICY_LINES_RE.search(text):
        score.policy_lines = int(m.group(1))

    errors_file = directory / "errors.txt"
    if errors_file.is_file():
        score.errors = sum(1 for line in errors_file.read_text(
            encoding="utf-8", errors="replace").splitlines() if line.strip())
    return score


def show_policy_score(root: Path, log_dir: Path,
                      header: str = "Policy testing") -> PolicyScore:
    """the confusion matrix, derived metrics and policy coverage."""
    score = read_policy_score(root)
    out.hdr(header)
    if not score.present:
        out.warn("No references/scorecard/scorecard_summary.txt — "
                 "policy testing did not run.")
        return score

    out.say(f"  {'expected':<10}  {'allowed':>8}  {'denied':>8}  {'total':>8}")
    out.say(f"  {out.dim}{'-' * 40}{out.off}")
    out.say(f"  {'allow':<10}  {score.allow_allowed:>8,}  "
            f"{score.allow_denied:>8,}  {score.allow_total:>8,}")
    out.say(f"  {'disallow':<10}  {score.disallow_allowed:>8,}  "
            f"{score.disallow_denied:>8,}  {score.disallow_total:>8,}")
    out.say(f"  {out.dim}{'-' * 40}{out.off}")
    out.say(f"  {'total':<10}  "
            f"{score.allow_allowed + score.disallow_allowed:>8,}  "
            f"{score.allow_denied + score.disallow_denied:>8,}  "
            f"{score.scored:>8,}")

    out.say("")
    metrics = [
        ("true positives (deny, correct)", f"{score.tp:,}"),
        ("true negatives (allow, correct)", f"{score.tn:,}"),
        ("false positives (denied, should allow)", f"{score.fp:,}"),
        ("false negatives (allowed, should deny)", f"{score.fn:,}"),
        ("accuracy", f"{score.accuracy:.1f}%"),
        ("precision", f"{score.precision:.1f}%"),
        ("recall", f"{score.recall:.1f}%"),
        ("F1", f"{score.f1:.1f}%"),
        ("policy coverage", f"{score.coverage:.1f}%"),
        ("covered / uncovered lines",
         f"{score.covered_lines:,} / {score.not_covered_lines:,}"),
        ("policy lines", f"{score.policy_lines:,}"),
    ]
    width = max(len(name) for name, _ in metrics)
    for name, value in metrics:
        out.say(f"  {name:<{width}}  {value:>9}")
    if score.errors:
        out.err(f"  {score.errors} case(s) could not be scored — "
                "see references/scorecard/errors.txt")

    _write_csv(log_dir / "policy_score.csv", ["metric", "value"],
               [("expected_allow_allowed", score.allow_allowed),
                ("expected_allow_denied", score.allow_denied),
                ("expected_disallow_allowed", score.disallow_allowed),
                ("expected_disallow_denied", score.disallow_denied),
                ("tp", score.tp), ("fp", score.fp),
                ("tn", score.tn), ("fn", score.fn),
                ("accuracy", round(score.accuracy, 2)),
                ("precision", round(score.precision, 2)),
                ("recall", round(score.recall, 2)),
                ("f1", round(score.f1, 2)),
                ("coverage", round(score.coverage, 2)),
                ("covered_lines", score.covered_lines),
                ("not_covered_lines", score.not_covered_lines),
                ("policy_lines", score.policy_lines)])
    return score


#: `Cluster <n>:` headings in cluster_results.txt, one per failure group.
_CLUSTER_RE = re.compile(r"^Cluster\s+(\d+):", re.M)
#: The two section headings the clustering writes, benign (fp) then malicious (fn).
_FP_SECTION = "Benign commands that should be allowed:"
_FN_SECTION = "Malicious commands that should not get allowed:"
#: The node list a `subgraph N:` block prints, used to tell a real finding
#: from a component that printed `node: []`.
_SUBGRAPH_NODES_RE = re.compile(r"^subgraph\s+\d+:\s*\n\s*node:\s*\n(.*)$",
                                re.M)


@dataclass
class ClusterCount:
    """How many failure clusters a red_suggestion run found."""

    clusters: int = 0
    fp_clusters: int = 0
    fn_clusters: int = 0
    cases: int = 0
    present: bool = False


def read_clusters(path: Path) -> ClusterCount:
    """Count clusters in a cluster_results.txt."""
    count = ClusterCount()
    if not path.is_file():
        return count
    text = path.read_text(encoding="utf-8", errors="replace")
    count.present = True
    # An empty file means the run found nothing to cluster, which is a real
    # result (no failures) rather than a missing measurement.
    fp_at = text.find(_FP_SECTION)
    fn_at = text.find(_FN_SECTION)
    for match in _CLUSTER_RE.finditer(text):
        count.clusters += 1
        in_fn = fn_at != -1 and match.start() > fn_at
        if in_fn:
            count.fn_clusters += 1
        elif fp_at != -1:
            count.fp_clusters += 1
    count.cases = len(re.findall(r"^Test Case\s+\d+:", text, re.M))
    return count


def show_patch_effect(before: ClusterCount, after: ClusterCount,
                      before_score, after_score, log_dir: Path) -> None:
    out.hdr("Patching effect (step 6)")
    if not (before.present and after.present):
        out.warn("No cluster_results.txt on one side — "
                 "patching effect not measured.")
        return

    def delta(lhs: int, rhs: int) -> str:
        diff = rhs - lhs
        if diff == 0:
            return "0"
        return f"{diff:+d}"

    rows = [
        ("failure clusters", before.clusters, after.clusters),
        ("  false-positive clusters", before.fp_clusters, after.fp_clusters),
        ("  false-negative clusters", before.fn_clusters, after.fn_clusters),
        ("clustered failing cases", before.cases, after.cases),
    ]
    if before_score.present and after_score.present:
        rows += [
            ("false positives (fp)", before_score.fp, after_score.fp),
            ("false negatives (fn)", before_score.fn, after_score.fn),
            ("failing cases total",
             before_score.fp + before_score.fn,
             after_score.fp + after_score.fn),
            ("policy lines", before_score.policy_lines,
             after_score.policy_lines),
            ("covered lines", before_score.covered_lines,
             after_score.covered_lines),
            ("uncovered lines", before_score.not_covered_lines,
             after_score.not_covered_lines),
        ]

    width = max(len(name) for name, _, _ in rows)
    out.say(f"  {'':<{width}}  {'before':>8}  {'after':>8}  {'delta':>8}")
    out.say(f"  {out.dim}{'-' * (width + 30)}{out.off}")
    for name, lhs, rhs in rows:
        out.say(f"  {name:<{width}}  {lhs:>8,}  {rhs:>8,}  "
                f"{delta(lhs, rhs):>8}")

    if before_score.present and after_score.present:
        out.say("")
        for name, lhs, rhs in (
            ("accuracy", before_score.accuracy, after_score.accuracy),
            ("precision", before_score.precision, after_score.precision),
            ("recall", before_score.recall, after_score.recall),
            ("F1", before_score.f1, after_score.f1),
            ("policy coverage", before_score.coverage, after_score.coverage),
        ):
            out.say(f"  {name:<{width}}  {lhs:>7.1f}%  {rhs:>7.1f}%  "
                    f"{rhs - lhs:>+7.1f}%")

    _write_csv(log_dir / "patch_effect.csv", ["metric", "before", "after"],
               [(name, f"{lhs},{rhs}") for name, lhs, rhs in rows])


#: One `Rule:` line per violation in regal_suggestion.txt, with its category
#: on a following line of the same record.
_REGAL_RULE_RE = re.compile(r"^Rule:\s+(\S+)", re.M)
_REGAL_CATEGORY_RE = re.compile(r"^Category:\s+(\S+)", re.M)


@dataclass
class LintCount:
    """Regal violations found in the policy."""

    violations: int = 0
    rules: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    present: bool = False


def read_lint(path: Path) -> LintCount:
    count = LintCount()
    if not path.is_file():
        return count
    text = path.read_text(encoding="utf-8", errors="replace")
    count.present = True
    names = _REGAL_RULE_RE.findall(text)
    count.violations = len(names)
    count.rules = len(set(names))
    for category in _REGAL_CATEGORY_RE.findall(text):
        count.by_category[category] = count.by_category.get(category, 0) + 1
    return count


@dataclass
class DuplicationCount:
    """Redundancy findings from the duplication analysis."""

    issues: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    subgraphs: int = 0
    #: Blocks printed with `node: []` — a component with nothing nameable in
    #: it. Tracked so a dropped count is explainable rather than just lower.
    empty_subgraphs: int = 0
    present: bool = False


def read_duplication(root: Path) -> DuplicationCount:
    count = DuplicationCount()
    outputs = root / "assets" / "opa" / "outputs"
    report = _load(outputs / "linting_feedback_de-duplication.json")
    if isinstance(report, dict):
        count.present = True
        for issue in report.get("issues") or []:
            count.issues += 1
            category = issue.get("category") or "uncategorized"
            count.by_category[category] = count.by_category.get(category, 0) + 1

    graph = outputs / "graph_suggestion.txt"
    if graph.is_file():
        count.present = True
        text = graph.read_text(encoding="utf-8", errors="replace")
        count.subgraphs = sum(
            1 for nodes in _SUBGRAPH_NODES_RE.findall(text)
            if nodes.strip() not in ("", "[]"))
        count.empty_subgraphs = len(
            re.findall(r"^\s*subgraph\b", text, re.M | re.I)) - count.subgraphs
    return count


def show_refinement_effect(title: str, before, after, rows: list[tuple],
                           log_dir: Path, csv_name: str) -> None:
    out.hdr(title)
    if not (getattr(before, "present", False)
            and getattr(after, "present", False)):
        out.warn("Measurement missing on one side — "
                 "effect not measured.")
        return

    width = max(len(name) for name, _, _ in rows)
    out.say(f"  {'':<{width}}  {'before':>8}  {'after':>8}  {'delta':>8}")
    out.say(f"  {out.dim}{'-' * (width + 30)}{out.off}")
    for name, lhs, rhs in rows:
        diff = rhs - lhs
        out.say(f"  {name:<{width}}  {lhs:>8,}  {rhs:>8,}  "
                f"{(f'{diff:+d}' if diff else '0'):>8}")
    _write_csv(log_dir / csv_name, ["metric", "before", "after"],
               [(name, f"{lhs},{rhs}") for name, lhs, rhs in rows])


def _policy_rows(before_score, after_score) -> list[tuple]:
    if not (before_score is not None and after_score is not None
            and before_score.present and after_score.present):
        return []
    return [
        ("policy lines", before_score.policy_lines, after_score.policy_lines),
        ("covered lines", before_score.covered_lines,
         after_score.covered_lines),
        ("uncovered lines", before_score.not_covered_lines,
         after_score.not_covered_lines),
        ("failing cases", before_score.fp + before_score.fn,
         after_score.fp + after_score.fn),
    ]


def _show_coverage_delta(before_score, after_score, width: int) -> None:
    if not (before_score is not None and after_score is not None
            and before_score.present and after_score.present):
        return
    out.say("")
    out.say(f"  {'policy coverage':<{width}}  {before_score.coverage:>7.1f}%  "
            f"{after_score.coverage:>7.1f}%  "
            f"{after_score.coverage - before_score.coverage:>+7.1f}%")


def show_lint_effect(before: LintCount, after: LintCount,
                     log_dir: Path, before_score=None,
                     after_score=None) -> None:
    categories = sorted(set(before.by_category) | set(after.by_category))
    rows = [("regal violations", before.violations, after.violations),
            ("distinct rules", before.rules, after.rules)]
    rows += [(f"  {name}", before.by_category.get(name, 0),
              after.by_category.get(name, 0)) for name in categories]
    rows += _policy_rows(before_score, after_score)
    show_refinement_effect("Regal effect (step 7)", before, after, rows,
                           log_dir, "regal_effect.csv")
    _show_coverage_delta(before_score, after_score,
                         max(len(n) for n, _, _ in rows))


def show_duplication_effect(before: DuplicationCount, after: DuplicationCount,
                            log_dir: Path, before_score=None,
                            after_score=None) -> None:
    categories = sorted(set(before.by_category) | set(after.by_category))
    rows = [("redundancy issues", before.issues, after.issues)]
    rows += [(f"  {name}", before.by_category.get(name, 0),
              after.by_category.get(name, 0)) for name in categories]
    rows.append(("unreachable subgraphs", before.subgraphs, after.subgraphs))
    rows += _policy_rows(before_score, after_score)
    show_refinement_effect("Duplication effect (step 8)", before, after, rows,
                           log_dir, "duplication_effect.csv")
    _show_coverage_delta(before_score, after_score,
                         max(len(n) for n, _, _ in rows))


def _write_csv(path: Path, header: list[str],
               rows: list[tuple[str, int]]) -> None:
    lines = [",".join(header)]
    lines += [f"{name.replace(',', ' ')},{value}" for name, value in rows]
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out.say(f"  {out.dim}csv: {path}{out.off}")
    except OSError as exc:
        out.warn(f"Could not write {path.name}: {exc}")
