# Architecture: employee (Enterprise Employee Hub)

## Layers

### HTTP API Layer
- File: `agent.py` (`/chat`, `/extract_tool_call`, `/health` endpoints, FastAPI on :9000)
- Role: Accepts inbound HTTP requests carrying an optional `user_profile` dict (JSON body field) alongside the user's natural-language question; builds the system prompt and forwards to the agent layer.
- Inputs: `question` (string), `user_profile` (optional dict — any key/value; caller-supplied).
- Outputs: System prompt string (built from `user_profile`) + user message passed into the LangGraph agent.
- Current enforcement: None — no authentication, no schema validation on `user_profile`, no role check.

### Agent Layer (LangGraph ReAct)
- File: `agent.py` (`build_agent`, `build_system_prompt`, `chat`, `extract_tool_call`)
- Role: Runs a LangGraph ReAct loop — the LLM reads the system prompt (which embeds `user_profile` key/values verbatim), decides which tool to call, and constructs tool arguments. Launches `server.py` over stdio via `MultiServerMCPClient`.
- Inputs: System prompt (containing verbatim `user_profile` entries), user message.
- Outputs: MCP `tools/call` requests over stdio with tool name + arguments.
- Current enforcement: None — `user_profile` contents are appended to the system prompt as plain text; the LLM may or may not respect constraints stated there. No structured enforcement gate between the agent and the MCP server.

### MCP Tool Server
- File: `server.py` (stdio transport, FastMCP)
- Role: Implements 29 tools as `@mcp.tool()` functions; each is a thin wrapper over an `api.*` function. Converts `ValueError` to `{"error": ...}`.
- Inputs: JSON-RPC `tools/call` with `name` and `arguments` over stdio.
- Outputs: Tool result dicts / lists, or `{"error": ...}` on invalid input.
- Current enforcement: Parameter type validation only (FastMCP schema). No authorization, no role checks, no ownership checks.

### API Layer
- File: `api/employees.py`, `api/org.py`, `api/departments.py`, `api/personal.py`, `api/leave.py`, `api/holidays_api.py`
- Role: Business logic — CRUD operations against the SQLite DB; validates data integrity (email domain, leave type enum, date ordering, etc.) and raises `ValueError` on violations.
- Inputs: Python function calls from `server.py`.
- Outputs: Dicts / lists returned from SQLite; `ValueError` on constraint failure.
- Current enforcement: Data integrity only (email domain format, leave type enum, date ordering). No authorization, no ownership checks, no role-based access.

### Database Layer
- File: `db.py`, `employee_hub.db` (SQLite)
- Role: Persistent store for all employee, personal, leave, holiday, and department records.
- Inputs: SQL queries from the API layer.
- Outputs: Raw records.
- Current enforcement: SQLite constraints only (NOT NULL, UNIQUE on email). No application-level authorization.

---

## Trust Boundaries

| Field | Source | Classification |
|---|---|---|
| `user_profile` (all keys) | HTTP caller (JSON body) | Self-reported — no cryptographic verification; caller can supply any key/value |
| `user_profile.user_id` | HTTP caller | Self-reported — caller asserts their own numeric user_id; not verified against any token |
| `user_profile.department` | HTTP caller | Self-reported — caller asserts their department |
| `user_profile.organization` | HTTP caller | Self-reported — caller asserts their organization |
| `user_profile.user_name` | HTTP caller | Self-reported |
| `input.name` (tool name, LLM-chosen) | Agent (LLM) | Self-reported — LLM-generated from user message and system prompt |
| `input.args.user_id` (tool argument) | Agent (LLM) | Self-reported — LLM-chosen from user message; no binding to authenticated identity |
| `input.args.salary` | Agent (LLM) | Self-reported — LLM-chosen |
| `input.args.email` | Agent (LLM) | Self-reported — LLM-chosen |
| `input.args.organization` | Agent (LLM) | Self-reported — LLM-chosen |
| `input.args.expiry_date`, `input.args.issue_date` | Agent (LLM) | Self-reported — LLM-chosen; no clock verification |
| `input.args.start_date`, `input.args.end_date` | Agent (LLM) | Self-reported — LLM-chosen for time-off requests |
| `input.args.status` | Agent (LLM) | Self-reported — LLM-chosen |
| `input.args.home_address`, `input.args.country_code` | Agent (LLM) | Self-reported — LLM-chosen |
| `input.args.leave_type` | Agent (LLM) | Self-reported — LLM-chosen from enum |
| `input.extensions.subject.user_id` | Caller-supplied `user_profile` | Self-reported — the acting user's identity is NOT verified |
| `input.extensions.subject.department` | Caller-supplied `user_profile` | Self-reported |
| `input.extensions.subject.organization` | Caller-supplied `user_profile` | Self-reported |
| `input.extensions.subject.user_name` | Caller-supplied `user_profile` | Self-reported |
| DB record data (manager_id, organization, country, etc.) | SQLite (`employee_hub.db`) | External/untrusted at OPA time — not present in OPA input; requires a runtime DB lookup |

