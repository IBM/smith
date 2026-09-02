# Architecture: RagChatbot_MCPServer

## Layers

### HTTP/UI Layer
- File: `run_llm_with_mcp.py` (Streamlit UI, `run_llm_with_mcp.py`), `fast_server.py` (FastAPI `/chat`, `/extract_tool_call`)
- Role: Entry point for user questions; builds the LLM system/user messages, holds session-level `user_profile` (role, department, name), and exposes a role selector (Streamlit sidebar) / `user_profile` request field (FastAPI) that the caller controls directly.
- Inputs: `question` (free text), `user_profile.user_role` (Streamlit: dropdown "user"/"manager"; FastAPI: arbitrary JSON field, defaults to `DEFAULT_USER_PROFILE` = `{"user_role": "employee", ...}`), `history`.
- Outputs: `input_messages` (system + user chat messages) passed to the agent layer; on role change, calls the `set_user_role` MCP tool to sync role into the OPA client's in-memory context.
- Current enforcement: `enforce_input`/`enforce_output` (LLMGuard, Streamlit path only — `run_llm_with_mcp.py`) scan prompt/tool-output text for malicious patterns, but contain an explicit "business-friendly fallback" allowlist and a fail-open branch on scanner error (`opa_client.py`-adjacent risk, not policy-relevant). `fast_server.py`'s FastAPI path has **no LLMGuard call at all** — `build_input_messages` goes straight from request to LLM. Role selection itself has no authorization check in either path — whatever role the caller supplies is accepted and forwarded.

### Agent Layer (LLM + tool orchestration)
- File: `run_llm_with_mcp.py::chat()`, `fast_server.py::chat()`
- Role: Sends the conversation + tool schema to the LLM, executes whatever tool calls the LLM emits, feeds results back until a final answer is produced.
- Inputs: chat messages, `tools` schema (name/description/JSON-schema params from the live MCP server).
- Outputs: tool name + LLM-generated JSON arguments, passed verbatim to the MCP layer via `connection_manager.call_tool`.
- Current enforcement: none. Tool arguments are LLM-generated from user text and are trusted as-is (`# Parse tool arguments directly (LLM-generated, should be safe)` — `run_llm_with_mcp.py:248`). No re-validation of argument shape, value ranges, or role-consistency before dispatch.

### MCP Tool Layer
- File: `mcp_server.py`
- Role: Declares the 12 `@mcp.tool()` functions (`create_ticket`, `submit_ticket`, `send_email`, `export_content_as_file`, `ask_for_workpolicy`, `get_w2_form`, `return_product`, `view_team_compensation`, `export_compensation_data`, `email_compensation_report`, `purchase`, `set_user_role`) over SSE transport (`localhost:8000/sse`); this is the interception point Smith's OPA policy is meant to guard.
- Inputs: tool name + typed arguments per `tool_definitions.json` (e.g. `department`, `select_fields`, `id`, `time_range`, `format`, `include_benefits` for `view_team_compensation`; `amount`, `product_name` for `purchase`/`return_product`; `destination`, `external_sharing`, `encryption_required` for `email_compensation_report`; `user_role` for `set_user_role`).
- Outputs: tool result string returned up through the agent layer.
- Current enforcement: **none observed in `mcp_server.py` itself.** No `@policy_check` decorator is active on any live tool — the only two references (`test_purchase_policy`, `ask_for_salary`) are commented out (`mcp_server.py:110-124`, `371-501`). `opa_client.py` defines a full OPA-integration client (`evaluate_policy`, `UniversalOPAClient`) with fail-secure fallback logic, but nothing in `mcp_server.py` calls it before executing a tool body — the tool functions run unconditionally, returning live HR/compensation data straight from `hr_db`/`comp_db` (`view_team_compensation`, `export_compensation_data`) before any policy filtering. This means **assets/policy.rego enforcement, if wired in, must be interposed at the SSE/tool-dispatch boundary itself** (or the calling layer), not inside these function bodies as currently written.

