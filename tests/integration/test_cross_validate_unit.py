# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the functions behind ``--flag cross_validate`` / ``apply_cross_validate``.

Two flags form one review loop over the cases the policy got *wrong*::

    cross_validate        policy_checking_results()  -> score the policy, writing
                                                        score_test_failures.txt
                          cross_validate_failed_cases()
                                                     -> parse_failures()
                                                     -> load_test_case()
                                                     -> LLM judge, per failure
                                                     -> is_adversarial_case() collapse
                                                     -> cross_validate_report.json

    apply_cross_validate  apply_cross_validate_results()
                                                     -> move / delete case files

The security-critical rule lives here: for an **adversarial** case
(``bypass_test_case*`` / ``promptfoo_test_case*``) any non-``keep`` verdict is
collapsed to ``remove``. A failed malicious probe must never be relabelled into
``allow/``, whatever the model says — so that collapse is tested against a model
that actively tries to relabel it.

FUNCTIONS UNDER TEST
--------------------
Listed — and laid out in this file — in the order the flags execute them.

STEP 1 · scoring the policy (``run_policy_evaluation``)
    Covered in ``test_policy_testing_unit.py``, where it is the flag's own
    top-level function. Not duplicated here.

STEP 2 · ``smith.test_case_evaluation.cross_validate``
    ``cross_validate_failed_cases`` — the no-LLM early returns, report shape,
                                      fenced/plain/malformed model output, the
                                      adversarial-collapse rule, and per-case
                                      error handling

    …and the machinery it drives, in the order a failure meets it:

    ``parse_failures``              — line filtering, label/decision extraction,
                                      path normalization, the compact-JSON match
    ``load_test_case``              — wrapped and bare envelopes, defaults
    ``is_adversarial_case``         — prefix detection, independent of directory

STEP 3 · ``smith.test_case_evaluation.apply_cross_validate``
    ``apply_cross_validate_results`` — every routing action, the ``cv_`` prefix,
                                      unknown actions, missing paths, empty
                                      reports, preserved files, and the
                                      created-on-demand destination bucket

NOT COVERED HERE (integration lane — see ``test_cross_validate_integration.py``)
    Real LLM judgements; a real ``make test`` against OPA in Docker; and the two
    flags driven end to end through the CLI.

