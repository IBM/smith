# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the functions behind ``smith --flag bypass_case_generation``.

The flag looks for places the **policy diverges from the guidance**, then turns
each divergence into a concrete adversarial test case::

    detect_bypass_vectors    LLM #1: guidance vs policy -> BypassReport
                             + bypass_report.{json,md}
    synthesize_bypass_cases  LLM #2: each vector -> abstract cases
                             + bypass_cases.json
    convert_bypass_case      route by label -> bypass_test_case*.json under
                             test_cases/{allow,disallow}/

Both LLM calls are faked here, so the parsing, filtering, label derivation and
file routing all run for real.

FUNCTIONS UNDER TEST
--------------------
Listed — and laid out in this file — in the order the flag executes them.

STEP 0 · ``smith.cli``
    ``generate_bypass_cases``   — the missing / empty policy guards, which return
                                  before either LLM is constructed

STEP 1 · ``smith.policy_agent.policy_analysis.bypass.analyze_bypass``
    ``detect_bypass_vectors``   — fence stripping, category filtering, the retry
                                  loop and its empty-report fallback, the written
                                  report pair, and that a transport error
                                  propagates rather than being swallowed

    …and the schema it fills:

    ``BypassReport.to_markdown`` — the empty-report wording a human reads

STEP 2 · ``smith.policy_agent.policy_analysis.bypass.synthesize_cases``
    ``synthesize_bypass_cases`` — the empty-vector short circuit (no LLM at all),
                                  required-field filtering, and the
                                  ``direction`` -> ``label`` derivation

STEP 3 · ``smith.test_generation.convert_test_case``
    ``convert_bypass_case``     — label routing to allow/ vs disallow/ with the
                                  ``bypass_test_case`` prefix, the unknown-label
                                  skip, and ``selected_tools`` filtering

NOT COVERED HERE (integration lane — see ``test_bypass_case_generation_integration.py``)
    Whether a real model finds real divergences in the fixture policy, and the
    CLI wiring that reaches these functions.

Deliberately absent: assertions on prompt text, and on ``_fill_template``'s
template-filling internals — that is ``translate_case``'s logic, covered with the
translation flag. Here it matters only that a converted case comes out as a
well-formed envelope in the right bucket.

Env-free: both ``OpenAI`` boundaries are patched, so no credentials, no network.
"""

from __future__ import annotations

import json

import pytest

from smith.cli import generate_bypass_cases
from smith.policy_agent.policy_analysis.bypass import analyze_bypass as analyze_mod
from smith.policy_agent.policy_analysis.bypass import synthesize_cases as synth_mod
from smith.policy_agent.policy_analysis.bypass.analyze_bypass import (
    MAX_BYPASS_PARSE_ATTEMPTS,
    detect_bypass_vectors,
)
from smith.policy_agent.policy_analysis.bypass.schema import BypassReport, BypassVector
from smith.policy_agent.policy_analysis.bypass.synthesize_cases import (
    synthesize_bypass_cases,
)
from smith.test_generation.convert_test_case import convert_bypass_case

from data_builders import bypass_vector, minimal_policy, write_json, write_text
from fakes import FakeOpenAI, fenced

pytestmark = pytest.mark.unit


#: A synthesized case as the model is asked to return it, before label derivation.
#: ``REQUIRED_FIELDS`` is action/condition/user_input/system_variables.
def synth_case(direction="guidance_deny_policy_allow", **extra) -> dict:
    case = {
        "action": "get_events",
        "condition": "a request omitting the topic field",
        "user_input": "Find me every conference you have.",
        "system_variables": {"user_role": "faculty"},
        "direction": direction,
    }
    case.update(extra)
    return case


@pytest.fixture
def policy(unit_env):
    """A non-empty policy on disk, so the flag's guards pass."""
    return write_text(unit_env.root / "policy.rego", minimal_policy())


def _fake_analyze_llm(monkeypatch, responses):
    fake = FakeOpenAI(responses=responses)
    monkeypatch.setattr(analyze_mod, "OpenAI", fake.as_factory())
    return fake


def _fake_synth_llm(monkeypatch, responses):
    fake = FakeOpenAI(responses=responses)
    monkeypatch.setattr(synth_mod, "OpenAI", fake.as_factory())
    return fake


def _detect(unit_env, policy, out="references/bypass/", **kw):
    """Call ``detect_bypass_vectors`` with the boilerplate arguments filled in."""
    return detect_bypass_vectors(
        "test-key",
        str(unit_env.root / out),
        "http://localhost/v1",
        str(policy),
        "test-model",
        0.0,
        1.0,
        kw.pop("guidance_file", None),
        **kw,
    )


