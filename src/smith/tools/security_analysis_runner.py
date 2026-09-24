# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Run security-analysis phases in isolated agent processes."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Mapping

from smith.tools.guidance_reconciliation import ReconciliationError
from smith.tools.security_analysis_checkpoint import (
    _is_emitted_verdict,
    checkpoint_from_environment,
    prepare_from_environment,
)

PHASES = ("A", "B", "C", "D")
PHASE_GUIDES = {
    "A": "architecture_analysis.md",
    "B": "policy_guidance_questionnaire.md",
    "C": "threat_model.md",
    "D": "enforcement_mapping.md",
}
PHASE_ARTIFACTS = {
    "A": "architecture.json",
    "B": "policy_guidance_questionnaire.json",
    "C": "threat_model.json",
    "D": "owasp_policy_guidelines.json",
}
PHASE_TIMEOUT_SECONDS = 1800
DEFAULT_AGENT_COMMAND = (
    "claude",
    "--print",
    "--output-format",
    "text",
    "--no-session-persistence",
    "--safe-mode",
    "--tools",
    "Read,Glob,Grep,Edit,Write,Bash",
    "--allowedTools",
    "Read,Glob,Grep,Edit,Write,Bash(rg *)",
    "--permission-mode",
    "acceptEdits",
    "--permission-prompts",
    "none",
)


def _resolve(base: Path, value: str | None, name: str) -> Path:
    if not value:
        raise ReconciliationError(f"{name} is not configured")
    path = Path(value)
    return path if path.is_absolute() else base / path


def _runner_command() -> list[str]:
    command = list(DEFAULT_AGENT_COMMAND)
    executable = command[0]
    if not (Path(executable).is_file() or shutil.which(executable)):
        raise ReconciliationError(
            f"security-analysis agent executable is unavailable: {executable}"
        )
    return command


def _phase_prompt(
    phase: str,
    workflow: Path,
    guide: Path,
    target: Path,
    analysis_dir: Path,
    artifact: Path,
    guidance: Path | None,
    system_vars: Path | None,
) -> str:
    optional_addendum = (
        f" Phase D may also replace {guidance.with_name('guidance_updated.txt')} "
        "when Novel/Additive guidance remains. If none remains, leave deletion "
        "to the coordinator."
        if phase == "D" and guidance is not None
        else ""
    )
    predecessor = (
        "No predecessor state is required for Phase A."
        if phase == "A"
        else f"Read predecessor state only from {analysis_dir / 'analysis_state.json'}."
    )
    return f"""You are the fresh, isolated worker for security-analysis Phase {phase}.
This process has no prior phase conversation. Complete only this phase.

Read these instructions completely:
- Shared workflow: {workflow}
- Phase guide: {guide}

Resolved inputs:
- Target: {target}
- Phase JSON to complete: {artifact}
- Guidance: {guidance if guidance is not None else "ABSENT"}
- System variables: {system_vars if system_vars is not None else "ABSENT"}
- Tool definitions: {target / "smith" / "tool_definitions.json"}

The coordinator has already prepared the phase JSON. Treat any existing values
as an unvalidated draft and refresh them from the permitted sources. {predecessor}
Do not run a Smith prepare, checkpoint, merge, or policy-creation command.
Modify only {artifact}.{optional_addendum}
Set the phase status and handoff status to PASS only when the phase guide's
completion requirements are satisfied. Finish after saving the structured JSON.
"""


def _remove_unneeded_addendum(analysis_dir: Path, guidance: Path | None) -> None:
    if guidance is None:
        return
    phase_path = analysis_dir / PHASE_ARTIFACTS["D"]
    try:
        state = json.loads(phase_path.read_text(encoding="utf-8"))
        rows = state["tables"]["Candidate Reconciliation"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return
    emitted = any(_is_emitted_verdict(str(row.get("Verdict", ""))) for row in rows)
    if not emitted:
        guidance.with_name("guidance_updated.txt").unlink(missing_ok=True)


def run_isolated_analysis(
    start_phase: str = "A",
    environment: Mapping[str, str] | None = None,
) -> str:
    """Run phases from ``start_phase`` through D in fresh agent processes."""
    env = dict(os.environ if environment is None else environment)
    start_phase = start_phase.upper()
    if start_phase not in PHASES:
        raise ReconciliationError("start phase must be one of A, B, C, or D")

    base = Path(env.get("BASE_URL") or ".").resolve()
    target = _resolve(base, env.get("TARGET_AGENT_PATH"), "TARGET_AGENT_PATH")
    guidance_value = env.get("GUIDANCE_FILE")
    guidance = (
        _resolve(base, guidance_value, "GUIDANCE_FILE") if guidance_value else None
    )
    system_value = env.get("SYSTEM_VAR_FILE")
    system_vars = (
        _resolve(base, system_value, "SYSTEM_VAR_FILE") if system_value else None
    )
    workflow = (
        base / "opa_policy/guidelines-security-analysis/guidelines-security-analysis.md"
    )
    steps_dir = workflow.parent / "steps"
    analysis_dir = target / "smith" / "guidelines-security-analysis"
    for required in (workflow, steps_dir):
        if not required.exists():
            raise ReconciliationError(
                f"security-analysis workflow path is missing: {required}"
            )

    command = _runner_command()

    selected = PHASES[PHASES.index(start_phase) :]
    completed: list[str] = []
    for phase in selected:
        guide = steps_dir / PHASE_GUIDES[phase]
        if not guide.is_file():
            raise ReconciliationError(f"phase {phase} guide is missing: {guide}")
        prepare_from_environment(phase, env)
        artifact = analysis_dir / PHASE_ARTIFACTS[phase]
        prompt = _phase_prompt(
            phase,
            workflow,
            guide,
            target,
            analysis_dir,
            artifact,
            guidance,
            system_vars,
        )
        process_env = dict(os.environ)
        process_env.update(env)
        process_env["SMITH_SECURITY_ANALYSIS_PHASE"] = phase
        print(f"Security analysis phase {phase}: starting isolated agent")
        try:
            result = subprocess.run(
                command,
                cwd=base,
                env=process_env,
                input=prompt,
                text=True,
                check=False,
                timeout=PHASE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise ReconciliationError(
                f"phase {phase} isolated agent timed out after "
                f"{PHASE_TIMEOUT_SECONDS}s; resume with "
                f"--flag security_analysis_run --phase {phase}"
            ) from exc
        except OSError as exc:
            raise ReconciliationError(
                f"phase {phase} isolated agent could not start: {exc}"
            ) from exc
        if result.returncode != 0:
            raise ReconciliationError(
                f"phase {phase} isolated agent exited with {result.returncode}; "
                f"resume with --flag security_analysis_run --phase {phase}"
            )
        if phase == "D":
            _remove_unneeded_addendum(analysis_dir, guidance)
        try:
            checkpoint_from_environment(phase, env)
        except ReconciliationError as exc:
            raise ReconciliationError(
                f"phase {phase} checkpoint failed: {exc}; resume with "
                f"--flag security_analysis_run --phase {phase}"
            ) from exc
        completed.append(phase)
        print(f"Security analysis phase {phase}: PASS")

    return "Security analysis isolated run: PASS (" + ", ".join(completed) + ")"


def run_from_environment(
    start_phase: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> str:
    return run_isolated_analysis(start_phase or "A", environment)
