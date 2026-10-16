# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
load_dotenv()

SKILL_ROOT = Path(os.environ["BASE_URL"].rstrip("/"))
PARENT = SKILL_ROOT.parents[2]

# ---------------------------------------------------------------------------
# Ports and URLs, read from the environment .env was just loaded into.
# ---------------------------------------------------------------------------
DEFAULTS: dict[str, str] = {
    "AGENT_URL": "http://localhost:9000",
    "MCP_URL": "http://localhost:8000/sse",
    "OPA_URL": "http://localhost:8181",
    "AGENT_PORT": "9000",
    "MCP_PORT": "8000",
    "OPA_PORT": "8181",
    # How long to wait for each service to come up, in seconds.
    "AGENT_START_TIMEOUT": "60",
    "MCP_START_TIMEOUT": "60",
    "OPA_START_TIMEOUT": "30",
}


def env_str(key: str) -> str:
    """A configured string: the environment, else the built-in default."""
    return os.getenv(key) or DEFAULTS.get(key, "")


def env_int(key: str) -> int:
    """A configured integer, falling back to the default on anything unparseable."""
    try:
        return int(str(env_str(key)).strip())
    except (TypeError, ValueError):
        return int(DEFAULTS[key])


def env_port(url_key: str, port_key: str) -> int:
    if explicit := os.getenv(port_key):
        try:
            return int(explicit.strip())
        except ValueError:
            pass
    try:
        if (port := urlparse(env_str(url_key)).port) is not None:
            return port
    except ValueError:
        pass
    return int(DEFAULTS[port_key])


AGENT_PORT = env_port("AGENT_URL", "AGENT_PORT")
MCP_PORT = env_port("MCP_URL", "MCP_PORT")
OPA_PORT = env_port("OPA_URL", "OPA_PORT")
AGENT_HEALTH_URL = f"http://localhost:{AGENT_PORT}/health"
OPA_HEALTH_URL = f"{env_str('OPA_URL').rstrip('/')}/health"
AGENT_START_TIMEOUT = env_int("AGENT_START_TIMEOUT")
MCP_START_TIMEOUT = env_int("MCP_START_TIMEOUT")
OPA_START_TIMEOUT = env_int("OPA_START_TIMEOUT")

DEFAULT_AGENT_APP = "agent:app"
AGENT_APP_MODULE = {"RagChatbot_MCPServer": "fast_server:app"}
STANDALONE_MCP = {"RagChatbot_MCPServer": "mcp_server.py"}
# Examples that serve tool definitions over plain http instead of a MCP server.
HTTP_TOOL_DEFS = {"hr-agent"}


def agent_app_module(example: str) -> str:
    return AGENT_APP_MODULE.get(example, DEFAULT_AGENT_APP)


def standalone_mcp_script(example: str) -> str | None:
    return STANDALONE_MCP.get(example)


# ---------------------------------------------------------------------------
# workflow steps
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Step:
    num: int
    name: str
    prompt: str


STEPS: tuple[Step, ...] = (
    Step(1, "create OPA policy",
         "/smith create an opa policy for target agent. "
         "Do not generate test cases."),
    Step(2, "generate test cases",
         "/smith generate test cases. Yes, regenerate the promptfoo config from "
         "the current guidance first. Generate both guidance targeted cases and "
         "policy bypass cases. "
         "STOP once the cases are generated: do not translate them and do not "
         "test the policy."),
    Step(3, "translate test cases",
         "/smith translate test cases. "
         "STOP once translation is done: do not test the policy."),
    Step(4, "policy testing",
         "/smith test my policy. "
         "STOP after reporting the results: do not cross-validate any case or patch the policy."),
    Step(5, "cross-validate failed test cases",
         "/smith cross validate checking test cases. "
         "STOP after applying the label corrections: do not patch the policy."),
    Step(6, "patch failed test cases",
         "/smith patch the failed test cases. "
         "STOP once patching finishes, do not run regal or the duplication check."),
    Step(7, "regal suggestions and fixes",
         "/smith get regal suggestions and fix the problems. "
         "STOP once the lint problems are fixed: do not run the duplication "
         "check."),
    Step(8, "duplication suggestions and fixes",
         "/smith get duplication suggestions and fix the problems. "
         "STOP once duplication is reduced"),
    Step(9, "final policy testing",
         "/smith test my policy. "),
    # Produces guidance only. It runs last so the earlier steps measure the
    # policy built from the author's original prose: enhancing the guidance
    # first would change the input every other step is scored against.
    Step(10, "enhance guidance with security analysis",
         "/smith run the security-grounded guidance analysis for the target "
         "agent, do not create or modify any policy."),
)
STEPS_BY_NUM = {s.num: s for s in STEPS}

