# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
import sys
from pathlib import Path

_ANSI = re.compile(r"\033\[[0-9;]*m")


class Console:
    def __init__(self, stream=None) -> None:
        stream = stream or sys.stdout
        color = hasattr(stream, "isatty") and stream.isatty()
        self.bold = "\033[1m" if color else ""
        self.dim = "\033[2m" if color else ""
        self.red = "\033[31m" if color else ""
        self.green = "\033[32m" if color else ""
        self.yellow = "\033[33m" if color else ""
        self.blue = "\033[36m" if color else ""
        self.off = "\033[0m" if color else ""
        #: When set, every line printed is appended here with colours stripped.
        self._capture: Path | None = None

    # -- capture ----------------------------------------------------------
    def capture_to(self, path: Path | None) -> Path | None:
        previous = self._capture
        self._capture = path
        return previous

    def _echo(self, msg: str) -> None:
        if self._capture is None:
            return
        try:
            with self._capture.open("a", encoding="utf-8") as fh:
                fh.write(_ANSI.sub("", msg) + "\n")
        except OSError:
            # Capturing is instrumentation: never fail a run over it.
            pass

    def _emit(self, msg: str, *, err: bool = False) -> None:
        print(msg, file=sys.stderr if err else sys.stdout, flush=True)
        self._echo(msg)

    # -- output -----------------------------------------------------------
    def say(self, msg: str = "") -> None:
        self._emit(msg)

    def info(self, msg: str) -> None:
        self._emit(f"{self.blue}==>{self.off} {msg}")

    def ok(self, msg: str) -> None:
        self._emit(f"{self.green}  ok{self.off} {msg}")

    def warn(self, msg: str) -> None:
        self._emit(f"{self.yellow}warn{self.off} {msg}")

    def err(self, msg: str) -> None:
        self._emit(f"{self.red} fail{self.off} {msg}", err=True)

    def hdr(self, msg: str) -> None:
        self._emit(f"\n{self.bold}{msg}{self.off}\n"
                   f"{self.dim}{'-' * 72}{self.off}")

    def block(self, text: str, indent: str = "    ") -> None:
        """Print a dimmed, indented block (a log excerpt or command preview)."""
        if not text or not text.strip():
            return
        body = "\n".join(indent + line for line in text.rstrip().splitlines())
        self._emit(f"{self.dim}{body}{self.off}")

    def dry(self, msg: str) -> None:
        self._emit(f"  {self.dim}(dry run) {msg}{self.off}")


# Shared instance; the modules import this rather than constructing their own.
out = Console()
