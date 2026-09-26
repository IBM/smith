# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for ``POST /reset``, the save route behind
``smith --flag classify_guidance``.

The Guidance Classifier UI's Save button commits the user's edited guidance. The
handler does two things in order, and **each one can fail**::

    1. overwrite <GUIDANCE_FILE>        the target agent's tracked guidance.txt
    2. write session_config.json        {use_ir, selected_tools}

SCOPE: WHY THIS ROUTE IS UNIT-ONLY
----------------------------------
The integration lane deliberately never calls ``/reset``: it rewrites a tracked
input. So the only safe place to exercise it is here, against a temporary tree.

FUNCTIONS UNDER TEST
--------------------
``smith.tools.guidance_classifier_server``

STEP 0 · ``_resolve_guidance_path`` — how the save target is resolved
STEP 1 · ``make_handler`` -> ``do_POST`` — the guidance overwrite
STEP 2 · ``make_handler`` -> ``do_POST`` — the session config, and how ``use_ir``
                                          is derived
Guards  the JSON guard and the unknown-path 404

NOT COVERED HERE (integration lane — see ``test_classify_guidance_integration.py``)
    The server actually starting, ``GET /`` and ``/config``, and ``POST /classify``
    against a real model.

Env-free: no socket is opened, no model is contacted.
"""

from __future__ import annotations

import io
import json

import pytest

from smith.tools.guidance_classifier_server import (
    _resolve_guidance_path,
    make_handler,
)

pytestmark = pytest.mark.unit


ORIGINAL_GUIDANCE = "1. The original rule the user must not lose.\n"
EDITED_GUIDANCE = "1. The edited rule the user just uploaded.\n"


def _post(handler_cls, path, body=b"", method="POST"):
    """Drive one request through the handler with no socket.

    ``BaseHTTPRequestHandler`` normally reads from a connection; here ``rfile`` is a
    canned request and ``wfile`` collects the response, so the whole route runs
    in-process.
    """
    request = (
        f"{method} {path} HTTP/1.1\r\nContent-Length: {len(body)}\r\n\r\n".encode()
        + body
    )

    class Driven(handler_cls):
        def __init__(self):
            self.rfile = io.BytesIO(request)
            self.wfile = io.BytesIO()
            self.client_address = ("127.0.0.1", 0)
            self.requestline = ""
            self.request_version = "HTTP/1.1"
            self.command = ""
            self.handle_one_request()

        def log_message(self, *_args):  # keep the test output quiet
            pass

    raw = Driven().wfile.getvalue().decode("utf-8", "replace")
    status = int(raw.split(" ", 2)[1])
    payload = raw.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in raw else ""
    return status, json.loads(payload) if payload.strip() else {}


@pytest.fixture
def server(unit_env):
    """A handler over a temporary tree, plus the paths it will write."""
    root = unit_env.root
    guidance = root / "smith" / "guidance.txt"
    guidance.parent.mkdir(parents=True, exist_ok=True)
    guidance.write_text(ORIGINAL_GUIDANCE)

    class Server:
        base = str(root)
        guidance_path = guidance
        session_config = root / "references" / "session_config.json"

        def handler(self):
            return make_handler(self.base, str(self.guidance_path), {"tools": []}, {})

    return Server()


def _reset_body(guidance=EDITED_GUIDANCE, **extra):
    return json.dumps({"guidance": guidance, **extra}).encode()


# ===========================================================================
# STEP 0 · _resolve_guidance_path — which file Save will overwrite
# ===========================================================================


def test_a_relative_guidance_file_is_joined_onto_the_base(unit_env):
    # Matches how the rest of Smith resolves paths: BASE_URL + the .env value. The
    # UI shows this path before the user commits, so it must be the real target.
    resolved = _resolve_guidance_path(
        "/skill/root", "examples/agent/smith/guidance.txt"
    )
    assert resolved == "/skill/root/examples/agent/smith/guidance.txt"


def test_an_absolute_guidance_file_is_used_as_given(unit_env):
    # An absolute override must not be re-anchored under BASE_URL, which would
    # produce a nonsense path and overwrite the wrong file — or nothing.
    resolved = _resolve_guidance_path("/skill/root", "/etc/agent/guidance.txt")
    assert resolved == "/etc/agent/guidance.txt"


# ===========================================================================
# STEP 1 · the guidance overwrite
# ===========================================================================


def test_a_successful_save_writes_both_files(server):
    # The happy path, in order: the guidance is replaced, and the session config
    # records the tool selection.
    handler = server.handler()

    status, payload = _post(
        handler, "/reset", _reset_body(selected_tools=["get_events"])
    )

    assert status == 200
    assert payload["ok"] is True
    assert server.guidance_path.read_text() == EDITED_GUIDANCE
    assert json.loads(server.session_config.read_text()) == {
        "use_ir": True,
        "selected_tools": ["get_events"],
    }


def test_the_uploaded_text_replaces_the_file_exactly(server):
    # CORRECTNESS: this is a commit of the user's edits, so the bytes must land
    # verbatim — no appending, no reformatting, no trailing-newline surprises.
    handler = server.handler()
    edited = "1. First rule.\n2. Second rule.\n\n# A comment\n"

    _post(handler, "/reset", _reset_body(guidance=edited))

    assert server.guidance_path.read_text() == edited


def test_the_guidance_directory_is_created_on_demand(server):
    # A fresh target agent may have no smith/ directory yet. Save must create it
    # rather than failing on a path that does not exist.
    import shutil

    shutil.rmtree(server.guidance_path.parent)
    handler = server.handler()

    status, _ = _post(handler, "/reset", _reset_body())

    assert status == 200
    assert server.guidance_path.read_text() == EDITED_GUIDANCE


def test_an_empty_upload_clears_the_guidance(server):
    """Pinned: an absent or empty ``guidance`` key blanks the file.

    ``payload.get("guidance", "")`` means a request without the key writes an empty
    string, silently erasing the user's rules. The UI always sends the field, so this
    is only reachable through a malformed client — but it is worth naming, since the
    route has no "you sent nothing" guard.
    """
    handler = server.handler()

    status, _ = _post(handler, "/reset", json.dumps({}).encode())

    assert status == 200
    assert server.guidance_path.read_text() == ""


# ===========================================================================
# STEP 2 · the session config
# ===========================================================================


def test_selecting_tools_turns_ir_mode_on(server):
    # `use_ir` is what every later stage keys on to filter cases to a tool subset,
    # so it must be derived from the selection rather than set independently.
    handler = server.handler()

    _post(handler, "/reset", _reset_body(selected_tools=["get_events", "other"]))

    config = json.loads(server.session_config.read_text())
    assert config["use_ir"] is True
    assert config["selected_tools"] == ["get_events", "other"]


def test_selecting_no_tools_turns_ir_mode_off(server):
    handler = server.handler()

    _post(handler, "/reset", _reset_body())

    config = json.loads(server.session_config.read_text())
    assert config["use_ir"] is False
    assert config["selected_tools"] == []


# ===========================================================================
# Guards — malformed requests reach no step at all
# ===========================================================================


def test_a_malformed_body_is_rejected_before_anything_is_written(server):
    handler = server.handler()

    status, payload = _post(handler, "/reset", b"{not json at all")

    assert status == 400
    assert payload["ok"] is False
    assert payload["error"] == "invalid JSON"
    assert server.guidance_path.read_text() == ORIGINAL_GUIDANCE


def test_an_unknown_post_path_is_a_clean_404(server):
    # The handler must answer rather than raise: an unhandled path that killed the
    # thread would take the UI down mid-session.
    handler = server.handler()

    status, payload = _post(handler, "/not-a-route", b"{}")

    assert status == 404
    assert payload["error"] == "not found"
    assert server.guidance_path.read_text() == ORIGINAL_GUIDANCE
