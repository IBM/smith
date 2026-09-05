# HR Agent — Smith Example

An HR copilot agent with an HTTP/JSON-RPC MCP tool server exposing
compensation, directory, repo-search, and email tools. The agent
speaks A2A on the inbound side and calls MCP `tools/call` on the
outbound side; this example demonstrates the full Smith workflow
(policy creation, test generation, testing, and refinement) plus the
security-grounded guidance analysis skill against a deliberately
sparse `smith/guidance.txt`.

## MCP Tools

The MCP server ([`server.py`](server.py)) is a FastAPI app that speaks
MCP-shaped JSON-RPC 2.0 over HTTP. It listens on `POST /mcp` and
exposes five tools:

| Tool | Description |
|------|-------------|
| `get_compensation` | Return salary, bonus, department, and optionally SSN for an employee. `include_ssn=true` returns the SSN and is only permitted for callers with the `view_ssn` permission; otherwise the SSN is redacted before tool execution. |
| `display_compensation` | Display a compensation band summary for an employee (band only, no salary figures). |
| `get_directory` | List the employee directory, optionally filtered by department. |
| `send_email` | Send an email. Must not carry SSNs or data the caller accessed earlier as sensitive in the same session. |
| `search_repos` | Search internal GitHub Enterprise repositories by name and visibility. Access is limited to repositories the caller's team is authorized for. |

## Starting the Agent

**Note:** Before starting a new example, run the clean script from the
repo root to remove generated artifacts left over from a previous
example. It clears everything under `references/` (preserving
`test_case_template.json`) and the generated ARES assets:

```bash
bash scripts/clean_generated.sh
```

Prerequisites: Ollama (or another OpenAI-compatible LLM endpoint)
running locally with the model pulled.

```bash
cd examples/hr-agent
ollama pull qwen3.5
pip install -r requirements.txt
```

Start the MCP tool server (in a separate terminal with the same
virtualenv):

```bash
uvicorn server:app --host 0.0.0.0 --port 9100
```

Start the agent:

```bash
python agent.py
```

The agent exposes:
- `POST /chat` — full agentic chat (executes tools via MCP)
- `POST /extract_tool_call` — extracts intended tool call without executing it

Under the hood the agent also speaks A2A `message/send` on the
inbound side — the containerized deployment routes through an
authbridge-cpex sidecar, but the local run connects directly.

Default configuration:
- Agent URL: `http://localhost:8001`
- MCP transport: `http`
- MCP endpoint: `http://localhost:9100/mcp`

## Smith Files (`smith/` directory)

| File | Description |
|------|-------------|
| `guidance.txt` | Natural language policy rules — this example ships with a **deliberately sparse** two-line guidance file about internal-repo access. Source of truth for policy generation. Use it as-is, or run the security-grounded guidance analysis workflow (Step 1.2 below) to enrich it. |
| `system_vars.json` | System variables available in the agent session (`user_name`, `roles`, `permissions`, `has_approval`). Maps to `input.extensions.subject.*` in the OPA policy. |
| `tool_definitions.json` | MCP tool definitions with parameters. Ships pre-generated here because `smith --flag get_mcp_parameter` currently expects a `/tool_definitions` endpoint that this HTTP MCP server doesn't yet expose — see the note under **Smith CLI Commands** below. Maps to `input.arguments.*`. |
| `promptfooconfig.yaml` | Promptfoo configuration for red-team test generation against this agent. Can be auto-generated with `smith --flag generate_promptfoo_config` (LLM + deterministic — review output before use). |
| `redteam.yaml` | Promptfoo red-team output file. |
| `policy_generated.rego` | The OPA policy generated from `guidance.txt`. |
| `smith_outputs/` | Intermediate results generated when running Smith (see below). |

Also present at the example root:
- `whole_guidance.txt` — a longer 7-line reference version of the
  guidance (compensation records, SSN visibility, repo search per
  team, email SSN block, compensation-adjustment approval
  thresholds). Use it as ground truth when comparing what the
  security-analysis workflow surfaces against what a fuller ruleset
  would look like.

### `smith/smith_outputs/` (generated artifacts)

`smith/smith_outputs/` in this example is organised per tool (one
subdirectory per MCP tool), each containing that tool's Smith
intermediates:

- `get_compensation/`
- `search_repo/`
- `send_email/`

Under each you may find `tool_definitions.json`, `policy_generated.rego`,
`policy_revised.rego`, `bypass_report.json`, etc., depending on which
CLI stages you have run.

## Smith CLI Commands

Make sure your `.env` points to this example:

