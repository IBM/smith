# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Local HTTP server for the Smith Policy Explorer.

Serves the bundled ``policy_explorer.html`` and a small ``/reset`` endpoint so a
button in the page can trigger a Python-side reset (run ``clean_generated.sh``
then overwrite ``guidance.txt``). It is meant to be opened in the current VS
Code window via the Simple Browser at the printed ``http://127.0.0.1:PORT`` URL.

The server binds to loopback only and is single-purpose; it is not a
general-purpose web server.
"""

import importlib.resources as resources
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _read_html() -> str:
    html = resources.files("smith.tools") / "policy_explorer.html"
    return html.read_text(encoding="utf-8")


def _resolve_guidance_path(base_url: str, guidance_file: str) -> str:
    """Resolve guidance.txt the same way the rest of Smith does: BASE_URL + GUIDANCE_FILE."""
    if os.path.isabs(guidance_file):
        return guidance_file
    return os.path.join(base_url, guidance_file)


def _find_clean_script(base_url: str) -> str:
    return os.path.join(base_url, "scripts", "clean_generated.sh")


def make_handler(base_url: str, guidance_path: str, clean_script: str):
    class Handler(BaseHTTPRequestHandler):
        # Quieter logging; still prints one line per request.
        def log_message(self, fmt, *a):  # noqa: A003 - stdlib signature
            print("[explorer] " + (fmt % a))

        def _send(self, code, body, content_type="application/json"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802 - stdlib signature
            if self.path in ("/", "/index.html"):
                self._send(200, _read_html(), "text/html; charset=utf-8")
                return
            if self.path == "/guidance":
                text = ""
                if os.path.exists(guidance_path):
                    with open(guidance_path, encoding="utf-8") as f:
                        text = f.read()
                self._send(
                    200,
                    json.dumps({"guidance": text, "path": guidance_path}),
                )
                return
            self._send(404, json.dumps({"error": "not found"}))

        def do_POST(self):  # noqa: N802 - stdlib signature
            if self.path != "/reset":
                self._send(404, json.dumps({"error": "not found"}))
                return

            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                self._send(400, json.dumps({"ok": False, "error": "invalid JSON"}))
                return
            guidance = payload.get("guidance", "")

            # 1) run the clean script (repo-root scope: no ROOT arg).
            if not os.path.exists(clean_script):
                self._send(
                    500,
                    json.dumps(
                        {
                            "ok": False,
                            "error": f"clean script not found: {clean_script}",
                        }
                    ),
                )
                return
            try:
                proc = subprocess.run(
                    ["bash", clean_script],
                    cwd=base_url,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except (subprocess.SubprocessError, OSError) as exc:
                self._send(500, json.dumps({"ok": False, "error": str(exc)}))
                return
            if proc.returncode != 0:
                self._send(
                    500,
                    json.dumps(
                        {
                            "ok": False,
                            "error": "clean_generated.sh failed",
                            "detail": proc.stderr or proc.stdout,
                        }
                    ),
                )
                return

            # 2) overwrite guidance.txt with the edited text.
            try:
                os.makedirs(os.path.dirname(guidance_path), exist_ok=True)
                with open(guidance_path, "w", encoding="utf-8") as f:
                    f.write(guidance)
            except OSError as exc:
                self._send(
                    500,
                    json.dumps({"ok": False, "error": f"write guidance failed: {exc}"}),
                )
                return

            # 3) write session_config.json with selected tools.
            selected_tools = payload.get("selected_tools", [])
            session_config_path = os.path.join(
                base_url,
                os.getenv("SESSION_CONFIG_FILE", "references/session_config.json"),
            )
            session_config = {
                "use_ir": bool(selected_tools),
                "selected_tools": selected_tools,
            }
            try:
                os.makedirs(os.path.dirname(session_config_path), exist_ok=True)
                with open(session_config_path, "w", encoding="utf-8") as f:
                    json.dump(session_config, f, indent=2)
            except OSError as exc:
                self._send(
                    500,
                    json.dumps(
                        {"ok": False, "error": f"write session_config failed: {exc}"}
                    ),
                )
                return

            self._send(
                200,
                json.dumps(
                    {
                        "ok": True,
                        "message": "Cleaned generated files and wrote "
                        + os.path.basename(guidance_path),
                        "path": guidance_path,
                    }
                ),
            )

    return Handler


def serve(port: int = 8100, host: str = "127.0.0.1") -> None:
    base_url = os.getenv("BASE_URL")
    guidance_file = os.getenv("GUIDANCE_FILE")
    if not base_url or not guidance_file:
        raise SystemExit(
            "serve_explorer needs BASE_URL and GUIDANCE_FILE set in .env "
            "(BASE_URL is the skill folder, GUIDANCE_FILE is the target agent's guidance.txt)."
        )

    guidance_path = _resolve_guidance_path(base_url, guidance_file)
    clean_script = _find_clean_script(base_url)

    handler = make_handler(base_url, guidance_path, clean_script)
    httpd = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}/"
    print(f"Policy Explorer serving at: {url}")
    print(f"  guidance.txt : {guidance_path}")
    print(f"  clean script : {clean_script}")
    print("Open the URL above in VS Code's Simple Browser (Cmd+Shift+P →")
    print('  "Simple Browser: Show"), then use the Reset button in the page.')
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Policy Explorer server.")
    finally:
        httpd.server_close()
