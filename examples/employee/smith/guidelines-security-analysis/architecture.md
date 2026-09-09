# Architecture Analysis — Enterprise Employee Hub

**Target agent path:** `examples/employee/`
**Generated:** 2026-09-04
**Workflow step:** A — Architecture Analysis

---

## 1. Source Files Examined

| File | Role |
|---|---|
| `examples/employee/agent.py` | LangGraph ReAct agent, FastAPI host, `build_system_prompt()` |
| `examples/employee/server.py` | FastMCP server, 33 `@mcp.tool()` functions |
| `examples/employee/smith/tool_definitions.json` | Authoritative tool parameter shapes (33 tools) |
| `examples/employee/smith/system_vars.json` | Session variables injected as `input.extensions.subject.*` |
| `examples/employee/smith/guidance.txt` | Natural-language policy (80 lines) |

---

## 2. Architecture Layers

```
┌──────────────────────────────────────────────────────────┐
│  Layer 5 — Client (HTTP)                                 │
│  POST /chat  { question, user_profile }                  │
│  POST /extract_tool_call  { question, user_profile }     │
└────────────────────┬─────────────────────────────────────┘
                     │ FastAPI (agent.py :9000)
┌────────────────────▼─────────────────────────────────────┐
│  Layer 4 — Agent Layer                                   │
│  LangGraph ReAct agent (create_react_agent)              │
│  build_system_prompt() — embeds user_profile key/values  │
│  verbatim into system prompt as Markdown list items      │
└────────────────────┬─────────────────────────────────────┘
                     │ tool calls (MCP/stdio)
┌────────────────────▼─────────────────────────────────────┐
│  Layer 3 — OPA Enforcement Point                         │
│  PEP intercepts every tool call before execution         │
│  input.action = tool name                                │
│  input.args.* = tool arguments                           │
│  input.extensions.subject.* = session variables          │
└────────────────────┬─────────────────────────────────────┘
                     │ allow/deny
┌────────────────────▼─────────────────────────────────────┐
│  Layer 2 — MCP Server (server.py)                        │
│  FastMCP "enterprise-employee-hub"                        │
│  33 @mcp.tool() wrappers over api.* functions            │
│  _safe() converts ValueError to {"error": ...}          │
│  No authorization of its own                             │
└────────────────────┬─────────────────────────────────────┘
                     │ Python API calls
┌────────────────────▼─────────────────────────────────────┐
│  Layer 1 — Data Layer                                    │
│  SQLite database (via db.get_connection())               │
│  api/ modules: employees, org, departments,              │
│  personal, leave, holidays_api                           │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Trust Boundaries

### 3a. Trust Boundary Table

| Boundary | Crossing | Source of values | Disposition | Notes |
|---|---|---|---|---|
| TB-1: Client → Agent | `user_profile` JSON dict | Caller-supplied; **self-reported** | The values are embedded verbatim into the system prompt via `build_system_prompt()` as Markdown list items. The LangGraph agent then reflects these into `input.extensions.subject.*` for OPA. | No authentication; any caller can supply any `user_id`, `department`, or `organization`. |
| TB-2: Agent → OPA PEP | `input.action`, `input.args.*`, `input.extensions.subject.*` | Agent constructs tool call from LLM output; subject from user_profile | Acts on / Echoed | The OPA policy is the **only** enforcement layer. |
| TB-3: OPA PEP → MCP | Allowed tool call with original args | Passed through if allow=true | Acts on | MCP server performs no additional authorization. |
| TB-4: MCP → SQLite | API function call with parameters | Derived from tool args | Acts on | DB enforces uniqueness/FK constraints only; no access control. |

### 3b. Tool Argument Disposition

For every tool, each argument is either **Acts on** (the tool writes, reads, or acts on the value as real data) or **n/a** (subject field — does not appear in tool parameters).

| Tool | Key arg(s) | Disposition |
|---|---|---|
| `add_employee` | `email`, `role`, `organization`, `department_id`, `manager_id`, `salary` | Acts on |
| `update_employee` | `user_id`, `email`, `role`, `organization`, `salary` | Acts on |
| `get_employee` | `user_id` | Acts on |
| `list_employees` | `department_id`, `manager_id`, `country_code` | Acts on |
| `get_manager` | `user_id` | Acts on |
| `get_direct_reports` | `user_id` | Acts on |
| `get_reporting_chain` | `user_id` | Acts on |
| `add_department` | `name` | Acts on |
| `update_department` | `department_id`, `name` | Acts on |
| `get_department` | `department_id` | Acts on |
| `list_departments` | (none) | — |
| `set_passport` | `user_id`, `issue_date`, `expiry_date` | Acts on |
| `update_passport` | `user_id`, `issue_date`, `expiry_date` | Acts on |
| `get_passport` | `user_id` | Acts on |
| `set_visa` | `user_id`, `issue_date`, `expiry_date` | Acts on |
| `update_visa` | `user_id`, `issue_date`, `expiry_date` | Acts on |
| `get_visa` | `user_id` | Acts on |
| `set_emergency_contact` | `user_id`, `relationship` | Acts on |
| `update_emergency_contact` | `user_id`, `relationship` | Acts on |
| `get_emergency_contact` | `user_id` | Acts on |
| `set_bank_account` | `user_id`, `account_number` | Acts on |
| `update_bank_account` | `user_id`, `account_number` | Acts on |
| `get_bank_account` | `user_id` | Acts on |
| `set_leave_allotment` | `user_id`, `leave_type`, `annual_days` | Acts on |
| `get_leave_allotments` | `user_id` | Acts on |
| `create_time_off_request` | `user_id`, `leave_type`, `start_date`, `end_date` | Acts on |
| `update_time_off_status` | `request_id`, `status` | Acts on |
| `get_time_off_request` | `request_id` | Acts on |
| `list_time_off_requests` | `user_id`, `status` | Acts on |
| `get_leave_balance` | `user_id`, `year` | Acts on |
| `add_holiday` | `country_code`, `holiday_date`, `name` | Acts on |
| `list_holidays` | `country_code` | Acts on |
| `delete_holiday` | `holiday_id` | Acts on |

**Subject fields** (`input.extensions.subject.*`): `user_id`, `user_name`, `department`, `organization` — these come from `user_profile`, not from tool parameters; Disposition = n/a for all tools.

---

## 4. Data Flow

```
POST /chat
  └─► build_system_prompt(user_profile)
        │  injects: user_id, user_name, department, organization
        │  verbatim into system prompt as: "- **key**: value"
        ▼
  LangGraph ReAct agent
        │  LLM selects tool + constructs args
        ▼
  OPA PEP (pre-execution intercept)
        │  input = { action, args, extensions: { subject } }
        │  allow := true/false
        ▼  (allow=true only)
  FastMCP server.py
        │  _safe(api_fn, *args)
        ▼
  SQLite via api.* modules
        │  returns dict or {"error": ...}
        ▼
  agent surfaces result to user
