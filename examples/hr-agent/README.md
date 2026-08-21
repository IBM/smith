# HR Agent — Smith Example

For reproducibility: The per-tool artifacts this
produces live under `smith/smith_outputs/{get_compensation,search_repo,send_email}/`.

---

## What has been changed in this agent

The agent (`agent.py`) speaks two protocols from a single codebase now:

- **A2A (original, no change)** (`python agent.py` / `main()`) 
- **A Smith HTTP shim (Added)** (`uvicorn agent:app`) — the two endpoints every Smith
  example exposes:
  - `POST /chat` — runs a full agent turn (LLM + tool execution), used by promptfoo.
  - `POST /extract_tool_call` — returns the model's intended `{tool_name, arguments}`
    **without executing it** (used by `smith --flag test_case_translation`).

### New access-control guidance

We translated the test cases into seven
rules across several tools (`whole_guidance.txt`):

```
1. Only HR employee can access compensation records (e.g., salary)
2. Only employees with `view_ssn` permission can view SSNs in compensation records. SSNs must be redacted if the HR does not have view_ssn.
3. Only employees in engineer or security team can search repositories. 
4. Engineers can only read internal repos. Security team member can search both internal and external repo.
5. Employees cannot send SSNs through email. Email containing SSNs must be blocked
```

`smith/guidance.txt` (the file `.env`'s `GUIDANCE_FILE` currently points at)
holds a slice of selected guidances, this is the output of the
Guidance Classifier described below.

---

## Prerequisites

**1. Installation of Skills**

```bash
cd ./bob/skills/
git clone <smith's most recent version>
```

Place the entire `smith` folder under the `skills/` or `plugin/` directory of your code agent (Claude Code, Bob, Aider, etc.). The coding agent automatically recognizes Smith as an open skill.

**2. Python environment**

```bash
cd ./smith
python -m venv .venv
source .venv/bin/activate
```

**3. Ares environment (optional in this example)**
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
**4. Promptfoo**.

```bash
npm install -g promptfoo
# To disable promptfoo remote connection:
export PROMPTFOO_DISABLE_TELEMETRY=1
export PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION=true
export PROMPTFOO_DISABLE_SHARING=true
```

---

## Install Smith CLI

Smith uses [uv](https://docs.astral.sh/uv/) for package management. From the repo root:

```bash
make install        # creates a uv venv and installs Smith (editable) + dev tools
```

Or install directly (dependencies are declared in `pyproject.toml`):

```bash
uv pip install -e .   # or: pip install -e .
```

This installs the `smith` CLI command.

## Configure `.env` for the HR agent

Copy the template and point Smith at this example:

```bash
cp .env_template .env
```

Set these values in `.env` (paths are relative to `BASE_URL`, which is the
absolute path to the skill folder **with a trailing slash**):

```dotenv
# --- where the skill lives ---
BASE_URL=/absolute/path/to/.bob/skills/smith/

# --- LLM used by Smith's own pipelines ---
OPENAI_API_KEY=<your key>
OPENAI_BASE_URL=<your LLM endpoint>
MODEL_SONNET=<model used across pipelines>

# --- the target agent (the HR agent's Smith shim) ---
AGENT_URL=http://localhost:9000

# --- point Smith at THIS example ---
TARGET_AGENT_PATH=examples/hr-agent/
GUIDANCE_FILE=examples/hr-agent/smith/guidance.txt
SYSTEM_VAR_FILE=examples/hr-agent/smith/system_vars.json
PROMPTFOO_CONFIG_FILE=examples/hr-agent/smith/promptfooconfig.yaml
PROMPTFOO_OUTPUT_FILE=examples/hr-agent/smith/redteam.yaml

# --- MCP transport ---
# hr-agent exposes its tool definitions directly at GET /tool_definitions, so the
# http transport just fetches that endpoint (no MCP server needed).
MCP_TRANSPORT=http
MCP_URL=http://localhost:9000/tool_definitions
```

---

## Start the agent and MCP server

Install the agent's dependencies and start Ollama with the model pulled:

```bash
cd examples/hr-agent
pip install -r requirements.txt
ollama pull qwen3.5
```

Start the MCP server (separate terminal):

```bash
uvicorn server:app --host 0.0.0.0 --port 9100
```

Start the agent (separate terminal):

```bash
uvicorn agent:app --host 0.0.0.0 --port 9000
```
---

## Run Smith (Refer to demo video if there is any problem)

### Select guidances

Launch the UI (serves on **port 8110**):

```bash
smith --flag classify_guidance
```

Then open `http://127.0.0.1:8110/` — in VS Code, `Cmd+Shift+P → open browser`.

**What you do in the UI:**

1. **Upload** a guidance document (e.g. `whole_guidance.txt`). The file on disk is never modified.
2. **Browse lines grouped by tool**, select the lines you want, and **combine** them into the guidance text for the tool(s) you're targeting.
3. Click **Reset**, to setup smith for selected guidancies.

Run the normal Smith workflow (below) against it, then repeat the Classifier for the next
tool. The results for each tool are what you see saved under
`smith/smith_outputs/get_compensation/`, `.../search_repo/`, and `.../send_email/`
(each with its own `guidance.txt`, `tool_definitions.json`, `policy.rego`, and a
CPEX-translated `policy_cpex.rego`).

---

### End-to-end Smith workflow

1. Ask smith to generate an opa policy for your target agent. 
2. Ask smith to generate test cases. 
3. Follow the instruction from smith, run `smith --flag generate_promptfoo_config` to generate promptfoo config for test case generation.
4. Ask smith to generate both kinds of test cases. 
5. (optional) evaluate test case generation quality.
6. Ask smith to test the policy after you have both test cases and policy.
7. Cross validate test cases and policy. 
8. Ask smith to patch, lint, deduplicate policy. 
9. Ask smith to translate policy into cpex format.
10. Ask smith to save copies, give smith the target save path.

## Deploying the generated policy (CPEX / OPA gateway)

`policy-opa-2.yaml` shows the end goal: the per-tool Rego policies Smith
generates (`smith_outputs/*/policy.rego`) are deployed as an in-process OPA PDP
on a policy gateway. Each tool route queries its package —
`data.compensation.allow`, `data.search_repo.allow`, `data.send_email.allow`. 