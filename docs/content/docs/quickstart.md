---
title: "Quick Start"
weight: 2
---

# Quick Start

## Prerequisites

- Python 3.11+
- [OPA](https://www.openpolicyagent.org/) + [Regal](https://github.com/StyraInc/regal#getting-started) (policy testing / linting; OPA runs in Docker for the scorecard)
- [ARES](https://github.com/IBM/ares) (red-teaming framework) — **optional**
- [Promptfoo](https://www.promptfoo.dev/) (red-teaming framework) — **optional**

Which red-teaming tools to use is controlled by the `ATTACK_TOOLS` environment variable (see [Configuration]({{< relref "/docs/configuration" >}})). Set to `none` to skip red-teaming entirely.

## Make Smith Discoverable as a Skill

Smith is an **agent skill**, not a tool you drive by hand. To use it, your coding agent must be able to discover it — place (or symlink) the Smith folder inside your agent's skills/plugins directory so it is picked up as an open skill. For example:

```bash
# Example layout — put Smith where your agent looks for skills
~/.bob/skills/smith        # (this is what BASE_URL should point at)
```

The exact location depends on your agent. Once Smith lives under the skills directory, the agent loads `SKILL.md` and exposes Smith's capabilities.

## Install Smith

Smith uses [uv](https://docs.astral.sh/uv/) for package management. From the repo root:

```bash
make install        # creates a uv venv and installs Smith (editable) + dev tools
```

Or install directly (dependencies are declared in `pyproject.toml`):

```bash
uv pip install -e .   # or: pip install -e .
```

This installs the `smith` CLI command.

## Install ARES (optional)

ARES installs into `src/smith/test_generation/ares/` with its own `.venv`:

```bash
cd src/smith/test_generation/ares
python -m venv .venv
source .venv/bin/activate
curl https://raw.githubusercontent.com/IBM/ares/refs/heads/main/install.sh | bash
ares install-plugin ares-autodan
ares install-plugin ares-human-jailbreak
ares install-plugin ares-garak
deactivate
# Setup ares configuration
cp ../ares_config/qwen-owasp-llm-01.yaml ./example_configs
cp ../ares_config/human_jailbreaks.json ./assets
export ARES_HOME=/absolute/path/to/smith/src/smith/test_generation/ares
# Switch back to the original Python environment
cd ../../../../
source .venv/bin/activate
```

## Install Promptfoo (optional)

```bash
npm install -g promptfoo
# To disable promptfoo remote connection:
export PROMPTFOO_DISABLE_TELEMETRY=1
export PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION=true
export PROMPTFOO_DISABLE_SHARING=true
```

## Configuration

```bash
cp .env_template .env
```

Fill in the values in `.env`. See the [Configuration]({{< relref "/docs/configuration" >}}) page for full details.

## Start the Target Agent

Smith talks to a **running** target agent (for `/chat` and `/extract_tool_call`) and to its MCP server (to extract tool definitions). Start both before running any `smith` flag.

Each example under `examples/<agent>/` ships its own `agent.py` (a FastAPI app), `server.py` (the MCP server), and a `requirements.txt`. Using `call-for-papers-mcp` as an example:

```bash
cd examples/call-for-papers-mcp
pip install -r requirements.txt

# Start the agent server on the port AGENT_URL points to (default 9000).
uvicorn agent:app --port 9000
```

This example's agent spawns its MCP server itself over stdio, so you do not start the MCP server separately. Match `.env` accordingly:

```
MCP_TRANSPORT=stdio
MCP_COMMAND=python
MCP_ARGS=server.py
MCP_CWD=examples/call-for-papers-mcp
```

For an SSE-based MCP server instead, set `MCP_TRANSPORT=sse` and `MCP_URL=http://localhost:8000/sse`.

## Chat with Smith

You don't invoke the `smith` CLI directly — you talk to your agent, and it orchestrates the `smith` pipeline stages for you.

1. **Ask your agent to list its skills.** It will show `smith` along with what it can do: create policies, generate and evaluate test cases, test policies, and automatically refine them.
2. **Chat with Smith in natural language**, e.g.:
   - "Create an OPA policy from my guidance."
   - "Generate test cases for this policy."
   - "Test the policy and tell me what fails."
   - "Improve the policy to fix the failing cases."

The agent reads the relevant guide under Smith's skill folder and runs the underlying stages (`smith --flag get_mcp_parameter`, `test_generation`, `test_case_evaluation`, `policy_testing`, …) on your behalf.

## End-to-End Workflow

Each example under `examples/<agent>/` has its own **`README.md`** that walks through the complete workflow end to end — starting the agent and MCP server, pointing `.env` at that example, and driving the full create → generate → test → refine lifecycle with Smith. Follow the README for the example you're using:

- [`examples/call-for-papers-mcp/README.md`](https://github.com/IBM/smith/blob/main/examples/call-for-papers-mcp/README.md)
- [`examples/car-price-mcp-main/README.md`](https://github.com/IBM/smith/blob/main/examples/car-price-mcp-main/README.md)
- [`examples/RagChatbot_MCPServer/README.md`](https://github.com/IBM/smith/blob/main/examples/RagChatbot_MCPServer/README.md)
