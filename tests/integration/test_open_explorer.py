# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration test for the ``open_explorer`` flag.

``open_explorer`` launches the Policy Explorer web UI (a ThreadingHTTPServer on
port 8100) and blocks. We drive it like a server: launch the flag as a
subprocess, poll the cheap ``GET /guidance`` JSON endpoint and the ``GET /`` HTML
root, assert they serve, then terminate. No LLM/agent/OPA needed.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request

import pytest

from helpers import BASE_URL

pytestmark = pytest.mark.integration

EXPLORER_PORT = 8100  # fixed in cli.py: serve(port=8100)


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _get(url: str, timeout: float = 3.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        return resp.status, resp.read().decode()


def test_open_explorer_serves_ui():
    if _port_in_use(EXPLORER_PORT):
        pytest.skip(f"port {EXPLORER_PORT} already in use")

    proc = subprocess.Popen(
        ["smith", "--flag", "open_explorer"],
        cwd=BASE_URL,
        env=dict(os.environ),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base = f"http://127.0.0.1:{EXPLORER_PORT}"
    try:
        deadline = time.time() + 30
        served = False
        while time.time() < deadline:
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                pytest.fail(f"open_explorer exited early:\n{out[-1200:]}")
            try:
                # /guidance is a cheap JSON endpoint; / serves the HTML UI.
                status, body = _get(f"{base}/guidance")
                assert status == 200
                assert "guidance" in json.loads(body)
                root_status, root_body = _get(f"{base}/")
                assert root_status == 200 and "<" in root_body
                served = True
                break
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(0.5)
        assert served, "explorer did not serve within the timeout"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
