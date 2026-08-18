# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for tools.guidance_classifier_server.

Covers the pure path resolvers and the /reset behaviour (clean script +
overwrite the .env guidance.txt + write session_config.json), driven directly
through the handler with a fake request rather than a live socket.
"""

import json
import os

import pytest

from smith.tools import guidance_classifier_server as srv


# ---------------------------------------------------------------------------
# path resolvers
# ---------------------------------------------------------------------------
def test_resolve_guidance_path_relative():
    got = srv._resolve_guidance_path("/base/", "examples/a/smith/guidance.txt")
    assert got == "/base/examples/a/smith/guidance.txt"


def test_resolve_guidance_path_absolute():
    got = srv._resolve_guidance_path("/base/", "/abs/guidance.txt")
    assert got == "/abs/guidance.txt"


def test_resolve_tool_definitions_prefers_target_agent(monkeypatch):
    monkeypatch.setenv("TARGET_AGENT_PATH", "examples/emp/")
    got = srv._resolve_tool_definitions_path("/base/")
    assert got == os.path.join("/base/", "examples/emp/", "smith", "tool_definitions.json")


def test_resolve_tool_definitions_falls_back_to_guidance_dir(monkeypatch):
    monkeypatch.delenv("TARGET_AGENT_PATH", raising=False)
    monkeypatch.setenv("GUIDANCE_FILE", "examples/emp/smith/guidance.txt")
    got = srv._resolve_tool_definitions_path("/base/")
    assert got.endswith(os.path.join("examples/emp/smith", "tool_definitions.json"))


# ---------------------------------------------------------------------------
# /reset through the handler (no live socket)
# ---------------------------------------------------------------------------
class _FakeRequest:
    """Minimal stand-in so we can instantiate a BaseHTTPRequestHandler subclass
    without a real connection. We bypass __init__ and call do_POST directly."""


def _make_handler_instance(handler_cls, path, body_bytes):
    h = handler_cls.__new__(handler_cls)  # skip BaseHTTPRequestHandler.__init__
    h.path = path
    h.headers = {"Content-Length": str(len(body_bytes))}
    h.rfile = _BytesReader(body_bytes)
    h._captured = {}

    def _send(code, body, content_type="application/json"):
        h._captured["code"] = code
        h._captured["body"] = body

    h._send = _send
    return h


class _BytesReader:
    def __init__(self, data):
        self._data = data

    def read(self, n):
        chunk, self._data = self._data[:n], self._data[n:]
        return chunk


@pytest.fixture
def reset_env(tmp_path, monkeypatch):
    """A skill-like tree + a stub clean script; returns (handler_cls, paths)."""
    base = tmp_path
    (base / "references").mkdir()
    guidance_path = base / "examples" / "a" / "smith" / "guidance.txt"
    guidance_path.parent.mkdir(parents=True)
    guidance_path.write_text("old guidance\n", encoding="utf-8")

    # stub clean script that just creates a marker (proves it ran, cwd=base)
    clean = base / "scripts" / "clean_generated.sh"
    clean.parent.mkdir()
    clean.write_text("#!/bin/bash\ntouch cleaned.marker\n", encoding="utf-8")

    tool_defs = base / "examples" / "a" / "smith" / "tool_definitions.json"
    tool_defs.write_text('{"tools": []}', encoding="utf-8")

    monkeypatch.setenv("SESSION_CONFIG_FILE", "references/session_config.json")
    monkeypatch.delenv("TARGET_AGENT_PATH", raising=False)

    handler_cls = srv.make_handler(
        str(base) + os.sep,
        str(guidance_path),
        str(clean),
        str(tool_defs),
        {"api_key": "k", "base_url": "u", "model": "m", "temp": 0.2, "top_p": 0.9},
    )
    return handler_cls, base, guidance_path


def test_reset_overwrites_guidance_and_writes_session_config(reset_env):
    handler_cls, base, guidance_path = reset_env
    payload = {"guidance": "new guidance\n", "selected_tools": ["set_passport"]}
    body = json.dumps(payload).encode()
    h = _make_handler_instance(handler_cls, "/reset", body)

    h.do_POST()

    assert h._captured["code"] == 200
    # 1) clean script ran (cwd == base)
    assert (base / "cleaned.marker").exists()
    # 2) guidance.txt overwritten with the editor text
    assert guidance_path.read_text() == "new guidance\n"
    # 3) session_config.json written from selected_tools
    cfg = json.loads((base / "references" / "session_config.json").read_text())
    assert cfg == {"use_ir": True, "selected_tools": ["set_passport"]}


def test_reset_no_selected_tools_sets_use_ir_false(reset_env):
    handler_cls, base, guidance_path = reset_env
    body = json.dumps({"guidance": "g\n", "selected_tools": []}).encode()
    h = _make_handler_instance(handler_cls, "/reset", body)
    h.do_POST()
    cfg = json.loads((base / "references" / "session_config.json").read_text())
    assert cfg == {"use_ir": False, "selected_tools": []}


def test_classify_endpoint_uses_mocked_classifier(reset_env, mocker):
    handler_cls, base, guidance_path = reset_env
    fake_lines = [
        {"index": 0, "raw": "- r", "text": "r", "tools": ["set_passport"], "reason": "x"}
    ]
    mocker.patch.object(srv, "classify_guidance_lines", return_value=fake_lines)
    body = json.dumps({"guidance": "- r\n"}).encode()
    h = _make_handler_instance(handler_cls, "/classify", body)
    h.do_POST()
    assert h._captured["code"] == 200
    out = json.loads(h._captured["body"])
    assert out["lines"] == fake_lines