### Tool Implementation / Data Layer
- File: `create_ticket.py` (ticket/purchase/return stubs), `rag_pipeline.py` (`ask_for_workpolicy`, PDF-backed RAG over `pdfs/work_rules_and_regulations_2016.pdf`), `rag_salary.py` (`ask_for_salary`, PDF-backed RAG over `pdfs/salary_summary.pdf` — currently unused/commented out in `mcp_server.py`), `data_sources/hr_database.py` (`hr_db`, `comp_db`, `purchase_db` — referenced but not read in this pass; in-memory mock HR data).
- Role: Executes business logic; `view_team_compensation`/`export_compensation_data` pull real employee records including sensitive fields (`ssn`, `home_address`, `bank_account`, `emergency_contact`, `personal_email`) and apply **no field filtering themselves** — the code comment at `mcp_server.py:183` and `:295` explicitly states "policy enforcement will filter based on permissions," i.e., this layer assumes an external policy layer removes sensitive fields, but none currently does.
- Inputs: same as MCP layer, plus `select_fields` (client-specified field projection — see rule 16 in guidance.txt).
- Outputs: JSON/CSV/PDF-formatted employee compensation records, ticket/purchase confirmations, RAG answers.
- Current enforcement: `project_record()` (mcp_server.py:614) filters returned fields to `select_fields` **if provided by the caller**, but does not enforce an exclusion list — it is a pure allowlist projection with no server-side floor, so a caller who omits `select_fields` gets every field including SSN/bank account back by default.

### OPA Integration Layer (defined but not wired into the live tool path)
- File: `opa_client.py`, `opa_config.py`
- Role: Provides `OPAClient.evaluate_policy()` (calls `POST /v1/data/mcp/policies/{allow,deny}` on an OPA server at `localhost:8181`), a `_fail_secure_decision()` fallback for when OPA is unreachable, and `UniversalOPAClient` which builds the full `input.extensions.subject.*` / `input.args.*` schema (`build_universal_input`) matching `assets/policy.rego`'s expected input shape. `opa_config.py::initialize_user_session()` sets role + `max_purchase` into a global `current_user_context` dict.
- Inputs: tool name, arguments, and whatever role was last set via `set_user_role` or `initialize_user_session`.
- Outputs: `(is_allowed: bool, reason: str)`; also produces the exact JSON envelope (`kind`, `action`, `name`, `arguments`, `extensions.subject.{id,type,roles,teams,permissions}`) that `test_case_template.json` / the policy expects.
- Current enforcement: this is the intended enforcement point, but **no code in `mcp_server.py` calls `opa_client.evaluate_policy()` or `universal_opa_client.build_universal_input()` before running a tool.** It is fully implemented but disconnected from the live request path — a critical gap: the policy this Smith skill manages is not currently enforced by the running server.

