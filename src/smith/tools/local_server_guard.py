# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import secrets

TOKEN_HEADER = "X-Smith-Token"
TOKEN_PLACEHOLDER = "__SMITH_RESET_TOKEN__"


def new_token() -> str:
    """Mint a per-process token for the served page to echo back."""
    return secrets.token_urlsafe(32)


def allowed_hosts(host: str, port: int) -> frozenset[str]:
    names = {host, "127.0.0.1", "localhost", "[::1]", "::1"}
    values = {f"{name}:{port}" for name in names}
    if port in (80, 443):
        values |= names
    return frozenset(v.lower() for v in values)


def allowed_origins(hosts: frozenset[str]) -> frozenset[str]:
    """Origins matching ``hosts``; the page is served over plain http."""
    return frozenset(f"http://{h}" for h in hosts)


def inject_token(html: str, token: str) -> str:
    return html.replace(TOKEN_PLACEHOLDER, token)


class GuardMixin:

    guard_hosts: frozenset[str] = frozenset()
    guard_origins: frozenset[str] = frozenset()
    guard_token: str = ""

    def _host_ok(self) -> bool:
        return (self.headers.get("Host") or "").strip().lower() in self.guard_hosts

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None:
            # A same-origin GET omits Origin; browsers always set it on the
            # cross-origin requests we care about.
            return True
        return origin.strip().lower() in self.guard_origins

    def _json_content_type(self) -> bool:
        ctype = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip()
        return ctype.lower() == "application/json"

    def _token_ok(self) -> bool:
        supplied = self.headers.get(TOKEN_HEADER) or ""
        return bool(self.guard_token) and secrets.compare_digest(
            supplied, self.guard_token
        )

    def check_request(self, *, require_token: bool) -> bool:
        if not self._host_ok() or not self._origin_ok():
            self._send(403, json.dumps({"error": "forbidden"}))
            return False
        if require_token:
            if not self._json_content_type():
                self._send(
                    415, json.dumps({"error": "expected Content-Type application/json"})
                )
                return False
            if not self._token_ok():
                self._send(403, json.dumps({"error": "forbidden"}))
                return False
        return True