```
TARGET_AGENT_PATH=examples/hr-agent/
GUIDANCE_FILE=examples/hr-agent/smith/guidance.txt
SYSTEM_VAR_FILE=examples/hr-agent/smith/system_vars.json
PROMPTFOO_CONFIG_FILE=examples/hr-agent/smith/promptfooconfig.yaml
PROMPTFOO_OUTPUT_FILE=examples/hr-agent/smith/redteam.yaml
MCP_TRANSPORT=http
MCP_URL=http://localhost:9100/mcp
```

Confirm with:

```bash
smith --flag get_current_agent
```

**Note on `smith --flag get_mcp_parameter`:** Smith's `http`
transport expects a `/tool_definitions` endpoint that returns tool
defs in Smith's shape ([extract_tools.py:122-124](../../src/smith/policy_generation/extract_tools.py#L122-L124)).
This example's [`server.py`](server.py) only exposes `/mcp`
(JSON-RPC 2.0 `tools/call`) and `/healthz`, so `get_mcp_parameter`
won't work out-of-the-box against a running hr-agent server. The
shipped [`smith/tool_definitions.json`](smith/tool_definitions.json)
is what downstream Smith stages use.

## How to Test Smith (End-to-End Workflow)

### Step 1: Generate Policy and Test Cases

#### Step 1.1: Generate Policy

Ask your coding agent to use skill Smith to generate an OPA policy
from the guidance file.

#### Step 1.2: (Recommended for this example) Security-Grounded Guidance Analysis

`smith/guidance.txt` here is intentionally sparse — two lines about
internal-repo access. Running the OWASP-grounded analysis before
policy generation surfaces the compensation/SSN/email rules that a
full ruleset should include (compare with `whole_guidance.txt` at
the example root). Same workflow as `SKILL.md`'s "Create an OPA
Policy with a Security-Grounded Guidance Analysis" entry.

Ask your coding agent:

> Create an OPA policy for this MCP server with a security-grounded guidance analysis.

The agent asks whether to run **Gated** (pause after each step) or
**Autonomous** (Steps A–D back-to-back with one final review), then
produces four artifacts under `smith/guidelines-security-analysis/`:

| Step | Output |
|------|--------|
| A — Architecture Analysis | `smith/guidelines-security-analysis/architecture.md` |
| B — Policy Guidance Questionnaire | `smith/guidelines-security-analysis/policy_guidance_questionnaire.md` |
| C — Threat Model against OWASP Top 10 for Agentic AI Security | `smith/guidelines-security-analysis/threat_model.md` |
| D — Enforcement Mapping | `smith/guidelines-security-analysis/owasp_policy_guidelines.md` + `smith/guidance_updated.txt` |

Review `smith/guidance_updated.txt` when the workflow completes.
When you're satisfied, tell the agent to merge — Step E appends
`smith/guidance_updated.txt` to `smith/guidance.txt` (preserving your
existing content byte-for-byte) and continues into Policy Creation
automatically.

#### Step 1.3: Generate Test Cases

To generate test cases, there are three options:

1. You can ask Smith to generate test cases after it finishes policy generation.

2. You can generate test cases via CLI when Smith is generating the policy:

```bash
smith --flag generate_promptfoo_config # optional: auto-generate promptfoo config (LLM + deterministic — review before use)
smith --flag test_generation          # guidance-targeted cases
smith --flag bypass_case_generation    # optional: policy-bypass cases (requires an existing, non-empty policy)
smith --flag test_case_evaluation      # optional, does not affect results
smith --flag test_case_translation     # shared; translates all cases, skipping any already translated
```

3. You can reuse existing test cases (skip the test case generation).
   For each example, generated test cases live in `./smith/test_cases/`
   for reuse. To use them, copy them to `references/test_cases/` and
   overwrite existing test cases.

### Step 2: Test the Policy

Run policy testing (via CLI or ask Smith):

```bash
smith --flag policy_testing
```

### Step 2.5: Cross-Validation (if needed)

- **If 0 test cases or 100% failure** — the policy has
  structural/syntax issues. Ask Smith to cross-validate the policy
  (it will follow `opa_policy/policy_cross_validation/policy_cross_validation.md`).
- **If mixed pass/fail** — some test case labels may be wrong. Ask
  Smith to cross-validate test cases before running the refinement
  loop (it should follow `test_generation/cross_validate.md`). This
  step can be time consuming depending on the number of failed test
  cases.

### Step 3: Improve the Policy

If Smith identifies failed test cases, ask it to:

1. **Fix failed test cases** — patch the policy to handle cases that should be denied but are currently allowed.
2. **Remove duplication** — eliminate redundant rules with overlapping logic.
3. **Fix formatting issues** — resolve Regal lint warnings and `opa fmt` differences.

Smith follows its refinement workflow: patch → regal format →
deduplication, running tests after each change.
