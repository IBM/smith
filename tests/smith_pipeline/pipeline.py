# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import subprocess
from pathlib import Path

from . import scorecard
from .config import STEPS_BY_NUM, overlay_for
from .console import out
from .runner import Runner
from .services import Services


class Pipeline:
    def __init__(self, root: Path, log_dir: Path, example: str,
                 steps: list[int], runner: Runner, services: Services, *,
                 clean: bool, dry_run: bool) -> None:
        self.root = root
        self.log_dir = log_dir
        self.example = example
        self.steps = steps
        self.runner = runner
        self.services = services
        self.clean = clean
        self.dry_run = dry_run

    def wants(self, num: int) -> bool:
        return num in self.steps

    # -- setup --------------------------------------------------------------
    def resolve_env(self) -> dict[str, str]:
        overlay = overlay_for(self.root, self.example)
        out.info(f"Environment for examples/{self.example}/")
        for key in sorted(overlay):
            out.say(f"  {out.dim}{key}={overlay[key]}{out.off}")
        return overlay

    def clean_artifacts(self) -> None:
        if not self.clean:
            return
        # The cleaner empties assets/policy.rego, so only run it when the policy
        # is about to be regenerated.
        if not self.wants(1):
            out.warn("Skipping clean: step 1 is not selected, so existing "
                     "artifacts are being reused.")
            return

        out.info("Cleaning generated artifacts (references/, ares assets, "
                 "assets/policy.rego)")
        if self.dry_run:
            out.dry("bash scripts/clean.sh")
            return

        script = self.root / "scripts" / "clean.sh"
        with (self.log_dir / "clean.log").open("wb") as fh:
            rc = subprocess.run(
                ["bash", str(script), str(self.root)],
                stdout=fh, stderr=subprocess.STDOUT,
            ).returncode
        if rc == 0:
            out.ok("Cleaned")
        else:
            out.warn("clean.sh reported problems — see logs/clean.log")

    # -- reporting ----------------------------------------------------------
    def show_scorecard(self, header: str) -> scorecard.Scorecard:
        """Print the policy-testing scorecard. Returned for callers that want it."""
        card = scorecard.read(self.root)
        out.hdr(header)
        if card.summary.strip():
            out.block(card.summary)
        else:
            out.warn("No scorecard at references/scorecard/"
                     "scorecard_summary.txt")
        return card

    # -- the workflow -------------------------------------------------------
    def run(self) -> int:
        # Order matters: an SSE example's agent connects to MCP on startup.
        if not self.services.start_mcp(self.example):
            return 1
        if not self.services.start_agent(self.example):
            return 1

        for num in (1, 2, 3, 4, 5, 6, 7, 8, 9):
            if not self.wants(num):
                continue
            result = self.runner.run(STEPS_BY_NUM[num])
            if not result.ok:
                # A failed testing step still leaves a scorecard worth seeing.
                if num in (4, 9):
                    out.warn(f"Step {num} reported an error; inspecting the "
                             "scorecard anyway.")
                else:
                    return 1
            if num == 4:
                self.show_scorecard("Scorecard after step 4")
            elif num == 9:
                self.show_scorecard("Final scorecard")

        return 0