---

## Data Flow

```
HTTP caller
  │  POST /chat  {question, user_profile: {user_id, department, organization, ...}}
  ▼
agent.py HTTP API layer (:9000)
  │  build_system_prompt() — embeds user_profile key/values verbatim into SYSTEM_PROMPT
  ▼
LangGraph ReAct agent
  │  LLM loop: reads system prompt + user message → selects tool + arguments
  ▼  stdio (MultiServerMCPClient)
server.py MCP tool server
  │  _safe(api_fn, *args, **kwargs) → raises ValueError on data errors
  ▼
api/* business logic
  ▼
employee_hub.db (SQLite)
  ▼
Response ← api ← server ({"error":...} or result dict) ← LLM ← HTTP caller
```

---

## Enforcement Points

### Current
- **API layer**: Data integrity only — email domain format, leave type enum, date ordering (issue < expiry), positive salary, valid status transitions (enum values).
- **MCP Tool Server**: FastMCP schema validation (parameter types and required fields).
- **No authorization layer exists anywhere in this system today.**

### Available (OPA-interceptable)
OPA intercepts at the agent → MCP server boundary (tool call pre-execution). Fields present as structured data at that point:

**From `input.extensions.subject.*` (populated from `user_profile`):**
- `input.extensions.subject.user_id` — integer (the acting user's self-reported ID)
- `input.extensions.subject.department` — string: one of `Corporate Leadership`, `Engineering`, `Product`, `HR`, `Finance`
- `input.extensions.subject.organization` — string: one of `IBM Corporation`, `Red Hat`, `Kyndryl`
- `input.extensions.subject.user_name` — string

**From `input.args.*` (tool arguments, LLM-chosen):**
- `user_id` (int) — target employee; present on most personal-record and leave tools
- `salary`, `salary_currency` (float, string) — on `add_employee`, `update_employee`
- `email` (string) — on `add_employee`, `update_employee`
- `organization` (string) — on `add_employee`, `update_employee`
- `department_id` (int) — on `add_employee`, `update_employee`, `list_employees`
- `manager_id` (int) — on `add_employee`, `update_employee`, `list_employees`
- `home_address`, `country_code` (string) — on `add_employee`, `update_employee`
- `expiry_date`, `issue_date` (string, YYYY-MM-DD) — on passport and visa tools
- `start_date`, `end_date` (string) — on `create_time_off_request`
- `leave_type` (string) — on `create_time_off_request`, `set_leave_allotment`
- `status` (string) — on `update_time_off_status`
- `annual_days` (int) — on `set_leave_allotment`
- `request_id` (int) — on `update_time_off_status`, `get_time_off_request`
- `holiday_id` (int) — on `delete_holiday`
- `country_code`, `holiday_date`, `name`, `year` — on holiday tools

**guidance.txt coverage sweep:**
| Rule | Fields needed at OPA time | Available? | Verdict |
|---|---|---|---|
| Employee may view/edit only own data | `subject.user_id` vs `args.user_id` | Partial — both present, but ownership of personal records requires knowing target user_id | OPA-enforceable for self-check: `args.user_id == subject.user_id` |
| Manager may view direct reports' data | `subject.user_id` + DB lookup (who are their direct reports?) | DB lookup not OPA-visible | **Blind spot** — requires runtime DB context |
| HR may view/edit all data | `subject.department == "HR"` | Available | OPA-enforceable |
| Only HR may add employee | `input.name`, `subject.department` | Available | OPA-enforceable |
| Non-IBM users blocked from IBM employee data | `subject.organization` + target employee's org | Target org is a DB field, not in OPA input | **Blind spot** — target org requires DB lookup |
| Salary updated only by HR or direct manager | `subject.department == "HR"` OR manager check (DB) | HR check available; manager check requires DB | Partial — HR half is OPA-enforceable; manager half is blind spot |
| Only HR may add/update department, holiday, leave allotment | `input.name`, `subject.department` | Available | OPA-enforceable |
| Passport/visa expiry > 6 months from now | `args.expiry_date` + current date (clock) | Clock not in OPA input | **Blind spot** — requires dynamic clock |
| Home address country must match current country | `args.home_address` / `args.country_code` + DB current country | DB lookup not available | **Blind spot** |
| Blacklist check on passport update | Blacklist status not in `system_vars.json` | Not available | **Blind spot** |
| Emergency contact in same area as employee | `args.city/country` + employee's DB location | DB lookup not available | **Blind spot** |
| Issue date < expiry date (same call) | `args.issue_date`, `args.expiry_date` | Available when both supplied | OPA-enforceable |
| Salary must be positive | `args.salary > 0` | Available | OPA-enforceable |
| Email domain matches organization | `args.email`, `args.organization` (same call) | Available when both supplied | OPA-enforceable |
| Time-off request only for self | `args.user_id == subject.user_id` | Available | OPA-enforceable |
| Time-off balance check | Requires computed balance (DB + year) | DB lookup not available | **Blind spot** |
| Paternity leave — baby details in conversation | Conversation history not in OPA input | Not available | **Blind spot** |
| Leave view by HR/self/direct manager | `subject.department == "HR"` OR `args.user_id == subject.user_id` OR manager (DB) | Partial — HR and self-check available; manager check is blind spot | Partial |
| Time-off status update rules (by role) | `subject.department` + requester/manager check (DB) | `subject.department == "HR"` available; requester/manager check requires DB | Partial |
| Time-off span ≤ 90 days | `args.start_date`, `args.end_date` | Available | OPA-enforceable |
| DB-write confirmation | Conversation history (agent behavior) | Not in OPA input | **Blind spot** |
| One tool call at a time | Agent behavior / LLM reasoning | Not in OPA input | **Blind spot** |
| Booking / frequent flyer | Not related to Employee Hub tools | N/A | **Out of scope** |

### Blind Spots
- **Manager/direct-report relationship**: requires a DB lookup (`SELECT * FROM employees WHERE manager_id = ?`); not present in OPA input at invocation time.
- **Target employee's organization**: when reading/writing another employee's record, the target's `organization` is a DB field, not visible in `input.args.*` or `input.extensions.subject.*`.
- **Current date / clock**: needed for the 6-month passport/visa expiry rule; OPA has no clock input.
- **Employee's current country**: needed for home-address country-change check; DB field not in OPA input.
- **Blacklist status**: no `blacklist` field in `system_vars.json`; not OPA-visible.
- **Emergency contact area match**: requires comparing `args.city`/`args.country` against the employee's DB location.
- **Leave balance**: requires computing `annual_days - used_days` from DB records.
- **Conversation history**: Paternity leave baby-details check and DB-write confirmation both require reading prior chat messages; not in OPA input.
- **All identity fields are self-reported**: `subject.user_id`, `subject.department`, `subject.organization` come from the caller's unverified `user_profile` JSON — OPA enforces what the caller claims, not what is cryptographically verified.