```

**Key security implication:** The LLM constructs `input.args.*` from the natural-language request. A prompt-injection payload in the user's question could steer the LLM to choose a different tool or supply different `user_id` values than the user actually owns. The only enforcement checkpoint is the OPA PEP — there is no server-side argument validation beyond what OPA enforces.

---

## 5. Enforcement Points

| Point | Location | Mechanism | Coverage |
|---|---|---|---|
| EP-1 (Primary) | OPA PEP at Agent→MCP boundary | `input.action` + `input.args.*` + `input.extensions.subject.*` evaluated against policy | Pre-execution; blocks tool call before DB write |
| EP-2 (DB constraints) | SQLite layer | Unique constraints on email; FK constraints | Post-execution; narrow data-integrity only |
| EP-3 (API layer) | `api/` modules (ValueError → {"error"}) | ValueError on invalid leave_type, date logic | Post-execution; narrow format validation only |

**The OPA policy is the sole access-control enforcement layer.** EP-2 and EP-3 are data-integrity guards, not access control.

---

## 6. Blind Spots

The following guidance.txt rules **cannot be enforced** at the OPA PEP layer because the required data is not present in `input.action`, `input.args.*`, or `input.extensions.subject.*` at invocation time:

| # | Rule from guidance.txt | Missing input | Impact |
|---|---|---|---|
| BS-1 | Manager may view direct reports' data | Target employee's `manager_id` is a DB field; not in `input.args.*` | No enforcement at OPA layer |
| BS-2 | Non-IBM users blocked from viewing IBM employee data | Target employee's `organization` is a DB field; not passed as OPA input | Cross-user org gate not enforceable |
| BS-3 | Salary may be updated only by HR or the employee's direct manager | Manager relationship requires DB lookup | Safe default (HR-or-self) enforced; manager exception is a blind spot |
| BS-4 | Passport/visa expiry date must be >6 months from update date | Current wall-clock date is not in OPA input | Date-span check not enforceable; issue_date < expiry_date check is enforceable |
| BS-5 | Home address update only within own current country | Employee's current country is a DB field | Not enforceable at OPA layer |
| BS-6 | Blacklist check blocks passport update | No `blacklist` field in `system_vars.json` or tool parameters | Not enforceable; requires new system variable |
| BS-7 | Emergency contact must reside in same area as employee | Employee's location is a DB field | Not enforceable at OPA layer |
| BS-8 | Time-off request: leave balance must be sufficient | Leave balance requires computing `annual_days − used_days` from DB | Not enforceable at OPA layer |
| BS-9 | Paternity leave approved only if baby details appear in conversation | Conversation history is not in OPA input | Agent-layer gate required |
| BS-10 | Requesting employee may set status only to Pending | Requires mapping `request_id` → requester `user_id` (DB lookup) | Partial enforcement only (can block non-HR from Approved/Denied) |
| BS-11 | DB write confirmation before writes | Conversation history not in OPA input | Agent-layer gate required |
| BS-12 | User delete confirmation phrase | Conversation history not in OPA input | Agent-layer gate required |
| BS-13 | Agent makes one tool call at a time | LLM reasoning behavior | Agent-layer / structured output required |

---

## 7. Undeclared Fields

The following fields appear in guidance.txt rules but are **not declared** in `system_vars.json` and are **not arguments** of the governing tools:

| Field | Appears in guidance.txt rule | Governing tool(s) | Status |
|---|---|---|---|
| `blacklist` | "An employee on the blacklist may not update their passport information." | `update_passport` | Not in `system_vars.json` or `update_passport` parameters — **enforcement impossible without adding this to system_vars.json** |
| `Manager` (as subject role) | "A Manager may view direct reports' data" | `get_employee`, personal-record tools | `department` values in system_vars.json are Corporate Leadership / Engineering / Product / HR / Finance — no "Manager" value; manager status requires DB lookup of `manager_id` |
| Target employee `organization` | "Users outside IBM are blocked from viewing IBM employee data" | `get_employee`, personal-record tools | The tool only receives `user_id`; target org is in the DB, not in `input.args.*` |

---

## 8. Summary

- **Trust model:** All `input.extensions.subject.*` values are self-reported (from `user_profile`). There is no cryptographic authentication anywhere in the stack.
- **Attack surface:** TB-1 (client → agent) is the primary injection point; a caller can supply any `user_profile` values. The OPA policy must not trust these without appropriate constraints.
- **Sole enforcement layer:** OPA PEP at Agent→MCP boundary. The MCP server performs no authorization.
- **Enforceable rules:** Role-based tool gates (HR-only), ownership checks via `args.user_id == subject.user_id`, salary positivity, email domain validation, time-off ownership and span, date ordering on passport/visa, leave-view ownership, time-off status role constraints.
- **Gap:** 13 blind spots, 3 undeclared fields — these are recorded here as load-bearing findings for Step D (Enforcement Mapping).
