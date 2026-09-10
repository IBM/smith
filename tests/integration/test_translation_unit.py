# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the function behind ``smith --flag test_case_translation``.

Translation is the step that turns an abstract generated case into something OPA
can actually evaluate. For every case under ``test_cases/{allow,disallow}/`` it
asks the target agent's ``/extract_tool_call`` endpoint which tool the prompt
*really* resolves to, then writes ``input.name`` and ``input.args`` back into the
file::

    pre-pass    input.name == "other"      -> wrong_cases/mcp_unrelated/<label>/
    skip        input.args already present -> left alone (re-runnable)
    POST        /extract_tool_call          -> input.name + input.args written back
    mismatch    resolved tool != assigned  -> wrong_cases/misclassified/<label>/
    failure     HTTP error / unreachable   -> case left untouched, run continues

FUNCTIONS UNDER TEST
--------------------
``smith.test_generation.extract_tool_args``

STEP 1 · the pre-pass, before any request
    ``run_extract_tool_args`` — ``name == "other"`` is quarantined without an
                                agent call, matched case-insensitively

STEP 2 · the request itself
    ``run_extract_tool_args`` — what is POSTed (prompt + subject), and that the
                                resolved name/args are written back to the file

STEP 3 · routing on the reply
    ``run_extract_tool_args`` — a matching tool stays put; a mismatched or
                                ``other`` tool is moved to ``misclassified/``

STEP 4 · re-runnability and failure
    ``run_extract_tool_args`` — an already-translated case costs no request; a
                                transport or HTTP failure leaves the case intact

STEP 5 · the report
    ``run_extract_tool_args`` — ``miscalled_cases.json``, always written, and the
                                pinned pre-move path it records

NOT COVERED HERE (integration lane — see ``test_translation_integration.py``)
    Whether the real agent resolves a realistic prompt to the expected tool, and
    the CLI wiring that supplies the case path and agent URL.

Deliberately absent: assertions on the printed progress counts beyond the report
itself, and on ``requests`` internals — the boundary is faked, so asserting the
timeout value back would only test the fake.

Env-free: ``requests.post`` is patched, so no agent and no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from smith.test_generation import extract_tool_args as eta_mod
from smith.test_generation.extract_tool_args import run_extract_tool_args

from fakes import FakeHTTPResponse, FakePoster

pytestmark = pytest.mark.unit


AGENT_URL = "http://127.0.0.1:9000"


def case(name="get_events", prompt="Find AI conferences.", subject=None, args=None):
    """One post-translation-shaped case, optionally already carrying ``args``."""
    inner = {
        "kind": "tool_call",
        "action": "execute",
        "name": name,
        "extensions": {
            "subject": subject or {"user_name": "Bob", "user_role": ["faculty"]},
            "agent": {"input": prompt},
        },
    }
    if args is not None:
        inner["args"] = args
    return {"input": inner}


@pytest.fixture
def tree(unit_env):
    """A writable case tree under the temp root, plus helpers to populate it.

    The function under test renames and rewrites files, so this must never be the
    committed fixture tree.
    """
    root = unit_env.root / "references" / "test_cases"

    class Tree:
        path = root

        def add(self, label, filename, payload):
            target = root / label / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, indent=4))
            return target

        def relpaths(self):
            """Every case file, relative to the tree root, for exact comparisons."""
            return sorted(
                str(p.relative_to(root))
                for p in root.rglob("*.json")
                if p.name != "miscalled_cases.json"
            )

        def report(self):
            return json.loads((root / "miscalled_cases.json").read_text())

    return Tree()


def _fake_post(monkeypatch, responses):
    fake = FakePoster(responses=responses)
    monkeypatch.setattr(eta_mod.requests, "post", fake)
    return fake


def _reply(tool_name="get_events", arguments=None):
    """The agent's ``/extract_tool_call`` contract: ``tool_name`` + ``arguments``."""
    return FakeHTTPResponse(
        {"tool_name": tool_name, "arguments": {} if arguments is None else arguments}
    )


# ===========================================================================
# STEP 1 · the pre-pass — quarantine before spending a request
# ===========================================================================


