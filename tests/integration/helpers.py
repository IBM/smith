# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Shared constants and helpers for Smith integration tests.

Kept separate from ``conftest.py`` (which holds the pytest fixtures) so test
modules can import these plainly (``from helpers import ...``); pytest puts the
test directory on ``sys.path``, so no package machinery is needed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
except ImportError:  # dotenv is a dev dep; fall back to the ambient env.
    pass

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE_POLICY = FIXTURES / "policy" / "policy.rego"
FIXTURE_TEST_CASES = FIXTURES / "test_cases"
BASE_URL = os.getenv("BASE_URL") or (str(Path(__file__).resolve().parents[2]) + "/")


def env_str(*parts: str, default: str | None = None) -> str:
    """Resolve ``BASE_URL + os.getenv(part)"""
    resolved = []
    for i, var in enumerate(parts):
        fallback = default if i == len(parts) - 1 else None
        value = os.getenv(var, fallback)
        if value is None:
            raise KeyError(
                f"{var} is not set in .env; integration tests resolve artifact "
                "paths from the same variables the smith CLI uses."
            )
        resolved.append(value)
    return BASE_URL + "".join(resolved)


def env_path(*parts: str, default: str | None = None) -> Path:
    """Resolve ``BASE_URL + os.getenv(part) + ...`` as a ``Path``."""
    return Path(env_str(*parts, default=default))


REAL_POLICY = env_path("POLICY_DIR", "POLICY_PATH")
REFERENCES = Path(BASE_URL + "references")
REAL_TEST_CASES = env_path("TEST_CASE_PATH", default="references/test_cases/")
SCORECARD = env_path("TEST_OUTPUT_DIR", default="references/scorecard/")

EXAMPLE = Path(BASE_URL + "examples/call-for-papers-mcp/")
DECOMP_FILE = env_path("DECOMP_FILE")
FLATTEN_FILE = env_path("FLATTEN_FILE")
VARS_FILE = env_path("VARS_FILE")
GREY_GUIDANCE_FILE = env_path("GREY_GUIDANCE_FILE")
CASE_FILE = env_path("CASE_FILE")
PROMPTFOO_ATTACK_FILE = env_path("ATTACK_FILE_PROMPT")

# --- bypass case generation -------------------------------------------------
BYPASS_REPORT_DIR = env_path("BYPASS_REPORT_DIR", default="references/bypass/")
BYPASS_CASES_FILE = env_path("BYPASS_CASE_FILE", default="references/bypass_cases.json")

SCORECARD_SUMMARY = SCORECARD / os.getenv("TEST_RESULT_PATH", "scorecard_summary.txt")
EXPECTED = {
    # confusion counts (allow-allowed=tn, allow-denied=fp,
    # disallow-denied=tp, disallow-allowed=fn)
    "tn": 30,
    "fp": 5,
    "tp": 70,
    "fn": 10,
    # per-experiment summary numbers
    "allow_total": 35,
    "disallow_total": 80,
    # coverage the OPA `opa test --coverage` run reports for this policy
    "coverage": 86.48648648648648,
    "covered_lines": 64,
    "not_covered_lines": 10,
    # `wc -l` of the fixture policy
    "policy_lines": 153,
}


def env_rel(path, is_dir: bool | None = None) -> str:
    """Express ``path`` the way an .env value does: relative to ``BASE_URL``."""
    target = Path(path).resolve()
    base = Path(BASE_URL).resolve()
    try:
        rel = target.relative_to(base).as_posix()
    except ValueError:
        raise ValueError(
            f"{target} is not under BASE_URL ({base}), so it cannot be expressed "
            "as an .env value. Point BASE_URL in .env at the checkout these "
            "integration tests live in."
        ) from None
    if is_dir is None:
        is_dir = str(path).endswith(("/", os.sep)) or target.is_dir()
    if rel and is_dir:
        rel += "/"
    return rel


def which(binary: str) -> bool:
    return shutil.which(binary) is not None


def run_smith(flag: str, *extra_args: str, timeout: int = 900, env: dict | None = None):
    """Invoke ``smith --flag <flag>`` from the real repo root."""
    return subprocess.run(
        ["smith", "--flag", flag, *extra_args],
        cwd=BASE_URL,
        env=env or dict(os.environ),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len([ln for ln in path.read_text().splitlines() if ln.strip()])


def load_json(path: Path):
    return json.loads(Path(path).read_text())


def parse_scorecard_summary(text: str) -> dict:
    """Parse ``scorecard_summary.txt`` into a structured dict.

    Returns::

        {
          "experiments": [
            {"experiment": <title>, "directory": <dir>,
             "allowed": int, "denied": int, "total": int},
            ...
          ],
          "coverage": float | None,
          "policy_lines": int | None,
        }

    Mirrors the block format written by ``src/smith/policy_testing/score_card.sh``.
    """
    experiments = []
    current: dict = {}
    coverage = None
    covered_lines = None
    not_covered_lines = None
    policy_lines = None
    lines = text.splitlines()
    for i, raw in enumerate(lines):
        line = raw.strip()
        if line.startswith("Experiment:"):
            current = {"experiment": line.split(":", 1)[1].strip()}
        elif line.startswith("Directory:"):
            current["directory"] = line.split(":", 1)[1].strip()
        elif line.startswith("Allowed:"):
            current["allowed"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("Denied:"):
            current["denied"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("Total:"):
            current["total"] = int(line.split(":", 1)[1].strip())
            experiments.append(current)
            current = {}
        elif '"covered_lines":' in line:
            covered_lines = int(line.split(":", 1)[1].strip().rstrip(","))
        elif '"not_covered_lines":' in line:
            not_covered_lines = int(line.split(":", 1)[1].strip().rstrip(","))
        elif '"coverage":' in line:
            coverage = float(line.split(":", 1)[1].strip().rstrip(","))
        elif line.startswith("The line number of current policy is:"):
            # The count is on the following non-empty line.
            for nxt in lines[i + 1 :]:
                if nxt.strip():
                    policy_lines = int(nxt.strip())
                    break
    return {
        "experiments": experiments,
        "coverage": coverage,
        "covered_lines": covered_lines,
        "not_covered_lines": not_covered_lines,
        "policy_lines": policy_lines,
    }
