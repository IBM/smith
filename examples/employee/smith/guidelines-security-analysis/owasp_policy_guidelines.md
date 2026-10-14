# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines
# Tool: Enterprise Employee Hub

---

## Architecture Summary

The Enterprise Employee Hub exposes an SQLite-backed employee directory through 33 FastMCP tools (employee records, org chart, departments, personal records, holidays, and time-off), invoked by a LangGraph ReAct agent over stdio transport. All identity claims (`user_id`, `department`, `organization`) are self-reported in the `user_profile` request body and embedded verbatim into the system prompt by `build_system_prompt()` — there is no cryptographic authentication, and the OPA PEP at the Agent→MCP boundary is the sole access-control enforcement layer.

---

## OWASP Top 10 for Agentic AI Security — Scope Assessment

### ASI01 — Agent Goal Hijack
**Risk:** Attackers inject instructions through `user_profile` values or the `question` field, redirecting the LangGraph agent to invoke tools it was not intended to invoke.
**Verdict:** Partial — The OPA PEP can block the resulting *tool call* if it violates access-control rules (e.g., wrong `user_id`, non-HR claiming HR tools), but it cannot intercept or validate the system prompt content or the LLM reasoning chain. The injection vectors themselves (TI-01-A, TI-01-B) are out of OPA scope; only their downstream effect on tool choice is partially visible.

### ASI02 — Tool Misuse and Exploitation
**Risk:** Callers abuse legitimate tools by supplying crafted arguments — wrong `user_id`, negative salary, mismatched email domain — to bypass access controls or corrupt data.
**Verdict:** In scope — All four threat instances (TI-02-A, TI-02-B, TI-02-C, TI-02-D) are visible as structured fields at tool invocation time: `input.extensions.subject.department`, `input.args.user_id`, `input.args.salary`, `input.args.email`, `input.args.organization`. OPA can enforce all of them.

### ASI03 — Identity and Privilege Abuse
**Risk:** Callers self-report false `user_id` or `department` values to bypass ownership or role checks.
**Verdict:** Partial — OPA enforces the structural ownership and role checks (`args.user_id == subject.user_id`, `subject.department == "HR"`). The authenticity of the subject fields themselves is a trust assumption that cannot be verified at OPA time; cryptographic identity verification is out of OPA scope and requires deployment-level change.

### ASI04 — Agentic Supply Chain Vulnerabilities
**Risk:** A compromised `server.py` or dependency would bypass the OPA PEP entirely, executing tool calls without interception.
**Verdict:** Out of scope — TI-04-A (MCP server integrity) is a runtime execution integrity concern. OPA only intercepts compliant stdio MCP calls; it cannot validate that the server binary or its dependencies are uncompromised.

### ASI05 — Unexpected Code Execution (RCE)
**Risk:** Agents generate and execute adversarial code.
**Verdict:** Not applicable — The Employee Hub server does not generate or execute code; no `eval()`, code generation tool, or code-execution pathway exists.

### ASI06 — Memory & Context Poisoning
**Risk:** Crafted `user_profile` values or `question` content poisons the LangGraph conversation history, influencing future ReAct reasoning.
**Verdict:** Out of scope — TI-06-A and TI-06-B involve agent reasoning layer state that is not visible as a structured OPA field at tool invocation time.

### ASI07 — Insecure Inter-Agent Communication
**Risk:** Compromised agent-to-agent channels.
**Verdict:** Not applicable — Single-agent architecture; no multi-agent orchestration, no A2A protocol.

### ASI08 — Cascading Failures
**Risk:** A single identity or ownership bypass enables a cascade of irreversible DB changes across all 33 tools.
**Verdict:** Partial — OPA's role gate (TI-08-A) and ownership check (TI-08-B) are the primary barriers. Stopping the individual tool calls at the OPA layer limits cascade propagation. Rate limiting and audit logging (recommended mitigations for blast radius) are out of OPA scope.

### ASI09 — Human-Agent Trust Exploitation
**Risk:** Attackers inject fabricated confirmation context or fake paternity leave details to bypass agent-layer confirmation gates.
**Verdict:** Out of scope — TI-09-A and TI-09-B target the LangGraph reasoning loop and conversation history; these are not visible as OPA-interceptable fields at invocation time.

