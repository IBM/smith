#!/usr/bin/env python3
# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
"""Drive the full Smith skill workflow end-to-end for one example agent.

This does the plumbing a human would otherwise do by hand:

  1. pick an example agent (interactive menu, or --example)
  2. repoint .env at that agent (TARGET_AGENT_PATH / GUIDANCE_FILE / ... / MCP_*)
  3. clean generated artifacts from the previous run
  4. start the target agent (+ a standalone MCP server where needed) and OPA
  5. run each workflow step as a `/smith ...` prompt through headless Claude Code
  6. stop what it started

Every LLM step goes through `claude -p` as a /smith prompt, exactly as an
interactive user would type it, so a run exercises the real skill orchestration
rather than calling the CLI stages directly.

`claude` itself is always invoked from <workspace>, because Claude Code resolves
`/smith` against `.claude/skills/` under its own working directory. Everything
else runs against the skill directory.

Usage (from anywhere):
    python3 .claude/skills/smith/tests/run_smith_pipeline.py --help
    python3 .claude/skills/smith/tests/run_smith_pipeline.py         # menu
    python3 .claude/skills/smith/tests/run_smith_pipeline.py -e employee
    python3 .claude/skills/smith/tests/run_smith_pipeline.py -e employee \
        --steps 4-8 --no-clean

See smith_pipeline/__init__.py for the module map.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(Path(__file__).resolve().parents[1])

# Configure only the executable; importing pipeline modules stays env-free.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from smith_pipeline.cli import main  # noqa: E402 — load settings before config imports

if __name__ == "__main__":
    sys.exit(main())
