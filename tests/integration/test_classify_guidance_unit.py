# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for ``POST /reset``, the destructive route behind
``smith --flag classify_guidance``.

The Guidance Classifier UI's Reset button commits the user's edited guidance. The
handler does three things in order, and **each one can fail**::

    1. run scripts/clean_generated.sh   delete every generated artifact
    2. overwrite <GUIDANCE_FILE>        the target agent's tracked guidance.txt
    3. write session_config.json        {use_ir, selected_tools}

SCOPE: WHY THIS ROUTE IS UNIT-ONLY
----------------------------------
The integration lane deliberately never calls ``/reset``: it deletes a developer's
generated files and rewrites a tracked input. So the only safe place to exercise it
is here, against a temporary tree.

FUNCTIONS UNDER TEST
--------------------
``smith.tools.guidance_classifier_server``

STEP 0 · ``_resolve_guidance_path`` — how the reset target is resolved
STEP 1 · ``make_handler`` -> ``do_POST`` — the clean-script step and its two
                                          failure modes
STEP 2 · ``make_handler`` -> ``do_POST`` — the guidance overwrite
STEP 3 · ``make_handler`` -> ``do_POST`` — the session config, and how ``use_ir``
                                          is derived
Guards  the JSON guard and the unknown-path 404

NOT COVERED HERE (integration lane — see ``test_classify_guidance_integration.py``)
    The server actually starting, ``GET /`` and ``/config``, and ``POST /classify``
    against a real model.

Env-free: no socket is opened, the clean script is a local stub, and no model is
contacted.
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
    """A handler over a temporary tree, plus the paths it will write.

    ``clean_script`` defaults to a stub that succeeds; individual tests replace it
    to drive the failure branches.
    """
    root = unit_env.root
    guidance = root / "smith" / "guidance.txt"
    guidance.parent.mkdir(parents=True, exist_ok=True)
    guidance.write_text(ORIGINAL_GUIDANCE)

    class Server:
        base = str(root)
        guidance_path = guidance
        session_config = root / "references" / "session_config.json"
        clean_script = root / "clean_generated.sh"
        #: Set by ``script`` so a test can assert the script really ran.
        marker = root / "clean_ran.marker"

        def script(self, body="#!/bin/bash\nexit 0\n", *, create=True):
            """Install a clean-script stub and return a handler bound to it."""
            if create:
                self.clean_script.write_text(body)
                self.clean_script.chmod(0o755)
            return make_handler(
                self.base,
                str(self.guidance_path),
                str(self.clean_script),
                {"tools": []},
                {},
            )

    return Server()


def _reset_body(guidance=EDITED_GUIDANCE, **extra):
    return json.dumps({"guidance": guidance, **extra}).encode()


# ===========================================================================
# STEP 0 · _resolve_guidance_path — which file Reset will overwrite
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
# STEP 1 · the clean script runs first, and its failures stop the sequence
# ===========================================================================


def test_a_successful_reset_runs_the_script_and_writes_both_files(server):
    # The happy path, in order: the script runs, the guidance is replaced, and the
    # session config records the tool selection.
    handler = server.script(f"#!/bin/bash\ntouch {server.marker}\nexit 0\n")

    status, payload = _post(
        handler, "/reset", _reset_body(selected_tools=["get_events"])
    )

    assert status == 200
    assert payload["ok"] is True
    assert server.marker.exists(), "the clean script did not run"
    assert server.guidance_path.read_text() == EDITED_GUIDANCE
    assert json.loads(server.session_config.read_text()) == {
        "use_ir": True,
        "selected_tools": ["get_events"],
    }


def test_a_missing_clean_script_aborts_before_touching_the_guidance(server):
    """CORRECTNESS: the guard exists so a misconfigured tree cannot half-reset.

    ``_find_clean_script`` builds the path from ``BASE_URL``, so a relocated or
    incomplete checkout yields a path that does not exist. Overwriting the guidance
    anyway would destroy the user's file while leaving the generated artifacts it was
    supposed to be consistent with in place.
    """
    handler = server.script(create=False)

    status, payload = _post(handler, "/reset", _reset_body())

    assert status == 500
    assert payload["ok"] is False
    assert "clean script not found" in payload["error"]
    assert (
        server.guidance_path.read_text() == ORIGINAL_GUIDANCE
    ), "the guidance was overwritten even though the reset could not proceed"
    assert not server.session_config.exists()