@pytest.mark.parametrize("name", ["other", "OTHER", "Other"])
def test_a_case_naming_no_tool_is_quarantined_without_an_agent_call(
    tree, monkeypatch, name
):
    tree.add("allow", "test_case0.json", case(name=name))
    fake = _fake_post(monkeypatch, [])

    run_extract_tool_args(str(tree.path), AGENT_URL)

    assert fake.call_count == 0, "an 'other' case must not reach the agent"
    assert tree.relpaths() == ["wrong_cases/mcp_unrelated/allow/test_case0.json"]


def test_both_labels_are_quarantined_into_their_own_subdirectory(tree, monkeypatch):
    # The label must survive the move: allow/ and disallow/ cases are scored
    # against opposite expectations, so merging them would destroy that.
    tree.add("allow", "test_case0.json", case(name="other"))
    tree.add("disallow", "test_case0.json", case(name="other"))
    _fake_post(monkeypatch, [])

    run_extract_tool_args(str(tree.path), AGENT_URL)

    assert tree.relpaths() == [
        "wrong_cases/mcp_unrelated/allow/test_case0.json",
        "wrong_cases/mcp_unrelated/disallow/test_case0.json",
    ]


# ===========================================================================
# STEP 2 · the request, and writing the answer back
# ===========================================================================


def test_the_agent_is_asked_with_the_prompt_and_the_subject(tree, monkeypatch):
    # Both halves matter: the agent needs the prompt to pick a tool, and the
    # subject because a role can change which tool it would call.
    subject = {"user_name": "Ann", "user_role": ["faculty"]}
    tree.add(
        "allow", "test_case0.json", case(prompt="Find ML papers.", subject=subject)
    )
    fake = _fake_post(monkeypatch, [_reply()])

    run_extract_tool_args(str(tree.path), AGENT_URL)

    assert fake.calls[0]["url"] == f"{AGENT_URL}/extract_tool_call"
    assert fake.calls[0]["json"] == {
        "question": "Find ML papers.",
        "user_profile": subject,
    }


def test_the_resolved_tool_and_args_are_written_into_the_case(tree, monkeypatch):
    """``input.args`` is what the policy's ``args.topic`` / ``args.limit`` rules read,
    so a case without it evaluates against an empty argument set and can never
    trigger an argument-based deny.
    """
    path = tree.add("allow", "test_case0.json", case())
    _fake_post(
        monkeypatch,
        [_reply("get_events", {"topic": "Artificial intelligence", "limit": 5})],
    )

    run_extract_tool_args(str(tree.path), AGENT_URL)

    written = json.loads(path.read_text())
    assert written["input"]["name"] == "get_events"
    assert written["input"]["args"] == {"topic": "Artificial intelligence", "limit": 5}
    # The rest of the envelope must survive untouched — OPA reads all of it.
    assert written["input"]["kind"] == "tool_call"
    assert written["input"]["extensions"]["agent"]["input"] == "Find AI conferences."


def test_a_missing_arguments_key_becomes_an_empty_argument_set(tree, monkeypatch):
    # A tool with no parameters is legitimate, so a reply without `arguments` must
    # still mark the case translated rather than being treated as a failure.
    path = tree.add("allow", "test_case0.json", case())
    _fake_post(monkeypatch, [FakeHTTPResponse({"tool_name": "get_events"})])

    run_extract_tool_args(str(tree.path), AGENT_URL)

    assert json.loads(path.read_text())["input"]["args"] == {}


# ===========================================================================
# STEP 3 · routing on what the agent answered
# ===========================================================================


def test_a_case_the_agent_agrees_with_stays_where_it_is(tree, monkeypatch):
    tree.add("allow", "test_case0.json", case(name="get_events"))
    _fake_post(monkeypatch, [_reply("get_events")])

    run_extract_tool_args(str(tree.path), AGENT_URL)

    assert tree.relpaths() == ["allow/test_case0.json"]
    assert tree.report() == [], "an agreeing case is not a miscall"


@pytest.mark.parametrize(
    "resolved,why",
    [
        ("different_tool", "the agent resolved a tool the case was not written for"),
        ("other", "the agent resolved no tool at all"),
    ],
    ids=["different-tool", "other"],
)
def test_a_case_the_agent_disagrees_with_is_moved_aside(
    tree, monkeypatch, resolved, why
):
    tree.add("allow", "test_case0.json", case(name="get_events"))
    _fake_post(monkeypatch, [_reply(resolved)])

    run_extract_tool_args(str(tree.path), AGENT_URL)

    assert tree.relpaths() == ["wrong_cases/misclassified/allow/test_case0.json"], why


