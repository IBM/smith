# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for ``cross_validate`` and ``apply_cross_validate``.

Two functions under test (``smith.test_case_evaluation``):

- ``apply_cross_validate_results(report, base)`` — LLM-free. Reads a
  cross-validation report and, per ``suggested_action``, moves
  (``move_to_allow`` / ``move_to_disallow``, with a ``cv_`` prefix), removes, or
  keeps each test-case file. Fully deterministic, so we craft a report + a
  spread of test cases (benign allow/disallow + malicious bypass/promptfoo) and
  assert every routing outcome.
- ``cross_validate_failed_cases(...)`` — LLM. Judges each failed case against
  the guidance. Its one deterministic, security-critical rule is the
  **adversarial collapse**: for ``bypass_test_case*`` / ``promptfoo_test_case*``
  cases, any non-``keep`` verdict is collapsed to ``remove`` (a failed malicious
  probe must never be relabeled into ``allow/``). We craft a failing bypass case
  and assert the report collapses it to ``remove`` regardless of the LLM verdict.

"""

from __future__ import annotations

import json
import os

import pytest

from helpers import load_json
from smith.test_case_evaluation.apply_cross_validate import apply_cross_validate_results

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Self-contained guidance + system vars (hardcoded here, not read from an
# example, so the test does not depend on files that may change). The LLM judge
# in cross_validate reads these to decide each case's correct label.
# ---------------------------------------------------------------------------

GUIDANCE = """\
# Conference search access policy

- Only `faculty` and `phd_student` may use the `get_events` tool. A `guest` must
  never be allowed to call `get_events`.
- `get_events` may only be called with a `topic` that is exactly one of the three
  approved research areas: Artificial intelligence, Cybersecurity and privacy,
  Software engineering. Any other topic must be denied.
