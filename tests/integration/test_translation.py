# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration test for ``smith --flag test_case_translation``.

Translation reads each case under ``references/test_cases/{allow,disallow}/``,
calls the agent's ``/extract_tool_call`` with the case's prompt + subject, and
writes the resolved ``input.name`` and ``input.args`` back into the file. Cases
are routed:
  - ``input.name == "other"`` (pre-pass, no agent call) -> ``wrong_cases/mcp_unrelated/``
  - resolved tool != assigned tool                       -> ``wrong_cases/misclassified/``
  - already has ``input.args``                           -> skipped (re-runnable)
  - otherwise                                            -> translated in place

Rather than depend on ``test_generation`` having run, we **craft** a small set
of cases — one per routing branch — so the inputs are controlled and each branch
is exercised deterministically. The ``"other"`` branch needs no LLM; the fill /
mismatch branches use the agent's ``/extract_tool_call`` (its own LLM), so those
tests take ``requires_llm`` + ``agent_server``.

The session backup restores ``references/test_cases/``.
"""

from __future__ import annotations

import json
import os

import pytest

from helpers import (
    EXAMPLE,
    FIXTURE_TEST_CASES,
    REAL_TEST_CASES,
    env_rel,
    load_json,
    run_smith,
)

pytestmark = pytest.mark.integration


def _base_case() -> dict:
    """A well-formed case template (fixture get_events allow case, no args)."""
    return load_json(FIXTURE_TEST_CASES / "allow" / "test_case0.json")


def _write_case(label: str, name: str, prompt: str, subject=None, args=None):
    """Craft one case under references/test_cases/<label>/ with a chosen shape."""
    case = _base_case()
    case["input"]["name"] = name
    case["input"]["extensions"]["agent"]["input"] = prompt
    if subject is not None:
        case["input"]["extensions"]["subject"] = subject
    if args is not None:
        case["input"]["args"] = args
    d = REAL_TEST_CASES / label
    d.mkdir(parents=True, exist_ok=True)
    # Unique-ish filename per (name, label).
    path = d / f"crafted_{name}_{label}.json"
    path.write_text(json.dumps(case, indent=4))
    return path


def _fresh_test_cases():
    import shutil

    if REAL_TEST_CASES.exists():
        shutil.rmtree(REAL_TEST_CASES)
    (REAL_TEST_CASES / "allow").mkdir(parents=True)
    (REAL_TEST_CASES / "disallow").mkdir(parents=True)


def _translation_env(agent_url: str) -> dict:
    env = dict(os.environ)
    rel = env_rel(EXAMPLE)
    env.update(
        {
            "AGENT_URL": agent_url,
            "TARGET_AGENT_PATH": rel,
            # Same location the assertions below read, rather than a second
            # literal that can drift from .env.
            "TEST_CASE_PATH": env_rel(REAL_TEST_CASES, is_dir=True),
        }
    )
    return env


def _run_translation(agent_url):
    return run_smith(
        "test_case_translation", timeout=300, env=_translation_env(agent_url)
    )


def _find(name):
    hits = list(REAL_TEST_CASES.rglob(name))
    return hits[0] if hits else None


# --- "other" routing: deterministic, no LLM/agent call ----------------------


def test_other_case_moved_to_mcp_unrelated(agent_server):
    # A case pre-labeled name="other" is moved to wrong_cases/mcp_unrelated/
    # in the first pass, before any /extract_tool_call. This is LLM-free.
    _fresh_test_cases()
    _write_case("allow", "other", "What is the weather today?")

    result = _run_translation(agent_server)
    assert result.returncode == 0, result.stderr

    moved = (
        REAL_TEST_CASES
        / "wrong_cases"
        / "mcp_unrelated"
        / "allow"
        / "crafted_other_allow.json"
    )
    assert moved.exists(), "an 'other' case was not moved to mcp_unrelated/"
    # It should no longer sit in allow/.
    assert not (REAL_TEST_CASES / "allow" / "crafted_other_allow.json").exists()


# --- already-translated: skipped, unchanged (re-runnable) -------------------


def test_already_translated_case_is_skipped(agent_server):
    _fresh_test_cases()
    preset_args = {"keywords": "ml", "topic": "Artificial intelligence", "limit": 5}
    path = _write_case("allow", "get_events", "already translated", args=preset_args)
    before = load_json(path)

    result = _run_translation(agent_server)
    assert result.returncode == 0, result.stderr

    # Untouched: still in allow/, args unchanged.
    after = load_json(path)
    assert after["input"]["args"] == before["input"]["args"] == preset_args


# --- fill args: a genuine get_events case is translated in place ------------


def test_case_is_translated_and_gains_args(requires_llm, agent_server):
    _fresh_test_cases()
    path = _write_case(
        "allow",
        "get_events",
        "Please search for conferences about machine learning with topic "
        "Artificial intelligence.",
    )
    assert "args" not in load_json(path)["input"]

    result = _run_translation(agent_server)
    assert result.returncode == 0, result.stderr

    landed = _find("crafted_get_events_allow.json")
    assert landed is not None, "case disappeared"
    case = load_json(landed)
    assert "args" in case["input"], f"translation did not add args: {case['input']}"
    assert isinstance(case["input"]["args"], dict)
    assert case["input"]["name"], "empty resolved tool name"


# --- mismatch: assigned tool != resolved tool -> misclassified --------------


def test_tool_mismatch_moved_to_misclassified(requires_llm, agent_server):
    _fresh_test_cases()
    # Assign a tool this agent does NOT expose, with a get_events-style prompt.
    # The agent resolves get_events (or "other"), which != send_email -> moved.
    _write_case(
        "disallow",
        "send_email",
        "Search for conferences about cybersecurity.",
    )

    result = _run_translation(agent_server)
    assert result.returncode == 0, result.stderr

    # No longer in disallow/; it was rerouted under wrong_cases/.
    assert not (
        REAL_TEST_CASES / "disallow" / "crafted_send_email_disallow.json"
    ).exists()
    moved = _find("crafted_send_email_disallow.json")
    assert moved is not None and "wrong_cases" in str(
        moved
    ), f"mismatch case not moved under wrong_cases/: {moved}"