### ASI10 — Rogue Agents
**Risk:** Compromised sub-agents operate within multi-agent trust hierarchies.
**Verdict:** Not applicable — Single-agent architecture; no agent delegation or sub-agent trust hierarchy.

---

## Summary Table

| OWASP Category | In OPA scope? | Out-of-scope owner |
|---|---|---|
| ASI01 Agent Goal Hijack | Partial | Agent layer (LangGraph prompt/reasoning) |
| ASI02 Tool Misuse | In scope | — |
| ASI03 Identity & Privilege Abuse | Partial | Deployment (cryptographic identity verification) |
| ASI04 Supply Chain | Out of scope | Infrastructure/deployment (runtime integrity) |
| ASI05 Unexpected RCE | Not applicable | — |
| ASI06 Memory & Context Poisoning | Out of scope | Agent layer |
| ASI07 Inter-Agent Communication | Not applicable | — |
| ASI08 Cascading Failures | Partial | Infrastructure (rate limiting, audit logging) |
| ASI09 Human-Agent Trust Exploitation | Out of scope | Agent layer |
| ASI10 Rogue Agents | Not applicable | — |

Categories flowing into the OPA policy: ASI02, ASI03 (partial), ASI08 (partial)

---

## Gap Register

| Threat | Layer | Recommended action |
|---|---|---|
| TI-01-A: System prompt injection via user_profile values | Agent layer | Sanitize user_profile values before embedding; strip Markdown injection patterns in build_system_prompt() |
| TI-01-B: Indirect goal redirection via question field | Agent layer | Apply prompt injection detection before passing question to ReAct loop |
| TI-04-A: MCP server stdio transport compromise | Infrastructure | Pin server.py dependencies by hash; verify server binary integrity at startup |
| TI-06-A: Context poisoning via user_profile in conversation history | Agent layer | Validate user_profile types/values against allowed sets before embedding |
| TI-06-B: Conversation manipulation bypassing write-confirmation gate | Agent layer | Enforce confirmation gate in LangGraph before issuing any write tool call; do not accept prior conversation claims as confirmation |
| TI-09-A: Confirmation gate bypass via fabricated context | Agent layer | Enforce confirmation gate in LangGraph; require explicit "yes" response in current turn |
| TI-09-B: Paternity leave approval manipulation via fake conversation history | Agent layer | Add structured system variable (e.g., `paternity_details_confirmed`) set by agent before invoking create_time_off_request with leave_type=Paternity |
| BS-1: Manager may view direct reports' data | Agent layer / DB layer | Pre-fetch manager relationship (SELECT manager_id) and pass as OPA input extension, or enforce at DB layer |
| BS-2: Non-IBM users blocked from IBM employee data | Agent layer / DB layer | Pre-fetch target employee's organization before tool call and pass as OPA input extension |
| BS-3: Salary updated only by HR or direct manager | Agent layer / DB layer | Pre-fetch manager relationship and pass as OPA input extension; safe default (HR-or-self) is OPA-enforceable |
| BS-4: Passport/visa expiry >6 months from update date | Agent layer | Add current_date to system_vars.json; pass as OPA input extension per invocation |
| BS-5: Home address only within own current country | Agent layer / DB layer | Pre-fetch employee's current country from DB and pass as OPA input extension |
| BS-6: Blacklist check on passport update | Agent layer | Add blacklist to system_vars.json; pass per-user blacklist status as OPA input extension |
| BS-7: Emergency contact in same area | Agent layer / DB layer | Pre-fetch employee location from DB and pass as OPA input extension |
| BS-8: Time-off balance check before request creation | Agent layer / DB layer | Pre-compute leave balance and pass as OPA input extension, or enforce at API layer |
| BS-9: Paternity leave approved only with baby details in conversation | Agent layer | Enforce at agent layer before issuing update_time_off_status with Approved and leave_type=Paternity |
| BS-10: Requesting employee may set status only to Pending | Agent layer / DB layer | Pre-fetch request owner's user_id (request_id → user_id) and pass as OPA input extension |
| BS-11: DB write confirmation before writes | Agent layer | Enforce confirmation gate in LangGraph before any write tool call |
| BS-12: User delete confirmation phrase | Agent layer | Enforce confirmation phrase at agent layer before invoking delete_employee |
| BS-13: Agent makes one tool call at a time | Agent layer | Enforce via structured output parsing; reject multi-tool responses |
| Rate limiting / audit logging (ASI08 cascade) | Infrastructure | Implement per-session rate limits; add immutable audit logging for all tool calls |
| Cryptographic authentication of subject claims (ASI03) | Infrastructure | Replace self-reported user_profile with cryptographically verified session tokens |