Env-free: the OpenAI client is replaced at its module seam, so no network call,
no credentials and no Docker are involved.
"""

from __future__ import annotations

import json

import pytest

from smith.test_case_evaluation import cross_validate as cv_mod
from smith.test_case_evaluation.apply_cross_validate import apply_cross_validate_results
from smith.test_case_evaluation.cross_validate import (
    cross_validate_failed_cases,
    is_adversarial_case,
    load_test_case,
    parse_failures,
)

from data_builders import (
    cross_validate_report,
    cv_case,
    envelope_case,
    failure_line,
    failures_file,
    guidance,
    system_vars,
    write_json,
    write_text,
)
from fakes import FakeOpenAI, fenced

pytestmark = pytest.mark.unit


# ===========================================================================
# STEP 2 · parse_failures — turning the scorecard's failure lines into work
# ===========================================================================


def test_parses_label_and_decision_from_a_failure_line(unit_env):
    path = unit_env.root / "references" / "test_cases" / "disallow" / "test_case0.json"
    f = write_text(
        unit_env.root / "failures.txt",
        failure_line(path, expected_allow=False, allowed=True),
    )
    (failure,) = parse_failures(str(f))
    # expected_label is the ON-DISK bucket; actual_decision is what OPA returned.
    assert failure["expected_label"] == "disallow"
    assert failure["actual_decision"] == "allow"
    assert failure["path"].endswith("test_case0.json")


def test_expected_allow_true_maps_to_the_allow_label(unit_env):
    f = write_text(
        unit_env.root / "failures.txt",
        failure_line("/x/test_case1.json", expected_allow=True, allowed=False),
    )
    (failure,) = parse_failures(str(f))
    assert failure["expected_label"] == "allow"
    assert failure["actual_decision"] == "deny"


def test_non_failure_lines_are_ignored(unit_env):
    f = write_text(
        unit_env.root / "failures.txt",
        "Scorecard Summary\n"
        "\n"
        "# a comment\n"
        + failure_line("/x/test_case0.json", False, True)
        + "\n[PASS expected_allow: true test_case: /x/ok.json]\n",
    )
    failures = parse_failures(str(f))
    assert len(failures) == 1, "only [FAIL lines are failures"
    assert failures[0]["path"].endswith("test_case0.json")


def test_paths_are_normalized(unit_env):
    f = write_text(
        unit_env.root / "failures.txt",
        '[FAIL expected_allow: false test_case: /a/b/../c/test_case0.json] {"result":true}\n',
    )
    (failure,) = parse_failures(str(f))
    assert failure["path"] == "/a/c/test_case0.json"


def test_an_empty_failures_file_yields_no_failures(unit_env):
    f = write_text(unit_env.root / "failures.txt", "")
    assert parse_failures(str(f)) == []


# ===========================================================================
# STEP 2 · load_test_case — reading the case the judge will be shown
# ===========================================================================


def test_loads_a_wrapped_envelope(unit_env):
    path = write_json(
        unit_env.root / "case.json",
        envelope_case(
            name="get_events",
            prompt="find AI conferences",
            args={"topic": "Artificial intelligence"},
            subject={"user_name": "Ann", "user_role": ["faculty"]},
        ),
    )
    data = load_test_case(str(path))
    assert data["tool_name"] == "get_events"
    assert data["args"] == {"topic": "Artificial intelligence"}
    assert data["subject"]["user_role"] == ["faculty"]
    assert data["agent_input"] == "find AI conferences"


def test_loads_a_bare_envelope_without_the_input_wrapper(unit_env):
    # It unwraps data.get("input", data), so a bare inner object also works.
    inner = envelope_case(name="get_events")["input"]
    path = write_json(unit_env.root / "bare.json", inner)
    assert load_test_case(str(path))["tool_name"] == "get_events"


def test_absent_fields_fall_back_to_documented_defaults(unit_env):
    path = write_json(unit_env.root / "sparse.json", {"input": {}})
    data = load_test_case(str(path))
    assert data["tool_name"] == "unknown"
    assert data["args"] == {}
    assert data["subject"] == {}
    assert data["agent_input"] == ""


# ===========================================================================
# STEP 2 · is_adversarial_case — the gate the collapse rule depends on
# ===========================================================================


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("bypass_test_case0.json", True),
        ("promptfoo_test_case12.json", True),
        ("test_case0.json", False),
        ("cv_test_case0.json", False),
        # A name merely CONTAINING the prefix is not a match: the check is
        # startswith on the basename.
        ("my_bypass_test_case0.json", False),
    ],
)
def test_adversarial_detection_by_filename_prefix(filename, expected):
    # A pure string check on the basename — no filesystem access, so the parent
    # directory need not exist. "/anywhere/" merely supplies something to strip.
    assert is_adversarial_case(f"/anywhere/{filename}") is expected


def test_detection_ignores_the_directory():
    # A bypass case sitting in allow/ is still adversarial — the label folder is
    # exactly what cross-validation may be about to change.
    assert is_adversarial_case("/refs/test_cases/allow/bypass_test_case3.json") is True


# ===========================================================================
# STEP 2 · cross_validate_failed_cases — early returns that need no LLM
# ===========================================================================


@pytest.fixture
def judge_inputs(unit_env):
    """Guidance + system vars on disk, and the report path to write to."""
    return {
        "guidance_file": str(write_text(unit_env.root / "guidance.txt", guidance())),
        "system_var_file": str(
            write_json(unit_env.root / "system_vars.json", system_vars())
        ),
        "output_file": str(unit_env.root / "references" / "cv_report.json"),
    }


def _run_cv(judge_inputs, failures_path):
    """Run the judge with whatever client is patched in; return the report or None."""
    cross_validate_failed_cases(
        failures_file=str(failures_path),
        guidance_file=judge_inputs["guidance_file"],
        system_var_file=judge_inputs["system_var_file"],
        output_file=judge_inputs["output_file"],
        api_key="unit-test-key",
        openai_base_url="http://unit.test/v1",
        model="unit-test-model",
        temp=0.2,
        top_p=0.9,
    )
    from pathlib import Path

    report_path = Path(judge_inputs["output_file"])
    return json.loads(report_path.read_text()) if report_path.exists() else None


def test_a_missing_failures_file_writes_no_report_and_calls_no_model(
    unit_env, judge_inputs, monkeypatch
):
    fake = FakeOpenAI()  # no responses: any call would raise
    monkeypatch.setattr(cv_mod, "OpenAI", fake.as_factory())

    report = _run_cv(judge_inputs, unit_env.root / "absent.txt")
    assert report is None, "no failures file -> no report"
    assert fake.call_count == 0, "the model must not be consulted"


def test_an_empty_failures_file_returns_before_any_model_call(
    unit_env, judge_inputs, monkeypatch
):
    fake = FakeOpenAI()
    monkeypatch.setattr(cv_mod, "OpenAI", fake.as_factory())

    empty = write_text(unit_env.root / "failures.txt", "")
    assert _run_cv(judge_inputs, empty) is None
    assert fake.call_count == 0


def test_a_failure_pointing_at_a_missing_case_is_skipped(
    unit_env, judge_inputs, monkeypatch
):
    fake = FakeOpenAI()
    monkeypatch.setattr(cv_mod, "OpenAI", fake.as_factory())

    f = write_text(
        unit_env.root / "failures.txt",
        failure_line(unit_env.root / "ghost.json", False, True),
    )
    report = _run_cv(judge_inputs, f)
    assert report["cases"] == [], "a vanished case yields no verdict"
    assert fake.call_count == 0, "and costs no model call"


# ===========================================================================
# STEP 2 · cross_validate_failed_cases — verdicts and the adversarial collapse
# ===========================================================================


def _write_case(unit_env, label, filename, **kwargs):
    path = unit_env.root / "references" / "test_cases" / label / filename
    return write_json(path, envelope_case(**kwargs))


def test_a_mislabel_verdict_is_recorded_with_its_action(
    unit_env, judge_inputs, monkeypatch
):
    case = _write_case(unit_env, "disallow", "test_case0.json", prompt="faculty search")
    fake = FakeOpenAI(
        responses=[
            {
                "label_correct": False,
                "suggested_action": "move_to_allow",
                "confidence": 0.9,
                "reason": "faculty with an approved topic is allowed",
            }
        ]
    )
    monkeypatch.setattr(cv_mod, "OpenAI", fake.as_factory())

    f = write_text(unit_env.root / "failures.txt", failure_line(case, False, True))
    report = _run_cv(judge_inputs, f)

    (entry,) = report["cases"]
    assert entry["suggested_action"] == "move_to_allow"
    assert entry["label_correct"] is False
    assert entry["confidence"] == pytest.approx(0.9)
    assert report["summary"]["mislabeled"] == 1


def test_a_fenced_json_response_is_parsed(unit_env, judge_inputs, monkeypatch):
    # Models routinely wrap JSON in a ```json fence; the parser strips it.
    case = _write_case(unit_env, "allow", "test_case1.json")
    fake = FakeOpenAI(
        responses=[fenced({"label_correct": True, "suggested_action": "keep"})]
    )
    monkeypatch.setattr(cv_mod, "OpenAI", fake.as_factory())

    f = write_text(unit_env.root / "failures.txt", failure_line(case, True, False))
    report = _run_cv(judge_inputs, f)
    assert report["cases"][0]["suggested_action"] == "keep"


def test_malformed_model_output_is_recorded_as_keep(
    unit_env, judge_inputs, monkeypatch
):
    # Unparseable output must never be treated as a relabel instruction: the case
    # is kept and the reason says why.
    case = _write_case(unit_env, "disallow", "test_case2.json")
    fake = FakeOpenAI(responses=["not json at all"])
    monkeypatch.setattr(cv_mod, "OpenAI", fake.as_factory())

    f = write_text(unit_env.root / "failures.txt", failure_line(case, False, True))
    report = _run_cv(judge_inputs, f)

    entry = report["cases"][0]
    assert entry["suggested_action"] == "keep"
    assert "Failed to parse" in entry["reason"]


def test_a_failing_model_call_is_recorded_as_keep(unit_env, judge_inputs, monkeypatch):
    case = _write_case(unit_env, "disallow", "test_case3.json")
    fake = FakeOpenAI(error=RuntimeError("connection reset"))
    monkeypatch.setattr(cv_mod, "OpenAI", fake.as_factory())

    f = write_text(unit_env.root / "failures.txt", failure_line(case, False, True))
    report = _run_cv(judge_inputs, f)

    entry = report["cases"][0]
    assert entry["suggested_action"] == "keep"
    assert "LLM call failed" in entry["reason"]
    assert entry["confidence"] == pytest.approx(0.0)


@pytest.mark.parametrize("prefix", ["bypass_test_case", "promptfoo_test_case"])
@pytest.mark.parametrize(
    "model_action", ["move_to_allow", "move_to_disallow", "remove"]
)
def test_adversarial_non_keep_verdicts_collapse_to_remove(
    unit_env, judge_inputs, monkeypatch, prefix, model_action
):
    # THE security-critical rule. Whatever the model proposes, a failed
    # adversarial probe is never relabelled into a benign bucket.
    case = _write_case(unit_env, "disallow", f"{prefix}0.json", prompt="as a guest…")
    fake = FakeOpenAI(
        responses=[{"label_correct": False, "suggested_action": model_action}]
    )
    monkeypatch.setattr(cv_mod, "OpenAI", fake.as_factory())

    f = write_text(unit_env.root / "failures.txt", failure_line(case, False, True))
    report = _run_cv(judge_inputs, f)

    entry = report["cases"][0]
    assert entry["suggested_action"] == "remove"
    assert (
        "collapsed to 'remove'" in entry["reason"]
    ), "the collapse must be explained in the report, not applied silently"


def test_the_collapse_preserves_the_models_own_reason(
    unit_env, judge_inputs, monkeypatch
):
    # The annotation is appended, not substituted: a reviewer reading the report
    # needs to see WHY the judge wanted to relabel, alongside the fact that the
    # suggestion was overridden.
    case = _write_case(unit_env, "disallow", "bypass_test_case2.json")
    fake = FakeOpenAI(
        responses=[
            {
                "label_correct": False,
                "suggested_action": "move_to_allow",
                "reason": "the payload was neutralized in translation",
            }
        ]
    )
    monkeypatch.setattr(cv_mod, "OpenAI", fake.as_factory())

    f = write_text(unit_env.root / "failures.txt", failure_line(case, False, True))
    entry = _run_cv(judge_inputs, f)["cases"][0]

    assert "neutralized in translation" in entry["reason"]
    assert "collapsed to 'remove'" in entry["reason"]
    # The collapse changes the ACTION only. label_correct still records the
    # judge's actual finding, so the summary counts remain truthful.
    assert entry["label_correct"] is False


def test_an_adversarial_keep_verdict_is_left_alone(unit_env, judge_inputs, monkeypatch):
    # 'keep' is already safe, so the collapse must not fire or annotate.
    case = _write_case(unit_env, "disallow", "bypass_test_case1.json")
    fake = FakeOpenAI(responses=[{"label_correct": True, "suggested_action": "keep"}])
    monkeypatch.setattr(cv_mod, "OpenAI", fake.as_factory())

    f = write_text(unit_env.root / "failures.txt", failure_line(case, False, True))
    entry = _run_cv(judge_inputs, f)["cases"][0]
    assert entry["suggested_action"] == "keep"
    assert "collapsed" not in entry["reason"]


def test_an_organic_case_may_be_relabelled(unit_env, judge_inputs, monkeypatch):
    # The counterpart: a normal test_case* IS eligible for a relabel, which is
    # what makes the adversarial exception meaningful.
    case = _write_case(unit_env, "disallow", "test_case9.json")
    fake = FakeOpenAI(
        responses=[{"label_correct": False, "suggested_action": "move_to_allow"}]
    )
    monkeypatch.setattr(cv_mod, "OpenAI", fake.as_factory())

    f = write_text(unit_env.root / "failures.txt", failure_line(case, False, True))
    entry = _run_cv(judge_inputs, f)["cases"][0]
    assert entry["suggested_action"] == "move_to_allow"


def test_the_prompt_carries_the_guidance_and_the_case_details(
    unit_env, judge_inputs, monkeypatch
):
    # The judge can only be right if it is actually shown the rules and the case.
    case = _write_case(
        unit_env,
        "disallow",
        "test_case4.json",
        prompt="search quantum physics events",
        args={"topic": "Quantum physics"},
    )
    fake = FakeOpenAI(responses=[{"label_correct": True, "suggested_action": "keep"}])
    monkeypatch.setattr(cv_mod, "OpenAI", fake.as_factory())

    f = write_text(unit_env.root / "failures.txt", failure_line(case, False, True))
    _run_cv(judge_inputs, f)

    prompt = fake.last_prompt()
    assert "faculty" in prompt, "the guidance must reach the judge"
    assert "Quantum physics" in prompt, "the case's args must reach the judge"
    assert fake.model_used() == "unit-test-model"


def test_a_long_agent_input_is_truncated_in_the_prompt(
    unit_env, judge_inputs, monkeypatch
):
    # The prompt caps agent_input at 500 chars. A jailbreak payload can be
    # arbitrarily long, so the cap is what keeps one failure from blowing the
    # context window for the whole run.
    case = _write_case(unit_env, "disallow", "test_case7.json", prompt="A" * 900)
    fake = FakeOpenAI(responses=[{"label_correct": True, "suggested_action": "keep"}])
    monkeypatch.setattr(cv_mod, "OpenAI", fake.as_factory())

    f = write_text(unit_env.root / "failures.txt", failure_line(case, False, True))
    _run_cv(judge_inputs, f)

    prompt = fake.last_prompt()
    assert "A" * 500 in prompt
    assert "A" * 501 not in prompt


def test_the_report_summary_counts_both_outcomes(unit_env, judge_inputs, monkeypatch):
    mislabeled = _write_case(unit_env, "disallow", "test_case5.json")
    policy_issue = _write_case(unit_env, "allow", "test_case6.json")
    fake = FakeOpenAI(
        responses=[
            {"label_correct": False, "suggested_action": "move_to_allow"},
            {"label_correct": True, "suggested_action": "keep"},
        ]
    )
    monkeypatch.setattr(cv_mod, "OpenAI", fake.as_factory())

    f = write_text(
        unit_env.root / "failures.txt",
        failures_file([(mislabeled, False, True), (policy_issue, True, False)]),
    )
    report = _run_cv(judge_inputs, f)

    assert report["summary"]["analyzed"] == 2
    assert report["summary"]["mislabeled"] == 1
    assert report["summary"]["policy_issue"] == 1
    assert fake.call_count == 2, "one model call per failure"


def test_a_skipped_case_is_counted_as_failed_but_not_analyzed(
    unit_env, judge_inputs, monkeypatch
):
    # total_failed comes from the failures file; analyzed from what was actually
    # reviewed. They must diverge when a case has vanished, or the report would
    # claim a verdict it never reached.
    real = _write_case(unit_env, "disallow", "test_case8.json")
    fake = FakeOpenAI(responses=[{"label_correct": True, "suggested_action": "keep"}])
    monkeypatch.setattr(cv_mod, "OpenAI", fake.as_factory())

    f = write_text(
        unit_env.root / "failures.txt",
        failures_file(
            [(real, False, True), (unit_env.root / "ghost.json", False, True)]
        ),
    )
    report = _run_cv(judge_inputs, f)

    assert report["summary"]["total_failed"] == 2
    assert report["summary"]["analyzed"] == 1
    assert fake.call_count == 1, "a vanished case must not cost a model call"


def test_the_report_records_what_apply_needs_to_act(
    unit_env, judge_inputs, monkeypatch
):
    # STEP 2 -> STEP 3 seam: apply_cross_validate_results reads exactly `path`,
    # `filename` and `suggested_action`. A report missing any of them would make
    # the next flag a silent no-op.
    case = _write_case(unit_env, "disallow", "test_case10.json")
    fake = FakeOpenAI(
        responses=[{"label_correct": False, "suggested_action": "move_to_allow"}]
    )
    monkeypatch.setattr(cv_mod, "OpenAI", fake.as_factory())

    f = write_text(unit_env.root / "failures.txt", failure_line(case, False, True))
    entry = _run_cv(judge_inputs, f)["cases"][0]

    assert entry["path"] == str(case)
    assert entry["filename"] == "test_case10.json"
    assert entry["suggested_action"] == "move_to_allow"


# ===========================================================================
# STEP 3 · apply_cross_validate_results — acting on the report
# ===========================================================================


@pytest.fixture
def case_tree(unit_env):
    """A mutable case tree (a copy of the frozen set is not needed here)."""
    base = unit_env.root / "references" / "test_cases"
    (base / "allow").mkdir(parents=True, exist_ok=True)
    (base / "disallow").mkdir(parents=True, exist_ok=True)
    return base


def _case_file(case_tree, label, filename):
    return write_json(case_tree / label / filename, envelope_case())


def test_move_to_allow_relocates_with_the_cv_prefix(unit_env, case_tree):
    src = _case_file(case_tree, "disallow", "test_case_a.json")
    report = write_json(
        unit_env.root / "report.json",
        cross_validate_report(cv_case(src, "move_to_allow")),
    )

    apply_cross_validate_results(str(report), str(case_tree) + "/")

    assert not src.exists()
    # The cv_ prefix marks the file as cross-validation-corrected.
    assert (case_tree / "allow" / "cv_test_case_a.json").exists()


def test_move_to_disallow_relocates_the_other_way(unit_env, case_tree):
    src = _case_file(case_tree, "allow", "test_case_b.json")
    report = write_json(
        unit_env.root / "report.json",
        cross_validate_report(cv_case(src, "move_to_disallow")),
    )

    apply_cross_validate_results(str(report), str(case_tree) + "/")

    assert not src.exists()
    assert (case_tree / "disallow" / "cv_test_case_b.json").exists()


def test_a_moved_case_arrives_with_its_content_intact(unit_env, case_tree):
    # A move must not rewrite the case: the relocated file is the same test, just
    # relabelled, and OPA will evaluate exactly these bytes.
    src = _case_file(case_tree, "disallow", "test_case_g.json")
    before = src.read_text()
    report = write_json(
        unit_env.root / "report.json",
        cross_validate_report(cv_case(src, "move_to_allow")),
    )

    apply_cross_validate_results(str(report), str(case_tree) + "/")

    assert (case_tree / "allow" / "cv_test_case_g.json").read_text() == before


@pytest.mark.parametrize(
    "action,bucket", [("move_to_allow", "allow"), ("move_to_disallow", "disallow")]
)
def test_a_destination_bucket_is_created_on_demand(unit_env, action, bucket):
    """Regression: ``shutil.move`` does not create intermediate directories.

    A fresh case tree, or one whose cases were all moved out by a previous run,
    has no such bucket — and the failure was mid-loop, leaving earlier cases
    already moved and the tree partially applied. See FIX.md §5.
    """
    base = unit_env.root / "references" / "test_cases"
    source_bucket = "disallow" if bucket == "allow" else "allow"
    src = write_json(base / source_bucket / "test_case_h.json", envelope_case())
    assert not (base / bucket).exists(), "the destination must be absent to start"

    report = write_json(
        unit_env.root / "report.json", cross_validate_report(cv_case(src, action))
    )
    apply_cross_validate_results(str(report), str(base) + "/")

    assert (base / bucket / "cv_test_case_h.json").exists()


def test_remove_deletes_the_case(unit_env, case_tree):
    src = _case_file(case_tree, "disallow", "bypass_test_case0.json")
    report = write_json(
        unit_env.root / "report.json", cross_validate_report(cv_case(src, "remove"))
    )

    apply_cross_validate_results(str(report), str(case_tree) + "/")
    assert not src.exists()


def test_keep_leaves_the_case_exactly_where_it_was(unit_env, case_tree):
    src = _case_file(case_tree, "disallow", "test_case_c.json")
    before = src.read_text()
    report = write_json(
        unit_env.root / "report.json", cross_validate_report(cv_case(src, "keep"))
    )

    apply_cross_validate_results(str(report), str(case_tree) + "/")

    assert src.exists() and src.read_text() == before
    assert not (case_tree / "allow" / "cv_test_case_c.json").exists()


def test_an_unknown_action_is_skipped_without_touching_the_file(unit_env, case_tree):
    src = _case_file(case_tree, "disallow", "test_case_d.json")
    report = write_json(
        unit_env.root / "report.json",
        cross_validate_report(cv_case(src, "teleport_to_maybe")),
    )

    apply_cross_validate_results(str(report), str(case_tree) + "/")
    assert src.exists(), "an unrecognized action must be inert, not destructive"


def test_a_case_entry_without_an_action_defaults_to_keep(unit_env, case_tree):
    # The default is the safe one: a truncated or hand-edited report must not
    # delete or relabel anything.
    src = _case_file(case_tree, "disallow", "test_case_i.json")
    entry = cv_case(src)
    entry.pop("suggested_action")
    report = write_json(unit_env.root / "report.json", cross_validate_report(entry))

    apply_cross_validate_results(str(report), str(case_tree) + "/")
    assert src.exists()


def test_every_action_routes_correctly_in_one_pass(unit_env, case_tree):
    moved_up = _case_file(case_tree, "disallow", "test_case_1.json")
    moved_down = _case_file(case_tree, "allow", "test_case_2.json")
    kept = _case_file(case_tree, "disallow", "test_case_3.json")
    removed = _case_file(case_tree, "disallow", "promptfoo_test_case0.json")

    report = write_json(
        unit_env.root / "report.json",
        cross_validate_report(
            cv_case(moved_up, "move_to_allow"),
            cv_case(moved_down, "move_to_disallow"),
            cv_case(kept, "keep"),
            cv_case(removed, "remove"),
        ),
    )

    apply_cross_validate_results(str(report), str(case_tree) + "/")

    assert (case_tree / "allow" / "cv_test_case_1.json").exists()
    assert (case_tree / "disallow" / "cv_test_case_2.json").exists()
    assert kept.exists()
    assert not removed.exists()


def test_a_missing_report_is_a_no_op(unit_env, case_tree):
    untouched = _case_file(case_tree, "allow", "test_case_e.json")
    apply_cross_validate_results(
        str(unit_env.root / "absent.json"), str(case_tree) + "/"
    )

    # A genuine no-op: nothing added, moved, removed, or conjured up.
    assert untouched.exists()
    assert [p.name for p in (case_tree / "allow").iterdir()] == ["test_case_e.json"]
    assert not (unit_env.root / "absent.json").exists()


def test_a_report_with_no_cases_is_a_no_op(unit_env, case_tree):
    untouched = _case_file(case_tree, "allow", "test_case_f.json")
    report = write_json(unit_env.root / "report.json", {"summary": {}, "cases": []})

    apply_cross_validate_results(str(report), str(case_tree) + "/")
    assert untouched.exists()


def test_a_case_that_has_already_vanished_is_skipped(unit_env, case_tree):
    ghost = case_tree / "disallow" / "ghost.json"
    report = write_json(
        unit_env.root / "report.json",
        cross_validate_report(cv_case(ghost, "move_to_allow")),
    )

    # Must not raise: applying a stale report is a normal occurrence.
    apply_cross_validate_results(str(report), str(case_tree) + "/")
    assert not (case_tree / "allow" / "cv_ghost.json").exists()


def test_a_stale_entry_does_not_stop_the_rest_of_the_report(unit_env, case_tree):
    # The loop must be resilient: one vanished case in a long report cannot be
    # allowed to abandon the corrections that follow it.
    ghost = case_tree / "disallow" / "ghost.json"
    real = _case_file(case_tree, "disallow", "test_case_j.json")
    report = write_json(
        unit_env.root / "report.json",
        cross_validate_report(
            cv_case(ghost, "move_to_allow"), cv_case(real, "move_to_allow")
        ),
    )

    apply_cross_validate_results(str(report), str(case_tree) + "/")
    assert (case_tree / "allow" / "cv_test_case_j.json").exists()