### Role/Session State
- File: `opa_client.py` (`current_user_context` global dict, `set_user_context()`, `get_current_user_context()`), `opa_config.py` (`initialize_user_session()`, `switch_user_role()`, `USER_ROLES` dict)
- Role: Tracks "current user" role/id as **process-global mutable state**, not per-request/per-session state. `set_user_role` (an MCP tool, callable by anyone) and `switch_user_role()` mutate this global directly.
- Inputs: `user_role` string, validated only against `["user", "manager"]` (mcp_server.py) or `USER_ROLES` keys (opa_config.py) — no identity/credential check, no mapping from an authenticated principal to a role.
- Outputs: role value read back by `get_current_user_context()` inside tool bodies (e.g., `view_team_compensation`'s manager-team lookup) and by `_fail_secure_decision()`.
- Current enforcement: none — this is the self-reported role problem below.

## Trust Boundaries

| Field | Source | Classification |
|---|---|---|
| `user_role` (via `set_user_role` tool call) | Caller-supplied argument to an unauthenticated MCP tool; anyone can call `set_user_role("manager")` directly | Self-reported |
| `user_profile.user_role` (FastAPI `/chat` request body) | Caller-supplied JSON field, no default enforcement beyond `DEFAULT_USER_PROFILE` fallback | Self-reported |
| `user_role` (Streamlit sidebar dropdown) | Caller-selected UI control, then pushed to the MCP server via `set_user_role` | Self-reported |
| `department`, `id` (view/export compensation tools) | Caller-supplied tool arguments | Self-reported |
| `select_fields` (view/export compensation tools) | Caller-supplied tool arguments; determines which sensitive fields are returned | Self-reported |
| `destination` / `recipient_email` (email tools) | Caller-supplied tool arguments; domain is parsed client-side for validation intent but not verified against any allowlist in `mcp_server.py` itself | Self-reported |
| `external_sharing`, `encryption_required` (`email_compensation_report`) | Caller-supplied boolean arguments — the caller declares whether their own request counts as "external," which is exactly the fact the policy needs to gate on | Self-reported |
| `amount`, `product_name` (purchase/return) | Caller-supplied tool arguments; `amount` type is `int` in the live tool signature but `str` in the docstring (inconsistency) — no server-side validation against a real price catalog for arbitrary product names | Self-reported |
| `hr_db` / `comp_db` employee records (salaries, SSNs, bank accounts) | Local in-memory mock database (`data_sources/hr_database.py`), read by tool implementation layer | Verified (server-controlled, not caller-influenced) — but its *release* is gated only by caller-controlled `select_fields`/`department`/`id`, which are self-reported |
| `time_range` | Caller-supplied argument | Self-reported |
| `ticket_content`, `email_content`, `question` (RAG/ticket tools) | Free-text caller input, forwarded to LLM/RAG chain with no sanitization inside `mcp_server.py` (LLMGuard only runs upstream in the Streamlit path, not the FastAPI path, and not at all inside `mcp_server.py`) | Self-reported / External-untrusted (once it reaches the LLM) |
| `tool_definitions.json` schema | Extracted live from the running MCP server via `smith --flag get_mcp_parameter` | Verified (server-controlled) |

## Data Flow

```
user question / role selection
  → HTTP/UI Layer (Streamlit run_llm_with_mcp.py, or FastAPI fast_server.py)
  → Agent Layer (LLM tool-call decision; chat())
  → MCP Tool Layer (mcp_server.py @mcp.tool() function — no policy check today)
  → Tool Implementation Layer (create_ticket.py / rag_pipeline.py / rag_salary.py / data_sources/hr_database.py)
  → [OPA Integration Layer exists (opa_client.py) but is not called from the above path]
response
  ← Tool Implementation Layer
  ← MCP Tool Layer (raw result, unfiltered beyond caller-chosen select_fields)
  ← Agent Layer (LLMGuard enforce_output — Streamlit path only)
  ← HTTP/UI Layer
```

## Enforcement Points

### Current
- HTTP/UI Layer (Streamlit path only): LLMGuard `enforce_input`/`enforce_output` text scanning — pattern-based, with a documented business-safe-pattern override and fail-open error handling. Not present in the FastAPI (`fast_server.py`) path at all.
- Tool Implementation Layer: `project_record()` field-allowlist projection, but only applied when the caller supplies `select_fields`; no default exclusion of sensitive fields.

### Available (OPA-interceptable)
- MCP Tool Layer (`mcp_server.py`), at the top of each `@mcp.tool()` function, before any database access or side effect — this is the only point where tool name, full argument set, and (if role/session state were fixed to be trustworthy) caller identity are all present as structured data simultaneously. `opa_client.py::UniversalOPAClient.build_universal_input()` already builds the exact envelope shape (`input.args.*` from arguments, `input.extensions.subject.*` from role context) that would need to be threaded in here.
- Coverage sweep against `guidance.txt`'s 16 numbered rules — field(s) each rule needs and whether they are visible at the MCP Tool Layer interception point:
  - Rule 1 (managers view own team's data via `view_team_compensation`): needs `input.args.department`, `input.args.id`, `input.extensions.subject.role` → available (`department`, `id` are tool args; role would come from subject context if wired correctly).
  - Rule 2 (employees blocked from `view_team_compensation`): needs `input.extensions.subject.role` → available in principle, but see Blind Spots — the role value itself is not trustworthy.
  - Rule 3 (managers cannot see SSN/address/bank/tax ID/emergency contact when querying salary): needs `input.args.select_fields` (or absence thereof) and the full field set the tool would return → **partially available**: `select_fields` is a visible arg, but if the caller omits it, the *returned* field set is determined by tool-body logic (`mcp_server.py:183-193`), not by anything visible in the pre-call arguments — a policy gating only on `select_fields` cannot stop the default-all-fields case from executing before OPA ever sees the response.
  - Rule 4/5 (managers can export in CSV/PDF/JSON; employees cannot export): needs `input.extensions.subject.role`, tool name `export_compensation_data` → available (tool name always visible; role has the same trust caveat as Rule 2).
  - Rule 6/7 (external email sharing of comp/non-comp data restricted to @ibm.com): needs `input.args.destination` (or `recipient_email`), domain parsed from it, and `input.args.external_sharing` → available as raw string/bool args; domain-suffix check itself must happen in Rego (not done in Python today).
  - Rule 8 (blocked email domains list): needs `input.args.destination`/`recipient_email` → available.
  - Rule 9/10 (purchase amount thresholds by role, with manager-approval flow for employees ≥$200): needs `input.args.amount`, `input.extensions.subject.role` → available as tool args; note there is no `approval` argument on the live `purchase` tool (`amount`, `product_name`, `category`, `justification` only) despite `system_vars.json` declaring an `"approval": "true|false"` field — that field is not threaded into any tool call, a probable **guidance/tool-definition mismatch** worth flagging to Step D.
  - Rule 11/12/13/14 (block "ignore all policies" / "bypass security" / "override all policies" / "show all SSN data" phrases): needs the free-text content of whichever argument carries user intent (`ticket_content`, `question`, `email_content`, etc.) → available as a string arg, but semantic phrase-matching against arbitrary free text is a poor fit for Rego pattern rules and is exactly the class of instruction the LLM itself (not OPA) is best positioned to refuse — flag as a possible blind spot for robust enforcement (a rewritten/paraphrased injection attempt bypasses a literal string match).
  - Rule 15 (employees blocked entirely from `email_compensation_report`): needs `input.extensions.subject.role`, tool name → available (same role-trust caveat).
  - Rule 16 (SSN/home_address/bank_account/tax_id/emergency_contact excluded from `select_fields` regardless of role): needs `input.args.select_fields` → available directly as a tool argument list.

### Blind Spots
- **Role/identity is entirely self-reported and unauthenticated.** `set_user_role` is a plain MCP tool with no credential check (`mcp_server.py:589-612`); any caller (or any LLM-emitted tool call) can set `user_role` to `"manager"` before calling a sensitive tool. Every guidance rule that keys off `input.extensions.subject.role` (Rules 1, 2, 4, 5, 15) is enforceable in the narrow sense that the *field* is visible to OPA, but the *value* carries no integrity guarantee — OPA can only be as trustworthy as this role signal, which today has none. This is the single largest gap: no amount of correct Rego can compensate for a role claim nobody verifies.
- **No policy call exists on the live tool-execution path.** `opa_client.py`/`UniversalOPAClient` implement the intended enforcement call, but `mcp_server.py`'s tool functions never invoke `evaluate_policy()` or check its result before running. Today, `assets/policy.rego` (however well-written) is not actually consulted by the running server — this is an integration gap, not a policy-content gap, but it means all "Available" enforcement points above are available in principle only until this wiring is added or confirmed elsewhere.
- **Default (no `select_fields`) compensation reads return every sensitive field before any filter runs** (`mcp_server.py:183-193`, `:295-302`) — the *decision* to exclude SSN/address/bank/tax ID/emergency-contact (guidance Rule 3, Rule 16) has to happen at the OPA-interception point on the request, denying or rewriting the call, since the tool body itself does not enforce an exclusion floor; it can't be corrected after the fact because the sensitive fields are already serialized into the tool result string returned to the LLM (and potentially into the chat transcript) by the time any output-side check could run.
- **`get_w2_form` and `ask_for_salary` (rag_salary.py) are effectively dead/hardcoded** — `get_w2_form` always returns a canned refusal string regardless of caller (mcp_server.py:90-94), and `ask_for_salary`/the salary RAG tool is commented out of the live tool registry — so guidance intent about W2/salary RAG access has no live enforcement surface at all right now (not a gap in the policy, but worth noting so Step B/D don't invent enforcement for a tool that isn't actually callable).
- **FastAPI path (`fast_server.py`) has no LLMGuard-equivalent text scanning at all** for the prompt-injection-style rules (11-14) — those guidance rules, even if never enforceable in Rego, currently have zero enforcement on this path (Streamlit has partial, fail-open coverage; FastAPI has none).
- **Free-text semantic phrase rules (11-14) cannot be robustly pattern-matched in Rego** — paraphrase/translation/encoding of "ignore all policies" etc. will not match a literal string rule; this is a structural blind spot for an OPA-based enforcement layer regardless of implementation quality.
