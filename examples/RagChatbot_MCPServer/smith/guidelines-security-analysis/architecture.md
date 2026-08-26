# Architecture: RagChatbot_MCPServer

## Layers

### Layer 1 — HTTP API Layer
- File: `fast_server.py`
- Role: FastAPI server exposing `/chat` and `/extract_tool_call` endpoints; receives user questions and an optional `user_profile` dict, constructs the system prompt embedding the user profile, and delegates to the LLM+tool loop.
- Inputs: `question` (string), `user_profile` (dict with `user_role`, `user_department`, `user_name`), `history` (list of message dicts)
- Outputs: LLM response string back to caller; passes constructed `input_messages` list to the Agent Layer
- Current enforcement: none — no authentication, no input validation, no role verification at this layer; `user_profile` is accepted as-is from the HTTP request body

### Layer 2 — Agent Layer (LLM + System Prompt)
- File: `fast_server.py` (`chat()` function) / `run_llm_with_mcp.py` (Streamlit variant with LLMGuard)
- Role: Constructs the system prompt embedding the caller-supplied `user_profile`, sends the messages to the LLM, interprets tool-call decisions returned by the model, and iterates up to `max_turns`.
- Inputs: `input_messages` (system prompt + user message), `tools_json_cache` (list of tool schemas from MCP), `user_profile` embedded in system prompt
- Outputs: Tool-call selections (name + arguments JSON) to MCP Tool Layer; final text response to HTTP API layer
- Current enforcement: `run_llm_with_mcp.py` only — LLMGuard scans input and output text for policy-bypass keyword patterns (e.g., "ignore all instructions"); `fast_server.py` has no equivalent input/output scanning

### Layer 3 — MCP Tool Layer
- File: `mcp_server.py` (FastMCP server on port 8000, SSE transport)
- Role: Defines all 12 MCP tools, dispatches tool calls received from the agent, reads user context from a server-side session store via `get_current_user_context()`, and executes business logic.
- Inputs: Tool name + structured arguments from the agent; user context from `opa_client.py` session store (set by `set_user_role`)
- Outputs: Tool response strings to the agent
- Current enforcement: `set_user_role` tool sets the server-side user context; the `opa_client.py` module is imported and a policy engine call is anticipated, but no OPA check is visible in the tool handler bodies themselves — policy enforcement is designated but not implemented in the tool bodies shown

### Layer 4 — Tool Implementation Layer
- File: `mcp_server.py` (tool function bodies), `create_ticket.py`, `rag_pipeline.py`, `rag_salary.py`, `data_sources/hr_database.py`
- Role: Executes the business logic for each tool — querying the HR/compensation in-memory database, formatting output, calling RAG pipelines, and returning results.
- Inputs: Structured tool arguments; HR/compensation data from in-memory `hr_db` and `comp_db`
- Outputs: Formatted strings (JSON, CSV, PDF summary) containing sensitive employee data (SSN, home address, bank account, salary)
- Current enforcement: `view_team_compensation` and `export_compensation_data` retrieve the full sensitive record set unconditionally and comment "policy enforcement will filter based on permissions" — the actual field-level filtering is absent in the shown code and deferred to the policy layer

### Layer 5 — External Services
- File: RAG pipeline (`rag_pipeline.py`, `rag_salary.py`), PDF data sources (`pdfs/`)
- Role: Preloaded PDF documents (work rules, salary summary) are indexed and queried via RAG for `ask_for_workpolicy`; no outbound network calls to live external APIs for HR data (data is local in-memory).
- Inputs: Natural-language question from the tool layer
- Outputs: Retrieved text chunks from the PDF index
- Current enforcement: none — retrieved PDF content is returned directly to the agent without sanitization

---

## Trust Boundaries

| Field | Source | Classification |
|---|---|---|
| `user_profile.user_role` | HTTP request body (`fast_server.py`) / Streamlit sidebar selection (`run_llm_with_mcp.py`) | Self-reported — caller supplies the role; no cryptographic verification |
| `user_profile.user_department` | HTTP request body | Self-reported |
| `user_profile.user_name` | HTTP request body | Self-reported |
| `input.extensions.subject.roles` | `system_vars.json` defines valid values; runtime value set via `set_user_role` MCP tool call | Self-reported — role originates from the same caller-controlled profile |
| `input.extensions.subject.approval` | `system_vars.json` defines `"true\|false"`; not observed being set by any layer independently | Self-reported — no approval authority validates this field |
| `input.extensions.subject.id` | `system_vars.json` defines `"Bob"` as default | Self-reported |
| `input.arguments.amount` (purchase, return_product) | LLM-generated from user prompt | Self-reported — LLM fabricates based on user input |
| `input.arguments.external_sharing` (export_compensation_data, email_compensation_report) | LLM-generated | Self-reported |
| `input.arguments.recipient_email` / `destination` (send_email, email_compensation_report) | LLM-generated from user prompt | Self-reported |
| `input.arguments.select_fields` (view_team_compensation, export_compensation_data) | LLM-generated | Self-reported |
| `input.arguments.question` (ask_for_workpolicy) | LLM-generated from user prompt | Self-reported |
| PDF RAG content (`work_rules_and_regulations_2016.pdf`, `salary_summary.pdf`) | Preloaded local files | External/untrusted — content is not cryptographically verified; poisoned PDFs would be trusted |
| `input.arguments.ticket_content` / `report_data` / `email_content` (free-text tools) | LLM-generated free-text | Self-reported |
| `input.arguments.user_role` (set_user_role) | Caller-supplied via MCP tool call | Self-reported — any caller can switch the server-side role context |