def test_the_report_records_the_disagreement_that_moved_the_case(tree, monkeypatch):
    tree.add("allow", "test_case0.json", case(name="get_events", prompt="Do a thing."))
    _fake_post(monkeypatch, [_reply("different_tool", {"x": 1})])

    run_extract_tool_args(str(tree.path), AGENT_URL)

    entry = tree.report()[0]
    assert entry["label"] == "allow"
    assert entry["assigned_tool"] == "get_events"
    assert entry["actual_tool"] == "different_tool"
    # The prompt and resolved args are what a human needs to judge which side was
    # wrong — the generated case or the policy's tool coverage.
    assert entry["agent_input"] == "Do a thing."
    assert entry["actual_args"] == {"x": 1}

# ===========================================================================
# STEP 4 · re-runnability, and surviving an unreachable agent
# ===========================================================================


def test_an_already_translated_case_costs_no_request(tree, monkeypatch):
    """The idempotency guard: ``args`` present means the work is already done.

    Translation is the expensive step (one agent call, and thus one model call, per
    case), so re-running after adding a few cases must not re-pay for the rest.
    Again given an empty response queue, so an unexpected request fails the test.
    """
    path = tree.add("allow", "test_case0.json", case(args={"topic": "AI"}))
    before = path.read_text()
    fake = _fake_post(monkeypatch, [])

    run_extract_tool_args(str(tree.path), AGENT_URL)

    assert fake.call_count == 0
    assert path.read_text() == before, "a translated case must not be rewritten"


def test_a_mix_of_new_and_translated_cases_only_pays_for_the_new_ones(
    tree, monkeypatch
):
    done = tree.add("allow", "test_case0.json", case(args={"topic": "AI"}))
    tree.add("allow", "test_case1.json", case())
    before = done.read_text()
    fake = _fake_post(monkeypatch, [_reply("get_events", {"topic": "ML"})])

    run_extract_tool_args(str(tree.path), AGENT_URL)

    assert fake.call_count == 1, "only the untranslated case should be sent"
    assert done.read_text() == before


@pytest.mark.parametrize(
    "response",
    [
        ConnectionError("agent unreachable"),
        FakeHTTPResponse(status_code=500),
    ],
    ids=["unreachable", "http-500"],
)
def test_a_failed_request_leaves_the_case_exactly_as_it_was(
    tree, monkeypatch, response
):
    path = tree.add("allow", "test_case0.json", case())
    before = path.read_text()
    _fake_post(monkeypatch, [response])

    run_extract_tool_args(str(tree.path), AGENT_URL)

    assert path.read_text() == before
    assert tree.relpaths() == ["allow/test_case0.json"], "the case must not be moved"
    assert (
        "args" not in json.loads(path.read_text())["input"]
    ), "without args the case is still pending, so a re-run retries it"


def test_one_failure_does_not_abandon_the_remaining_cases(tree, monkeypatch):
    # The loop continues past an error, so a transient blip costs one case rather
    # than the whole run.
    failed = tree.add("allow", "test_case0.json", case())
    ok = tree.add("allow", "test_case1.json", case())
    _fake_post(monkeypatch, [ConnectionError("blip"), _reply("get_events", {"a": 1})])

    run_extract_tool_args(str(tree.path), AGENT_URL)

    assert "args" not in json.loads(failed.read_text())["input"]
    assert json.loads(ok.read_text())["input"]["args"] == {"a": 1}


# ===========================================================================
# STEP 5 · the report is always written
# ===========================================================================


def test_the_report_is_written_even_when_nothing_was_processed(tree, monkeypatch):
    # An empty tree still produces the artifact, so a downstream reader never has
    # to distinguish "no miscalls" from "translation never ran".
    tree.path.mkdir(parents=True, exist_ok=True)
    _fake_post(monkeypatch, [])

    run_extract_tool_args(str(tree.path), AGENT_URL)

    assert tree.report() == []
    # And the quarantine buckets exist, ready for a later run.
    assert (tree.path / "wrong_cases" / "mcp_unrelated").is_dir()
    assert (tree.path / "wrong_cases" / "misclassified").is_dir()
