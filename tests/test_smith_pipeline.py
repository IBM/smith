# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the evaluation pipeline runner (tests/smith_pipeline/)."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

# The pipeline package lives beside this file and is not installed.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from smith_pipeline import scorecard  
from smith_pipeline.cli import ( 
    parse_steps,
    previous_runs,
    resolve_carry,
    resolve_resume,
)
from smith_pipeline.config import STEPS, STEPS_BY_NUM, Step  
from smith_pipeline.runner import (  
    Runner,
    StepResult,
    read_usage_csv,
)
from smith_pipeline.trace import (  
    live_line,
    render,
    session_id,
    usage_totals,
)

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def make_runner(tmp_path: Path, **kw) -> Runner:
    """A Runner with the defaults a real run uses, overridable per test."""
    opts = dict(permission_mode="bypassPermissions", model=None, timeout=60,
                trace=True, yolo=False, dry_run=False, follow=False)
    opts.update(kw)
    return Runner(tmp_path, tmp_path, **opts)


def result_event(*, cost=0.5, turns=4, inp=100, out=200, cread=1000,
                 ccreate=500, sid="sess-1") -> str:
    """One `result` NDJSON event, shaped like Claude Code's stream-json."""
    return json.dumps({
        "type": "result",
        "session_id": sid,
        "num_turns": turns,
        "total_cost_usd": cost,
        "usage": {
            "input_tokens": inp,
            "output_tokens": out,
            "cache_read_input_tokens": cread,
            "cache_creation_input_tokens": ccreate,
        },
    })


def write_trace(path: Path, *events: str) -> Path:
    path.write_text("\n".join(events) + "\n", encoding="utf-8")
    return path


USAGE_HEADER = ("step,name,input_tokens,output_tokens,cache_read_tokens,"
                "cache_creation_tokens,total_tokens,turns,cost_usd,seconds,ok")


# --------------------------------------------------------------------------
# step selection
# --------------------------------------------------------------------------
class TestParseSteps:
    def test_default_is_every_step_in_order(self):
        assert parse_steps(None) == [s.num for s in STEPS]

    @pytest.mark.parametrize("spec,expected", [
        ("1,2,3", [1, 2, 3]),
        ("4-8", [4, 5, 6, 7, 8]),
        ("5", [5]),
        (" 1 , 2 ", [1, 2]),          # whitespace tolerated
        ("3,1,2", [1, 2, 3]),         # reordered into pipeline order
        ("2,2,2", [2]),               # de-duplicated
        ("1,4-6,9", [1, 4, 5, 6, 9]), # mixed list and range
    ])
    def test_accepted_specs(self, spec, expected):
        assert parse_steps(spec) == expected

    @pytest.mark.parametrize("spec", ["abc", "1-", "-3", "1,,x", "2.5"])
    def test_unparseable_spec_exits_2(self, spec):
        with pytest.raises(SystemExit) as exc:
            parse_steps(spec)
        assert exc.value.code == 2

    @pytest.mark.parametrize("spec", ["0", "99", "1,42"])
    def test_out_of_range_step_exits_2(self, spec):
        with pytest.raises(SystemExit) as exc:
            parse_steps(spec)
        assert exc.value.code == 2

    def test_one_past_the_last_step_is_rejected(self):
        """Derived from STEPS so adding a step does not turn this into a
        test of a now-valid number."""
        with pytest.raises(SystemExit) as exc:
            parse_steps(str(len(STEPS) + 1))
        assert exc.value.code == 2

    def test_backwards_range_selects_nothing(self):
        """A reversed range yields no steps, so the run would do nothing."""
        assert parse_steps("9-4") == []


