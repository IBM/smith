# Architecture: RagChatbot_MCPServer

## Layers

### HTTP API Layer
- File: `fast_server.py`
- Role: Exposes `POST /chat` (full agentic tool loop) and `POST /extract_tool_call` (single LLM completion, no tool execution) over FastAPI; receives JSON with `question`, optional `user_profile`, and optional `history`.
- Inputs: `question` (string), `user_profile` (dict — caller-supplied, unauthenticated), `history` (list of message dicts)
- Outputs: Assembled message list passed to the Agent Layer; tool results routed back as tool-role messages
- Current enforcement: None. No authentication, no input scanning, no rate-limiting at this layer.

### Agent Layer
- File: `fast_server.py` (`build_input_messages`, `chat`)
- Role: Constructs the system prompt (embedding the caller-supplied `user_profile` verbatim), runs a `max_turns=10` OpenAI-compatible tool-use loop via a local LLM, and dispatches tool calls through the MCP session.
- Inputs: Assembled messages (system prompt + user question + history); tool schema from `tools_json_cache`
- Outputs: Tool-call requests (tool name + JSON arguments) sent to the MCP Tool Layer; final text response returned to caller
- Current enforcement: None. The `user_profile` dict (including `user_role`) is embedded verbatim in the system prompt with no verification. `DEFAULT_USER_PROFILE` uses `"employee"` role.

### MCP Tool Layer
- File: `mcp_server.py` (FastMCP over SSE on port 8000)
- Role: Receives tool-call requests over SSE, exposes 11 active tools, and dispatches to business logic. This is the only point where tool name and full structured arguments are simultaneously present before any side effect.
- Inputs: Tool name and typed arguments per tool (see tool_definitions.json for authoritative shapes)
- Outputs: Tool return strings sent back over SSE to the Agent Layer
- Current enforcement: None at the MCP protocol boundary. No OPA interception is wired into the dispatch path. Note: `set_user_role` is commented out in `mcp_server.py` and is NOT an active tool, despite appearing in `tool_definitions.json` (generated from a prior state).

### Tool Implementation Layer
- File: `mcp_server.py` (tool function bodies) + `opa_client.py` (`current_user_context` global)
- Role: Implements per-tool business logic; reads role state from the process-global `current_user_context` dict; contains an OPA client (`OPAClient`, `UniversalOPAClient`) that is defined but **not called** from any active tool — the decorator `@policy_check` is commented out on every usage.
- Inputs: Tool arguments; process-global `current_user_context`
- Outputs: Formatted strings returned to MCP Tool Layer
- Current enforcement: The OPA client exists and has a `_fail_secure_decision` fallback, but it is dead code — no active tool invokes `evaluate_policy`. `project_record()` in `view_team_compensation` / `export_compensation_data` filters the returned fields to `select_fields` if provided, but only after sensitive data (SSN, home address, bank account, personal email) is already included in the candidate record unconditionally.

### External Services
- File: `rag_pipeline.py` (preloaded PDF via HuggingFace embeddings), `data_sources/hr_database.py` (in-memory HR/compensation data)
- Role: Provide the underlying data (HR records, compensation data, PDF policy text) that tool implementations query.
- Inputs: Query strings / employee IDs
- Outputs: Structured HR/compensation data or RAG-generated text
- Current enforcement: None.

---

## Trust Boundaries