---

## Policy Rules (OPA scope only)

### Input Schema

| Field | Source |
|---|---|
| `input.action` | Tool name (from MCP tool call) |
| `input.args.user_id` | Tool argument (integer) — the target employee |
| `input.args.salary` | Tool argument (optional number) |
| `input.args.email` | Tool argument (optional string) |
| `input.args.organization` | Tool argument (optional string) |
| `input.args.leave_type` | Tool argument (string) |
| `input.args.start_date` | Tool argument (string, YYYY-MM-DD) |
| `input.args.end_date` | Tool argument (string, YYYY-MM-DD) |
| `input.args.status` | Tool argument (string) — time-off request status |
| `input.args.issue_date` | Tool argument (optional string, YYYY-MM-DD) |
| `input.args.expiry_date` | Tool argument (optional string, YYYY-MM-DD) |
| `input.extensions.subject.user_id` | Session variable — the acting user's own user_id |
| `input.extensions.subject.department` | Session variable — acting user's department |
| `input.extensions.subject.organization` | Session variable — acting user's organization |
| `input.extensions.subject.user_name` | Session variable — acting user's display name |

### Known Values

- **HR-only write tools:** `add_employee`, `add_department`, `update_department`, `add_holiday`, `delete_holiday`, `set_leave_allotment`
- **Personal-record tools (ownership required):** `set_passport`, `update_passport`, `get_passport`, `set_visa`, `update_visa`, `get_visa`, `set_emergency_contact`, `update_emergency_contact`, `get_emergency_contact`, `set_bank_account`, `update_bank_account`, `get_bank_account`
- **Employee-record tools (ownership required):** `get_employee`, `update_employee`
- **Leave-view tools (ownership required):** `get_leave_allotments`, `list_time_off_requests`, `get_leave_balance`, `get_time_off_request`
- **Passport/visa date tools:** `set_passport`, `update_passport`, `set_visa`, `update_visa`
- **HR department value:** `"HR"` (from system_vars.json department array)
- **Organization domain map:** `IBM Corporation` → `@ibm.com`; `Red Hat` → `@redhat.com`; `Kyndryl` → `@kyndryl.com`
- **Valid time-off statuses:** `Pending`, `Approved`, `Denied`
- **Time-off span limit:** 90 calendar days (end_date − start_date ≤ 90)

---

### Rule: HR_ONLY
- **OWASP:** ASI02 (Tool Misuse), ASI03 (Identity & Privilege Abuse)
- **Threat instances:** TI-02-A, TI-08-A
- **Severity:** Hard block
- **Condition:** The tool called is in the HR-only write tools set AND `input.extensions.subject.department` is not `"HR"`
- **Matching:** Exact set membership for tool name; exact equality for department value
- **Governed tools:** `add_employee`, `add_department`, `update_department`, `add_holiday`, `delete_holiday`, `set_leave_allotment`
- **Field verification:**
  - `input.action` — present for all tool calls
  - `input.extensions.subject.department` — declared in `system_vars.json`
  - All 6 tools confirmed in `tool_definitions.json`
- **Mitigation grounding:** ASI02: "Least Agency and Least Privilege for Tools — Define per-tool least-privilege profiles and restrict agentic tool functionality"; "Policy Enforcement Middleware ('Intent Gate') — A pre-execution Policy Enforcement Point (PEP/PDP) validates intent and arguments."

---