# --------------------------------------------------------------------------
# command construction
# --------------------------------------------------------------------------
class TestBuildCommand:
    def test_core_flags(self, tmp_path):
        cmd = make_runner(tmp_path).build_command("hello")
        assert cmd[:3] == ["claude", "-p", "hello"]
        assert "--permission-mode" in cmd
        assert cmd[cmd.index("--add-dir") + 1] == str(tmp_path)

    def test_tracing_requests_the_event_stream(self, tmp_path):
        cmd = make_runner(tmp_path, trace=True).build_command("p")
        assert cmd[cmd.index("--output-format") + 1] == "stream-json"
        assert "--verbose" in cmd

    def test_no_trace_omits_stream_flags(self, tmp_path):
        cmd = make_runner(tmp_path, trace=False).build_command("p")
        assert "--output-format" not in cmd

    def test_bypass_mode_sends_no_allowlist(self, tmp_path):
        """An allowlist on top of bypassPermissions is redundant."""
        cmd = make_runner(tmp_path).build_command("p")
        assert "--allowedTools" not in cmd

    def test_restrictive_mode_sends_an_allowlist(self, tmp_path):
        cmd = make_runner(tmp_path, permission_mode="acceptEdits") \
            .build_command("p")
        assert "--allowedTools" in cmd

    def test_yolo_skips_permissions_and_allowlist(self, tmp_path):
        cmd = make_runner(tmp_path, permission_mode="acceptEdits", yolo=True) \
            .build_command("p")
        assert "--dangerously-skip-permissions" in cmd
        assert "--allowedTools" not in cmd

    def test_model_passed_through(self, tmp_path):
        cmd = make_runner(tmp_path, model="haiku").build_command("p")
        assert cmd[cmd.index("--model") + 1] == "haiku"

    def test_autorun_approval_is_appended_to_every_prompt(self, tmp_path):
        """SKILL.md makes the agent ask before editing the policy; headless
        nobody can answer, so each prompt carries approval up front."""
        runner = make_runner(tmp_path)
        full = runner.full_prompt(STEPS_BY_NUM[1])
        assert full.startswith(STEPS_BY_NUM[1].prompt)
        assert "explicit approval" in full
        assert str(tmp_path) in full  # skill root is substituted in


class TestSessionResumption:
    def test_no_session_means_no_resume_flag(self, tmp_path):
        assert "--resume" not in make_runner(tmp_path).build_command("p")

    def test_chained_session_resumes(self, tmp_path):
        runner = make_runner(tmp_path, chain=True)
        runner.session = "abc"
        cmd = runner.build_command("p")
        assert cmd[cmd.index("--resume") + 1] == "abc"

    def test_explicit_resume_survives_no_chain(self, tmp_path):
        """--resume names a session deliberately, so --no-chain must not
        discard it; only the automatic step-to-step threading is off."""
        runner = make_runner(tmp_path, chain=False, resume="xyz")
        cmd = runner.build_command("p")
        assert cmd[cmd.index("--resume") + 1] == "xyz"

    def test_no_chain_without_resume_does_not_resume(self, tmp_path):
        runner = make_runner(tmp_path, chain=False)
        runner.session = "leaked-from-somewhere"
        assert "--resume" not in runner.build_command("p")