| Field | Source | Classification | Disposition |
|---|---|---|---|
| `input.name` (tool name) | MCP protocol (set by Agent Layer LLM) | Self-reported | Acts on — routes tool dispatch |
| `input.args.ticket_content` | Caller via Agent LLM | Self-reported | Acts on — passed to `raw_create_ticket` / `raw_submit_ticket` |
| `input.args.question` | Caller via Agent LLM | Self-reported | Acts on — passed to RAG pipeline |
| `input.args.recipient_email` | Caller via Agent LLM | Self-reported | Echoed — interpolated into response string only; no actual email sent |
| `input.args.subject` | Caller via Agent LLM | Self-reported | Echoed — interpolated into response string only |
| `input.args.body` | Caller via Agent LLM | Self-reported | Echoed — interpolated into response string only |
| `input.args.email_content` | Caller via Agent LLM | Self-reported | Echoed — interpolated into response string only |
| `input.args.attached_file` | Caller via Agent LLM | Self-reported | Echoed — interpolated into response string only |
| `input.args.data` | Caller via Agent LLM | Self-reported | Echoed — interpolated into response string only |
| `input.args.file_name` | Caller via Agent LLM | Self-reported | Echoed — interpolated into response string only |
| `input.args.select_fields` | Caller via Agent LLM | Self-reported | Acts on — passed to `project_record()` to filter output fields |
| `input.args.department` | Caller via Agent LLM | Self-reported | Acts on — used to look up manager/team in `hr_db` |
| `input.args.id` | Caller via Agent LLM | Self-reported | Acts on — filters results to a specific employee |
| `input.args.time_range` | Caller via Agent LLM | Self-reported | Echoed — stored in output metadata only; does not filter query |
| `input.args.format` | Caller via Agent LLM | Self-reported | Acts on — determines JSON vs CSV vs PDF output path |
| `input.args.include_benefits` | Caller via Agent LLM | Self-reported | Acts on — controls whether stock/benefits fields are included |
| `input.args.external_sharing` (`export_compensation_data`) | Caller via Agent LLM | Self-reported | Echoed — stored in `export_metadata` dict only; does not gate the export |
| `input.args.export_type` | Caller via Agent LLM | Self-reported | Acts on — gates salary_history / bonus_history inclusion |
| `input.args.business_justification` | Caller via Agent LLM | Self-reported | Echoed — stored in `export_metadata` dict only; does not gate the export |
| `input.args.destination` | Caller via Agent LLM | Self-reported | Acts on — domain extracted and interpolated into response string; no real email sent |
| `input.args.report_data` | Caller via Agent LLM | Self-reported | Echoed — interpolated into response string only |
| `input.args.external_sharing` (`email_compensation_report`) | Caller via Agent LLM | Self-reported | Echoed — interpolated into response string only; does not gate sending |
| `input.args.encryption_required` | Caller via Agent LLM | Self-reported | Echoed — interpolated into response string only; no encryption is applied |
| `input.args.amount` (`purchase`, `return_product`) | Caller via Agent LLM | Self-reported | Acts on — used for catalog lookup and order ID; does NOT gate the purchase (no threshold check in body) |
| `input.args.product_name` | Caller via Agent LLM | Self-reported | Acts on — used for catalog lookup |
| `input.args.category` (`purchase`) | Caller via Agent LLM | Self-reported | Ignored — immediately overwritten by `category = None` in the function body |
| `input.args.justification` (`purchase`) | Caller via Agent LLM | Self-reported | Ignored — declared as parameter but never referenced in the function body |
| `input.extensions.subject.roles` / `current_user_context.user_role` | Process-global state initialized at server start (`set_user_context("mcp_user", "user")`) | Self-reported | Acts on — read by `view_team_compensation` / `export_compensation_data` / `purchase` via `get_current_user_context()`. Note: `set_user_role` tool is currently commented out — role cannot be changed at runtime |
| `user_profile` (HTTP API request body) | Caller | Self-reported | Echoed into system prompt — embedded verbatim by `build_input_messages`; not propagated to `input.extensions.subject` |
| `history` (HTTP API request body) | Caller | Self-reported | Echoed into system prompt — re-injected as context on every turn |
| RAG PDF content | External (bundled PDF, HuggingFace BAAI/bge-small-en-v1.5 embeddings) | External/untrusted | Acts on — returned to LLM context via `ask_for_workpolicy`; no provenance check |

---

## Data Flow

```
User → POST /chat (fast_server.py)
     → build_input_messages [embeds caller-supplied user_profile + history in system prompt]
     → LLM tool-use loop (OpenAI-compatible client, max_turns=10)
     → SSE call_tool → mcp_server.py tool body
     → hr_database / rag_pipeline (data)
     → response string ← tool body ← SSE ← chat loop
     → ChatResponse.answer ← POST /chat

POST /extract_tool_call:
User → fast_server.py → single LLM completion (no tool execution)
     → ExtractToolCallResponse(tool_name, arguments)
```

---

## Enforcement Points

### Current
- None active. All `@policy_check` decorators and `opa_client.evaluate_policy` calls are commented out in `mcp_server.py`. The OPA client exists but is dead code.
- `project_record()` in `view_team_compensation` / `export_compensation_data` will filter output fields to `select_fields` if provided, but sensitive fields (SSN, home_address, bank_account, personal_email, emergency_contact) are already included in the candidate record unconditionally before filtering — OPA must intercept before the tool runs to prevent exposure.
- **Important:** `export_compensation_data` body also adds ssn, personal_email, home_address, bank_account from `comp_db.sensitive_data` to its candidate record (lines ~296–303), despite its docstring only listing non-sensitive available fields. The actual output can include PII regardless of what `select_fields` names.