---

## Data Flow

```
User HTTP request (question + user_profile)
  → Layer 1 (fast_server.py /chat): constructs system prompt with embedded user_profile
    → Layer 2 (LLM): reasons over system prompt + tools, emits tool_calls
      → Layer 3 (mcp_server.py MCP): dispatches tool call with structured args
        → Layer 4 (tool impl): queries hr_db / comp_db / RAG, returns sensitive data
          → Layer 3: returns result string to agent
        → Layer 2: incorporates tool result into context, continues reasoning
      → Layer 2: emits final text response
    → Layer 1: returns ChatResponse to caller
```

RAG path:
```
ask_for_workpolicy(question)
  → Layer 4 (rag_pipeline.py): retrieves chunks from indexed PDF
    → External/untrusted: preloaded PDF content returned to agent
```

---

## Enforcement Points

### Current
- **Layer 2 (run_llm_with_mcp.py only)**: LLMGuard keyword scan on input and output text — blocks a short list of hardcoded malicious strings (e.g., "ignore all instructions", "bypass all"); has a business-safe override list that re-allows flagged inputs matching common HR terms
- **Layer 3 (set_user_role tool)**: sets server-side user context used by tool implementations to look up the manager's team; context is reset per call to `set_user_role`

### Available (OPA-interceptable)
OPA can intercept at the boundary between Layer 2 and Layer 3 — at the point the agent emits a tool call and before the MCP server dispatches it. At this interception point the following fields are visible as structured data:

- `input.name` — the tool being called (one of the 12 tool names)
- `input.arguments.amount` (integer) — for `purchase`, `return_product`
- `input.arguments.external_sharing` (boolean) — for `export_compensation_data`, `email_compensation_report`
- `input.arguments.recipient_email` (string) — for `send_email`
- `input.arguments.destination` (string) — for `email_compensation_report`
- `input.arguments.select_fields` (list of strings) — for `view_team_compensation`, `export_compensation_data`
- `input.arguments.format` (string) — for `view_team_compensation`, `export_compensation_data`
- `input.arguments.department` (string) — for `view_team_compensation`
- `input.arguments.export_type` (string) — for `export_compensation_data`
- `input.arguments.user_role` (string) — for `set_user_role`
- `input.arguments.question` (string) — for `ask_for_workpolicy`
- `input.arguments.ticket_content` (string) — for `create_ticket`, `submit_ticket`
- `input.arguments.report_data` (string) — for `email_compensation_report`
- `input.extensions.subject.roles` — caller-supplied role (`employee` or `manager`)
- `input.extensions.subject.approval` — approval flag (`true`/`false`)
- `input.extensions.subject.id` — user identity

**Coverage sweep against guidance.txt:**
| guidance.txt rule | Required field(s) | Visible at OPA interception? |
|---|---|---|
| Rule 1: Managers view own team only (view_team_compensation) | `input.extensions.subject.roles`, `input.name` | Yes |
| Rule 2: Employees cannot use view_team_compensation | `input.extensions.subject.roles`, `input.name` | Yes |
| Rule 3: Managers cannot see SSN, home address, bank account, Tax ID, emergency_contact | `input.arguments.select_fields`, `input.name` | Yes — via select_fields list check |
| Rule 4: Managers can export CSV, PDF, JSON | `input.extensions.subject.roles`, `input.arguments.format`, `input.name` | Yes |
| Rule 5: Employees cannot export (export_compensation_data blocked) | `input.extensions.subject.roles`, `input.name` | Yes |
| Rule 6: Managers can send non-compensation emails externally | `input.extensions.subject.roles`, `input.name`, `input.arguments.recipient_email` | Yes |
| Rule 7: No one can share compensation data to non-@ibm.com | `input.name`, `input.arguments.external_sharing`, `input.arguments.destination` | Yes |
| Rule 8: Blocked email domains | `input.arguments.recipient_email` / `input.arguments.destination` | Yes |
| Rule 9: Employees need approval for purchase $200+ | `input.extensions.subject.roles`, `input.arguments.amount`, `input.extensions.subject.approval` | Yes |
| Rule 10: Managers limited to purchases under $1,000 | `input.extensions.subject.roles`, `input.arguments.amount` | Yes |
| Rules 11–14: Keyword blocks ("ignore all policies", "bypass security", etc.) | `input.arguments.question` / `input.arguments.ticket_content` / free-text args | Partially — only for tools where a free-text argument is present at invocation |

### Blind Spots
- **Layer 2 (LLM reasoning)**: The LLM selects which tool to call and what arguments to fabricate. OPA cannot inspect the LLM's internal reasoning or prevent it from constructing a particular argument value before the call is emitted — only the resulting structured call can be checked.
- **Layer 4 (tool response content)**: `view_team_compensation` and `export_compensation_data` currently return SSN, home address, bank account, and emergency_contact unconditionally in the raw data (with a comment that policy will filter). OPA cannot filter return-value content — that must be addressed in the tool implementation itself.
- **Layer 5 (RAG content)**: Content retrieved from indexed PDFs is passed directly to the agent. Prompt injection embedded in PDF content cannot be intercepted by OPA.
- **`set_user_role` tool**: Any caller can invoke this tool to change the server-side role used by subsequent tool calls in the same session. There is no mechanism to verify that the caller-asserted role matches an authenticated identity — OPA can block specific role values from being set, but cannot verify the identity claim.