# ===========================================================================
# STEP 0 · the guards in generate_bypass_cases
#
# Deliberately unmocked: both guards return before an LLM client is built, so if
# either ever stopped short-circuiting, the real OpenAI would be constructed and
# these tests would fail loudly instead of silently passing.
# ===========================================================================


@pytest.mark.parametrize(
    "content,expected",
    [(None, "policy not found"), ("", "is empty")],
    ids=["missing", "empty"],
)
def test_an_unusable_policy_skips_before_any_llm_work(
    unit_env, capsys, content, expected
):
    path = unit_env.root / "assets" / "policy.rego"
    if content is not None:
        write_text(path, content)

    result = generate_bypass_cases(
        "key",
        "http://localhost/v1",
        "model",
        0.0,
        1.0,
        str(path),
        None,
        None,
        None,
        None,
        str(unit_env.root / "references" / "test_cases") + "/",
        str(unit_env.root / "references" / "bypass") + "/",
        str(unit_env.root / "references" / "bypass_cases.json"),
        str(unit_env.root) + "/",
    )

    assert result == ""
    out = capsys.readouterr().out
    assert "skipped" in out.lower()
    assert expected in out
    # No divergence report either: the guard fires before step 1.
    assert not (unit_env.root / "references" / "bypass").exists()


# ===========================================================================
# STEP 1 · detect_bypass_vectors
# ===========================================================================


def test_a_fenced_reply_is_unwrapped_before_parsing(unit_env, policy, monkeypatch):
    # Real models routinely wrap JSON in a ```json fence despite being told not
    # to. Without stripping it, every reply would count as malformed.
    _fake_analyze_llm(monkeypatch, [fenced([bypass_vector()])])
    report = _detect(unit_env, policy)
    assert len(report.vectors) == 1


def test_a_category_outside_the_schema_is_dropped_not_fatal(
    unit_env, policy, monkeypatch
):
    # The model is free to invent a category name. Constructing BypassVector with
    # one would raise, so unknown categories are filtered first — a partial report
    # is worth more than an aborted run.
    _fake_analyze_llm(
        monkeypatch,
        [
            [
                bypass_vector(category="mind_control"),
                bypass_vector(category="type_confusion"),
            ]
        ],
    )
    report = _detect(unit_env, policy)
    assert [v.category for v in report.vectors] == ["type_confusion"]


def test_malformed_json_is_retried_and_can_recover(unit_env, policy, monkeypatch):
    # A transient bad-format reply must not be written out as an empty report, so
    # each attempt is a fresh model call. Recovery stops the loop early.
    fake = _fake_analyze_llm(monkeypatch, ["not json at all", [bypass_vector()]])
    report = _detect(unit_env, policy)
    assert len(fake.calls) == 2, "it should stop as soon as a reply parses"
    assert len(report.vectors) == 1


def test_persistently_malformed_json_falls_back_to_an_empty_report(
    unit_env, policy, monkeypatch, capsys
):
    fake = _fake_analyze_llm(monkeypatch, ["bad"] * MAX_BYPASS_PARSE_ATTEMPTS)
    report = _detect(unit_env, policy)

    assert len(fake.calls) == MAX_BYPASS_PARSE_ATTEMPTS, "the retry budget is bounded"
    assert report.vectors == []
    # An empty report is a *reported* outcome, not a silent one: the next step
    # writes an empty case list and the run ends without adversarial cases.
    assert "failed to return valid JSON" in capsys.readouterr().out


def test_a_transport_error_propagates_rather_than_reporting_no_divergences(
    unit_env, policy, monkeypatch
):
    """Pinned distinction: a *parse* failure degrades, a *transport* failure does not.

    The model call sits outside the try/except, so an unreachable endpoint raises
    and the flag exits nonzero. That is the safer behaviour — reporting "no bypass
    vectors found" when the analysis never ran would be a false all-clear on a
    security check — so it is asserted deliberately rather than treated as a gap.
    """
    fake = FakeOpenAI(error=RuntimeError("connection refused"))
    monkeypatch.setattr(analyze_mod, "OpenAI", fake.as_factory())

    with pytest.raises(RuntimeError, match="connection refused"):
        _detect(unit_env, policy)


def test_both_report_formats_are_written(unit_env, policy, monkeypatch):
    # The JSON feeds step 2; the Markdown is for a human. Both are part of the
    # flag's contract, and the directory may not exist yet.
    _fake_analyze_llm(monkeypatch, [[bypass_vector(field="args.topic")]])
    _detect(unit_env, policy)

    out = unit_env.root / "references" / "bypass"
    saved = json.loads((out / "bypass_report.json").read_text())
    assert saved["vectors"][0]["field"] == "args.topic"
    assert "# Policy Bypass Analysis Report" in (out / "bypass_report.md").read_text()


