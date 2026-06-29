#!/usr/bin/env python3
# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
"""Insert or verify SPDX license headers across Smith's source tree.

All in-scope file types use ``#`` line comments (Python, shell, YAML, Makefile,
Dockerfile, Rego), so a single header form covers everything:

    # Copyright 2026 Smith authors
    # SPDX-License-Identifier: Apache-2.0

The header is inserted after any shebang (``#!...``) and after a leading encoding
declaration. Files that already carry an ``SPDX-License-Identifier`` line are
left untouched, so the tool is idempotent.

Scope (see ``INCLUDE_*``/``EXCLUDE_DIRS`` below): Smith core only — ``src/smith/``
(excluding the vendored ARES tree), ``assets/`` (excluding generated OPA
outputs), and root configs. Generated artifacts (``references/``,
``assets/opa/outputs/``) and the ``examples/`` example agents (which bundle
third-party-derived MCP server code) are excluded.

Usage:
    python src/smith/tools/license_headers.py --check   # exit 1 if any file lacks a header
    python src/smith/tools/license_headers.py --fix     # insert missing headers in place
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

COPYRIGHT = "# Copyright 2026 Smith authors"
SPDX = "# SPDX-License-Identifier: Apache-2.0"
HEADER_LINES = [COPYRIGHT, SPDX]
SPDX_MARKER = "SPDX-License-Identifier"

# Repository root, derived from this file's location:
# src/smith/tools/license_headers.py -> parents[3] is the repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]

# File extensions that get a header (all use "#" comments).
INCLUDE_EXTENSIONS = {".py", ".rego", ".sh", ".yaml", ".yml"}
# Filenames (no extension) that get a header.
INCLUDE_FILENAMES = {"Makefile", "Dockerfile"}

# Directory path fragments (relative to repo root, POSIX style) to skip entirely:
# vendored upstreams, generated artifacts, third-party-derived examples, and the
# usual build/VCS/tooling noise.
EXCLUDE_DIRS = (
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".ruff_cache",
    ".sketchpad",
    "build",
    "dist",
    ".eggs",
    "src/smith/test_generation/ares",  # vendored ARES inputs (separate upstream)
    "references",  # generated pipeline artifacts
    "assets/opa/outputs",  # generated OPA intermediates
    # The example agents under examples/ bundle third-party-derived MCP server
    # code (e.g. call-for-papers-mcp ships an upstream MIT license), so Smith does
    # not stamp its Apache header on them. Only Smith core is headered.
    "examples",
)


def is_excluded(rel_path: Path) -> bool:
    """True if the file falls under any excluded directory."""
    posix = rel_path.as_posix()
    parts = set(rel_path.parts)
    for frag in EXCLUDE_DIRS:
        if "/" in frag:
            if posix == frag or posix.startswith(frag + "/"):
                return True
        elif frag in parts:
            return True
    return False


def in_scope(path: Path) -> bool:
    return path.suffix in INCLUDE_EXTENSIONS or path.name in INCLUDE_FILENAMES


def iter_target_files() -> list[Path]:
    files = []
    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(REPO_ROOT)
        if is_excluded(rel) or not in_scope(path):
            continue
        files.append(path)
    return files


def has_header(text: str) -> bool:
    # Check only the top of the file so we don't match SPDX strings in payloads.
    head = text.splitlines()[:10]
    return any(SPDX_MARKER in line for line in head)


def insert_header(text: str) -> str:
    lines = text.splitlines(keepends=True)
    prefix = []
    rest = lines

    # Preserve a shebang on the first line.
    if rest and rest[0].startswith("#!"):
        prefix.append(rest[0])
        rest = rest[1:]
    # Preserve a Python encoding declaration on the (now) first line.
    if rest and "coding:" in rest[0] and rest[0].lstrip().startswith("#"):
        prefix.append(rest[0])
        rest = rest[1:]

    header = "".join(line + "\n" for line in HEADER_LINES)
    # A blank line between the header and existing content, unless the file is empty.
    separator = "\n" if rest and rest[0].strip() else ""
    return "".join(prefix) + header + separator + "".join(rest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--check",
        action="store_true",
        help="report files missing a header (exit 1 if any)",
    )
    group.add_argument(
        "--fix", action="store_true", help="insert missing headers in place"
    )
    args = parser.parse_args()

    missing = [
        p for p in iter_target_files() if not has_header(p.read_text(encoding="utf-8"))
    ]

    if args.check:
        if missing:
            print(f"{len(missing)} file(s) missing an SPDX header:")
            for p in missing:
                print(f"  {p.relative_to(REPO_ROOT)}")
            return 1
        print("All in-scope files carry an SPDX header.")
        return 0

    # --fix
    for p in missing:
        p.write_text(insert_header(p.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"  + {p.relative_to(REPO_ROOT)}")
    print(f"Inserted headers into {len(missing)} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
