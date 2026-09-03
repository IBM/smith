# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration test for ``smith --flag test_generation``.

Realistic workflow:

1. **Boot the example agent** (``agent_server`` fixture) — the
   ``call-for-papers-mcp`` FastAPI app, which also spawns its MCP server over
   stdio. Generation extracts tool definitions from that MCP server, so it must
   be running.
2. Feed a small, CRAFTED guidance (two rules) + system vars — written to
   references/ and protected/cleaned by backup_file, NOT the example's files —
   and run the real ``test_generation`` pipeline ONCE with
   ``ATTACK_TOOLS=promptfoo`` (ARES omitted so no ARES install is needed). The
   Promptfoo redteam config is a frozen fixture copy.
3. **Validate the output files' formats**, not just their presence — each stage
   of the pipeline writes a known-shaped artifact — AND that the Promptfoo
   red-team path produced its attack file + ``promptfoo_test_case*.json``.

Because LLM output is not deterministic, assertions check *shape and required
fields*, never exact counts or wording. Requires a real LLM (``requires_llm``),
the example agent (``agent_server``), and the ``promptfoo`` CLI
(``requires_promptfoo``).
"""

from __future__ import annotations

import json
import os
import shutil

import pytest

from helpers import (
    CASE_FILE,
    DECOMP_FILE,
    EXAMPLE,
    FIXTURES,
    FLATTEN_FILE,
    GREY_GUIDANCE_FILE,
    PROMPTFOO_ATTACK_FILE,
    REAL_TEST_CASES,
    REFERENCES,
    VARS_FILE,
    env_rel,
    load_json,
    run_smith,
)

pytestmark = pytest.mark.integration

FIXTURE_PROMPTFOO_CONFIG = FIXTURES / "promptfoo" / "promptfooconfig.yaml"
PROMPTFOO_OUTPUT_FILE = REFERENCES / "__test_redteam_output__.yaml"

# All intermediate files test_generation must produce (none may be missing/empty).
INTERMEDIATES = [DECOMP_FILE, FLATTEN_FILE, VARS_FILE, GREY_GUIDANCE_FILE, CASE_FILE]

# Crafted, self-contained inputs (written to references/ so BASE_URL + path
# resolves; protected by backup_file). We deliberately use a SMALL guidance —
# two rules — so the run is fast and the expectations are tight, rather than
# reading the example's full guidance/system_vars (which may change).
CRAFTED_GUIDANCE_FILE = REFERENCES / "__test_guidance__.txt"
CRAFTED_SYSTEM_VARS_FILE = REFERENCES / "__test_system_vars__.json"

CRAFTED_GUIDANCE = """\
1. Only faculty and phd_student may use get_events; a guest must never be allowed.
2. get_events may only be called with a topic that is exactly one of: Artificial intelligence, Cybersecurity and privacy, Software engineering.
"""

CRAFTED_SYSTEM_VARS = {
    "action_list": ["get_events", "other"],
    # decompose_guidance requires action_description (one entry per action).
    "action_description": {
        "get_events": "Search for academic conferences by keywords and topic.",
        "other": "Any other general question.",
    },
    "user_name": "Bob",
    "user_role": ["faculty", "phd_student", "guest"],
    "research_area": [
        "Artificial intelligence",
        "Cybersecurity and privacy",
        "Software engineering",
    ],
}

# Keys every decomposition record must carry (see decompose_guidance output).
DECOMP_KEYS = {
    "guidance",
    "action",
    "common_constraints",
    "allow_conditions",
    "disallow_conditions",
}


def _generation_env(agent_url: str) -> dict:
    env = dict(os.environ)
    rel = env_rel(EXAMPLE)
    env.update(
        {
            "AGENT_URL": agent_url,
            "GUIDANCE_FILE": env_rel(CRAFTED_GUIDANCE_FILE),
            "SYSTEM_VAR_FILE": env_rel(CRAFTED_SYSTEM_VARS_FILE),
            "PROMPTFOO_CONFIG_FILE": env_rel(FIXTURE_PROMPTFOO_CONFIG),
            "PROMPTFOO_OUTPUT_FILE": env_rel(PROMPTFOO_OUTPUT_FILE),
            # MCP is spawned by the example agent over stdio from its own dir.
            "MCP_TRANSPORT": "stdio",
            "MCP_COMMAND": "python",
            "MCP_ARGS": "server.py",
            "MCP_CWD": rel,
            "ATTACK_TOOLS": "promptfoo",
            "SESSION_CONFIG_FILE": "references/__no_session_config__.json",
        }
    )
    return env


def test_test_generation_outputs_and_formats(
    stage,
    requires_llm,
    requires_promptfoo,
    agent_server,
    isolate_generation_artifacts,
    backup_file,
):
    backup_file(PROMPTFOO_ATTACK_FILE)
    backup_file(PROMPTFOO_OUTPUT_FILE)
    backup_file(CRAFTED_GUIDANCE_FILE)
    backup_file(CRAFTED_SYSTEM_VARS_FILE)
    CRAFTED_GUIDANCE_FILE.write_text(CRAFTED_GUIDANCE)
    CRAFTED_SYSTEM_VARS_FILE.write_text(json.dumps(CRAFTED_SYSTEM_VARS, indent=2))

    for f in INTERMEDIATES + [PROMPTFOO_ATTACK_FILE, PROMPTFOO_OUTPUT_FILE]:
        if f.exists():
            f.unlink()
    if REAL_TEST_CASES.exists():
        shutil.rmtree(REAL_TEST_CASES)

    # Act: agent is already up (fixture); run the real generation pipeline.
    result = run_smith(
        "test_generation", timeout=1800, env=_generation_env(agent_server)
    )
    assert result.returncode == 0, (
        f"test_generation failed (rc={result.returncode}).\n"
        f"--- stdout tail ---\n{result.stdout[-2000:]}\n"
        f"--- stderr tail ---\n{result.stderr[-1000:]}"
    )
    # Surface the pipeline's own stdout on any later assertion failure.
    print(result.stdout[-2000:])

    # Every intermediate must exist and be non-empty — this also guards against a
    # silent short-circuit (the CLI exiting 0 having produced nothing).
    for f in INTERMEDIATES:
        assert f.exists(), f"intermediate not produced: {f.name}"
        assert f.stat().st_size > 0, f"intermediate is empty: {f.name}"

    # Validate each intermediate's format.
    _assert_decomposition_format()
    _assert_flatten_format()
    _load_nonempty_list(VARS_FILE)
    _load_nonempty_list(GREY_GUIDANCE_FILE)
    _assert_case_file_format()
    _assert_final_test_cases_format()

    # Validate the Promptfoo red-team path end to end.
    _assert_promptfoo_output()


# ---------------------------------------------------------------------------
# Per-file format checks.
# ---------------------------------------------------------------------------

ABSTRACT_LABELS = {
    "allow",
    "disallow",
    "ares_malicious",
    "promptfoo_malicious",
    "bypass_malicious",
    "bypass_benign",
}


def _load_nonempty_list(path):
    """Load a JSON file and assert it is a non-empty list; return it."""
    data = load_json(path)
    assert isinstance(data, list) and data, f"{path.name} is not a non-empty list"
    return data


def _assert_decomposition_format():
    """decomp_file.json: non-empty list of records carrying the decomposition keys."""
    for rec in _load_nonempty_list(DECOMP_FILE):
        assert isinstance(rec, dict)
        missing = DECOMP_KEYS - rec.keys()
        assert not missing, f"decomposition record missing keys: {missing}"
        assert isinstance(rec["allow_conditions"], list)
        assert isinstance(rec["disallow_conditions"], list)


def _assert_flatten_format():
    """decomp_flatten_file.json: newline-delimited guidance lines (text, not JSON)."""
    lines = [ln for ln in FLATTEN_FILE.read_text().splitlines() if ln.strip()]
    assert lines, "flatten file has no guidance lines"


def _assert_case_file_format():
    """test_cases.json: non-empty list of abstract cases, each with a valid label."""
    for case in _load_nonempty_list(CASE_FILE):
        assert isinstance(case, dict) and "label" in case, f"bad abstract case: {case}"
        assert case["label"] in ABSTRACT_LABELS, f"unexpected label: {case['label']}"


def _assert_final_test_cases_format():
    """references/test_cases/{allow,disallow}/*.json: OPA-envelope test cases."""
    allow_dir = REAL_TEST_CASES / "allow"
    disallow_dir = REAL_TEST_CASES / "disallow"
    files = list(allow_dir.glob("*.json")) + list(disallow_dir.glob("*.json"))
    assert files, "generation produced zero final test cases"
    for f in files:
        inp = load_json(f).get("input", {})
        assert "name" in inp, f"{f.name} input lacks a tool 'name'"
        assert "extensions" in inp, f"{f.name} input lacks 'extensions'"


def _assert_promptfoo_output():
    """Promptfoo path: redteam yaml written, attack file classified, cases converted."""
    # 1) promptfoo wrote its generated redteam yaml.
    assert (
        PROMPTFOO_OUTPUT_FILE.exists() and PROMPTFOO_OUTPUT_FILE.stat().st_size > 0
    ), "promptfoo redteam output yaml missing/empty — generation did not run"
    # 2) the attack file is a non-empty list and classification ran (each case
    #    carries an `action` tool name, not None).
    for c in _load_nonempty_list(PROMPTFOO_ATTACK_FILE):
        assert c.get("action"), f"promptfoo case missing/None 'action' (tool): {c}"
    # 3) the converted promptfoo cases land under disallow/ with the prefix and
    #    carry a valid OPA input envelope.
    cases = list((REAL_TEST_CASES / "disallow").glob("promptfoo_test_case*.json"))
    assert cases, "no promptfoo_test_case*.json produced under disallow/"
    inp = load_json(cases[0]).get("input", {})
    assert "name" in inp, "converted promptfoo case lacks a tool 'name'"
