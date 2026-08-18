# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for cli.resolve_attack_tools — env parsing/validation."""

import pytest

from smith.cli import resolve_attack_tools


def test_default_when_unset(monkeypatch):
    monkeypatch.delenv("ATTACK_TOOLS", raising=False)
    assert resolve_attack_tools() == {"ares", "promptfoo"}


def test_single_tool(monkeypatch):
    monkeypatch.setenv("ATTACK_TOOLS", "promptfoo")
    assert resolve_attack_tools() == {"promptfoo"}


def test_comma_separated_with_spaces_and_case(monkeypatch):
    monkeypatch.setenv("ATTACK_TOOLS", " ARES , PromptFoo ")
    assert resolve_attack_tools() == {"ares", "promptfoo"}


def test_none_discarded(monkeypatch):
    monkeypatch.setenv("ATTACK_TOOLS", "none")
    assert resolve_attack_tools() == set()


def test_none_mixed_with_real_tool(monkeypatch):
    monkeypatch.setenv("ATTACK_TOOLS", "none,ares")
    assert resolve_attack_tools() == {"ares"}


def test_empty_string_is_empty_set(monkeypatch):
    monkeypatch.setenv("ATTACK_TOOLS", "")
    # empty -> falls back to the default via os.getenv? No: getenv returns "",
    # split yields nothing, so the result is the empty set.
    assert resolve_attack_tools() == set()


def test_unknown_tool_exits(monkeypatch):
    monkeypatch.setenv("ATTACK_TOOLS", "ares,bogus")
    with pytest.raises(SystemExit) as exc:
        resolve_attack_tools()
    assert exc.value.code == 1