# --------------------------------------------------------------------------
# resolving --resume last / --carry last
# --------------------------------------------------------------------------
class TestResolveFromPreviousRuns:
    @staticmethod
    def _run_dir(root: Path, name: str, *, sid=None, usage=None, age=0.0):
        d = root / "logs" / name
        d.mkdir(parents=True)
        if sid:
            write_trace(d / "step1-x.trace.jsonl", result_event(sid=sid))
        if usage:
            (d / "usage.csv").write_text(usage, encoding="utf-8")
        if age:
            stamp = time.time() - age
            import os
            os.utime(d, (stamp, stamp))
        return d

    def test_newest_run_wins_even_with_a_non_timestamp_name(self, tmp_path):
        """Run directories are usually timestamps but need not be; ordering
        must be by mtime, or a hand-named directory sorts ahead of every
        timestamp and is wrongly picked as "last"."""
        self._run_dir(tmp_path, "20260101-000000", sid="old", age=9000)
        self._run_dir(tmp_path, "zzz_hand_named", sid="misleading", age=6000)
        self._run_dir(tmp_path, "20260102-000000", sid="newest", age=10)
        this = self._run_dir(tmp_path, "current")

        assert [d.name for d in previous_runs(tmp_path, before=this)][0] \
            == "20260102-000000"
        assert resolve_resume(tmp_path, "last", this) == "newest"

    def test_literal_session_id_passes_through_untouched(self, tmp_path):
        this = self._run_dir(tmp_path, "current")
        assert resolve_resume(tmp_path, "literal-id", this) == "literal-id"

    def test_resume_last_falls_back_when_no_session_exists(self, tmp_path):
        this = self._run_dir(tmp_path, "current")
        self._run_dir(tmp_path, "no_trace_run", age=100)
        assert resolve_resume(tmp_path, "last", this) is None

    def test_resume_last_skips_runs_whose_trace_has_no_session(self, tmp_path):
        """A step killed before emitting a result leaves a trace with no id;
        resolution must keep looking rather than give up."""
        empty = self._run_dir(tmp_path, "20260103-000000", age=10)
        write_trace(empty / "step1-x.trace.jsonl",
                    json.dumps({"type": "assistant"}))
        self._run_dir(tmp_path, "20260101-000000", sid="older", age=5000)
        this = self._run_dir(tmp_path, "current")
        assert resolve_resume(tmp_path, "last", this) == "older"

    def test_this_run_is_never_its_own_predecessor(self, tmp_path):
        this = self._run_dir(tmp_path, "current", sid="self")
        assert resolve_resume(tmp_path, "last", this) is None

    def test_carry_last_finds_the_newest_usage_csv(self, tmp_path):
        self._run_dir(tmp_path, "20260101-000000", usage=USAGE_HEADER, age=900)
        newest = self._run_dir(tmp_path, "20260102-000000",
                               usage=USAGE_HEADER, age=10)
        this = self._run_dir(tmp_path, "current")
        assert resolve_carry(tmp_path, "last", this) == newest / "usage.csv"

    def test_carry_accepts_a_directory(self, tmp_path):
        d = self._run_dir(tmp_path, "20260101-000000", usage=USAGE_HEADER)
        this = self._run_dir(tmp_path, "current")
        assert resolve_carry(tmp_path, str(d), this) == d / "usage.csv"

    def test_carry_accepts_a_file(self, tmp_path):
        d = self._run_dir(tmp_path, "20260101-000000", usage=USAGE_HEADER)
        this = self._run_dir(tmp_path, "current")
        csv = d / "usage.csv"
        assert resolve_carry(tmp_path, str(csv), this) == csv

    def test_carry_missing_file_returns_none(self, tmp_path):
        this = self._run_dir(tmp_path, "current")
        assert resolve_carry(tmp_path, str(tmp_path / "nope"), this) is None

    def test_no_logs_directory_is_not_an_error(self, tmp_path):
        assert previous_runs(tmp_path) == []
        assert resolve_resume(tmp_path, "last", tmp_path / "x") is None


# --------------------------------------------------------------------------
# trace parsing
# --------------------------------------------------------------------------
class TestUsageTotals:
    def test_reads_every_token_class(self, tmp_path):
        t = write_trace(tmp_path / "t.jsonl", result_event())
        u = usage_totals(t)
        assert u["input_tokens"] == 100
        assert u["output_tokens"] == 200
        assert u["cache_read_input_tokens"] == 1000
        assert u["cache_creation_input_tokens"] == 500
        assert u["turns"] == 4
        assert u["cost_usd"] == 0.5

    def test_missing_file_yields_no_totals(self, tmp_path):
        assert usage_totals(tmp_path / "absent.jsonl") == {}

    def test_non_json_lines_are_skipped(self, tmp_path):
        t = write_trace(tmp_path / "t.jsonl",
                        "a startup warning on stderr", result_event())
        assert usage_totals(t)["turns"] == 4

    def test_trace_without_a_result_event_yields_no_totals(self, tmp_path):
        t = write_trace(tmp_path / "t.jsonl", json.dumps({"type": "assistant"}))
        assert usage_totals(t) == {}


