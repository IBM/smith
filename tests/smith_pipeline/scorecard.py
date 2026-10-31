# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
"""Reading the policy-testing scorecard."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

TOTAL_RE = re.compile(r"^Total:\s+(\d+)", re.M)


@dataclass(frozen=True)
class Scorecard:
    scored: int # Number of test cases OPA actually evaluated
    failures: int # Failing cases, or -1 when no failures file exists
    summary: str # Raw scorecard_summary.txt, for display.

    @property
    def ran(self) -> bool:
        return self.failures >= 0

    @property
    def all_passed(self) -> bool:
        return self.failures == 0


def scorecard_dir(root: Path) -> Path:
    return root / "references" / "scorecard"


def read(root: Path) -> Scorecard:
    d = scorecard_dir(root)
    summary_file = d / "scorecard_summary.txt"
    failures_file = d / "score_test_failures.txt"

    summary = ""
    scored = 0
    if summary_file.is_file():
        summary = summary_file.read_text(encoding="utf-8", errors="replace")
        scored = sum(int(n) for n in TOTAL_RE.findall(summary))

    if failures_file.is_file():
        text = failures_file.read_text(encoding="utf-8", errors="replace")
        failures = sum(1 for line in text.splitlines()
                       if line.startswith("[FAIL"))
    else:
        failures = -1

    return Scorecard(scored=scored, failures=failures, summary=summary)