def test_a_missing_guidance_file_is_a_warning_not_a_failure(
    unit_env, policy, monkeypatch, capsys
):
    # Guidance is the ground truth for "what should this policy do", so its
    # absence weakens the analysis — but the policy's evident intent still gives
    # the model something to work with, so the run continues.
    _fake_analyze_llm(monkeypatch, [[bypass_vector()]])
    report = _detect(unit_env, policy, guidance_file=str(unit_env.root / "absent.txt"))

    assert len(report.vectors) == 1
    assert "guidance file not found" in capsys.readouterr().out


def test_an_empty_report_says_so_in_the_markdown():
    # The human-facing half of a zero-vector run must state the result, since a
    # report with no findings otherwise looks identical to a broken one.
    assert "No bypass vectors detected" in BypassReport(vectors=[]).to_markdown()


# ===========================================================================
# STEP 2 · synthesize_bypass_cases
# ===========================================================================


def test_no_vectors_writes_an_empty_list_without_calling_the_model(unit_env):
    # Deliberately unmocked: the early return happens before any client is built,
    # so reaching the boundary would raise here. This is the guard that keeps a
    # clean policy from costing an LLM call.
    out = unit_env.root / "references" / "bypass_cases.json"
    assert (
        synthesize_bypass_cases(
            "key",
            "http://localhost/v1",
            "m",
            0.0,
            1.0,
            BypassReport(vectors=[]),
            str(out),
        )
        == []
    )
    assert json.loads(out.read_text()) == []


@pytest.mark.parametrize(
    "direction,expected_label",
    [
        ("guidance_deny_policy_allow", "bypass_malicious"),
        ("guidance_allow_policy_deny", "bypass_benign"),
    ],
)
def test_the_divergence_direction_decides_the_label(
    unit_env, monkeypatch, direction, expected_label
):
    """CORRECTNESS: this mapping is the whole point of the step.

    ``guidance_deny_policy_allow`` means the guidance forbids the request but the
    policy allows it — so the case is *malicious* and belongs in ``disallow/``.
    The reverse direction is a legitimate request being over-blocked, so it is
    *benign* and belongs in ``allow/``. Inverting this would teach the suite that
    an exploit is expected behaviour.
    """
    _fake_synth_llm(monkeypatch, [[synth_case(direction=direction)]])
    out = unit_env.root / "references" / "bypass_cases.json"

    cases = synthesize_bypass_cases(
        "key",
        "http://localhost/v1",
        "m",
        0.0,
        1.0,
        BypassReport(vectors=[BypassVector(**bypass_vector())]),
        str(out),
    )

    assert [c["label"] for c in cases] == [expected_label]
    # And the derived label reaches disk, since step 3 reads the file, not the
    # return value.
    assert json.loads(out.read_text())[0]["label"] == expected_label


def test_an_unspecified_direction_is_treated_as_malicious(unit_env, monkeypatch):
    # Fail safe: a case whose direction the model omitted defaults to malicious,
    # so an ambiguous case is expected to be DENIED. Defaulting to benign would
    # add a case asserting an unverified exploit should be allowed.
    _fake_synth_llm(
        monkeypatch, [[{k: v for k, v in synth_case().items() if k != "direction"}]]
    )
    out = unit_env.root / "references" / "bypass_cases.json"

    cases = synthesize_bypass_cases(
        "key",
        "http://localhost/v1",
        "m",
        0.0,
        1.0,
        BypassReport(vectors=[BypassVector(**bypass_vector())]),
        str(out),
    )
    assert cases[0]["label"] == "bypass_malicious"


def test_a_case_missing_a_required_field_is_dropped(unit_env, monkeypatch):
    # Every downstream step indexes these fields directly, so a partial case
    # would crash the conversion rather than degrade it.
    incomplete = {k: v for k, v in synth_case().items() if k != "user_input"}
    _fake_synth_llm(monkeypatch, [[incomplete, synth_case()]])
    out = unit_env.root / "references" / "bypass_cases.json"

    cases = synthesize_bypass_cases(
        "key",
        "http://localhost/v1",
        "m",
        0.0,
        1.0,
        BypassReport(vectors=[BypassVector(**bypass_vector())]),
        str(out),
    )
    assert len(cases) == 1, "the incomplete case should have been filtered out"