### Rule: OWNERSHIP (personal records)
- **OWASP:** ASI02 (Tool Misuse), ASI03 (Identity & Privilege Abuse)
- **Threat instances:** TI-02-B, TI-03-A, TI-08-B
- **Severity:** Hard block
- **Condition:** The tool called is in the personal-record tools set AND `input.extensions.subject.department` is not `"HR"` AND `input.args.user_id` does not equal `input.extensions.subject.user_id`
- **Matching:** Exact set membership for tool name; exact equality for department; exact integer equality for user_id
- **Governed tools:** `set_passport`, `update_passport`, `get_passport`, `set_visa`, `update_visa`, `get_visa`, `set_emergency_contact`, `update_emergency_contact`, `get_emergency_contact`, `set_bank_account`, `update_bank_account`, `get_bank_account`
- **Field verification:**
  - Each of the 12 tools declares `user_id` as a required integer parameter (confirmed in `tool_definitions.json`)
  - `input.extensions.subject.department` — declared in `system_vars.json`
  - `input.extensions.subject.user_id` — declared in `system_vars.json`
- **Mitigation grounding:** ASI02: "Action-Level Authentication and Approval — Require explicit authentication for each tool invocation." ASI03: "Enforce Task-Scoped, Time-Bound Permissions."

---

### Rule: OWNERSHIP (employee records)
- **OWASP:** ASI02 (Tool Misuse), ASI03 (Identity & Privilege Abuse)
- **Threat instances:** TI-02-B, TI-03-A
- **Severity:** Hard block
- **Condition:** The tool called is `get_employee` or `update_employee` AND `input.extensions.subject.department` is not `"HR"` AND `input.args.user_id` does not equal `input.extensions.subject.user_id`
- **Matching:** Exact equality for tool name; exact equality for department; exact integer equality for user_id
- **Governed tools:** `get_employee`, `update_employee`
- **Field verification:**
  - `get_employee` declares `user_id` (required integer) — confirmed in `tool_definitions.json`
  - `update_employee` declares `user_id` (required integer) — confirmed in `tool_definitions.json`
  - `input.extensions.subject.department`, `input.extensions.subject.user_id` — declared in `system_vars.json`
- **Mitigation grounding:** ASI02: "Least Agency and Least Privilege for Tools." ASI03: "Mandate Per-Action Authorization."

---

### Rule: SALARY_INVALID
- **OWASP:** ASI02 (Tool Misuse)
- **Threat instance:** TI-02-C
- **Severity:** Hard block
- **Condition:** The tool called is `add_employee` or `update_employee` AND `input.args.salary` is present (not null) AND `input.args.salary` is less than or equal to zero
- **Matching:** Exact set membership for tool name; numeric comparison (≤ 0) for salary
- **Governed tools:** `add_employee`, `update_employee`
- **Field verification:**
  - `add_employee` declares `salary` as optional number (`anyOf: [number, null]`) — confirmed in `tool_definitions.json`
  - `update_employee` declares `salary` as optional number (`anyOf: [number, null]`) — confirmed in `tool_definitions.json`
- **Mitigation grounding:** ASI02: "Policy Enforcement Middleware ('Intent Gate') — validates intent and arguments, enforces schemas."

---

### Rule: EMAIL_DOMAIN
- **OWASP:** ASI02 (Tool Misuse)
- **Threat instance:** TI-02-D
- **Severity:** Hard block
- **Condition:** The tool called is `add_employee` or `update_employee` AND both `input.args.email` and `input.args.organization` are present in the same call AND the email address domain suffix does not match the organization's required corporate domain (IBM Corporation → @ibm.com; Red Hat → @redhat.com; Kyndryl → @kyndryl.com)
- **Matching:** Exact set membership for tool name; substring/suffix check for email domain; exact equality for organization value
- **Governed tools:** `add_employee`, `update_employee`
- **Field verification:**
  - `add_employee` declares `email` (required string) and `organization` (optional string) — confirmed in `tool_definitions.json`
  - `update_employee` declares `email` (optional string) and `organization` (optional string) — confirmed in `tool_definitions.json`
  - Organization values (`IBM Corporation`, `Red Hat`, `Kyndryl`) appear in `system_vars.json` and in tool descriptions