def test_a_failing_clean_script_aborts_before_touching_the_guidance(server):
    """CORRECTNESS: the same property, for a script that runs but exits non-zero.

    This is the more dangerous case — the script may have deleted *some* artifacts
    before failing. Replacing the guidance on top of that would leave the tree in a
    state no one can reason about, so the sequence stops and says why.
    """
    handler = server.script("#!/bin/bash\necho 'permission denied' >&2\nexit 1\n")

    status, payload = _post(handler, "/reset", _reset_body())

    assert status == 500
    assert payload["ok"] is False
    assert payload["error"] == "clean_generated.sh failed"
    # The script's own stderr is forwarded, since that is the actionable part.
    assert "permission denied" in payload["detail"]
    assert server.guidance_path.read_text() == ORIGINAL_GUIDANCE
    assert not server.session_config.exists()


def test_the_clean_script_runs_from_the_project_root(server):
    # `clean_generated.sh` deletes paths relative to where it runs, so a wrong cwd
    # would either delete nothing or delete somewhere else entirely.
    handler = server.script(f"#!/bin/bash\npwd > {server.marker}\nexit 0\n")

    status, _ = _post(handler, "/reset", _reset_body())

    assert status == 200
    assert server.marker.read_text().strip() == server.base


# ===========================================================================
# STEP 2 · the guidance overwrite
# ===========================================================================


def test_the_uploaded_text_replaces_the_file_exactly(server):
    # CORRECTNESS: this is a commit of the user's edits, so the bytes must land
    # verbatim — no appending, no reformatting, no trailing-newline surprises.
    handler = server.script()
    edited = "1. First rule.\n2. Second rule.\n\n# A comment\n"

    _post(handler, "/reset", _reset_body(guidance=edited))

    assert server.guidance_path.read_text() == edited


def test_the_guidance_directory_is_created_on_demand(server):
    # A fresh target agent may have no smith/ directory yet. Reset must create it
    # rather than failing on a path that does not exist.
    import shutil

    shutil.rmtree(server.guidance_path.parent)
    handler = server.script()

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
    handler = server.script()

    status, _ = _post(handler, "/reset", json.dumps({}).encode())

    assert status == 200
    assert server.guidance_path.read_text() == ""


# ===========================================================================
# STEP 3 · the session config
# ===========================================================================


def test_selecting_tools_turns_ir_mode_on(server):
    # `use_ir` is what every later stage keys on to filter cases to a tool subset,
    # so it must be derived from the selection rather than set independently.
    handler = server.script()

    _post(handler, "/reset", _reset_body(selected_tools=["get_events", "other"]))

    config = json.loads(server.session_config.read_text())
    assert config["use_ir"] is True
    assert config["selected_tools"] == ["get_events", "other"]


def test_selecting_no_tools_turns_ir_mode_off(server):
    handler = server.script()

    _post(handler, "/reset", _reset_body())

    config = json.loads(server.session_config.read_text())
    assert config["use_ir"] is False
    assert config["selected_tools"] == []


# ===========================================================================
# Guards — malformed requests reach no step at all
# ===========================================================================


def test_a_malformed_body_is_rejected_before_anything_is_deleted(server):
    """The JSON guard precedes the clean script, so a bad request destroys nothing.

    Ordering matters: parsing after running the script would delete a developer's
    artifacts on a request that was never actionable.
    """
    handler = server.script(f"#!/bin/bash\ntouch {server.marker}\nexit 0\n")

    status, payload = _post(handler, "/reset", b"{not json at all")

    assert status == 400
    assert payload["ok"] is False
    assert payload["error"] == "invalid JSON"
    assert not server.marker.exists(), "the clean script ran on a malformed request"
    assert server.guidance_path.read_text() == ORIGINAL_GUIDANCE


def test_an_unknown_post_path_is_a_clean_404(server):
    # The handler must answer rather than raise: an unhandled path that killed the
    # thread would take the UI down mid-session.
    handler = server.script()

    status, payload = _post(handler, "/not-a-route", b"{}")

    assert status == 404
    assert payload["error"] == "not found"
    assert server.guidance_path.read_text() == ORIGINAL_GUIDANCE