def test_unparseable_output_yields_no_cases_rather_than_raising(unit_env, monkeypatch):
    # Unlike step 1 there is no retry here, so a malformed reply ends the step
    # with an empty file — the run continues and simply generates nothing.
    _fake_synth_llm(monkeypatch, ["}{ not json"])
    out = unit_env.root / "references" / "bypass_cases.json"

    cases = synthesize_bypass_cases(
        "key",
        "http://localhost/v1",
        "m",
        0.0,
        1.0,
        BypassReport(vectors=[BypassVector(**bypass_vector())]),
        str(out),
    )
    assert cases == []
    assert json.loads(out.read_text()) == []


# ===========================================================================
# STEP 3 · convert_bypass_case
# ===========================================================================


def test_each_label_is_routed_to_its_bucket_with_the_bypass_prefix(unit_env):
    """CORRECTNESS: the routing the rest of the suite depends on.

    The ``bypass_test_case`` prefix is not cosmetic — cross-validate's adversarial
    collapse matches on it to refuse relabelling a malicious probe as benign. A
    case written under the plain ``test_case`` prefix would lose that protection.
    """
    cases_file = write_json(
        unit_env.root / "bypass_cases.json",
        [
            dict(synth_case(), label="bypass_malicious"),
            dict(synth_case(), label="bypass_benign"),
        ],
    )
    out = str(unit_env.root / "references" / "test_cases") + "/"

    convert_bypass_case(str(cases_file), str(unit_env.case_template), out)

    root = unit_env.root / "references" / "test_cases"
    assert (root / "disallow" / "bypass_test_case0.json").exists(), (
        "a malicious bypass case must land in disallow/ — the policy is expected "
        "to deny it"
    )
    assert (root / "allow" / "bypass_test_case0.json").exists(), (
        "a benign bypass case must land in allow/ — it is a legitimate request "
        "the policy wrongly blocks"
    )


def test_a_converted_case_is_a_well_formed_opa_envelope(unit_env):
    # Step 3 -> policy_testing: OPA evaluates these bytes, so the tool name and
    # the prompt must survive into the envelope the template defines.
    cases_file = write_json(
        unit_env.root / "bypass_cases.json",
        [dict(synth_case(user_input="Show me everything."), label="bypass_malicious")],
    )
    out = str(unit_env.root / "references" / "test_cases") + "/"

    convert_bypass_case(str(cases_file), str(unit_env.case_template), out)

    written = json.loads(
        (
            unit_env.root
            / "references"
            / "test_cases"
            / "disallow"
            / "bypass_test_case0.json"
        ).read_text()
    )
    assert written["input"]["name"] == "get_events"
    assert written["input"]["extensions"]["agent"]["input"] == "Show me everything."


def test_a_case_with_an_unrecognized_label_is_skipped(unit_env, capsys):
    # An unlabeled case has no defined intended decision, so guessing a bucket
    # would invent an expectation. It is skipped and reported instead.
    cases_file = write_json(
        unit_env.root / "bypass_cases.json",
        [
            dict(synth_case(), label="who_knows"),
            dict(synth_case(), label="bypass_benign"),
        ],
    )
    out = str(unit_env.root / "references" / "test_cases") + "/"

    result = convert_bypass_case(str(cases_file), str(unit_env.case_template), out)

    assert len(result["bypass_benign"]) == 1
    assert result["bypass_malicious"] == []
    assert "unknown label" in capsys.readouterr().out


def test_cases_for_unselected_tools_are_filtered_out(unit_env, capsys):
    # When the explorer restricts a run to a subset of tools, a bypass case
    # targeting another tool is noise — the same rule translate_case applies.
    cases_file = write_json(
        unit_env.root / "bypass_cases.json",
        [
            dict(synth_case(action="get_events"), label="bypass_malicious"),
            dict(synth_case(action="other_tool"), label="bypass_malicious"),
        ],
    )
    out = str(unit_env.root / "references" / "test_cases") + "/"

    result = convert_bypass_case(
        str(cases_file), str(unit_env.case_template), out, selected_tools={"get_events"}
    )

    assert len(result["bypass_malicious"]) == 1
    assert "Filtered 1 bypass case" in capsys.readouterr().out


def test_an_empty_case_file_writes_no_files(unit_env):
    # The end state of a clean policy: zero divergences all the way through, and
    # crucially no stale case files left behind for policy_testing to score.
    cases_file = write_json(unit_env.root / "bypass_cases.json", [])
    out = str(unit_env.root / "references" / "test_cases") + "/"

    result = convert_bypass_case(str(cases_file), str(unit_env.case_template), out)

    assert result == {"bypass_malicious": [], "bypass_benign": []}
    root = unit_env.root / "references" / "test_cases"
    assert not list(root.rglob("bypass_test_case*.json"))
