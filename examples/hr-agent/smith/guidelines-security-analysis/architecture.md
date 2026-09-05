# Architecture Analysis — HR Agent

## 1. System Overview

The HR Agent is a multi-layer agentic system that allows users (via HTTP/A2A) to interact with HR data through a natural-language agent backed by an MCP tool server. The system exposes 6 tools that act on employee compensation records, directory data, repository access, and email communication.

OPA policy enforcement is applied at the Agent→MCP boundary (Layer 2→Layer 4), intercepting all tool calls before execution.

---

## 2. Layer Map

| # | Layer | Component | File | Description |
|---|-------|-----------|------|-------------|
| 1 | A2A / HTTP API | FastAPI entrypoints | `agent.py` | Receives inbound requests via `/chat` (Smith shim) and A2A path. Validates that at least one of `X-User-Token` or `Authorization` is present on the A2A path; Smith shim sets headers to empty strings. |
| 2 | Agent Loop | `HRAgent` | `agent.py` | LiteLLM completion loop. Holds per-session conversation history (`_histories[session_id]`). Dispatches tool calls via `call_tool()`. Forwards `X-User-Token`, `Authorization`, `X-Session-Id` to MCP server. |
| 3 | Sidecar (authbridge-cpex) | Forward proxy | *(absent locally)* | In K8s: Cedar PDP, SSN redaction, PII scan, session taint. **Not present in local/Smith runs.** All sidecar mitigations are unavailable at this intercept layer. |
| 4 | MCP Tool Server | FastAPI JSON-RPC | `server.py` | Receives tool calls on `:9100/mcp`. Routes to tool implementations. No authorization at this layer — executes any tool call received. |
| 5 | Tool Implementation | Python functions | `server.py` | 6 tool functions operating on in-memory fixtures: `EMPLOYEES` dict, `SENT_EMAILS` list, `REPOS` list. |

**OPA intercept point: Layer 2 → Layer 4** (agent dispatches tool call; OPA evaluates before MCP server receives it).

---

## 3. Tool Inventory and Argument Disposition

| Tool | Parameter | Type | Required | Disposition | Notes |
|------|-----------|------|----------|-------------|-------|
| `get_compensation` | `employee_id` | string | yes | Acts on | Selects which employee record to return |
| `get_compensation` | `include_ssn` | boolean | no (default false) | Acts on | If true, SSN field is added to response |
| `display_compensation` | `employee_id` | string | yes | Acts on | Selects which employee to show band summary for |
| `get_directory` | `department` | string | no (default "") | Acts on | Filters returned employee list by department |
| `send_email` | `to` | string | yes | Acts on | Email recipient — written to SENT_EMAILS |
| `send_email` | `subject` | string | yes | Acts on | Email subject — written to SENT_EMAILS |
| `send_email` | `body` | string | yes | Acts on | Email body — written to SENT_EMAILS |
| `search_repos` | `repo_name` | string | no | Acts on | Substring filter on repo names |
| `search_repos` | `visibility` | string | yes (enum) | Acts on | Filters repos by visibility: `internal`, `public`, `external` |
| `adjust_compensation` | `employee_id` | string | yes | Acts on | Selects which employee's salary to modify |
| `adjust_compensation` | `amount` | integer | yes | Acts on | Dollar amount added directly to `employee["salary"]` |

No arguments are Echoed or Ignored. All parameters influence the tool's execution or output.

---

## 4. Trust Boundaries

| Field Path | Source | Trusted? | Notes |
|------------|--------|----------|-------|
| `input.extensions.subject.roles` | Self-reported by caller via request headers | No | Populated from `X-User-Token` or `Authorization` headers; no cryptographic verification in local runs |
| `input.extensions.subject.permissions` | Self-reported | No | Same as above |
| `input.extensions.subject.has_approval` | Self-reported | No | String "true" or "false"; trivially spoofable in local runs |
| `input.extensions.subject.user_name` | Self-reported | No | Advisory only |
| `input.args.*` | LLM-generated / caller-supplied | No | All tool arguments are constructed by the LLM from conversation context; not independently verified |
| `EMPLOYEES` / `REPOS` / `SENT_EMAILS` | Server-side in-memory fixtures | Yes | Authoritative data held server-side; not attacker-controlled |
| `SYSTEM_PROMPT` | Hardcoded in `agent.py` | Yes (advisory) | Static, not user-controlled; provides behavioral guidance to LLM but cannot be cryptographically enforced |

