# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Offline regressions for the evaluation runner.

FUNCTIONS UNDER TEST
--------------------
Pipeline.run                    — failures stop dependent steps and reporting
Pipeline.run_flags              — selected environment and subprocess failures
Pipeline.measure_*              — fresh reports and complete scorecards
reports.read_lint/read_duplication — failed tools are absent measurements
Runner.report_usage             — sum independent, resumed and carried usage

Claude and CLI subprocesses are the faked boundaries. Filesystem checks,
scorecard parsing and pipeline decisions run for real under unit_env.root.
The policy-generation guide's deny precedence is tested against real OPA in
test_smith_pipeline_integration.py.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
from types import SimpleNamespace

import pytest

from smith_pipeline import reports
from smith_pipeline.config import STEPS_BY_NUM, overlay_for
from smith_pipeline.pipeline import MeasurementError, Pipeline
from smith_pipeline.runner import Runner, StepResult, read_usage_csv

pytestmark = pytest.mark.unit


@pytest.fixture
def pipeline(unit_env):
    root = unit_env.root
    log_dir = root / "logs"
    log_dir.mkdir()
    runner = Runner(
        root,
        log_dir,
        permission_mode="bypassPermissions",
        model=None,
        timeout=30,
        trace=True,
        yolo=False,
        dry_run=False,
        follow=False,
        overlay=overlay_for(root, "employee"),
    )
    services = SimpleNamespace(start_mcp=lambda _: True, start_agent=lambda _: True)
    return Pipeline(
        root, log_dir, "employee", [1, 2], runner, services, clean=False, dry_run=False
    )