- **Mitigation grounding:** ASI02: "Semantic and Identity Validation ('Semantic Firewalls') — Enforce fully qualified names; validate the intended semantics of tool calls rather than relying on syntax alone."

---

### Rule: TIMEOFF_OWNERSHIP
- **OWASP:** ASI02 (Tool Misuse), ASI03 (Identity & Privilege Abuse)
- **Threat instance:** TI-03-A (ownership bypass on time-off creation)
- **Severity:** Hard block
- **Condition:** The tool called is `create_time_off_request` AND `input.extensions.subject.department` is not `"HR"` AND `input.args.user_id` does not equal `input.extensions.subject.user_id`
- **Matching:** Exact equality for tool name; exact equality for department; exact integer equality for user_id
- **Governed tool:** `create_time_off_request`
- **Field verification:**
  - `create_time_off_request` declares `user_id` (required integer) — confirmed in `tool_definitions.json`
  - `input.extensions.subject.department`, `input.extensions.subject.user_id` — declared in `system_vars.json`
- **Mitigation grounding:** ASI02: "Action-Level Authentication and Approval."

---

### Rule: TIMEOFF_SPAN
- **OWASP:** ASI02 (Tool Misuse)
- **Threat instance:** TI-02-B (parameter manipulation on time-off)
- **Severity:** Hard block
- **Condition:** The tool called is `create_time_off_request` AND both `input.args.start_date` and `input.args.end_date` are present AND the difference `end_date − start_date` exceeds 90 calendar days
- **Matching:** Exact equality for tool name; date arithmetic (ISO YYYY-MM-DD) for span
- **Governed tool:** `create_time_off_request`
- **Field verification:**
  - `create_time_off_request` declares `start_date` (required string) and `end_date` (required string) — confirmed in `tool_definitions.json`
- **Mitigation grounding:** ASI02: "Policy Enforcement Middleware — enforces schemas and rate limits."

---

### Rule: DATE_ORDER
- **OWASP:** ASI02 (Tool Misuse)
- **Threat instance:** TI-02-B (parameter manipulation on date fields)
- **Severity:** Hard block
- **Condition:** The tool called is one of the passport/visa date tools AND both `input.args.issue_date` and `input.args.expiry_date` are present in the same call AND `issue_date` is not strictly earlier than `expiry_date`
- **Matching:** Exact set membership for tool name; ISO date comparison (issue_date < expiry_date)
- **Governed tools:** `set_passport`, `update_passport`, `set_visa`, `update_visa`
- **Field verification:**
  - `set_passport` declares `issue_date` (optional string) and `expiry_date` (optional string) — confirmed
  - `update_passport` declares `issue_date` (optional string) and `expiry_date` (optional string) — confirmed
  - `set_visa` declares `issue_date` (optional string) and `expiry_date` (optional string) — confirmed
  - `update_visa` declares `issue_date` (optional string) and `expiry_date` (optional string) — confirmed
- **Mitigation grounding:** ASI02: "Policy Enforcement Middleware — enforces schemas."

---

### Rule: LEAVE_OWNERSHIP
- **OWASP:** ASI02 (Tool Misuse), ASI03 (Identity & Privilege Abuse)
- **Threat instances:** TI-02-B, TI-03-A
- **Severity:** Hard block
- **Condition:** The tool called is in the leave-view tools set AND `input.extensions.subject.department` is not `"HR"` AND `input.args.user_id` does not equal `input.extensions.subject.user_id`
- **Matching:** Exact set membership for tool name; exact equality for department; exact integer equality for user_id
- **Governed tools:** `get_leave_allotments`, `list_time_off_requests`, `get_leave_balance`, `get_time_off_request`
- **Field verification:**
  - `get_leave_allotments` declares `user_id` (required integer) — confirmed
  - `list_time_off_requests` declares `user_id` (optional integer) — confirmed
  - `get_leave_balance` declares `user_id` (required integer) — confirmed
  - `get_time_off_request` declares `request_id` (required integer), NOT `user_id` — **NARROWED**: the ownership check on `user_id` does not apply to `get_time_off_request` because that tool does not take `user_id` as a parameter. The rule covers the other three tools only. `get_time_off_request` is dropped from this rule's governed tools. [STEP 6b criterion 1b: `user_id` absent from `get_time_off_request` parameters]