class TestSessionId:
    def test_prefers_the_result_event(self, tmp_path):
        t = write_trace(
            tmp_path / "t.jsonl",
            json.dumps({"type": "assistant", "session_id": "early"}),
            result_event(sid="final"),
        )
        assert session_id(t) == "final"

    def test_falls_back_to_any_event_carrying_one(self, tmp_path):
        """A step killed before its result event can still be continued."""
        t = write_trace(tmp_path / "t.jsonl",
                        json.dumps({"type": "assistant", "session_id": "only"}))
        assert session_id(t) == "only"

    def test_absent_when_no_event_has_one(self, tmp_path):
        t = write_trace(tmp_path / "t.jsonl", json.dumps({"type": "assistant"}))
        assert session_id(t) is None


class TestLiveLine:
    def test_tool_call_shows_name_and_detail(self):
        ev = json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash",
             "input": {"command": "smith --flag policy_testing"}}]}})
        assert live_line(ev) == "Bash: smith --flag policy_testing"

    def test_assistant_text_is_shown(self):
        ev = json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Running the tests."}]}})
        assert live_line(ev) == "Running the tests."

    def test_tool_error_is_flagged(self):
        ev = json.dumps({"type": "user", "message": {"content": [
            {"type": "tool_result", "is_error": True,
             "content": [{"text": "opa: connection refused"}]}]}})
        assert live_line(ev).startswith("error: ")

    def test_result_event_summarises(self):
        line = live_line(result_event(cost=0.25, turns=7))
        assert "done" in line and "turns=7" in line

    @pytest.mark.parametrize("raw", [
        "",
        "   ",
        "not json",
        json.dumps({"type": "content_block_delta", "delta": {"text": "x"}}),
        json.dumps({"type": "message_start"}),
        json.dumps([1, 2, 3]),            # JSON, but not an object
    ])
    def test_noise_produces_no_line(self, raw):
        """Partial deltas repeat text the completed message carries, and a
        malformed line must never break a running step."""
        assert live_line(raw) == ""


class TestRender:
    def test_interleaves_prose_tool_calls_and_results(self):
        text = render(raw="\n".join([
            json.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Writing the policy."},
                {"type": "tool_use", "name": "Write",
                 "input": {"file_path": "/p.rego"}}]}}),
            json.dumps({"type": "user", "message": {"content": [
                {"type": "tool_result", "content": [{"text": "ok"}]}]}}),
            result_event(),
        ]))
        assert "Writing the policy." in text
        assert "[tool] Write: /p.rego" in text
        assert "[result] ok" in text
        assert "turns=4" in text

    def test_repeated_text_is_not_duplicated(self):
        same = {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "identical"}]}}
        text = render(raw="\n".join([json.dumps(same), json.dumps(same)]))
        assert text.count("identical") == 1


# --------------------------------------------------------------------------
# token and cost accounting — the evaluation plan's cost table
# --------------------------------------------------------------------------
class TestStepResultAccounting:
    def test_tokens_sum_all_four_classes(self, tmp_path):
        t = write_trace(tmp_path / "t.jsonl", result_event())
        r = StepResult(True, 10, tmp_path / "l", t, "", usage_totals(t))
        assert r.tokens() == 100 + 200 + 1000 + 500

    def test_tokens_is_zero_without_usage(self, tmp_path):
        assert StepResult(True, 1, tmp_path / "l").tokens() == 0

    def test_cost_line_breaks_out_cached_input(self, tmp_path):
        t = write_trace(tmp_path / "t.jsonl", result_event())
        r = StepResult(True, 10, tmp_path / "l", t, "", usage_totals(t))
        line = r.cost_line()
        assert "turns=4" in line
        assert "cached=1,000" in line
        assert "cost=$0.5000" in line

    def test_cost_line_empty_without_usage(self, tmp_path):
        assert StepResult(True, 1, tmp_path / "l").cost_line() == ""


