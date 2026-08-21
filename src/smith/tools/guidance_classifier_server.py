# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Local HTTP server for the Smith Guidance Classifier.

An *upstream* companion to the Policy Explorer (``explorer_server.py``). Where
the explorer browses the decomposed per-tool ``specs/*.json`` produced by the
full pipeline, this tool works on the raw ``guidance.txt`` *before* generation:
it classifies each guidance line to the MCP tool call(s) it governs (via
``classify_guidance_lines``, an LLM pass over ``tool_definitions.json``) and
serves an explorer-style UI to browse lines by tool, tick lines to combine, and
reset Smith's inputs.

The server binds to loopback only and is single-purpose; it is not a
general-purpose web server. Open the printed ``http://127.0.0.1:PORT`` URL in VS
Code's Simple Browser.
"""

import importlib.resources as resources
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from smith.tools.classify_guidance_lines import classify_guidance_lines


def _read_html() -> str:
    html = resources.files("smith.tools") / "guidance_classifier.html"
    return html.read_text(encoding="utf-8")


def _resolve_guidance_path(base_url: str, guidance_file: str) -> str:
    """Resolve guidance.txt the same way the rest of Smith does: BASE_URL + GUIDANCE_FILE."""
    if os.path.isabs(guidance_file):
        return guidance_file
    return os.path.join(base_url, guidance_file)


def _find_clean_script(base_url: str) -> str:
    return os.path.join(base_url, "scripts", "clean_generated.sh")


def make_handler(base_url, guidance_path, clean_script, tool_definitions, model_cfg):
    def _classify_text(guidance):
        """Run the LLM classification over a guidance string uploaded by the UI."""
        try:
            lines = classify_guidance_lines(
                model_cfg["api_key"],
                model_cfg["base_url"],
                model_cfg["model"],
                model_cfg["temp"],
                model_cfg["top_p"],
                guidance,
                tool_definitions,
            )
        except Exception as exc:  # noqa: BLE001 - surface any LLM/IO error to the UI
            return None, f"classification failed: {exc}"
        return lines, None

    class Handler(BaseHTTPRequestHandler):
        # Quieter logging; still prints one line per request.
        def log_message(self, fmt, *a):  # noqa: A003 - stdlib signature
            print("[classifier] " + (fmt % a))

        def _send(self, code, body, content_type="application/json"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _read_json_body(self):
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw or b"{}")

        def do_GET(self):  # noqa: N802 - stdlib signature
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._send(200, _read_html(), "text/html; charset=utf-8")
                return
            if path == "/config":
                # The UI needs to know where Reset writes (the .env guidance.txt)
                # and how many tools were extracted from the live MCP server.
                self._send(
                    200,
                    json.dumps(
                        {
                            "guidance_path": guidance_path,
                            "tool_count": len(tool_definitions.get("tools", [])),
                        }
                    ),
                )
                return
            self._send(404, json.dumps({"error": "not found"}))

        def do_POST(self):  # noqa: N802 - stdlib signature
            if self.path == "/classify":
                # Classify guidance TEXT uploaded in the browser (the file on the
                # user's disk is never read server-side).
                try:
                    payload = self._read_json_body()
                except json.JSONDecodeError:
                    self._send(400, json.dumps({"error": "invalid JSON"}))
                    return
                guidance = payload.get("guidance", "")
                lines, err = _classify_text(guidance)
                if err:
                    self._send(500, json.dumps({"error": err}))
                    return
                self._send(
                    200,
                    json.dumps({"lines": lines}),
                )
                return

            if self.path != "/reset":
                self._send(404, json.dumps({"error": "not found"}))
                return

            try:
                payload = self._read_json_body()
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


def serve(tool_definitions, port: int = 8110, host: str = "127.0.0.1") -> None:
    base_url = os.getenv("BASE_URL")
    guidance_file = os.getenv("GUIDANCE_FILE")
    if not base_url or not guidance_file:
        raise SystemExit(
            "serve needs BASE_URL and GUIDANCE_FILE set in .env "
            "(BASE_URL is the skill folder, GUIDANCE_FILE is the target agent's guidance.txt)."
        )

    guidance_path = _resolve_guidance_path(base_url, guidance_file)
    clean_script = _find_clean_script(base_url)
    model_cfg = {
        "api_key": os.getenv("OPENAI_API_KEY"),
        "base_url": os.getenv("OPENAI_BASE_URL"),
        "model": os.getenv("MODEL_SONNET"),
        "temp": float(os.getenv("TEMP", "0.2")),
        "top_p": float(os.getenv("TOP_P", "0.9")),
    }

    handler = make_handler(
        base_url, guidance_path, clean_script, tool_definitions, model_cfg
    )
    httpd = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}/"
    print(f"Guidance Classifier serving at: {url}")
    print(f"  reset target      : {guidance_path}  (.env GUIDANCE_FILE)")
    print(f"  tools extracted   : {len(tool_definitions.get('tools', []))}")
    print(f"  clean script      : {clean_script}")
    print("Open the URL above in VS Code's Simple Browser (Cmd+Shift+P →")
    print('  "Simple Browser: Show"), then upload a guidance file to classify it.')
    print("Reset writes the uploaded/edited text to the reset target above; the")
    print("file you upload on disk is never modified.")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Guidance Classifier server.")
    finally:
        httpd.server_close()
