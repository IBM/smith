# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import subprocess
from pathlib import Path

from . import reports, scorecard
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
            out.err("clean.sh failed — see logs/clean.log")
            raise SystemExit(1)

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

    def validate_scorecard(self, before: dict[Path, int | None]
                           ) -> scorecard.Scorecard | None:
        """Require this testing step to score every case without OPA errors."""
        for path, previous_mtime in before.items():
            if not path.is_file():
                out.err(f"Policy testing did not create {path.name}.")
                return None
            if path.stat().st_mtime_ns == previous_mtime:
                out.err(f"Policy testing did not update {path.name}; refusing "
                        "to use a stale scorecard.")
                return None

        errors_file = scorecard.scorecard_dir(self.root) / "errors.txt"
        if not errors_file.is_file():
            out.err("Policy testing did not create errors.txt.")
            return None
        errors = [line for line in errors_file.read_text(
            encoding="utf-8", errors="replace").splitlines() if line.strip()]
        if errors:
            out.err(f"Policy testing could not score {len(errors)} case(s); "
                    "see references/scorecard/errors.txt.")
            return None

        case_root = self.root / "references" / "test_cases"
        expected = sum(1 for label in ("allow", "disallow")
                       for _ in (case_root / label).rglob("*.json"))
        card = scorecard.read(self.root)
        if expected == 0:
            out.err("No allow/disallow test cases exist to score.")
            return None
        if card.scored != expected:
            out.err(f"Policy testing scored {card.scored} of {expected} "
                    "test cases; see references/scorecard/.")
            return None
        return card

    # -- per-stage evaluation tables ----------------------------------------
    def show_stage_report(self, step_name: str) -> None:
        """Print the evaluation table this stage produces, if it has one.

        The tables come from `smith_evaluation_plan.md`; each is emitted by
        the step whose artifacts it counts, so a run can be transcribed
        without re-deriving anything afterwards.
        """
        if self.dry_run:
            return
        table = {
            "generate test cases": reports.show_suite,
            "translate test cases": reports.show_translation,
            "cross-validate failed test cases": reports.show_cross_validation,
        }.get(step_name)
        if table:
            table(self.root, self.log_dir)

    # -- the workflow -------------------------------------------------------
    def run(self) -> int:
        # Order matters: an SSE example's agent connects to MCP on startup.
        if not self.services.start_mcp(self.example):
            return 1
        if not self.services.start_agent(self.example):
            return 1

        for num in sorted(STEPS_BY_NUM):
            if not self.wants(num):
                continue
            before = {}
            if num in (4, 9):
                directory = scorecard.scorecard_dir(self.root)
                files = (directory / "scorecard_summary.txt",
                         directory / "score_test_failures.txt")
                before = {path: (path.stat().st_mtime_ns if path.is_file()
                                 else None) for path in files}
            step = STEPS_BY_NUM[num]
            result = self.runner.run(step)
            if not result.ok:
                return 1
            # Keyed on the step's name, not its number, so inserting a step
            # cannot silently attach a table to the wrong stage.
            self.show_stage_report(step.name)
            if num == 4:
                if self.validate_scorecard(before) is None:
                    return 1
                self.show_scorecard("Scorecard after step 4")
            elif num == 9:
                if self.validate_scorecard(before) is None:
                    return 1
                card = self.show_scorecard("Final scorecard")
                if card.failures:
                    out.err(f"Final policy testing has {card.failures} "
                            "failing case(s).")
                    return 1

        return 0