class TestUsageCsv:
    def test_round_trip_through_the_written_file(self, tmp_path):
        """The table's CSV is what the evaluation plan transcribes, so a
        written row must read back with the same numbers."""
        t = write_trace(tmp_path / "t.jsonl", result_event())
        runner = make_runner(tmp_path)
        runner.ledger = [(STEPS_BY_NUM[1],
                          StepResult(True, 42, tmp_path / "l", t, "",
                                     usage_totals(t)))]
        runner.report_usage()

        rows = read_usage_csv(tmp_path / "usage.csv")
        assert len(rows) == 1
        assert rows[0]["input_tokens"] == 100
        assert rows[0]["total_tokens"] == 1800
        assert rows[0]["cost_usd"] == 0.5
        assert rows[0]["seconds"] == 42

    def test_header_only_file_has_no_rows(self, tmp_path):
        p = tmp_path / "u.csv"
        p.write_text(USAGE_HEADER + "\n", encoding="utf-8")
        assert read_usage_csv(p) == []

    def test_unreadable_file_is_tolerated(self, tmp_path):
        assert read_usage_csv(tmp_path / "absent.csv") == []

    def test_malformed_values_coerce_to_zero(self, tmp_path):
        """A truncated or hand-edited CSV must not abort a finished run."""
        p = tmp_path / "u.csv"
        p.write_text(USAGE_HEADER + "\n1,x,NaNtoken,5,5,5,5,5,notafloat,5,1\n",
                     encoding="utf-8")
        row = read_usage_csv(p)[0]
        assert row["input_tokens"] == 0
        assert row["cost_usd"] == 0.0

    def test_failed_step_is_recorded_as_not_ok(self, tmp_path):
        t = write_trace(tmp_path / "t.jsonl", result_event())
        runner = make_runner(tmp_path)
        runner.ledger = [(STEPS_BY_NUM[4],
                          StepResult(False, 9, tmp_path / "l", t, "timed out",
                                     usage_totals(t)))]
        runner.report_usage()
        assert read_usage_csv(tmp_path / "usage.csv")[0]["ok"] == 0


class TestCostIsSessionCumulative:
    """`total_cost_usd` is a SESSION total"""

    def test_total_takes_the_max_not_the_sum(self, tmp_path, capsys):
        runner = make_runner(tmp_path)
        for num, cost in ((1, 0.6109), (2, 1.3249), (3, 1.6018)):
            t = write_trace(tmp_path / f"t{num}.jsonl", result_event(cost=cost))
            runner.ledger.append((STEPS_BY_NUM[num],
                                  StepResult(True, 10, tmp_path / "l", t, "",
                                             usage_totals(t))))
        runner.report_usage()
        shown = capsys.readouterr().out
        assert "$1.6018" in shown      # the final session figure
        assert "$3.5376" not in shown  # 0.6109 + 1.3249 + 1.6018
        assert "$3.5377" not in shown

    def test_tokens_still_sum_across_steps(self, tmp_path, capsys):
        """Only cost is cumulative; the token counts are genuinely per-step."""
        runner = make_runner(tmp_path)
        for num in (1, 2):
            t = write_trace(tmp_path / f"t{num}.jsonl",
                            result_event(inp=100, out=200, cread=0, ccreate=0))
            runner.ledger.append((STEPS_BY_NUM[num],
                                  StepResult(True, 10, tmp_path / "l", t, "",
                                             usage_totals(t))))
        runner.report_usage()
        rows = read_usage_csv(tmp_path / "usage.csv")
        assert sum(int(r["input_tokens"]) for r in rows) == 200
        assert "600" in capsys.readouterr().out  # grand total of all classes

    def test_cost_column_is_marked_as_cumulative(self, tmp_path, capsys):
        t = write_trace(tmp_path / "t.jsonl", result_event())
        runner = make_runner(tmp_path)
        runner.ledger = [(STEPS_BY_NUM[1],
                          StepResult(True, 1, tmp_path / "l", t, "",
                                     usage_totals(t)))]
        runner.report_usage()
        shown = capsys.readouterr().out
        assert "cost*" in shown
        assert "session total" in shown