- **Governing tools (post-narrowing):** `get_leave_allotments`, `list_time_off_requests`, `get_leave_balance`
- **Mitigation grounding:** ASI02: "Least Agency and Least Privilege for Tools." ASI03: "Isolate Agent Identities and Contexts."

---

### Rule: TIMEOFF_STATUS
- **OWASP:** ASI02 (Tool Misuse), ASI03 (Identity & Privilege Abuse)
- **Threat instances:** TI-02-A, TI-03-A (role-based status update)
- **Severity:** Hard block
- **Condition:** The tool called is `update_time_off_status` AND `input.extensions.subject.department` is not `"HR"` AND `input.args.status` is `"Approved"` or `"Denied"`
- **Matching:** Exact equality for tool name; exact equality for department; exact set membership for status value
- **Governed tool:** `update_time_off_status`
- **Field verification:**
  - `update_time_off_status` declares `request_id` (required integer) and `status` (required string) — confirmed in `tool_definitions.json`. Status values `Pending`, `Approved`, `Denied` appear in the tool description.
  - `input.extensions.subject.department` — declared in `system_vars.json`
- **Mitigation grounding:** ASI02: "Action-Level Authentication and Approval — require explicit authentication for each tool invocation." ASI03: "Enforce Task-Scoped, Time-Bound Permissions."

---

## Citation Verification Log (STEP 6b)

- R1 (HR_ONLY): All 6 tools confirm `input.action`; `subject.department` in system_vars.json. ✓
- R2 (OWNERSHIP personal): All 12 tools declare `user_id` required. ✓
- R3 (OWNERSHIP employee): Both tools declare `user_id` required. ✓
- R4 (SALARY_INVALID): Both tools declare `salary` optional number. ✓
- R5 (EMAIL_DOMAIN): Both tools declare `email` and `organization`. ✓
- R6 (TIMEOFF_OWNERSHIP): `create_time_off_request` declares `user_id` required. ✓
- R7 (TIMEOFF_SPAN): `create_time_off_request` declares `start_date`/`end_date` required. ✓
- R8 (DATE_ORDER): All 4 passport/visa tools declare `issue_date`/`expiry_date` optional. ✓
- R9 (LEAVE_OWNERSHIP): **NARROWED** — `get_time_off_request` dropped (no `user_id` parameter); 3 remaining tools verified. `Citations verified: 9/9 — 1 rule narrowed (LEAVE_OWNERSHIP covers 3 of 4 originally governed tools; get_time_off_request dropped for missing user_id field per criterion 1b)`
- R10 (TIMEOFF_STATUS): `update_time_off_status` declares `status` required; values confirmed in description. ✓

**Overall: Citations verified: 9/9 — 1 rule narrowed (LEAVE_OWNERSHIP, get_time_off_request dropped, criterion 1b)**

---

## Violation Code Reference

| Code | OWASP | Governed Tools | Severity |
|---|---|---|---|
| `HR_ONLY` | ASI02, ASI03 | add_employee, add_department, update_department, add_holiday, delete_holiday, set_leave_allotment | Hard block |
| `OWNERSHIP` | ASI02, ASI03 | 12 personal-record tools + get_employee + update_employee | Hard block |
| `SALARY_INVALID` | ASI02 | add_employee, update_employee | Hard block |
| `EMAIL_DOMAIN` | ASI02 | add_employee, update_employee | Hard block |
| `TIMEOFF_OWNERSHIP` | ASI02, ASI03 | create_time_off_request | Hard block |
| `TIMEOFF_SPAN` | ASI02 | create_time_off_request | Hard block |
| `DATE_ORDER` | ASI02 | set_passport, update_passport, set_visa, update_visa | Hard block |
| `LEAVE_OWNERSHIP` | ASI02, ASI03 | get_leave_allotments, list_time_off_requests, get_leave_balance | Hard block |
| `TIMEOFF_STATUS` | ASI02, ASI03 | update_time_off_status | Hard block |
