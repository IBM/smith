---
title: "Configuration"
weight: 3
---

# Configuration

Almost every path in the codebase is assembled from `.env` at runtime via `os.getenv`, not hardcoded. The dominant pattern is `BASE_URL + os.getenv("SOME_PATH")`.

## Setup

```bash
cp .env_template .env
```

## Required — you must fill these in

These variables have **no usable default** and ship as placeholders in `.env_template`. Smith will not run until you replace them with real values:

| Variable | Placeholder in `.env_template` | What to set it to |
|----------|--------------------------------|-------------------|
| `BASE_URL` | `base url of your skill folder` | Absolute path to your skill folder, **with a trailing slash**, e.g. `/path/.bob/skills/smith/` |
| `OPENAI_API_KEY` | `your api key` | API key for your LLM provider |
| `OPENAI_BASE_URL` | `your base url` | Base URL for the LLM API endpoint |
| `MODEL_SONNET` | `GCP/claude-4-sonnet` | Model used across the pipelines — change to your provider's model id |
| `TARGET_AGENT_PATH` | `examples/your_mcp_server/` | Relative path to the target MCP server directory, e.g. `examples/RagChatbot_MCPServer/` |
| `GUIDANCE_FILE` | `examples/your_mcp_server/smith/guidance.txt` | Path to the policy guidance file |
| `SYSTEM_VAR_FILE` | `examples/your_mcp_server/smith/system_vars.json` | Path to the system-variables JSON — test generation fails without it |
| `ARES_HOME` | `path to your ares project directory` | Absolute path to your ARES install. **Only required when `ATTACK_TOOLS` includes `ares`** |

The sections below list these alongside the optional variables in context. Anything without a **Required** default has a working default; change it only if you need to.

## Core Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BASE_URL` | Absolute path to your skill folder, **with a trailing slash** | **Required** — no default |
| `OPENAI_API_KEY` | API key for your LLM provider | **Required** — no default |
| `OPENAI_BASE_URL` | Base URL for the LLM API endpoint | **Required** — no default |
| `MODEL_SONNET` | Model used across the pipelines | **Required** — `GCP/claude-4-sonnet` |
| `TEMP` | Sampling temperature | `0.2` |
| `TOP_P` | Nucleus sampling top-p | `0.9` |

## Target Agent

| Variable | Description | Default |
|----------|-------------|---------|
| `TARGET_AGENT_PATH` | Relative path to the target MCP server directory | **Required** — `examples/your_mcp_server/` |
| `GUIDANCE_FILE` | Path to the policy guidance file | **Required** — `examples/your_mcp_server/smith/guidance.txt` |
| `SYSTEM_VAR_FILE` | Path to the system-variables JSON — test generation fails without it | **Required** — `examples/your_mcp_server/smith/system_vars.json` |
| `AGENT_URL` | URL of the target agent server (must expose `/chat` and `/extract_tool_call`) | `http://localhost:9000` |
| `INFERENCE_MODEL` | Model name for the target agent's LLM (e.g., a RITS model name) | `qwen3.5:latest` |
| `INFERENCE_BASE_URL` | Base URL for the agent's LLM API | `http://localhost:11434/v1` |
| `INFERENCE_API_KEY` | API key for the agent's LLM (use `ollama` for local Ollama) | `ollama` |

## MCP Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_TRANSPORT` | MCP transport type: `sse` or `stdio` | `sse` |
| `MCP_URL` | MCP server URL (SSE transport only) | `http://localhost:8000/sse` |
| `MCP_COMMAND` / `MCP_ARGS` / `MCP_CWD` | MCP launch command, args, and working dir (**stdio transport only**) | *(unset)* |

## Red-Teaming Tools

| Variable | Description | Default |
|----------|-------------|---------|
| `ATTACK_TOOLS` | Comma-separated list of red-teaming tools to run during test generation. Valid values: `ares`, `promptfoo`, `ares,promptfoo`, `none` | `ares,promptfoo` |
| `ARES_HOME` | Absolute path to the ARES installation directory | **Required when `ATTACK_TOOLS` includes `ares`** — no default |
| `PROMPTFOO_CONFIG_FILE` | Promptfoo red-team config path | `examples/your_mcp_server/smith/promptfooconfig.yaml` |
| `PROMPTFOO_OUTPUT_FILE` | Promptfoo generated output path | `examples/your_mcp_server/smith/redteam1.yaml` |
| `OLLAMA_BASE_URL` | Base URL for promptfoo's native ollama provider (no `/v1` suffix). Distinct from the agent's `INFERENCE_BASE_URL` | `http://localhost:11434` |

## Policy Testing

| Variable | Description | Default |
|----------|-------------|---------|
| `BAD_COMMAND_PATH` | Path to allow test cases | `references/test_cases/allow` |
| `BENIGN_COMMAND_PATH` | Path to disallow test cases | `references/test_cases/disallow` |
| `TEST_OUTPUT_DIR` | Where the scorecard harness writes results | `references/scorecard/` |
| `CROSS_VALIDATE_OUTPUT` | Cross-validation report output path | `references/cross_validate_report.json` |

## Test Case Generation

| Variable | Description | Default |
|----------|-------------|---------|
| `BATCH_PROCESSING` | Enable batch processing | `true` |
| `BATCH_SIZE` | Batch size for processing | `10` |
| `CASE_GENERATION_BATCH_SIZE` | Batch size for case generation | `5` |

## Test Case Evaluation

| Variable | Description | Default |
|----------|-------------|---------|
| `CLASSIFY_TOP_N` | Number of top guidance candidates for classification | `3` |
| `TIER2_HIGH_THRESHOLD` | High confidence threshold for Tier 2 | `0.70` |
| `TIER2_LOW_THRESHOLD` | Low confidence threshold for Tier 2 | `0.35` |
| `MAX_LLM_CALLS` | Cap on Tier-3 LLM judge calls (blank = unlimited) | *(unlimited)* |

## Policy Refinement

| Variable | Description | Default |
|----------|-------------|---------|
| `CLUSTER_EPS` | DBSCAN maximum cosine distance between samples | `0.3` |
| `CLUSTER_MIN_SAMPLES` | Minimum samples to form a cluster | `2` |

See `.env_template` for the full list including all intermediate file paths.