class TestCarriedTotals:
    def test_carried_rows_are_added_and_labelled(self, tmp_path, capsys):
        prior = tmp_path / "prior.csv"
        prior.write_text(
            USAGE_HEADER + "\n"
            "1,create OPA policy,611,2406,304383,63283,370683,12,0.6109,470,1\n",
            encoding="utf-8")
        t = write_trace(tmp_path / "t.jsonl",
                        result_event(cost=1.6018, inp=5, out=412,
                                     cread=155058, ccreate=30243))
        runner = make_runner(tmp_path, carry=prior)
        runner.ledger = [(STEPS_BY_NUM[3],
                          StepResult(True, 130, tmp_path / "l", t, "",
                                     usage_totals(t)))]
        runner.report_usage()

        shown = capsys.readouterr().out
        assert "(carried)" in shown
        assert "total (cumulative)" in shown
        assert f"{611 + 5:,}" in shown          # input tokens summed
        assert "$1.6018" in shown               # max, not 0.6109 + 1.6018

    def test_carry_is_empty_without_the_flag(self, tmp_path):
        assert make_runner(tmp_path).carried == []

    def test_a_carried_failure_stays_a_failure(self, tmp_path, capsys):
        """`ok` must round-trip, or re-reporting a run quietly promotes its
        failed steps to passes."""
        prior = tmp_path / "prior.csv"
        prior.write_text(
            USAGE_HEADER + "\n"
            "4,policy testing,1,2,3,4,10,2,0.1,5,0\n", encoding="utf-8")
        runner = make_runner(tmp_path, carry=prior)
        assert runner.carried[0]["ok"] == 0

        t = write_trace(tmp_path / "t.jsonl", result_event())
        runner.ledger = [(STEPS_BY_NUM[5],
                          StepResult(True, 1, tmp_path / "l", t, "",
                                     usage_totals(t)))]
        runner.report_usage()
        assert "failed" in capsys.readouterr().out
        rows = read_usage_csv(tmp_path / "usage.csv")
        assert rows[0]["ok"] == 0   # carried failure preserved on re-emit

    def test_a_csv_without_an_ok_column_reads_as_passing(self, tmp_path):
        """Older CSVs predate the `ok` round-trip; absence must not mean
        failure."""
        prior = tmp_path / "old.csv"
        prior.write_text(
            "step,name,input_tokens,output_tokens,cache_read_tokens,"
            "cache_creation_tokens,total_tokens,turns,cost_usd,seconds\n"
            "1,create OPA policy,1,2,3,4,10,2,0.1,5\n", encoding="utf-8")
        assert read_usage_csv(prior)[0]["ok"] == 1


class TestReportUsageEdgeCases:
    def test_no_ledger_prints_nothing(self, tmp_path, capsys):
        make_runner(tmp_path).report_usage()
        assert capsys.readouterr().out == ""

    def test_ledger_without_usage_warns_instead_of_crashing(self, tmp_path,
                                                            capsys):
        runner = make_runner(tmp_path, trace=False)
        runner.ledger = [(STEPS_BY_NUM[1], StepResult(True, 1, tmp_path / "l"))]
        runner.report_usage()
        assert "No usage recorded" in capsys.readouterr().out

    def test_dry_run_steps_are_not_billed(self, tmp_path):
        """A dry run makes no API calls, so it must not appear in the table."""
        runner = make_runner(tmp_path, dry_run=True)
        runner.run(STEPS_BY_NUM[1])
        assert runner.ledger == []