### Available (OPA-interceptable)
- **MCP Tool Layer** (`mcp_server.py`): Before any tool body executes, the tool name (`input.name`) and all declared arguments (`input.args.*`) are present as structured data. This is the sole viable OPA interception point. Fields available at interception time:
  - `input.name` — tool name (routes dispatch)
  - `input.args.ticket_content` — `create_ticket`, `submit_ticket` (prompt-injection checks)
  - `input.args.question` — `ask_for_workpolicy` (prompt-injection checks)
  - `input.args.recipient_email`, `input.args.body`, `input.args.email_content` — `send_email` (domain check, content policy)
  - `input.args.destination`, `input.args.report_data`, `input.args.external_sharing` — `email_compensation_report`
  - `input.args.select_fields` — `view_team_compensation`, `export_compensation_data` (field filter; OPA must block null/absent)
  - `input.args.external_sharing` — `export_compensation_data` (currently only echoed, but OPA can block if set true)
  - `input.args.amount` — `purchase`, `return_product` (threshold checks)
  - `input.extensions.subject.roles` — role field from session context (maps to `system_vars.json` `roles`)

### Blind Spots
- **Agent Layer** (LLM reasoning): The LLM decides which tool to call and what arguments to pass. Prompt injection through `user_profile`, `history`, or free-text args (`question`, `ticket_content`, etc.) can manipulate the LLM's decisions before OPA ever sees a tool call. OPA cannot inspect LLM intermediate reasoning.
- **`/extract_tool_call` endpoint**: Extracts tool intent without executing, so OPA never intercepts this path.
- **`/chat` endpoint — system prompt injection**: The caller-supplied `user_profile` dict is embedded verbatim in the system prompt with no verification. A caller can embed `user_role: manager` or arbitrary instructions.
- **Post-execution response content**: OPA cannot inspect what the tool returns after execution. Sensitive fields that escape `project_record()` filtering are visible in the LLM's context and final response.
- **Process-global role state** (`current_user_context`): Role is set at server start to `"user"` and cannot currently be changed (set_user_role is commented out). Any remaining shared state still risks cross-request bleed.
- **`_fail_secure_decision` fallback**: When OPA is unreachable, `purchase` and `return_product` are treated as safe ("fail open"). `_fail_secure_decision` lists them explicitly in `safe_actions` at line 113 — this diverges from guidance.txt Rules 9–10 for `purchase`.

---

## Undeclared Fields

| Field | Referenced by guidance rule # | Declared by | Consequence |
|---|---|---|---|
| `input.args.select_fields` (for SSN/address exclusion) | Rule 3 | `view_team_compensation`, `export_compensation_data` | Enforceable for both tools via `select_fields`; however `export_compensation_data` body also adds PII fields unconditionally to its candidate record from `comp_db.sensitive_data` regardless of `select_fields` — field-level filtering via `project_record()` applies post-hoc |
| `input.extensions.subject.roles` | Rules 1, 2, 3, 4, 5, 6, 7, 9, 10 | No tool arg; comes from `current_user_context` (process-global, set at startup as `"user"`) | Rules enforceable at MCP Tool Layer via `input.extensions.subject.roles` from session state — but `set_user_role` is currently commented out, so role is always `"user"` at runtime |
| `input.extensions.subject.approval` | Rule 9 (employee purchase ≥$200 requires approval) | No tool or system var populates this at runtime | Any OPA rule checking `input.extensions.subject.approval == "true"` will never fire; the approval gate is permanently blocked until the application populates this field |
| `input.args.justification` | Rule 9 (implicitly — approval evidence) | `purchase` only (optional, default null) | **Ignored** in function body — never read after parameter declaration; a rule gating on justification being present cannot guarantee approval actually occurred |
| `input.args.encryption_required` | Implied by Rules 7 / data-security intent | `email_compensation_report` only | **Echoed** — interpolated into response string only; no encryption applied regardless of value; rules permitting calls because this flag is set provide false assurance |
| `tax_id` | Rule 3 (SSN/sensitive fields list) | No tool declares `tax_id` as a parameter | A rule checking `select_fields` for `"tax_id"` can never fire; `view_team_compensation`'s available fields list does not include `tax_id` |