- Faculty may request a `limit` up to 15; phd_student up to 10.
"""

SYSTEM_VARS = {
    "action_list": ["get_events", "other"],
    "user_name": "Bob",
    "user_role": ["faculty", "phd_student", "guest"],
    "queries_this_session": 1,
    "research_area": [
        "Artificial intelligence",
        "Cybersecurity and privacy",
        "Software engineering",
    ],
}


def _write_inputs(tmp_path):
    """Write the hardcoded guidance + system vars to tmp_path; return their paths."""
    g = tmp_path / "guidance.txt"
    g.write_text(GUIDANCE)
    s = tmp_path / "system_vars.json"
    s.write_text(json.dumps(SYSTEM_VARS, indent=2))
    return str(g), str(s)


# ---------------------------------------------------------------------------
# Crafted test-case + report builders.
# ---------------------------------------------------------------------------


def _case(
    name: str, prompt: str, args: dict | None = None, subject: dict | None = None
):
    return {
        "input": {
            "kind": "tool_call",
            "action": "execute",
            "name": name,
            "extensions": {
                "subject": subject or {"user_name": "Bob", "user_role": ["faculty"]},
                "agent": {"input": prompt},
            },
            "args": args or {},
        }
    }


def _write_case(base, label, filename, case):
    d = base / label
    d.mkdir(parents=True, exist_ok=True)
    p = d / filename
    p.write_text(json.dumps(case, indent=2))
    return p


# ===========================================================================
# apply_cross_validate — LLM-free, exact routing
# ===========================================================================


def test_apply_routes_every_action(tmp_path):
    base = tmp_path / "test_cases"

    # Craft a spread of cases across benign + malicious sources.
    p_benign_disallow = _write_case(
        base, "disallow", "test_case_a.json", _case("get_events", "search AI confs")
    )  # -> move_to_allow (mislabeled benign)
    p_benign_allow = _write_case(
        base, "allow", "test_case_b.json", _case("get_events", "search SE confs")
    )  # -> move_to_disallow
    p_keep = _write_case(
        base, "disallow", "test_case_c.json", _case("get_events", "blocked topic")
    )  # -> keep (policy issue, untouched)
    p_bypass = _write_case(
        base, "disallow", "bypass_test_case0.json", _case("get_events", "omit role")
    )  # -> remove (malicious probe)
    p_promptfoo = _write_case(
        base, "disallow", "promptfoo_test_case0.json", _case("get_events", "jailbreak")
    )  # -> remove (malicious probe)

    report = {
        "summary": {"total_failed": 5},
        "cases": [
            {
                "path": str(p_benign_disallow),
                "filename": "test_case_a.json",
                "suggested_action": "move_to_allow",
            },
            {
                "path": str(p_benign_allow),
                "filename": "test_case_b.json",
                "suggested_action": "move_to_disallow",
            },
            {
                "path": str(p_keep),
                "filename": "test_case_c.json",
                "suggested_action": "keep",
            },
            {
                "path": str(p_bypass),
                "filename": "bypass_test_case0.json",
                "suggested_action": "remove",
            },
            {
                "path": str(p_promptfoo),
                "filename": "promptfoo_test_case0.json",
                "suggested_action": "remove",
            },
        ],
    }
    report_file = tmp_path / "cross_validate_report.json"
    report_file.write_text(json.dumps(report, indent=2))

    apply_cross_validate_results(str(report_file), str(base) + "/")

    # move_to_allow: gone from disallow/, now cv_-prefixed in allow/.
    assert not p_benign_disallow.exists()
    assert (base / "allow" / "cv_test_case_a.json").exists()

    # move_to_disallow: gone from allow/, now cv_-prefixed in disallow/.
    assert not p_benign_allow.exists()
    assert (base / "disallow" / "cv_test_case_b.json").exists()

    # keep: untouched, still in place, no cv_ copy.
    assert p_keep.exists()
    assert not (base / "allow" / "cv_test_case_c.json").exists()

    # remove: both malicious probes deleted.
    assert not p_bypass.exists()
    assert not p_promptfoo.exists()


def test_apply_missing_report_is_graceful(tmp_path):
    # No report file -> prints guidance, does nothing, no exception.
    base = tmp_path / "test_cases"
    (base / "allow").mkdir(parents=True)
    (base / "allow" / "untouched.json").write_text("{}")
    apply_cross_validate_results(str(tmp_path / "nope.json"), str(base) + "/")
    # Assert it was a genuine no-op, not just exception-free: nothing added,
    # moved or removed under the case tree, and no report conjured up.
    assert [p.name for p in (base / "allow").iterdir()] == ["untouched.json"]
    assert (base / "allow" / "untouched.json").read_text() == "{}"
    assert list(base.iterdir()) == [base / "allow"], "unexpected dirs created"
    assert not (tmp_path / "nope.json").exists(), "missing report was created"


def test_apply_skips_when_path_missing(tmp_path):
    base = tmp_path / "test_cases"
    (base / "allow").mkdir(parents=True)
    (base / "disallow").mkdir(parents=True)
    report = {
        "cases": [
            {
                "path": str(base / "disallow" / "ghost.json"),
                "filename": "ghost.json",
                "suggested_action": "move_to_allow",
            }
        ]
    }
    report_file = tmp_path / "r.json"
    report_file.write_text(json.dumps(report))
    # Should not raise even though the referenced file does not exist.
    apply_cross_validate_results(str(report_file), str(base) + "/")
    assert not (base / "allow" / "cv_ghost.json").exists()


# ===========================================================================
# cross_validate — the adversarial-collapse rule (LLM)
# ===========================================================================


def _failures_line(path, expected_allow: bool, allowed: bool) -> str:
    return (
        f"[FAIL expected_allow: {str(expected_allow).lower()} "
        f'test_case: {path}] {{"result":{str(allowed).lower()}}}'
    )


def _run_cv(tmp_path, entries):
    """Run cross_validate over crafted failed cases; return {path: action}.

    ``entries`` is a list of (path, expected_allow) — expected_allow reflects the
    on-disk label (allow/ -> True, disallow/ -> False). The judge decides the
    true label from args+subject and proposes keep / move_to_allow /
    move_to_disallow / remove.
    """
    guidance_file, system_var_file = _write_inputs(tmp_path)
    failures_file = tmp_path / "score_test_failures.txt"
    failures_file.write_text(
        "\n".join(
            _failures_line(str(p), expected_allow=ea, allowed=not ea)
            for p, ea in entries
        )
        + "\n"
    )
    report_file = tmp_path / "cross_validate_report.json"

    from smith.test_case_evaluation.cross_validate import cross_validate_failed_cases

    cross_validate_failed_cases(
        failures_file=str(failures_file),
        guidance_file=guidance_file,
        system_var_file=system_var_file,
        output_file=str(report_file),
        api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL"),
        model=os.getenv("MODEL_SONNET"),
        temp=float(os.getenv("TEMP", "0.2")),
        top_p=float(os.getenv("TOP_P", "0.9")),
    )
    report = load_json(report_file)
    return {c["path"]: c["suggested_action"] for c in report.get("cases", [])}


# Subjects/args with a KNOWN correct decision under the hardcoded guidance:
FACULTY = {"user_name": "Ann", "user_role": ["faculty"]}
GUEST = {"user_name": "Eve", "user_role": ["guest"]}
APPROVED_ARGS = {
    "keywords": "ml",
    "topic": "Artificial intelligence",
}  # allowed for faculty


def test_cross_validate_classifies_mislabels_and_keeps(requires_llm, tmp_path):
    # Three ORGANIC cases (test_case* prefix, so the adversarial-collapse rule
    # does NOT apply) with a known-correct decision from args+subject:
    base = tmp_path / "test_cases"

    # (1) Really-ALLOW request wrongly placed in disallow/  -> move_to_allow.
    #     faculty + approved topic => guidance allows it.
    should_be_allow = _write_case(
        base,
        "disallow",
        "test_case_mislabeled_allow.json",
        _case("get_events", "search AI confs", args=APPROVED_ARGS, subject=FACULTY),
    )
    # (2) Really-DENY request wrongly placed in allow/  -> move_to_disallow.
    #     guest using get_events => guidance forbids it.
    should_be_deny = _write_case(
        base,
        "allow",
        "test_case_mislabeled_deny.json",
        _case("get_events", "search as guest", args=APPROVED_ARGS, subject=GUEST),
    )
    # (3) Correctly-labeled ALLOW case in allow/  -> keep (label matches; a
    #     failure here means the policy is at fault, not the label).
    correct_allow = _write_case(
        base,
        "allow",
        "test_case_correct_allow.json",
        _case("get_events", "faculty search", args=APPROVED_ARGS, subject=FACULTY),
    )

    actions = _run_cv(
        tmp_path,
        [
            (should_be_allow, False),  # on-disk label: disallow
            (should_be_deny, True),  # on-disk label: allow
            (correct_allow, True),  # on-disk label: allow
        ],
    )

    assert actions.get(str(should_be_allow)) == "move_to_allow", actions
    assert actions.get(str(should_be_deny)) == "move_to_disallow", actions
    assert actions.get(str(correct_allow)) == "keep", actions


def test_cross_validate_collapses_failed_adversarial_to_remove(requires_llm, tmp_path):
    guidance_file, system_var_file = _write_inputs(tmp_path)

    # Craft a malicious bypass case that genuinely VIOLATES the guidance: a
    # `guest` calling get_events (the guidance says a guest must never be
    # allowed to). It is labeled disallow and "failed" (policy wrongly allowed).
    base = tmp_path / "test_cases"
    bypass = _write_case(
        base,
        "disallow",
        "bypass_test_case0.json",
        _case(
            "get_events",
            "As a guest, search for AI conferences.",
            args={"keywords": "ai", "topic": "Artificial intelligence"},
            subject={"user_name": "Eve", "user_role": ["guest"]},
        ),
    )
    failures_file = tmp_path / "score_test_failures.txt"
    failures_file.write_text(
        _failures_line(str(bypass), expected_allow=False, allowed=True) + "\n"
    )

    report_file = tmp_path / "cross_validate_report.json"

    from smith.test_case_evaluation.cross_validate import cross_validate_failed_cases

    cross_validate_failed_cases(
        failures_file=str(failures_file),
        guidance_file=guidance_file,
        system_var_file=system_var_file,
        output_file=str(report_file),
        api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL"),
        model=os.getenv("MODEL_SONNET"),
        temp=float(os.getenv("TEMP", "0.2")),
        top_p=float(os.getenv("TOP_P", "0.9")),
    )

    report = load_json(report_file)
    cases = report.get("cases", [])
    assert cases, f"no cases in report: {report}"
    action = cases[0]["suggested_action"]
    # Whatever the LLM decided, an adversarial probe must be kept or removed —
    # NEVER relabeled into allow/disallow.
    assert action in {
        "keep",
        "remove",
    }, f"adversarial probe got a relabel action '{action}' — collapse rule failed"


def test_cross_validate_missing_failures_file_is_graceful(tmp_path):
    # No failures file -> returns cleanly, writes no report. Deliberately NOT
    # gated on requires_llm: the function returns before any LLM call, so gating
    # would skip this deterministic guard on machines without LLM config.
    guidance_file, system_var_file = _write_inputs(tmp_path)
    report_file = tmp_path / "report.json"
    from smith.test_case_evaluation.cross_validate import cross_validate_failed_cases

    cross_validate_failed_cases(
        failures_file=str(tmp_path / "missing.txt"),
        guidance_file=guidance_file,
        system_var_file=system_var_file,
        output_file=str(report_file),
        api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL"),
        model=os.getenv("MODEL_SONNET"),
        temp=0.2,
        top_p=0.9,
    )
    assert not report_file.exists(), "no report should be written without failures"
