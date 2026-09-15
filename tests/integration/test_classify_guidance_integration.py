# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration test for ``smith --flag classify_guidance``.

The flag launches the Guidance Classifier UI: it pulls MCP tool definitions, then
serves a ``ThreadingHTTPServer`` and **blocks** until interrupted::

    get_tool_definitions()   spawn the MCP server, list its tools
    serve(port=8110)         serve the UI, then httpd.serve_forever()

Because the flag never returns, there is no completed run to inspect the way the
other flags allow. So it is driven **like a server**: launch the CLI as a
subprocess, wait for it to answer, assert what it serves, then terminate it.

WHAT IS ASSERTED
----------------
The server comes up, and the classification it exists to perform actually works:

* the flag starts and stays up rather than exiting early (a missing ``BASE_URL``
  or ``GUIDANCE_FILE`` makes ``serve`` raise ``SystemExit``, which this catches)
* MCP tool extraction happened *before* serving, and found at least one tool —
  the UI's whole purpose is mapping guidance lines onto those tools
* ``GET /config`` reports the reset target and the tool count the UI needs
* ``GET /`` serves the HTML UI
* an unknown path is a clean 404 rather than a traceback
* **``POST /classify`` runs ``classify_guidance_lines`` against a real model** and
  maps a rule naming a tool onto that tool — the flag's actual purpose

ASSERTING CORRECTNESS
---------------------
Which tools a model picks is its own judgement, so exact assertions are confined
to inputs with one defensible answer, plus the parts decided in code:

* A rule that **names ``get_events`` explicitly** must map to it. The example agent
  exposes exactly one tool, so there is no competing alternative — this is not a
  coin flip.
* A **definitional** line ("a manager is an employee with…") must map to ``[]``.
  Empty is the documented answer for a line that gates no tool call, and the guide
  permits asserting a "no match" outcome where the input genuinely warrants it.
* **Source order and line identity** are pure bookkeeping: the thread pool writes
  into a pre-sized list by position, and bullet markers are stripped into ``text``
  while ``raw`` keeps the verbatim line.

NOT COVERED HERE
----------------
The ``/reset`` three-step sequence (clean script, guidance write, session_config
write) and its failure ordering. It was already tested in unit test. 

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

#: Fixed in cli.py: ``serve(tool_definitions, port=8110)``.
CLASSIFIER_PORT = 8110

#: The flag spawns an MCP server before it serves, so first byte takes a while.
STARTUP_TIMEOUT = 90.0

#: The tool the example agent exposes — the only name a classification may contain.
EXPECTED_TOOL = "get_events"

