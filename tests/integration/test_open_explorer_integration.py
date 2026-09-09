# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration test for ``smith --flag open_explorer``.

The flag launches the Policy Explorer UI — a ``ThreadingHTTPServer`` on port 8100 —
and **blocks** until interrupted::

    serve(port=8100)   serve the UI, then httpd.serve_forever()

Because the flag never returns, there is no completed run to inspect the way the
other flags allow. So it is driven **like a server**: launch the CLI as a
subprocess, wait for it to answer, assert it is serving, then terminate it.

SCOPE: THE SERVER RUNS
----------------------
Deliberately narrow — this lane proves the command works and the UI is reachable,
nothing more:

* the flag starts and stays up rather than exiting early
* ``GET /`` serves the HTML UI
* ``GET /guidance`` answers, so the UI has data to render
* an unknown path is a clean 404 rather than a traceback
* the process shuts down when terminated

The *content* of what it serves is not checked. The guidance text it returns is
just the configured file read back, and ``get_current_agent`` already covers that
that path resolves.

NO UNIT LANE
------------
None. The flag is two lines — an import and ``serve(port=8100)`` — and the handler
logic behind it belongs to the explorer UI rather than to a pipeline stage.

``POST /reset`` IS NEVER EXERCISED
---------------------------------
It runs ``scripts/clean_generated.sh`` and then overwrites the target agent's real
``guidance.txt``. Deleting a developer's generated artifacts and rewriting a tracked
input file is not something a test may do to the working tree — the same reason the
classifier's identical route is left alone.

The port is hardcoded in ``cli.py`` (``serve(port=8100)``), so unlike a
fixture-chosen free port this test must skip when 8100 is already busy.

Needs no LLM, no agent, no OPA, no Docker.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

from helpers import SmithEnv

pytestmark = pytest.mark.integration

#: Fixed in cli.py: ``serve(port=8100)``.
EXPLORER_PORT = 8100

#: No MCP server or model to wait for here, so startup is quick.
STARTUP_TIMEOUT = 45.0


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _get(url: str, timeout: float = 5.0):
    """GET a URL; return ``(status, body)``.

    An HTTP error *code* is returned rather than raised, so a 404 is assertable. A
    connection failure returns ``(None, "")`` — during startup polling the server is
    simply not listening yet, which is expected rather than an error.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()
    except (urllib.error.URLError, ConnectionError, OSError):
        return None, ""


@pytest.fixture(scope="module")
def explorer_server():
    """Launch the flag ONCE, wait until it serves, and always terminate it."""
    if _port_in_use(EXPLORER_PORT):
        pytest.skip(f"port {EXPLORER_PORT} is already in use")

    env = SmithEnv()
    proc = subprocess.Popen(
        [sys.executable, "-m", "smith.cli", "--flag", "open_explorer"],
        cwd=str(env.base),
        env=env.override(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base = f"http://127.0.0.1:{EXPLORER_PORT}"

    try:
        deadline = time.time() + STARTUP_TIMEOUT
        while time.time() < deadline:
            # An early exit is a real failure, not a slow start: `serve` raises
            # SystemExit on missing configuration. Surface the output rather than
            # timing out with no explanation.
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                pytest.fail(
                    f"open_explorer exited early (rc={proc.returncode}):\n{out[-2000:]}"
                )
            status, _ = _get(f"{base}/guidance", timeout=2.0)
            if status == 200:
                break
            time.sleep(0.5)
        else:
            proc.terminate()
            out = ""
            try:
                out = proc.communicate(timeout=5)[0] or ""
            except subprocess.TimeoutExpired:
                proc.kill()
            pytest.fail(
                f"the explorer did not serve within {STARTUP_TIMEOUT:.0f}s:\n"
                f"{out[-2000:]}"
            )

        yield {"base": base, "proc": proc}
    finally:
        proc.terminate()
        try:
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()


# ===========================================================================
# The server runs
# ===========================================================================


def test_the_flag_stays_running_while_it_serves(explorer_server):
    # A blocking server that has exited is the failure mode this flag is most prone
    # to, since `serve` raises SystemExit on missing configuration.
    assert (
        explorer_server["proc"].poll() is None
    ), "the flag exited instead of continuing to serve"


def test_the_ui_is_served_at_the_root(explorer_server):
    status, body = _get(explorer_server["base"] + "/")
    assert status == 200
    # It must be the HTML UI, not a JSON error page that happens to be a 200.
    assert "<" in body[:200].lower(), f"root did not serve HTML: {body[:200]!r}"


def test_the_guidance_endpoint_answers(explorer_server):
    # The UI's data call. Only that it answers with the expected JSON shape is
    # checked — the guidance text itself is just the configured file read back.
    status, body = _get(explorer_server["base"] + "/guidance")
    assert status == 200
    assert "guidance" in json.loads(body)


def test_an_unknown_path_is_a_clean_404(explorer_server):
    # The handler must answer rather than raise: an unhandled path that killed the
    # thread would take the UI down mid-session.
    status, body = _get(explorer_server["base"] + "/does-not-exist")
    assert status == 404
    assert json.loads(body)["error"] == "not found"