**Key risk**: All identity fields (`roles`, `permissions`, `has_approval`) are self-reported. A caller that can set HTTP headers can claim any role or permission. This is the primary enforcement gap when authbridge-cpex is absent.

---

## 5. Guidance Coverage Sweep

Current `guidance.txt` (2 rules):

```
All employees can only access internal repositories.
All employees cannot access other teams' repositories.
```

| Rule # | Rule Text | OPA Field Required | Field Available? | Status |
|--------|-----------|--------------------|------------------|--------|
| 1 | All employees can only access internal repositories. | `input.args.visibility` (via `search_repos`) | Yes — `visibility` is a required enum parameter in `tool_definitions.json` | Enforceable |
| 2 | All employees cannot access other teams' repositories. | `input.extensions.subject.team` | **No** — not declared in `system_vars.json`, not present in any tool schema | Blind spot — cannot fire as stated |

### Undeclared Fields

| Field | Required By | Declared In | Status |
|-------|-------------|-------------|--------|
| `input.extensions.subject.team` | Rule 2 | Nothing | Not declared anywhere — rule cannot be enforced without this field |

### Coverage Gaps (tools with no corresponding guidance rule)

The following tools and risk vectors have no corresponding rule in the current `guidance.txt`:

| Tool / Vector | Risk | Guidance Coverage |
|---------------|------|-------------------|
| `get_compensation` | Any role can retrieve salary + SSN data | None |
| `display_compensation` | Any role can view compensation bands | None |
| `adjust_compensation` | Any role can raise any salary by any amount | None |
| `send_email` | Any role can send email with arbitrary content, including PII/SSN | None |
| `search_repos` (role gate) | Any role can search repos — guidance says "internal only", not "engineers/security only" | Partial (visibility only, no role restriction) |

---

## 6. Enforcement Points Summary

| OPA `input` Path | Available | Populated By |
|------------------|-----------|-------------|
| `input.name` | Yes | Tool name from dispatch |
| `input.args.employee_id` | Yes | Caller |
| `input.args.include_ssn` | Yes | LLM / caller |
| `input.args.amount` | Yes | LLM / caller |
| `input.args.visibility` | Yes | LLM / caller |
| `input.args.department` | Yes | LLM / caller |
| `input.args.to` | Yes | LLM / caller |
| `input.args.subject` | Yes | LLM / caller |
| `input.args.body` | Yes | LLM / caller |
| `input.args.repo_name` | Yes | LLM / caller |
| `input.extensions.subject.roles` | Yes | Identity headers (self-reported) |
| `input.extensions.subject.permissions` | Yes | Identity headers (self-reported) |
| `input.extensions.subject.has_approval` | Yes | Identity headers (self-reported) |
| `input.extensions.subject.team` | **No** | Not declared — see Rule 2 blind spot |

---

## 7. Data Flow Diagram (Text)

```
User / A2A Client
      │
      ▼ HTTP (X-User-Token, Authorization, X-Session-Id)
┌─────────────────────────────┐
│  Layer 1: FastAPI Entrypoint│  agent.py /chat  /a2a
│  (Smith shim or A2A path)   │
└─────────────┬───────────────┘
              │ session_id, message
              ▼
┌─────────────────────────────┐
│  Layer 2: HRAgent Loop      │  LiteLLM completion
│  (LLM + tool dispatch)      │  per-session history
└─────────────┬───────────────┘
              │ tool_name + args
              ▼
         ┌──────────┐
         │  OPA     │  ← INTERCEPT POINT
         │  Policy  │  input = {name, args, extensions}
         └────┬─────┘
              │ allow / deny
              ▼
┌─────────────────────────────┐
│  Layer 3: authbridge-cpex   │  ABSENT in local/Smith runs
│  (Cedar PDP, SSN redact)    │  Cedar, PII scan unavailable
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Layer 4: MCP Tool Server   │  server.py :9100/mcp
│  (FastAPI JSON-RPC)         │  No authz — executes all calls
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Layer 5: Tool Implementation│  EMPLOYEES, REPOS, SENT_EMAILS
│  (Python functions)         │  in-memory fixtures
└─────────────────────────────┘
```