#: Two lines, kept minimal because each costs one LLM call.
CLASSIFY_GUIDANCE = (
    "1. Only faculty may use the get_events tool to search conferences.\n"
    "2. A manager is an employee with at least one direct report.\n"
)


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _get(url: str, timeout: float = 5.0):
    """GET a URL; return ``(status, body)``.

    An HTTP error *code* is returned rather than raised, so a 404 is assertable.
    A connection failure returns ``(None, "")`` — during startup polling the
    server is simply not listening yet, which is expected rather than an error.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()
    except (urllib.error.URLError, ConnectionError, OSError):
        return None, ""


def _post(url: str, payload, timeout: float = 600.0):
    """POST JSON; return ``(status, body)``. HTTP error codes are returned, not raised.

    ``payload`` may be ``bytes`` to send a deliberately malformed body. The default
    timeout is generous because ``/classify`` fans out one model call per line.
    """
    data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


@pytest.fixture(scope="module")
def classifier_server():
    """Launch the flag ONCE, wait until it serves, and always terminate it."""
    if _port_in_use(CLASSIFIER_PORT):
        pytest.skip(f"port {CLASSIFIER_PORT} is already in use")

    env = SmithEnv()
    proc = subprocess.Popen(
        [sys.executable, "-m", "smith.cli", "--flag", "classify_guidance"],
        cwd=str(env.base),
        env=env.override(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base = f"http://127.0.0.1:{CLASSIFIER_PORT}"

    try:
        deadline = time.time() + STARTUP_TIMEOUT
        while time.time() < deadline:
            # An early exit is a real failure, not a slow start: `serve` raises
            # SystemExit when BASE_URL/GUIDANCE_FILE are unset, and tool
            # extraction can fail outright. Surface the output rather than
            # timing out with no explanation.
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                pytest.fail(
                    f"classify_guidance exited early (rc={proc.returncode}):\n"
                    f"{out[-2000:]}"
                )
            status, _ = _get(f"{base}/config", timeout=2.0)
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
                f"the classifier did not serve within {STARTUP_TIMEOUT:.0f}s:\n"
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
# The command works and the server is up
# ===========================================================================


def test_the_flag_stays_running_while_it_serves(classifier_server):
    # A blocking server that has exited is the failure mode this flag is most
    # prone to, since `serve` raises SystemExit on missing configuration.
    assert (
        classifier_server["proc"].poll() is None
    ), "the flag exited instead of continuing to serve"


def test_the_ui_is_served_at_the_root(classifier_server):
    status, body = _get(classifier_server["base"] + "/")
    assert status == 200
    # It must be the HTML UI, not a JSON error page that happens to be a 200.
    assert "<" in body[:200].lower(), f"root did not serve HTML: {body[:200]!r}"


def test_the_config_endpoint_reports_what_the_ui_needs(classifier_server):
    """``/config`` is the UI's bootstrap call, and both fields are load-bearing.

    ``guidance_path`` is where Reset will write, so the UI shows it to the user
    before they overwrite anything. ``tool_count`` proves MCP extraction ran: a
    count of zero means the classifier would offer no tools to map guidance onto,
    making the UI useless even though the server is up.
    """
    status, body = _get(classifier_server["base"] + "/config")
    assert status == 200

    config = json.loads(body)
    assert config["guidance_path"].endswith(
        ".txt"
    ), f"the reset target should be a guidance text file: {config['guidance_path']!r}"
    assert config["tool_count"] > 0, (
        "no MCP tools were extracted, so there is nothing to classify guidance "
        "against"
    )


def test_an_unknown_path_is_a_clean_404(classifier_server):
    # The handler must answer rather than raise: an unhandled path that killed the
    # thread would take the UI down mid-session.
    status, body = _get(classifier_server["base"] + "/does-not-exist")
    assert status == 404
    assert json.loads(body)["error"] == "not found"


# ===========================================================================
# POST /classify — classify_guidance_lines against a real model
# ===========================================================================


@pytest.fixture(scope="module")
def classified(classifier_server):
    """POST ``/classify`` ONCE; yield the ``lines`` it returned."""
    env = SmithEnv()
    missing = env.missing("OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL_SONNET")
    if missing:
        pytest.skip(f"Smith LLM not configured (missing {', '.join(missing)})")

    status, body = _post(
        classifier_server["base"] + "/classify", {"guidance": CLASSIFY_GUIDANCE}
    )
    assert status == 200, f"/classify failed with {status}: {body[:1000]}"

    payload = json.loads(body)
    assert "lines" in payload, f"the response has no 'lines' key: {payload}"
    lines = payload["lines"]
    assert (
        len(lines) == 2
    ), f"both guidance lines should have been classified, got {len(lines)}: {lines}"
    return lines


def test_a_rule_naming_a_tool_is_mapped_to_that_tool(classified):
    """CORRECTNESS: the crafted rule names ``get_events`` in its own text."""
    rule = classified[0]
    assert rule["tools"] == [EXPECTED_TOOL], (
        f"a rule explicitly naming {EXPECTED_TOOL} was mapped to "
        f"{rule['tools']} (reason: {rule.get('reason')!r})"
    )


def test_a_definitional_line_is_mapped_to_no_tool(classified):
    """CORRECTNESS: empty is the documented answer for a line that gates nothing."""
    definition = classified[1]
    assert definition["tools"] == [], (
        f"a definitional line was mapped to {definition['tools']} "
        f"(reason: {definition.get('reason')!r})"
    )


def test_every_line_is_returned_in_source_order_with_its_identity(classified):
    assert [line["index"] for line in classified] == [0, 1]
    assert classified[0]["raw"].startswith("1. ")
    assert not classified[0]["text"].startswith(
        "1. "
    ), "the bullet marker was not stripped"
    assert classified[0]["text"] in classified[0]["raw"]


def test_every_line_carries_a_reason(classified):
    for line in classified:
        assert line["reason"].strip(), f"line {line['index']} has no reason"
        assert (
            "failed to parse" not in line["reason"].lower()
        ), f"the model's reply could not be parsed: {line['reason']!r}"


def test_a_malformed_classify_body_is_rejected_without_calling_the_model(
    classifier_server,
):
    status, body = _post(
        classifier_server["base"] + "/classify", b"{not json", timeout=30.0
    )
    assert status == 400
    assert json.loads(body)["error"] == "invalid JSON"
