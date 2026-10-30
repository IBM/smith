# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
"""Running one workflow step as a `/smith ...` prompt through headless Claude."""
from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import (
    ALLOWED_TOOLS,
    ASKED_PATTERNS,
    AUTORUN_TEMPLATE,
    PARENT,
    UNKNOWN_CMD,
    Step,
)
from .console import out
from .trace import live_line, render_file, session_id, usage_totals


_CSV_INTS = ("input_tokens", "output_tokens", "cache_read_tokens",
             "cache_creation_tokens", "total_tokens", "turns", "seconds",
             # `ok` round-trips too, so a carried row keeps the knowledge that
             # its step failed rather than being silently promoted to a pass.
             "ok")


def read_usage_csv(path: Path) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        out.warn(f"--carry: cannot read {path}: {exc}")
        return rows
    import csv as _csv
    for raw in _csv.DictReader(text.splitlines()):
        row: dict[str, float | int | str] = {}
        for key in _CSV_INTS:
            # A CSV written before `ok` was round-tripped has no such column;
            # treat those rows as passes rather than silently failing them.
            default = 1 if key == "ok" else 0
            try:
                raw_value = raw.get(key)
                row[key] = (default if raw_value in (None, "")
                            else int(raw_value))
            except ValueError:
                row[key] = default
        try:
            row["cost_usd"] = float(raw.get("cost_usd") or 0.0)
        except ValueError:
            row["cost_usd"] = 0.0
        row["step"] = raw.get("step") or "?"
        row["name"] = raw.get("name") or ""
        rows.append(row)
    return rows


@dataclass
class StepResult:
    ok: bool
    elapsed: int
    log: Path
    trace: Path | None = None
    reason: str = ""
    usage: dict[str, float | int] = field(default_factory=dict)
    """Cost/turn/token totals from the trace; empty when tracing is off."""

    def tokens(self) -> int:
        """Total tokens for the step: input + output + both cache classes."""
        return sum(
            int(self.usage.get(key, 0) or 0)
            for key in ("input_tokens", "output_tokens",
                        "cache_read_input_tokens",
                        "cache_creation_input_tokens")
        )

    def cost_line(self) -> str:
        """A one-line cost summary, or "" when the trace carried no totals."""
        bits = []
        if (turns := self.usage.get("turns")) is not None:
            bits.append(f"turns={turns}")
        if total := self.tokens():
            inp = int(self.usage.get("input_tokens", 0) or 0)
            outp = int(self.usage.get("output_tokens", 0) or 0)
            cached = int(self.usage.get("cache_read_input_tokens", 0) or 0)
            bits.append(f"tokens={total:,} (in={inp:,} out={outp:,} "
                        f"cached={cached:,})")
        if (cost := self.usage.get("cost_usd")) is not None:
            bits.append(f"cost=${cost:.4f}")
        return "  ".join(bits)


