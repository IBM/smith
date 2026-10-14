# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
"""Argument parsing, preflight checks, and the entry point."""
from __future__ import annotations

import argparse
import atexit
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .config import (
    AGENT_PORT,
    MCP_PORT,
    OPA_HEALTH_URL,
    PARENT,
    SKILL_ROOT,
    STEPS,
    STEPS_BY_NUM,
    UNKNOWN_CMD,
    standalone_mcp_script,
)
from .console import out
from .examples import choose as choose_example
from .pipeline import Pipeline
from .runner import Runner
from .services import Services, docker_available, port_open
from .trace import session_id


def parse_steps(spec: str | None) -> list[int]:
    """Parse "1,2,3" / "4-8" / "5" into an ordered, de-duplicated step list."""
    if not spec:
        return [s.num for s in STEPS]

    picked: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if m := re.fullmatch(r"(\d+)-(\d+)", part):
            picked.update(range(int(m.group(1)), int(m.group(2)) + 1))
        elif part.isdigit():
            picked.add(int(part))
        else:
            out.err(f"Cannot parse --steps value: {part!r}")
            raise SystemExit(2)

    for num in sorted(picked):
        if num not in STEPS_BY_NUM:
            valid = " ".join(str(s.num) for s in STEPS)
            out.err(f"Step {num} is not a valid step (valid: {valid})")
            raise SystemExit(2)

    # Always run in pipeline order, regardless of how they were listed.
    return [s.num for s in STEPS if s.num in picked]


def build_parser() -> argparse.ArgumentParser:
    steps_help = "\n".join(f"  {s.num}  {s.name}" for s in STEPS)
    p = argparse.ArgumentParser(
        prog="run_smith_pipeline.py",
        description="Run the full Smith workflow for one example agent.",
        epilog=f"Steps:\n{steps_help}\n\n"
               "Logs land in .claude/skills/smith/logs/<timestamp>/.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-e", "--example",
                   help="Example under examples/ (skips the interactive menu).")
    p.add_argument("-s", "--steps", dest="steps_spec", metavar="LIST",
                   help="Steps to run, e.g. 1,2,3 or 4-8 (default: all).")
    p.add_argument("-m", "--model",
                   help="Model for `claude -p` (default: Claude Code's own).")
    p.add_argument("--timeout", type=int, default=3600, metavar="SECONDS",
                   help="Per-step timeout (default: 3600).")
    p.add_argument("--permission-mode", default="bypassPermissions", metavar="M",
                   help="claude --permission-mode (default: bypassPermissions, "
                        "since an unattended run cannot answer prompts).")
    p.add_argument("--yolo", "--dangerously-skip-permissions",
                   dest="yolo", action="store_true",
                   help="Pass --dangerously-skip-permissions. Sandboxes only.")
    p.add_argument("--no-clean", dest="clean", action="store_false",
                   help="Do not run scripts/clean.sh first.")
    p.add_argument("--keep-services", action="store_true",
                   help="Leave the agent/MCP/OPA running on exit.")
    p.add_argument("--no-chain", dest="chain", action="store_false",
                   help="Run each step as a fresh conversation. By default a "
                        "step resumes the previous one's session, so it "
                        "inherits what that step worked out. Requires tracing.")
    p.add_argument("--resume", metavar="SESSION_ID",
                   help="Continue an existing Claude session.")
    p.add_argument("--carry", metavar="CSV_OR_DIR",
                   help="Add an earlier run's token totals to this run's "
                        "usage table, so the total is cumulative across.")
    p.add_argument("--no-trace", dest="trace", action="store_false",
                   help="Log only the agent's final summary. By default each "
                        "step also records every tool call it made, plus the "
                        "raw event stream in <step>.trace.jsonl.")
    p.add_argument("--no-follow", dest="follow", action="store_false",
                   help="Do not echo each step's activity while it runs. By "
                        "default progress is streamed live; with this flag a "
                        "step prints nothing until it finishes.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would happen; run nothing.")
    return p


def previous_runs(root: Path, before: Path | None = None) -> list[Path]:
    logs = root / "logs"
    if not logs.is_dir():
        return []
    runs = [d for d in logs.iterdir()
            if d.is_dir() and (before is None or d != before)]
    return sorted(runs, key=lambda d: d.stat().st_mtime, reverse=True)