# --------------------------------------------------------------------------
# transcript classification
# --------------------------------------------------------------------------
class TestClassify:
    def test_clean_transcript_passes(self):
        assert Runner.classify("wrote the policy\nDone.") == ""

    def test_unresolved_skill_is_caught(self):
        """`claude` exits 0 even when the slash command never resolved."""
        assert "did not resolve" in Runner.classify("Unknown command: /smith")

    @pytest.mark.parametrize("tail", [
        "Shall I proceed?",
        "Should I proceed with the patch?",
        "Do you want me to continue?",
        "Awaiting your approval.",
        "I need your permission to run this.",
    ])
    def test_a_step_that_stopped_to_ask_is_a_failure(self, tail):
        """SKILL.md tells the agent to pause for a human "yes"; headless that
        is a step which did no work, not a success."""
        assert "asking for confirmation" in Runner.classify(f"did work\n{tail}")

    def test_approval_language_mid_run_is_ignored(self):
        """Only the tail is inspected: these words legitimately appear while
        the agent narrates what it is doing."""
        text = "Shall I proceed?\n" + "\n".join(f"line {i}" for i in range(10))
        assert Runner.classify(text) == ""

    def test_empty_transcript_passes(self):
        assert Runner.classify("") == ""


# --------------------------------------------------------------------------
# live output
# --------------------------------------------------------------------------
class TestFollow:
    def test_follow_requires_tracing(self, tmp_path):
        """Following renders stream-json events; with --no-trace there are
        none, so piping stdout would swallow the output entirely."""
        assert make_runner(tmp_path, trace=False, follow=True).follow is False
        assert make_runner(tmp_path, trace=True, follow=True).follow is True

    def test_tee_writes_every_byte_and_returns_the_exit_code(self, tmp_path):
        runner = make_runner(tmp_path, follow=True, timeout=30)
        events = [result_event(), json.dumps({"type": "assistant"})]
        script = "; ".join(
            f"print({json.dumps(e)})" for e in events) + "; raise SystemExit(0)"
        proc = subprocess.Popen([sys.executable, "-c", script],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        target = tmp_path / "t.jsonl"
        with target.open("wb") as fh:
            rc = runner._tee(proc, fh)
        assert rc == 0
        assert usage_totals(target)["turns"] == 4

    def test_tee_reassembles_events_split_across_reads(self, tmp_path):
        """_tee reads fixed-size chunks, so one JSON event can straddle two
        reads. A half-line must be buffered, not parsed or dropped: the saved
        trace feeds both the rendered log and the usage table."""
        runner = make_runner(tmp_path, follow=True, timeout=30)
        event = result_event(turns=11)
        # Emit the event in two writes with a pause, forcing a split read.
        script = (
            f"import sys,time; d={event!r}; "
            "sys.stdout.write(d[:20]); sys.stdout.flush(); time.sleep(0.2); "
            "sys.stdout.write(d[20:] + chr(10)); sys.stdout.flush()"
        )
        proc = subprocess.Popen([sys.executable, "-c", script],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        target = tmp_path / "t.jsonl"
        with target.open("wb") as fh:
            assert runner._tee(proc, fh) == 0
        assert target.read_text().strip() == event
        assert usage_totals(target)["turns"] == 11

    def test_tee_handles_output_with_no_trailing_newline(self, tmp_path):
        """A child killed mid-write leaves a final line unterminated; it must
        still reach the file."""
        runner = make_runner(tmp_path, follow=True, timeout=30)
        proc = subprocess.Popen(
            [sys.executable, "-c",
             "import sys; sys.stdout.write('no trailing newline')"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        target = tmp_path / "t.jsonl"
        with target.open("wb") as fh:
            runner._tee(proc, fh)
        assert target.read_text() == "no trailing newline"

    def test_tee_propagates_a_nonzero_exit(self, tmp_path):
        runner = make_runner(tmp_path, follow=True, timeout=30)
        proc = subprocess.Popen([sys.executable, "-c", "raise SystemExit(3)"],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        with (tmp_path / "t.jsonl").open("wb") as fh:
            assert runner._tee(proc, fh) == 3

    def test_tee_enforces_the_timeout_on_a_silent_child(self, tmp_path):
        runner = make_runner(tmp_path, follow=True, timeout=1)
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        started = time.monotonic()
        try:
            with pytest.raises(subprocess.TimeoutExpired):
                with (tmp_path / "t.jsonl").open("wb") as fh:
                    runner._tee(proc, fh)
            assert time.monotonic() - started < 5
        finally:
            proc.kill()
            proc.wait()


# --------------------------------------------------------------------------
# scorecard
# --------------------------------------------------------------------------
class TestScorecard:
    @staticmethod
    def _write(root: Path, summary: str | None, failures: str | None):
        d = root / "references" / "scorecard"
        d.mkdir(parents=True, exist_ok=True)
        if summary is not None:
            (d / "scorecard_summary.txt").write_text(summary, encoding="utf-8")
        if failures is not None:
            (d / "score_test_failures.txt").write_text(failures,
                                                       encoding="utf-8")

    def test_totals_are_summed_across_both_sections(self, tmp_path):
        self._write(tmp_path, "Allow\nTotal:     22\n\nDisallow\nTotal:     26\n",
                    "")
        assert scorecard.read(tmp_path).scored == 48

    def test_failures_are_counted(self, tmp_path):
        self._write(tmp_path, "Total:     10\n",
                    "[FAIL: expected_allow: true, allow: false\n[FAIL: x\n")
        card = scorecard.read(tmp_path)
        assert card.failures == 2
        assert card.ran and not card.all_passed

    def test_an_all_passed_run_reads_as_ran_with_no_failures(self, tmp_path):
        """score_card.sh writes `echo "$FAILS"`, so a clean run leaves the
        file present but blank — which must not read as "never ran"."""
        self._write(tmp_path, "Total:     10\n", "\n")
        card = scorecard.read(tmp_path)
        assert card.ran and card.all_passed and card.failures == 0

    def test_absent_failures_file_means_testing_never_ran(self, tmp_path):
        self._write(tmp_path, "Total:     10\n", None)
        card = scorecard.read(tmp_path)
        assert card.failures == -1
        assert not card.ran
        assert not card.all_passed

    def test_absent_scorecard_is_empty_not_an_error(self, tmp_path):
        card = scorecard.read(tmp_path)
        assert card.scored == 0 and not card.ran and card.summary == ""

    def test_summary_is_returned_verbatim_for_display(self, tmp_path):
        self._write(tmp_path, "Total:     3\nextra detail\n", "")
        assert "extra detail" in scorecard.read(tmp_path).summary


# --------------------------------------------------------------------------
# step definitions — the prompts are the contract with the skill
# --------------------------------------------------------------------------
class TestStepDefinitions:
    def test_steps_are_numbered_consecutively_from_one(self):
        assert [s.num for s in STEPS] == list(range(1, len(STEPS) + 1))

    def test_the_pipeline_runs_every_defined_step(self):
        """Pipeline.run must iterate STEPS_BY_NUM rather than a hardcoded
        range, or a newly added step is silently never executed."""
        source = (Path(__file__).resolve().parent
                  / "smith_pipeline" / "pipeline.py").read_text()
        assert "sorted(STEPS_BY_NUM)" in source

    def test_every_prompt_invokes_the_skill(self):
        assert all(s.prompt.startswith("/smith ") for s in STEPS)

    def test_lookup_is_consistent_with_the_ordered_list(self):
        assert all(STEPS_BY_NUM[s.num] is s for s in STEPS)

    def test_step_2_answers_both_questions_the_guide_asks(self):
        prompt = STEPS_BY_NUM[2].prompt.lower()
        assert "promptfoo" in prompt
        assert "bypass" in prompt

    def test_log_filenames_are_shell_safe(self, tmp_path):
        for step in STEPS:
            slug = step.name.replace(" ", "-")
            assert "/" not in slug and "'" not in slug and '"' not in slug