class Runner:
    def __init__(self, root: Path, log_dir: Path, *, permission_mode: str,
                 model: str | None, timeout: int, trace: bool, yolo: bool,
                 dry_run: bool, overlay: dict[str, str] | None = None,
                 chain: bool = True, follow: bool = True,
                 resume: str | None = None,
                 carry: Path | None = None) -> None:
        self.root = root
        self.log_dir = log_dir
        self.permission_mode = permission_mode
        self.model = model
        self.timeout = timeout
        self.trace = trace
        self.yolo = yolo
        self.dry_run = dry_run
        # Echo each streamed event as it arrives. Needs the stream-json feed,
        # so it is off whenever tracing is.
        self.follow = follow and trace
        self.overlay: dict[str, str] = overlay or {}
        self.autorun = AUTORUN_TEMPLATE.format(skill_root=root)
        # Steps continue one conversation, so a later step inherits what an
        # earlier one worked out. Set from the first step's trace; needs
        # tracing on, since the id only appears in the stream-json events.
        self.chain = chain
        # Seeded by --resume, so the first step continues an earlier run's
        # conversation instead of starting cold. From then on it is maintained
        # exactly as a chained run's is.
        self.session: str | None = resume
        self.seeded = resume is not None
        # Per-step usage in run order, for the end-of-run cost table.
        self.ledger: list[tuple[Step, StepResult]] = []
        # Totals carried in from an earlier run's usage.csv (--carry), so the
        # table can report a cumulative figure across invocations.
        self.carried: list[dict[str, float | int | str]] = (
            read_usage_csv(carry) if carry else []
        )

    # -- command construction ----------------------------------------------
    def build_command(self, prompt: str) -> list[str]:
        cmd = ["claude", "-p", prompt,
               "--permission-mode", self.permission_mode,
               "--add-dir", str(self.root)]
        # An explicitly seeded session (--resume) is honoured even with
        # --no-chain: the user named it, so it is not the chaining default.
        if self.session and (self.chain or self.seeded):
            cmd += ["--resume", self.session]
        if self.yolo:
            cmd.append("--dangerously-skip-permissions")
        elif self.permission_mode != "bypassPermissions":
            # bypassPermissions already allows everything; an allowlist on top
            # of it is redundant and can conflict.
            cmd += ["--allowedTools", *ALLOWED_TOOLS]
        if self.model:
            cmd += ["--model", self.model]
        if self.trace:
            cmd += ["--verbose", "--output-format", "stream-json",
                    "--include-partial-messages"]
        return cmd

    def full_prompt(self, step: Step) -> str:
        return f"{step.prompt}\n\n{self.autorun}"

    # -- live output --------------------------------------------------------
    def _tee(self, proc: subprocess.Popen, fh) -> int:
        """Copy the child's stdout to `fh`, echoing progress as it arrives. Without this a step shows nothing until it exits"""
        deadline = time.monotonic() + self.timeout
        assert proc.stdout is not None
        pending = b""
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(timeout=remaining):
                    raise subprocess.TimeoutExpired(proc.args, self.timeout)
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    break
                fh.write(chunk)
                fh.flush()
                pending += chunk
                *lines, pending = pending.split(b"\n")
                for raw in lines:
                    if line := live_line(raw.decode("utf-8", errors="replace")):
                        out.say(f"  {out.dim}|{out.off} {line}")
        if pending:
            if line := live_line(pending.decode("utf-8", errors="replace")):
                out.say(f"  {out.dim}|{out.off} {line}")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(proc.args, self.timeout)
        return proc.wait(timeout=remaining)

    # -- verdict ------------------------------------------------------------
    @staticmethod
    def classify(text: str) -> tuple[bool, str]:
        """``(ok, reason)`` for a transcript that exited 0.

        A step whose skill never resolved ran nothing, so it fails. A step that
        closed with a question is different: these prompts tell the agent to
        stop before the next stage, so a trailing "shall I proceed?" usually
        follows work that did finish. That is reported as a warning and the
        step's own results are kept, rather than discarding a completed step
        over its sign-off.
        """
        if UNKNOWN_CMD.search(text):
            return False, "the '/smith' skill did not resolve — nothing was run"
        # Only inspect the tail: "approval" can legitimately appear mid-run.
        tail = "\n".join(text.splitlines()[-5:])
        if ASKED_PATTERNS.search(tail):
            return True, ("ended by asking whether to continue; treating the "
                          "step as finished")
        return True, ""

    # -- execution ----------------------------------------------------------
    def run(self, step: Step) -> StepResult:
        """Run one step, recording its usage for the end-of-run cost table."""
        result = self._run(step)
        if not self.dry_run:
            self.ledger.append((step, result))
        return result

    def _run(self, step: Step) -> StepResult:
        slug = step.name.replace(" ", "-")
        log = self.log_dir / f"step{step.num}-{slug}.log"
        trace_path = self.log_dir / f"step{step.num}-{slug}.trace.jsonl"

        out.hdr(f"Step {step.num} — {step.name}")
        out.say(f"  {out.dim}prompt:{out.off} {step.prompt}")
        resuming = self.session and (self.chain or self.seeded)
        if resuming:
            out.say(f"  {out.dim}resuming session {self.session}{out.off}")

        if self.dry_run:
            out.dry(f'claude -p "{step.prompt} [+ autorun approval]" '
                    f"--permission-mode {self.permission_mode}"
                    + (f" --resume {self.session}" if resuming else ""))
            return StepResult(True, 0, log)

        target = trace_path if self.trace else log
        started = time.monotonic()
        timed_out = False

        with target.open("wb") as fh:
            proc = subprocess.Popen(
                self.build_command(self.full_prompt(step)),
                cwd=PARENT,
                # Stream through a pipe when following, so each event can be
                # echoed as it arrives; otherwise write straight to the file.
                stdout=subprocess.PIPE if self.follow else fh,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env={**os.environ, **self.overlay},
            )
            try:
                if self.follow:
                    rc = self._tee(proc, fh)
                else:
                    rc = proc.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except (ProcessLookupError, PermissionError, OSError):
                    proc.terminate()
                try:
                    rc = proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    rc = -9

        elapsed = int(time.monotonic() - started)

        if self.trace:
            log.write_text(render_file(trace_path), encoding="utf-8")
            if self.chain and (sid := session_id(trace_path)):
                if self.session is None:
                    out.say(f"  {out.dim}session {sid} "
                            f"(later steps will resume it){out.off}")
                self.session = sid
        elif self.chain:
            # No stream-json, so no session id to thread.
            self.chain = False
            out.warn("--no-trace: steps cannot share context (the session id "
                     "comes from the trace).")

        text = log.read_text(encoding="utf-8", errors="replace")
        if self.follow:
            out.block("\n".join(text.splitlines()[-12:]))
        else:
            out.block(text if self.trace
                      else "\n".join(text.splitlines()[-40:]))

        result_trace = trace_path if self.trace else None
        # Reported even on failure: a step that timed out still spent the money.
        usage = usage_totals(trace_path) if self.trace else {}

        if timed_out:
            reason = f"timed out after {self.timeout}s"
            out.err(f"Step {step.num} {reason} (log: {log.name})")
            return StepResult(False, elapsed, log, result_trace, reason, usage)
        if rc != 0:
            reason = f"exited {rc}"
            out.err(f"Step {step.num} {reason} after {elapsed}s "
                    f"(log: {log.name})")
            return StepResult(False, elapsed, log, result_trace, reason, usage)
        ok, reason = self.classify(text)
        if not ok:
            out.err(f"Step {step.num}: {reason}.")
            out.err(f"Log: {log.name}")
            return StepResult(False, elapsed, log, result_trace, reason, usage)
        if reason:
            out.warn(f"Step {step.num}: {reason}.")

        result = StepResult(True, elapsed, log, result_trace, reason, usage)
        suffix = f"  {cost}" if (cost := result.cost_line()) else ""
        out.ok(f"Step {step.num} finished in {elapsed}s (log: {log.name})"
               f"{suffix}")
        return result

    # -- cost reporting -----------------------------------------------------
    def report_usage(self) -> None:
        """Print the per-step cost table, and write it as CSV beside the logs."""
        if not self.ledger:
            return
        rows = [(s, r) for s, r in self.ledger if r.usage]
        if not rows and not self.carried:
            out.warn("No usage recorded (tracing off, or no step produced a "
                     "result event).")
            return

        out.hdr("Token usage by step")
        head = (f"  {'step':<34}{'in':>10}{'out':>9}{'cached':>11}"
                f"{'total':>11}{'turns':>7}{'cost*':>10}{'time':>7}")
        out.say(head)
        out.say(f"  {out.dim}{'-' * (len(head) - 2)}{out.off}")

        def g(r: StepResult, key: str) -> int:
            return int(r.usage.get(key, 0) or 0)

        tot = {k: 0 for k in ("input_tokens", "output_tokens",
                              "cache_read_input_tokens",
                              "cache_creation_input_tokens")}
        # `cost_usd` is a SESSION total, not a per-step figure: with steps
        # chained by --resume, each one already includes every earlier step's
        # cost. So the run's cost is the LARGEST value seen, never the sum.
        tot_cost = 0.0
        tot_time = 0
        csv = ["step,name,input_tokens,output_tokens,cache_read_tokens,"
               "cache_creation_tokens,total_tokens,turns,cost_usd,seconds,ok"]

        # Carried-in rows first, dimmed, so the cumulative total is auditable:
        # the reader can see which steps came from an earlier invocation.
        for row in self.carried:
            tot["input_tokens"] += int(row["input_tokens"])
            tot["output_tokens"] += int(row["output_tokens"])
            tot["cache_read_input_tokens"] += int(row["cache_read_tokens"])
            tot["cache_creation_input_tokens"] += int(
                row["cache_creation_tokens"])
            tot_cost = max(tot_cost, float(row["cost_usd"]))
            tot_time += int(row["seconds"])
            mark = "  (carried)" if int(row.get("ok", 1)) else \
                   "  (carried, failed)"
            label = f"{row['step']} {row['name']}"[:32] + mark
            out.say(f"  {out.dim}{label:<34}{int(row['input_tokens']):>10,}"
                    f"{int(row['output_tokens']):>9,}"
                    f"{int(row['cache_read_tokens']):>11,}"
                    f"{int(row['total_tokens']):>11,}"
                    f"{int(row['turns']):>7}"
                    f"{'$' + format(float(row['cost_usd']), '.4f'):>10}"
                    f"{str(int(row['seconds'])) + 's':>7}{out.off}")
            csv.append(
                f"{row['step']},{row['name']},{int(row['input_tokens'])},"
                f"{int(row['output_tokens'])},{int(row['cache_read_tokens'])},"
                f"{int(row['cache_creation_tokens'])},"
                f"{int(row['total_tokens'])},{int(row['turns'])},"
                f"{float(row['cost_usd']):.6f},{int(row['seconds'])},"
                f"{int(row.get('ok', 1))}"
            )

        for step, r in rows:
            for k in tot:
                tot[k] += g(r, k)
            cost = float(r.usage.get("cost_usd", 0.0) or 0.0)
            tot_cost = max(tot_cost, cost)
            tot_time += r.elapsed
            mark = "" if r.ok else "  (failed)"
            label = f"{step.num} {step.name}"[:32] + mark
            out.say(f"  {label:<34}{g(r, 'input_tokens'):>10,}"
                    f"{g(r, 'output_tokens'):>9,}"
                    f"{g(r, 'cache_read_input_tokens'):>11,}"
                    f"{r.tokens():>11,}"
                    f"{int(r.usage.get('turns', 0) or 0):>7}"
                    f"{'$' + format(cost, '.4f'):>10}"
                    f"{str(r.elapsed) + 's':>7}")
            csv.append(
                f"{step.num},{step.name},{g(r, 'input_tokens')},"
                f"{g(r, 'output_tokens')},{g(r, 'cache_read_input_tokens')},"
                f"{g(r, 'cache_creation_input_tokens')},{r.tokens()},"
                f"{int(r.usage.get('turns', 0) or 0)},{cost:.6f},"
                f"{r.elapsed},{int(r.ok)}"
            )

        grand = sum(tot.values())
        out.say(f"  {out.dim}{'-' * (len(head) - 2)}{out.off}")
        label = "total (cumulative)" if self.carried else "total"
        out.say(f"  {label:<34}{tot['input_tokens']:>10,}"
                f"{tot['output_tokens']:>9,}"
                f"{tot['cache_read_input_tokens']:>11,}"
                f"{grand:>11,}"
                f"{'':>7}{'$' + format(tot_cost, '.4f'):>10}"
                f"{str(tot_time) + 's':>7}")
        if cc := tot["cache_creation_input_tokens"]:
            out.say(f"  {out.dim}cache-creation tokens: {cc:,} "
                    f"(included in total){out.off}")
        out.say(f"  {out.dim}* cost is the session total as of that step, not "
                f"the step alone: chained steps share one session, so the "
                f"figures are cumulative and the total is the final value, "
                f"not their sum.{out.off}")

        path = self.log_dir / "usage.csv"
        try:
            path.write_text("\n".join(csv) + "\n", encoding="utf-8")
            out.say(f"  {out.dim}csv: {path}{out.off}")
        except OSError as exc:
            out.warn(f"Could not write usage.csv: {exc}")