def resolve_resume(root: Path, value: str, this_run: Path) -> str | None:
    if value != "last":
        return value
    for run in previous_runs(root, before=this_run):
        traces = sorted(run.glob("step*.trace.jsonl"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
        for trace in traces:
            if sid := session_id(trace):
                out.ok(f"--resume last: session {sid} (from {run.name})")
                return sid
    out.warn("--resume last: no previous session found under logs/ — "
             "starting a fresh conversation.")
    return None


def resolve_carry(root: Path, value: str, this_run: Path) -> Path | None:
    """The usage.csv named by --carry: a file, a run directory, or 'last'."""
    if value == "last":
        for run in previous_runs(root, before=this_run):
            if (csv := run / "usage.csv").is_file():
                out.ok(f"--carry last: {csv.parent.name}/usage.csv")
                return csv
        out.warn("--carry last: no previous usage.csv found under logs/.")
        return None

    path = Path(value).expanduser()
    if not path.is_absolute():
        for base in (Path.cwd(), root):
            if (candidate := base / path).exists():
                path = candidate
                break
    if path.is_dir():
        path = path / "usage.csv"
    if not path.is_file():
        out.warn(f"--carry: no usage.csv at {path}")
        return None
    return path


def preflight(root: Path, example: str, steps: list[int], *,
              dry_run: bool = False) -> None:
    out.info("Preflight checks")
    fatal = False

    if claude := shutil.which("claude"):
        ver = subprocess.run(["claude", "--version"], capture_output=True,
                             text=True).stdout.strip().splitlines()
        out.ok(f"claude: {claude}" + (f" ({ver[0]})" if ver else ""))
    else:
        out.err("The 'claude' CLI is not on PATH — this script drives it "
                "headlessly.")
        fatal = True

    if (root / ".venv" / "bin" / "python").is_file():
        out.ok("venv: .venv/bin/python")
    else:
        out.err("No virtualenv at .venv — run 'make install' in the skill.")
        fatal = True

    if not shutil.which("docker"):
        out.warn("docker not found — OPA cannot start, so policy testing fails.")
    elif not docker_available():
        out.warn("docker is installed but not running — start it for policy "
                 "testing.")
    else:
        out.ok("docker: running")

    for tool, why in (("regal", "step 7 output will be reduced"),
                      ("opa", "scorecard coverage analysis is skipped")):
        if path := shutil.which(tool):
            out.ok(f"{tool}: {path}")
        else:
            out.warn(f"{tool} not found — {why}.")

    # From the environment .env was loaded into, so quoting is interpreted the
    # same way the `smith` CLI interprets it.
    attack = os.getenv("ATTACK_TOOLS")
    if attack and attack != "none":
        out.ok(f"ATTACK_TOOLS={attack}")
        if "promptfoo" in attack and not shutil.which("promptfoo"):
            out.warn("ATTACK_TOOLS includes promptfoo but its CLI is not on "
                     "PATH.")
            out.warn("legitimate cases only, not resistance to red-teaming.")
    else:
        out.warn(f"ATTACK_TOOLS={attack or 'unset'} — no adversarial coverage "
                 "in step 2.")

    out.ok(f"agent port: {AGENT_PORT} (from AGENT_URL)")
    out.ok(f"MCP port: {MCP_PORT} (from MCP_URL)")
    out.ok(f"OPA health: {OPA_HEALTH_URL}")
    if not dry_run:
        required_ports = [(AGENT_PORT, "target agent")]
        if standalone_mcp_script(example):
            required_ports.append((MCP_PORT, "MCP server"))
        if any(num >= 4 for num in steps):
            # make test publishes OPA on host port 8181, regardless of OPA_URL.
            required_ports.append((8181, "OPA"))
        for port, service in required_ports:
            if port_open(port):
                out.err(f"Port {port} is already in use ({service}); stop the "
                        "existing service before running this evaluation.")
                fatal = True
    if fatal:
        raise SystemExit(1)


def verify_skill(dry_run: bool) -> None:
    """Confirm `/smith` resolves before running anything that depends on it."""
    try:
        shown = SKILL_ROOT.relative_to(PARENT)
    except ValueError:
        shown = SKILL_ROOT  # skill lives outside the workspace (overridden)
    out.ok(f"skill: {shown}/SKILL.md")
    out.ok(f"claude cwd: {PARENT}")
    if dry_run:
        return

    try:
        proc = subprocess.run(
            ["claude", "-p", "/smith", "--permission-mode", "plan"],
            cwd=PARENT, capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        out.err("Timed out checking whether '/smith' resolves in headless mode.")
        raise SystemExit(1) from None
    combined = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 or not combined.strip() or UNKNOWN_CMD.search(combined):
        out.err(f"Could not verify '/smith' when claude runs in {PARENT} "
                f"(exit code {proc.returncode}):")
        out.block("\n".join(combined.splitlines()[:30]))
        out.err("Claude Code looks for .claude/skills/<name>/SKILL.md under "
                "its cwd.")
        out.err(f"Expected: {SKILL_ROOT / 'SKILL.md'}")
        raise SystemExit(1)
    out.ok("skill: /smith resolves in headless mode")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not (SKILL_ROOT / "SKILL.md").is_file():
        out.err(f"No skill found at {SKILL_ROOT} (expected SKILL.md there).")
        out.err("SKILL_ROOT comes from BASE_URL in .env — point it at the "
                "skill directory (with a trailing slash).")
        return 1

    # `claude` must run from the directory holding .claude/skills/, or `/smith`
    # will not resolve. Catch a broken layout here rather than mid-run.
    if not (PARENT / ".claude" / "skills").is_dir():
        out.err(f"No .claude/skills/ under {PARENT} — '/smith' will not resolve.")
        out.err("PARENT is derived from BASE_URL by stripping the trailing "
                ".claude/skills/<name>/, so BASE_URL must point at a skill "
                "inside a workspace laid out that way.")
        return 1

    root = SKILL_ROOT
    steps = parse_steps(args.steps_spec)
    run_ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    # Logs live outside references/ on purpose: clean.sh wipes
    # everything under references/, which would delete this run's own logs.
    log_dir = root / "logs" / run_ts

    out.hdr("Smith pipeline runner")
    out.say(f"  root:  {root}")
    out.say(f"  run:   {run_ts}")
    out.say(f"  steps: {' '.join(str(n) for n in steps)}")
    if args.dry_run:
        out.say(f"  {out.yellow}mode:  dry run{out.off}")

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        out.err(f"Could not create the log directory {log_dir}: {exc}")
        return 1
    out.ok(f"logs: {log_dir}")

    example = choose_example(root, args.example)
    preflight(root, example, steps, dry_run=args.dry_run)
    verify_skill(args.dry_run)

    services = Services(root, log_dir, dry_run=args.dry_run,
                        keep=args.keep_services)
    runner = Runner(root, log_dir, permission_mode=args.permission_mode,
                    model=args.model, timeout=args.timeout, trace=args.trace,
                    yolo=args.yolo, dry_run=args.dry_run, chain=args.chain,
                    follow=args.follow,
                    resume=(resolve_resume(root, args.resume, log_dir)
                            if args.resume else None),
                    carry=(resolve_carry(root, args.carry, log_dir)
                           if args.carry else None))
    pipeline = Pipeline(root, log_dir, example, steps, runner, services,
                        clean=args.clean, dry_run=args.dry_run)

    atexit.register(services.stop)
    try:
        overlay = pipeline.resolve_env()
        runner.overlay = overlay
        services.overlay = overlay
        pipeline.clean_artifacts()
        code = pipeline.run()
    except KeyboardInterrupt:
        out.say("")
        out.warn("Interrupted — shutting down services.")
        runner.report_usage()
        return 130
    finally:
        services.stop()
        atexit.unregister(services.stop)

    # Printed whatever the outcome: a run that failed at step 4 still spent
    # what steps 1-3 cost, and that is the number the cost table needs.
    runner.report_usage()

    if code == 0:
        out.hdr("Done")
        out.say(f"  example: {example}")
        out.say(f"  logs:    {log_dir}")
    return code
