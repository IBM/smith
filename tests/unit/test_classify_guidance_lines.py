# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the pure helpers in tools.classify_guidance_lines.

The LLM call itself (`classify_line`) is exercised with a mocked OpenAI client
so no network access is required.
"""

import json

import pytest

from smith.tools import classify_guidance_lines as mod


# ---------------------------------------------------------------------------
# split_guidance_lines
# ---------------------------------------------------------------------------
def test_split_skips_blank_and_headings():
    text = "# Heading\n\n- a rule\n\n## Another\nplain rule\n"
    lines = mod.split_guidance_lines(text)
    texts = [ln["text"] for ln in lines]
    assert texts == ["a rule", "plain rule"]


def test_split_strips_bullets_and_numbering_but_keeps_raw():
    text = "- dash rule\n* star rule\n1. numbered rule\n2) paren rule\n"
    lines = mod.split_guidance_lines(text)
    assert [ln["text"] for ln in lines] == [
        "dash rule",
        "star rule",
        "numbered rule",
        "paren rule",
    ]
    # raw retains the original marker so the UI can locate the verbatim line
    assert lines[0]["raw"] == "- dash rule"
    assert lines[2]["raw"] == "1. numbered rule"


def test_split_preserves_source_line_index():
    text = "# H\n\nfirst\nsecond\n"
    lines = mod.split_guidance_lines(text)
    # "first" is on source line index 2, "second" on 3 (0-based)
    assert [ln["index"] for ln in lines] == [2, 3]


def test_split_empty_text():
    assert mod.split_guidance_lines("") == []


# ---------------------------------------------------------------------------
# load_tool_list
# ---------------------------------------------------------------------------
def test_load_tool_list(tmp_path):
    p = tmp_path / "tool_definitions.json"
    p.write_text(
        json.dumps(
            {
                "tools": [
                    {"name": "a", "description": "  does a  "},
                    {"name": "b"},
                    {"description": "no name — skipped"},
                ]
            }
        ),
        encoding="utf-8",
    )
    tools = mod.load_tool_list(str(p))
    assert tools == [
        {"name": "a", "description": "does a"},
        {"name": "b", "description": ""},
    ]


def test_load_tool_list_missing_tools_key(tmp_path):
    p = tmp_path / "td.json"
    p.write_text(json.dumps({"source": "x"}), encoding="utf-8")
    assert mod.load_tool_list(str(p)) == []


# ---------------------------------------------------------------------------
# classify_line (mocked OpenAI client)
# ---------------------------------------------------------------------------
def _mock_client(mocker, content):
    """Patch OpenAI so classify_line's chat completion returns `content`."""
    fake_msg = mocker.Mock()
    fake_msg.content = content
    fake_choice = mocker.Mock()
    fake_choice.message = fake_msg
    fake_resp = mocker.Mock()
    fake_resp.choices = [fake_choice]

    fake_client = mocker.Mock()
    fake_client.chat.completions.create.return_value = fake_resp
    mocker.patch.object(mod, "OpenAI", return_value=fake_client)
    return fake_client


TOOLS = [{"name": "set_passport", "description": "set passport"},
         {"name": "get_visa", "description": "read visa"}]


def test_classify_line_filters_to_valid_names(mocker):
    _mock_client(
        mocker,
        json.dumps({"tools": ["set_passport", "not_a_tool"], "reason": "r"}),
    )
    out = mod.classify_line("k", "u", "m", 0.2, 0.9, "rule", TOOLS)
    assert out == {"tools": ["set_passport"], "reason": "r"}


def test_classify_line_dedupes_and_preserves_order(mocker):
    _mock_client(
        mocker,
        json.dumps({"tools": ["get_visa", "set_passport", "get_visa"], "reason": ""}),
    )
    out = mod.classify_line("k", "u", "m", 0.2, 0.9, "rule", TOOLS)
    assert out["tools"] == ["get_visa", "set_passport"]


def test_classify_line_parses_json_fence(mocker):
    fenced = "```json\n" + json.dumps({"tools": ["get_visa"], "reason": "x"}) + "\n```"
    _mock_client(mocker, fenced)
    out = mod.classify_line("k", "u", "m", 0.2, 0.9, "rule", TOOLS)
    assert out["tools"] == ["get_visa"]


def test_classify_line_empty_tools(mocker):
    _mock_client(mocker, json.dumps({"tools": [], "reason": "global"}))
    out = mod.classify_line("k", "u", "m", 0.2, 0.9, "rule", TOOLS)
    assert out == {"tools": [], "reason": "global"}


def test_classify_line_parse_failure_falls_back(mocker):
    _mock_client(mocker, "not json at all")
    out = mod.classify_line("k", "u", "m", 0.2, 0.9, "rule", TOOLS)
    assert out["tools"] == []
    assert "parse" in out["reason"].lower()


def test_classify_line_non_list_tools_coerced(mocker):
    _mock_client(mocker, json.dumps({"tools": "set_passport", "reason": "r"}))
    out = mod.classify_line("k", "u", "m", 0.2, 0.9, "rule", TOOLS)
    assert out["tools"] == ["set_passport"]
