# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
"""Discovering the example agents and choosing one."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .console import out


def guidance_line_count(example_dir: Path) -> int:
    """Count non-blank guidance lines.

    Guidance files do not always end with a newline (hr-agent's does not), which
    makes a naive `wc -l`-style count under-report.
    """
    f = example_dir / "smith" / "guidance.txt"
    try:
        text = f.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if line.strip())


def tool_count(example_dir: Path) -> int | None:
    """Number of MCP tools, or None when unknown.

    tool_definitions.json is {"tools": [...]}, so count that array — counting
    every `"name"` key would also count nested parameter names and inflate it.
    """
    f = example_dir / "smith" / "tool_definitions.json"
    if not f.is_file():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    tools = data.get("tools", data) if isinstance(data, dict) else data
    return len(tools) if isinstance(tools, list) else None


def discover(root: Path) -> list[str]:
    """Example names usable by the pipeline (those carrying Smith inputs)."""
    base = root / "examples"
    if not base.is_dir():
        return []
    return sorted(
        d.name for d in base.iterdir()
        if d.is_dir() and (d / "smith" / "guidance.txt").is_file()
    )


def choose(root: Path, requested: str | None) -> str:
    """Resolve `requested`, or prompt with a menu when it is None."""
    names = discover(root)
    if not names:
        out.err(f"No usable examples under {root / 'examples'} "
                "(each needs smith/guidance.txt).")
        sys.exit(1)

    if requested:
        if requested in names:
            return requested
        out.err(f"Example {requested!r} not found. Available: {' '.join(names)}")
        sys.exit(1)

    out.hdr("Select an example agent")
    for i, name in enumerate(names, 1):
        d = root / "examples" / name
        tools = tool_count(d)
        extra = f", {tools} tools" if tools is not None else ""
        out.say(f"  {out.bold}{i}{out.off}) {name:<24} "
                f"{out.dim}({guidance_line_count(d)} guidance lines{extra})"
                f"{out.off}")
    out.say("")

    try:
        raw = input(f"Example [1-{len(names)}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        out.say("")
        sys.exit(130)

    if not raw.isdigit() or not 1 <= int(raw) <= len(names):
        out.err(f"Invalid selection: {raw}")
        sys.exit(1)

    chosen = names[int(raw) - 1]
    out.ok(f"Selected: {chosen}")
    return chosen
