# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
"""Terminal output helpers: colours, status lines, indented blocks."""
from __future__ import annotations

import sys


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

    def say(self, msg: str = "") -> None:
        print(msg, flush=True)

    def info(self, msg: str) -> None:
        print(f"{self.blue}==>{self.off} {msg}", flush=True)

    def ok(self, msg: str) -> None:
        print(f"{self.green}  ok{self.off} {msg}", flush=True)

    def warn(self, msg: str) -> None:
        print(f"{self.yellow}warn{self.off} {msg}", flush=True)

    def err(self, msg: str) -> None:
        print(f"{self.red} fail{self.off} {msg}", file=sys.stderr, flush=True)

    def hdr(self, msg: str) -> None:
        print(f"\n{self.bold}{msg}{self.off}\n{self.dim}{'-' * 72}{self.off}",
              flush=True)

    def block(self, text: str, indent: str = "    ") -> None:
        """Print a dimmed, indented block (a log excerpt or command preview)."""
        if not text or not text.strip():
            return
        body = "\n".join(indent + line for line in text.rstrip().splitlines())
        print(f"{self.dim}{body}{self.off}", flush=True)

    def dry(self, msg: str) -> None:
        print(f"  {self.dim}(dry run) {msg}{self.off}", flush=True)


# Shared instance; the modules import this rather than constructing their own.
out = Console()
