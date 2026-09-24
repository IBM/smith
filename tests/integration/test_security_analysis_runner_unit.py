# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Offline tests for isolated security-analysis phase orchestration."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from smith.tools.guidance_reconciliation import ReconciliationError
from smith.tools import security_analysis_runner as runner

pytestmark = pytest.mark.unit


def test_default_runner_is_non_persistent_and_tool_limited(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(runner.shutil, "which", lambda _name: "/usr/bin/claude")

    command = runner._runner_command()

    assert command[0] == "claude"
    assert "--no-session-persistence" in command
    assert "--safe-mode" in command
    assert "Read,Glob,Grep,Edit,Write,Bash(rg *)" in command
    assert "--resume" not in command
    assert "--continue" not in command


def _environment(root: Path) -> dict[str, str]:
    workflow = root / "opa_policy/guidelines-security-analysis"
    steps = workflow / "steps"
    steps.mkdir(parents=True)
    (workflow / "guidelines-security-analysis.md").write_text("shared")
    for guide in runner.PHASE_GUIDES.values():
        (steps / guide).write_text("phase")
    return {
        "BASE_URL": str(root),
        "TARGET_AGENT_PATH": "target",
        "GUIDANCE_FILE": "target/smith/guidance.txt",
        "SYSTEM_VAR_FILE": "target/smith/system_vars.json",
    }


def test_runner_launches_one_fresh_process_and_checkpoint_per_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    environment = _environment(tmp_path)
    events: list[tuple[str, str]] = []
    prompts: list[str] = []

    monkeypatch.setattr(runner, "_runner_command", lambda: ["fake-agent"])
    monkeypatch.setattr(
        runner,
        "prepare_from_environment",
        lambda phase, _env: events.append(("prepare", phase)),
    )
    monkeypatch.setattr(
        runner,
        "checkpoint_from_environment",
        lambda phase, _env: events.append(("checkpoint", phase)),
    )

    def fake_run(command, **kwargs):
        phase = kwargs["env"]["SMITH_SECURITY_ANALYSIS_PHASE"]
        events.append(("agent", phase))
        prompts.append(kwargs["input"])
        assert command == ["fake-agent"]
        assert kwargs["check"] is False
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.run_isolated_analysis(environment=environment)

    assert result == "Security analysis isolated run: PASS (A, B, C, D)"
    assert events == [
        ("prepare", "A"),
        ("agent", "A"),
        ("checkpoint", "A"),
        ("prepare", "B"),
        ("agent", "B"),
        ("checkpoint", "B"),
        ("prepare", "C"),
        ("agent", "C"),
        ("checkpoint", "C"),
        ("prepare", "D"),
        ("agent", "D"),
        ("checkpoint", "D"),
    ]
    assert [f"Phase {phase}" in prompt for phase, prompt in zip("ABCD", prompts)] == [
        True,
        True,
        True,
        True,
    ]
    assert all("no prior phase conversation" in prompt for prompt in prompts)


def test_runner_resumes_at_requested_phase_and_stops_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    environment = _environment(tmp_path)
    phases: list[str] = []

    monkeypatch.setattr(runner, "_runner_command", lambda: ["fake-agent"])
    monkeypatch.setattr(runner, "prepare_from_environment", lambda *_args: None)
    monkeypatch.setattr(runner, "checkpoint_from_environment", lambda *_args: None)

    def fake_run(command, **kwargs):
        phase = kwargs["env"]["SMITH_SECURITY_ANALYSIS_PHASE"]
        phases.append(phase)
        return subprocess.CompletedProcess(command, 7 if phase == "C" else 0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    with pytest.raises(ReconciliationError, match=r"resume .* --phase C"):
        runner.run_isolated_analysis("C", environment)

    assert phases == ["C"]


def test_runner_reports_checkpoint_phase_for_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    environment = _environment(tmp_path)

    monkeypatch.setattr(runner, "_runner_command", lambda: ["fake-agent"])
    monkeypatch.setattr(runner, "prepare_from_environment", lambda *_args: None)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0),
    )

    def fail_checkpoint(phase, _environment):
        raise ReconciliationError(f"invalid {phase}")

    monkeypatch.setattr(runner, "checkpoint_from_environment", fail_checkpoint)

    with pytest.raises(
        ReconciliationError, match=r"phase B checkpoint failed.*--phase B"
    ):
        runner.run_isolated_analysis("B", environment)


def test_runner_removes_stale_addendum_when_phase_d_emits_nothing(tmp_path: Path):
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    (analysis_dir / "owasp_policy_guidelines.json").write_text(
        json.dumps(
            {
                "tables": {
                    "Candidate Reconciliation": [
                        {"Candidate ID": "C1", "Verdict": "Covered"}
                    ]
                }
            }
        )
    )
    guidance = tmp_path / "guidance.txt"
    guidance.write_text("Existing guidance")
    addendum = tmp_path / "guidance_updated.txt"
    addendum.write_text("Stale proposal")

    runner._remove_unneeded_addendum(analysis_dir, guidance)

    assert not addendum.exists()