AUTORUN_TEMPLATE = """\
The Smith skill directory is {skill_root} — treat it as the working directory \
for this task: run every command from there (cd into it first) and resolve every \
relative path in the skill's instructions against it.

Run the Smith CLI as the absolute path {skill_root}/.venv/bin/smith (for example \
'{skill_root}/.venv/bin/smith --flag get_current_agent'). Do NOT invoke a bare \
'smith' — an unrelated broken 'smith' shim shadows it on PATH here.

This is an unattended automated run: you have my explicit approval and my "yes" \
in advance for every step of this task, including creating and modifying \
assets/policy.rego. Do not stop to ask for confirmation or approval at any \
point — carry the task through to completion, then report what you did."""

# Used only when --permission-mode is not bypassPermissions.
ALLOWED_TOOLS = (
    "Read", "Write", "Edit", "Glob", "Grep", "TodoWrite", "Task",
    "Bash(smith:*)", "Bash(*/smith:*)", "Bash(*/.venv/bin/smith:*)",
    "Bash(.venv/bin/smith:*)", "Bash(cd:*)", "Bash(source:*)",
    "Bash(make:*)", "Bash(opa:*)", "Bash(regal:*)", "Bash(curl:*)",
    "Bash(cat:*)", "Bash(ls:*)", "Bash(grep:*)", "Bash(sed:*)", "Bash(awk:*)",
    "Bash(head:*)", "Bash(tail:*)", "Bash(wc:*)", "Bash(find:*)",
    "Bash(python:*)", "Bash(cp:*)", "Bash(mkdir:*)", "Bash(echo:*)",
    "Bash(test:*)", "Bash(jq:*)",
)

# A step whose transcript ENDS on one of these did no work: it stopped to ask.
ASKED_PATTERNS = re.compile(
    r"(shall|should) i proceed|do you want me to|let me know if|"
    r"awaiting (your )?(approval|confirmation)|"
    r"(need|require) (your )?(approval|permission)|permission to (run|execute)",
    re.I,
)
# `claude` exits 0 even when the slash command was never recognised.
UNKNOWN_CMD = re.compile(r"^\s*(unknown command|no such command)", re.I | re.M)


# ---------------------------------------------------------------------------
# The per-example overlay: what changes when you point the runner at another
# example. Handed to every subprocess as env=, so .env is never written.
# ---------------------------------------------------------------------------
NO_SESSION_CONFIG = "references/__no_session_config__.json"


def overlay_for(root: Path, example: str) -> dict[str, str]:
    """The complete set of owned settings for `example`."""
    rel = f"examples/{example}/"
    overlay = {
        "TARGET_AGENT_PATH": rel,
        "GUIDANCE_FILE": f"{rel}smith/guidance.txt",
        "SYSTEM_VAR_FILE": f"{rel}smith/system_vars.json",
        "PROMPTFOO_CONFIG_FILE": f"{rel}smith/promptfooconfig.yaml",
        "PROMPTFOO_OUTPUT_FILE": f"{rel}smith/redteam.yaml",
        "AGENT_URL": f"http://localhost:{AGENT_PORT}",
        "SESSION_CONFIG_FILE": NO_SESSION_CONFIG,
    }

    if standalone_mcp_script(example):
        # RagChatbot needs a standalone SSE server on :8000.
        overlay["MCP_TRANSPORT"] = "sse"
        overlay["MCP_URL"] = f"http://localhost:{MCP_PORT}/sse"
    elif example in HTTP_TOOL_DEFS:
        # hr-agent serves its tool definitions over plain http.
        overlay["MCP_TRANSPORT"] = "http"
        overlay["MCP_URL"] = f"http://localhost:{AGENT_PORT}/tool_definitions"
    elif (root / "examples" / example / "server.py").is_file():
        overlay["MCP_TRANSPORT"] = "stdio"
        overlay["MCP_COMMAND"] = "python"
        overlay["MCP_ARGS"] = "server.py"
        overlay["MCP_CWD"] = f"examples/{example}/"

    return overlay