def write_report(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_scorecard(root, *, errors="", total=2):
    directory = root / "references/scorecard"
    write_report(
        directory / "scorecard_summary.txt",
        (
            "Experiment: Test cases that should result in an allow decision\n"
            "Allowed: 1\nDenied: 0\nTotal: 1\n"
            "Experiment: Test cases that should result in a deny decision\n"
            f"Allowed: 0\nDenied: {total - 1}\nTotal: {total - 1}\n"
        ),
    )
    write_report(directory / "score_test_failures.txt", "")
    write_report(directory / "errors.txt", errors)


def write_cases(root):
    for label in ("allow", "disallow"):
        write_report(root / "references/test_cases" / label / "case.json", "{}")


def test_a_failed_step_stops_before_dependent_steps_and_reports(pipeline, monkeypatch):
    called = []

    def run(step):
        called.append(step.num)
        return StepResult(False, 1, pipeline.log_dir / "failed.log", reason="exited 1")

    monkeypatch.setattr(pipeline.runner, "run", run)
    monkeypatch.setattr(
        pipeline, "_report", lambda *_: pytest.fail("reported a failed step")
    )
    assert pipeline.run() == 1
    assert called == [1]


def test_successful_steps_continue_and_report(pipeline, monkeypatch):
    called = []

    def run(step):
        called.append(step.num)
        log = pipeline.log_dir / f"step{step.num}.log"
        log.write_text("finished")
        return StepResult(True, 1, log)

    monkeypatch.setattr(pipeline.runner, "run", run)
    assert pipeline.run() == 0
    assert called == [1, 2]


def test_measurement_commands_receive_the_selected_example(pipeline, monkeypatch):
    monkeypatch.setenv("SYSTEM_VAR_FILE", "examples/inactive/smith/system_vars.json")
    calls = []

    def run(argv, **kwargs):
        calls.append(kwargs)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr("smith_pipeline.pipeline.subprocess.run", run)
    pipeline.run_flags("before", "regal_suggestion")
    assert (
        calls[0]["env"]["SYSTEM_VAR_FILE"] == "examples/employee/smith/system_vars.json"
    )
    assert calls[0]["env"]["PATH"] == os.environ["PATH"]
    assert calls[0]["timeout"] == 30


def test_a_failed_measurement_stops_instead_of_reading_old_reports(
    pipeline, monkeypatch
):
    write_report(
        pipeline.root / "assets/opa/outputs/regal_suggestion.txt", "Rule: old\n"
    )
    monkeypatch.setattr(
        "smith_pipeline.pipeline.subprocess.run",
        lambda argv, **_: subprocess.CompletedProcess(argv, 1),
    )
    with pytest.raises(MeasurementError, match="exit 1"):
        pipeline.measure_lint("after")


@pytest.mark.parametrize("existing", [False, True])
def test_an_exit_zero_measurement_must_create_or_update_its_report(
    pipeline, monkeypatch, existing
):
    if existing:
        write_report(
            pipeline.root / "assets/opa/outputs/regal_suggestion.txt", "Rule: old\n"
        )
    monkeypatch.setattr(
        "smith_pipeline.pipeline.subprocess.run",
        lambda argv, **_: subprocess.CompletedProcess(argv, 0),
    )
    with pytest.raises(MeasurementError, match="did not update"):
        pipeline.measure_lint("after")


@pytest.mark.parametrize(
    "message",
    [
        "regal lint could not be run: binary missing",
        "regal lint failed (exit 127). Is Regal installed?",
    ],
)
def test_regal_launch_failures_are_not_clean_measurements(pipeline, message):
    path = pipeline.root / "regal.txt"
    write_report(path, message)
    assert not reports.read_lint(path).present


def test_an_empty_regal_report_is_a_valid_clean_measurement(pipeline):
    path = pipeline.root / "regal.txt"
    write_report(path, "")
    result = reports.read_lint(path)
    assert result.present and result.violations == 0


def test_a_failed_regal_tool_cannot_be_reported_even_when_cli_exits_zero(
    pipeline, monkeypatch
):
    def run(argv, **_):
        write_report(
            pipeline.root / "assets/opa/outputs/regal_suggestion.txt",
            "regal lint could not be run: binary missing",
        )
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr("smith_pipeline.pipeline.subprocess.run", run)
    with pytest.raises(MeasurementError, match="Regal did not run"):
        pipeline.measure_lint("before")


@pytest.mark.parametrize("kind", ["stale", "errors", "incomplete"])
def test_policy_measurements_reject_invalid_scorecards(pipeline, monkeypatch, kind):
    write_cases(pipeline.root)
    if kind == "stale":
        write_scorecard(pipeline.root)

    def run(argv, **_):
        if kind != "stale":
            write_scorecard(
                pipeline.root,
                errors="case.json\n" if kind == "errors" else "",
                total=1 if kind == "incomplete" else 2,
            )
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr("smith_pipeline.pipeline.subprocess.run", run)
    with pytest.raises(MeasurementError, match="Incomplete policy score"):
        pipeline.measure_policy_score("after")


def test_a_fresh_complete_measurement_reports_real_findings(pipeline, monkeypatch):
    write_cases(pipeline.root)
    calls = []

    def run(argv, **_):
        calls.append(argv[-1])
        if argv[-1] == "regal_suggestion":
            write_report(
                pipeline.root / "assets/opa/outputs/regal_suggestion.txt",
                "Rule: unused-rule\nCategory: bugs\n",
            )
        else:
            write_scorecard(pipeline.root)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr("smith_pipeline.pipeline.subprocess.run", run)
    lint, score = pipeline.measure_lint("after")
    assert calls == ["regal_suggestion", "policy_testing"]
    assert lint.violations == 1 and score.scored == 2
    assert score.tp == 1 and score.tn == 1


def test_malformed_duplication_json_is_not_rescued_by_a_graph_report(pipeline):
    outputs = pipeline.root / "assets/opa/outputs"
    write_report(outputs / "linting_feedback_de-duplication.json", "{")
    write_report(outputs / "graph_suggestion.txt", "subgraph 1:\nnode:\n['unused']")
    assert not reports.read_duplication(pipeline.root).present


@pytest.mark.parametrize("phase", ["before", "after"])
def test_measurement_failure_causes_a_nonzero_pipeline_exit(
    pipeline, monkeypatch, phase
):
    pipeline.steps = [7]
    calls = []

    def measure(when):
        if when == phase:
            raise MeasurementError("measurement failed")
        return reports.LintCount(present=True), reports.PolicyScore(present=True)

    def run(step):
        calls.append(step.num)
        log = pipeline.log_dir / "step7.log"
        log.write_text("finished")
        return StepResult(True, 1, log)

    monkeypatch.setattr(pipeline, "measure_lint", measure)
    monkeypatch.setattr(pipeline.runner, "run", run)
    assert pipeline.run() == 1
    assert calls == ([] if phase == "before" else [7])
    assert not (pipeline.log_dir / "regal_effect.csv").exists()


@pytest.mark.parametrize("chain", [False, True])
def test_costs_sum_across_independent_and_resumed_invocations(pipeline, capsys, chain):
    runner = pipeline.runner
    runner.chain = chain
    first_trace = runner.log_dir / "one.trace.jsonl"
    second_trace = runner.log_dir / "two.trace.jsonl"
    write_report(first_trace, json.dumps({"type": "result", "session_id": "first"}))
    write_report(
        second_trace,
        json.dumps({"type": "result", "session_id": "first" if chain else "second"}),
    )
    second_cost = 3.0 if chain else 2.0
    runner.ledger = [
        (
            STEPS_BY_NUM[1],
            StepResult(
                True,
                1,
                runner.log_dir / "one.log",
                trace=first_trace,
                usage={"cost_usd": 1.0, "input_tokens": 10},
            ),
        ),
        (
            STEPS_BY_NUM[2],
            StepResult(
                True,
                1,
                runner.log_dir / "two.log",
                trace=second_trace,
                usage={"cost_usd": second_cost, "input_tokens": 20},
            ),
        ),
    ]
    runner.report_usage()
    total = next(
        line
        for line in capsys.readouterr().out.splitlines()
        if line.strip().startswith("total ")
    )
    assert "$3.0000" in total
    with (runner.log_dir / "usage.csv").open() as file:
        rows = list(csv.DictReader(file))
    assert [float(row["cost_usd"]) for row in rows] == [1.0, second_cost]
    assert [row["session_id"] for row in rows] == [
        "first",
        "first" if chain else "second",
    ]


@pytest.mark.parametrize("resumed", [False, True])
def test_carried_costs_count_each_session_once(pipeline, capsys, resumed):
    runner = pipeline.runner
    trace = runner.log_dir / "two.trace.jsonl"
    write_report(
        trace,
        json.dumps({"type": "result", "session_id": "earlier" if resumed else "new"}),
    )
    runner.carried = [
        {
            "step": "1",
            "name": "earlier",
            "input_tokens": 10,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "total_tokens": 10,
            "turns": 1,
            "seconds": 1,
            "cost_usd": 1.0,
            "ok": 1,
            "session_id": "earlier",
        }
    ]
    runner.ledger = [
        (
            STEPS_BY_NUM[2],
            StepResult(
                True,
                1,
                runner.log_dir / "two.log",
                trace=trace,
                usage={"cost_usd": 3.0 if resumed else 2.0, "input_tokens": 20},
            ),
        )
    ]
    runner.report_usage()
    total = next(
        line
        for line in capsys.readouterr().out.splitlines()
        if line.strip().startswith("total (cumulative)")
    )
    assert "$3.0000" in total


def test_legacy_usage_csv_recovers_session_ids_from_sibling_traces(pipeline):
    path = pipeline.log_dir / "legacy.csv"
    write_report(path, "step,name,cost_usd\n1,create,1\n2,generate,3\n")
    for step in (1, 2):
        write_report(
            pipeline.log_dir / f"step{step}-example.trace.jsonl",
            json.dumps({"type": "result", "session_id": "shared"}),
        )
    rows = read_usage_csv(path)
    assert [row["session_id"] for row in rows] == ["shared", "shared"]
