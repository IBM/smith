# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0
"""Starting and stopping the target agent, its MCP server, and OPA."""
from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from .config import (
    AGENT_HEALTH_URL,
    AGENT_PORT,
    AGENT_START_TIMEOUT,
    MCP_PORT,
    MCP_START_TIMEOUT,
    OPA_HEALTH_URL,
    OPA_START_TIMEOUT,
    agent_app_module,
    standalone_mcp_script,
)
from .console import out


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(
        ["docker", "info"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


class Services:
    def __init__(self, root: Path, log_dir: Path, *, dry_run: bool,
                 keep: bool, overlay: dict[str, str] | None = None) -> None:
        self.root = root
        self.log_dir = log_dir
        self.dry_run = dry_run
        self.keep = keep
        # The example agent and its MCP server read the same overlay the steps
        # do, so an SSE example's agent connects to the MCP port this run chose.
        self.overlay: dict[str, str] = overlay or {}
        self.agent: subprocess.Popen | None = None
        self.mcp: subprocess.Popen | None = None
        self.opa_started = False

    # -- helpers ------------------------------------------------------------
    def example_python(self, example: str) -> str:
        """The interpreter for an example: its own venv when it ships one
        (employee does), otherwise the skill's."""
        own = self.root / "examples" / example / ".venv" / "bin" / "python"
        return str(own if own.is_file() else
                   self.root / ".venv" / "bin" / "python")

    def _spawn(self, argv: list[str], cwd: Path, log_name: str
               ) -> subprocess.Popen:
        log = (self.log_dir / log_name).open("wb")
        return subprocess.Popen(
            argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,
            env={**os.environ, **self.overlay},
        )

    def _tail(self, name: str, n: int = 20) -> None:
        try:
            text = (self.log_dir / name).read_text(
                encoding="utf-8", errors="replace")
        except OSError:
            return
        out.block("\n".join(text.splitlines()[-n:]))

    def _make(self, target: str) -> int:
        with (self.log_dir / "opa.log").open("ab") as log:
            return subprocess.run(
                ["make", "-s", target], cwd=self.root,
                stdout=log, stderr=subprocess.STDOUT,
                env={**os.environ, **self.overlay},
            ).returncode

    # -- MCP ----------------------------------------------------------------
    def start_mcp(self, example: str) -> bool:
        """Start a standalone MCP server if this example needs one."""
        script = standalone_mcp_script(example)
        if not script:
            return True  # stdio example: the agent launches its own server
        d = self.root / "examples" / example
        if not (d / script).is_file():
            out.warn(f"examples/{example}/{script} not found — no MCP server.")
            return True
        if port_open(MCP_PORT):
            out.err(f"Port {MCP_PORT} became occupied before the MCP server "
                    "could start; stop the existing service and retry.")
            return False

        out.info(f"Starting MCP server: examples/{example}/{script} "
                 f"(SSE on :{MCP_PORT})")
        if self.dry_run:
            out.dry(f"cd examples/{example} && python {script}")
            return True

        self.mcp = self._spawn([self.example_python(example), script], d,
                               "mcp_server.log")
        # SSE streams, so a plain fetch would hang: wait for the port instead.
        for _ in range(MCP_START_TIMEOUT):
            if self.mcp.poll() is not None:
                out.err("MCP server exited — see logs/mcp_server.log")
                self._tail("mcp_server.log")
                return False
            if port_open(MCP_PORT):
                out.ok(f"MCP server (:{MCP_PORT}) is listening")
                return True
            time.sleep(1)
        out.err(f"MCP server did not open :{MCP_PORT} in time")
        return False

    # -- agent --------------------------------------------------------------
    def start_agent(self, example: str) -> bool:
        module = agent_app_module(example)
        entry = module.split(":")[0] + ".py"
        d = self.root / "examples" / example

        if not (d / entry).is_file():
            out.warn(f"examples/{example} has no {entry} — skipping agent.")
            out.warn("Steps needing the live agent (translate, promptfoo) "
                     "will not work.")
            return True
        if port_open(AGENT_PORT):
            out.err(f"Port {AGENT_PORT} became occupied before the target "
                    "agent could start; stop the existing service and retry.")
            return False

        out.info(f"Starting target agent: examples/{example} "
                 f"(uvicorn {module} on :{AGENT_PORT})")
        if self.dry_run:
            out.dry(f"cd examples/{example} && uvicorn {module} "
                    f"--host 0.0.0.0 --port {AGENT_PORT}")
            return True

        self.agent = self._spawn(
            [self.example_python(example), "-m", "uvicorn", module,
             "--host", "0.0.0.0", "--port", str(AGENT_PORT)],
            d, "agent.log",
        )
        for _ in range(AGENT_START_TIMEOUT):
            if self.agent.poll() is not None:
                out.err("Agent failed to start — see logs/agent.log")
                self._tail("agent.log")
                return False
            if http_ok(AGENT_HEALTH_URL):
                out.ok(f"agent (:{AGENT_PORT}) is up")
                return True
            if port_open(AGENT_PORT):
                out.ok(f"agent (:{AGENT_PORT}) is listening")
                return True
            time.sleep(1)
        out.err(f"Agent did not answer on :{AGENT_PORT} in time")
        self._tail("agent.log")
        return False

    # -- OPA ----------------------------------------------------------------
    def start_opa(self, *, reload: bool = False) -> None:
        if self.dry_run:
            out.dry("make opaserver/stop && make opaserver/start")
            return
        if not docker_available():
            out.warn("Docker unavailable — skipping OPA. Policy testing "
                     "will fail.")
            return

        policy = self.root / "assets" / "policy.rego"
        # An empty policy file makes OPA exit immediately.
        if not policy.is_file() or policy.stat().st_size == 0:
            out.warn("assets/policy.rego is empty — OPA will start once a "
                     "policy has been written.")
            return

        out.info("Reloading OPA with the current policy" if reload
                 else "Starting OPA server on :8181")
        self._make("opaserver/stop")
        if self._make("opaserver/start") != 0:
            out.warn("make opaserver/start failed — see logs/opa.log")
            self._tail("opa.log")
            return
        self.opa_started = True
        for _ in range(OPA_START_TIMEOUT):
            if http_ok(OPA_HEALTH_URL):
                out.ok("OPA (:8181) is up")
                return
            time.sleep(1)
        out.warn("OPA did not answer /health in time.")

    # -- teardown -----------------------------------------------------------
    def stop(self) -> None:
        if self.keep:
            if self.agent or self.mcp or self.opa_started:
                out.info("--keep-services: leaving the services this run "
                         "started up.")
            return

        for label, proc in (("target agent", self.agent),
                            ("MCP server", self.mcp)):
            if proc is None or proc.poll() is not None:
                continue
            out.info(f"Stopping {label} (pid {proc.pid})")
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        self.agent = None
        self.mcp = None

        if self.opa_started:
            out.info("Stopping OPA server")
            self._make("opaserver/stop")
            self.opa_started = False
