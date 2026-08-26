# OWASP Top 10 for Agentic AI Security — Scope Assessment and Policy Guidelines
# Tool: employee (Enterprise Employee Hub — 29 tools)

---

## Architecture Summary

The Enterprise Employee Hub is a LangGraph ReAct agent (`agent.py`, FastAPI :9000) that launches a local FastMCP server (`server.py`, stdio) providing 29 tools across employees, org chart, departments, sensitive personal records (passport, visa, emergency contact, bank account), time-off/leave, and country holidays — all backed by a shared SQLite database. There is no authentication or authorization layer anywhere in the stack; the caller's identity is entirely self-reported via a `user_profile` JSON body field that is injected verbatim into the LLM system prompt. OPA intercepts at the agent → MCP server boundary where `input.name`, `input.args.*`, and `input.extensions.subject.*` (populated from `user_profile`) are all present as structured data — but every identity field is self-reported, so OPA's enforcement is only as strong as what the caller claims.

---

## OWASP Top 10 for Agentic AI Security — Scope Assessment

### ASI01 — Agent Goal Hijack
**Risk:** Callers inject arbitrary keys into `user_profile` that the LLM treats as authoritative constraints, falsely claiming HR status or redirecting the agent to call write tools on behalf of the attacker.
**Verdict:** Partial — OPA can block the resulting tool call based on `subject.department` and ownership checks; it cannot intercept the LLM's reasoning about the injected `user_profile` values (Agent layer).

### ASI02 — Tool Misuse and Exploitation
**Risk:** The LLM or crafted prompts assemble tool calls with invalid parameters (zero salary, wrong email domain, out-of-range dates, excessive leave span, unauthorized administrative actions) that corrupt the database.
**Verdict:** Partial — OPA can enforce parameter integrity rules (salary > 0, email domain, date ordering, 90-day span, HR-only admin tools); exfiltration chain patterns (iterating all bank accounts in a loop) are out of OPA scope (Agent layer).

### ASI03 — Identity and Privilege Abuse
**Risk:** Callers forge `user_profile` to claim any identity (`user_id`, `department`, `organization`) and access/modify any employee's sensitive data without restriction.
**Verdict:** In scope (with caveat) — OPA can enforce role-based and ownership-based rules using `subject.department` and `subject.user_id` vs `args.user_id`; however, all identity is self-reported so OPA provides defense-in-depth only, not cryptographic identity assurance.

### ASI04 — Agentic Supply Chain Vulnerabilities
**Risk:** Compromised third-party packages (`langchain-*`, `mcp`, `openai`) or an unpinned LLM model alter tool argument construction or bypass identity field population.
**Verdict:** Out of scope — OPA cannot verify package integrity at invocation time. Ownership: Infrastructure/Deployment.

### ASI05 — Unexpected Code Execution (RCE)
**Risk:** Agents that generate and execute code create RCE pathways.
**Verdict:** Out of scope — no code-generation or execution tools. Not applicable.

### ASI06 — Memory & Context Poisoning
**Risk:** Sensitive DB response data (salary, bank account, passport numbers) returned into the LLM context influences subsequent tool-call decisions, or false context is built across turns to claim manager status.
**Verdict:** Out of scope — OPA intercepts pre-execution; it cannot inspect tool responses or conversation history. Ownership: Agent layer (output filtering, conversation isolation).

### ASI07 — Insecure Inter-Agent Communication
**Risk:** Multi-agent inter-agent communication vulnerabilities.
**Verdict:** Out of scope — single-agent deployment; MCP server is a local stdio subprocess. Not applicable.

### ASI08 — Cascading Failures
**Risk:** A single agentic turn chains `list_employees` → `get_bank_account` × N, exfiltrating all bank account records in one unbroken reasoning loop.
**Verdict:** Partial — OPA enforces ownership rules on each individual tool call in the chain; it cannot see the cross-call chain pattern. The per-call ownership check is the effective mitigation.

### ASI09 — Human-Agent Trust Exploitation
**Risk:** Prompt injection causes the agent to fabricate authority justifications for accessing other employees' data; high-volume queries exfiltrate data below alerting thresholds.
**Verdict:** Out of scope — LLM reasoning and UX layers; not OPA-enforceable.

### ASI10 — Rogue Agents
**Risk:** Malicious peer agents deviate from intended scope.
**Verdict:** Out of scope — single-agent deployment. Not applicable.

---

## Summary Table

| OWASP Category | In OPA scope? | Out-of-scope owner |
|---|---|---|
| ASI01 Agent Goal Hijack | Partial | Agent layer (system prompt isolation, user_profile validation) |
| ASI02 Tool Misuse and Exploitation | Partial | Agent layer (exfiltration chains, rate limits) |
| ASI03 Identity and Privilege Abuse | Yes (self-reported caveat) | Infrastructure (authentication layer needed) |
| ASI04 Agentic Supply Chain Vulnerabilities | No | Infrastructure/Deployment |
| ASI05 Unexpected Code Execution (RCE) | No | N/A |
| ASI06 Memory & Context Poisoning | No | Agent layer (output filtering) |
| ASI07 Insecure Inter-Agent Communication | No | N/A |
| ASI08 Cascading Failures | Partial | Agent layer (cross-call chain detection) |
| ASI09 Human-Agent Trust Exploitation | No | Agent layer / UX |
| ASI10 Rogue Agents | No | N/A |

Categories flowing into the OPA policy: ASI01 (partial), ASI02 (partial), ASI03, ASI08 (partial)

---

## Gap Register

| Threat | Layer | Recommended action |
|---|---|---|
| ASI01 T2 — Arbitrary `user_profile` keys injected into system prompt override LLM constraints | Agent layer | Validate and allowlist `user_profile` keys against `system_vars.json` schema before injecting into system prompt; reject unknown keys |
| ASI01 T3 — LLM independently calls write tools based on inferred user intent without explicit instruction | Agent layer | Strengthen SYSTEM_PROMPT with explicit "only act on explicit user instructions" constraints; require confirmation for all write operations |
| ASI01 T4 — False manager context built across conversation turns | Agent layer | Bound conversation history; do not allow self-asserted manager claims in conversation to override identity from `user_profile` |
| ASI02 T2 — Loop exfiltration: `list_employees` → `get_bank_account` × N | Agent layer | Implement rate limiting per session; require explicit confirmation before bulk-read patterns |
| ASI03 (all) — All identity fields are self-reported with no cryptographic verification | Infrastructure | Add an authentication layer (JWT, OAuth, mTLS) upstream of the agent; propagate verified identity claims into `user_profile` |
| ASI03 T3 — Caller claims IBM organization to bypass org-isolation rule | Infrastructure | Enforce organization identity from a verified JWT claim, not from self-reported `user_profile.organization` |
| ASI03 T4 — Caller claims `user_id` of target's manager to assert manager privilege | Infrastructure + OPA | OPA cannot verify manager relationships; add `manager_ids` array to `system_vars.json` populated from the DB at session creation; or move manager-check enforcement to the agent layer via a DB pre-check |
| ASI04 T1 — Compromised third-party packages alter tool argument construction | Infrastructure/Deployment | Pin all Python dependencies by hash; maintain SBOM; use reproducible container builds |
| ASI04 T2 — Unpinned LLM model (`qwen3.5:latest`) — poisoned update alters tool-selection behaviour | Infrastructure/Deployment | Pin model by digest; gate model updates through a test suite |
| ASI06 T1 — Crafted DB field (e.g., `title`, `home_address`) injected via a prior write poisons LLM context | Agent layer | Sanitise tool responses before feeding into LLM context; strip or redact unexpected long-form text in employee record fields |
| ASI06 T2 — Caller builds false manager context across turns | Agent layer | Do not allow user messages to override identity claims; re-validate `user_profile` fields at each turn |
| ASI08 T2 — Corrupted `add_employee` call seeds session context for follow-up `update_employee` calls | Agent layer | Clear or quarantine session context after a failed or denied tool call |
| ASI09 T1 — LLM fabricates authority justification for accessing another employee's data | Agent layer | Strengthen SYSTEM_PROMPT prohibitions; monitor LLM outputs for authority-fabrication patterns |
| ASI09 T2 — High-volume queries below alerting threshold exfiltrate PII | Agent layer / UX | Implement per-session request rate limiting; alert on unusual access patterns (many distinct `user_id` values in one session) |
| Non-IBM org isolation (guidance "Users outside IBM org blocked from IBM data") | Infrastructure | Requires knowing target employee's organization at OPA time — add `target_employee_org` as a runtime-populated subject field, or enforce at the agent layer via a pre-check DB query |
| Direct manager authorization for salary updates | Infrastructure + OPA | OPA cannot verify manager relationships statically; add `manager_of` array to subject fields, or enforce at agent layer |
| 6-month passport/visa expiry rule | Agent layer | The current date is not in OPA input; enforce in `api/personal.py` (already partially enforced by API layer date ordering); or inject `current_date` as a system variable |
| Home address country-change restriction | Infrastructure + Agent layer | Requires knowing employee's current country from DB; enforce in `api/employees.py` with a pre-update DB lookup |
| Blacklist check on passport update | Infrastructure | Add `is_blacklisted` boolean to `system_vars.json` populated from the DB at session creation |
| Emergency contact area match | Infrastructure | Requires DB lookup for employee's location; enforce in the API layer |
| Leave balance check before `create_time_off_request` | Infrastructure | Requires computed DB query; enforce in `api/leave.py` |
| Paternity leave baby-details check | Agent layer | Requires scanning conversation history; enforce in agent pre-tool-call hook |
| DB-write confirmation requirement | Agent layer | Enforce in agent layer — require "yes" confirmation before any write tool call; not OPA-enforceable |
| Booking/frequent-flyer rule | N/A | Not an Employee Hub tool; remove from guidance.txt |

---

## Policy Rules (OPA scope only)

### Input Schema
| Field | Source |
|---|---|
| `input.name` | Tool name (LLM-chosen string) |
| `input.args.user_id` | Tool argument (int) — target employee |
| `input.args.salary` | Tool argument (float) |
| `input.args.email` | Tool argument (string) |
| `input.args.organization` | Tool argument (string) — in add/update employee calls |
| `input.args.expiry_date` | Tool argument (string, YYYY-MM-DD) |
| `input.args.issue_date` | Tool argument (string, YYYY-MM-DD) |
| `input.args.start_date`, `input.args.end_date` | Tool argument (string, YYYY-MM-DD) |
| `input.args.status` | Tool argument (string) — time-off status |
| `input.args.leave_type` | Tool argument (string) |
| `input.extensions.subject.user_id` | Self-reported — caller's asserted user ID (int) |
| `input.extensions.subject.department` | Self-reported — caller's asserted department (string) |
| `input.extensions.subject.organization` | Self-reported — caller's asserted organization (string) |

### Known values
- HR department: `"HR"`
- HR-only admin tools: `add_employee`, `add_department`, `update_department`, `add_holiday`, `delete_holiday`, `set_leave_allotment`
- Sensitive personal read tools: `get_passport`, `get_visa`, `get_bank_account`, `get_emergency_contact`, `get_employee`
- Sensitive personal write tools: `set_passport`, `update_passport`, `set_visa`, `update_visa`, `set_emergency_contact`, `update_emergency_contact`, `set_bank_account`, `update_bank_account`
- Leave view tools: `get_leave_allotments`, `get_leave_balance`, `get_time_off_request`, `list_time_off_requests`
- Organization email domains: `IBM Corporation` → `@ibm.com`; `Red Hat` → `@redhat.com`; `Kyndryl` → `@kyndryl.com`
- Valid time-off statuses: `Pending`, `Approved`, `Denied`
- Manager-settable statuses: `Approved`, `Denied` (requires DB manager check — partial enforcement only for non-HR block)

---

### Rule: HR_ONLY_ADMIN
- OWASP: ASI03 (Identity and Privilege Abuse) + ASI01 — catalog mitigation: "Mandate Per-Action Authorization: Re-verify each privileged step with a centralized policy engine"
- Severity: Hard block
- Condition: `input.name` is one of `add_employee`, `add_department`, `update_department`, `add_holiday`, `delete_holiday`, `set_leave_allotment` AND `input.extensions.subject.department != "HR"`
- Matching: Exact set-membership for tool name; exact equality for department

### Rule: PERSONAL_READ_OWN_OR_HR
- OWASP: ASI03 (Identity and Privilege Abuse) + ASI08 — catalog mitigation: "Enforce Task-Scoped, Time-Bound Permissions"
- Severity: Hard block
- Condition: `input.name` is one of `get_passport`, `get_visa`, `get_bank_account`, `get_emergency_contact`, `get_employee` AND `input.args.user_id != input.extensions.subject.user_id` AND `input.extensions.subject.department != "HR"`
- Matching: Exact set-membership for tool name; numeric equality for user_id; exact equality for department

### Rule: PERSONAL_WRITE_OWN_OR_HR
- OWASP: ASI03 (Identity and Privilege Abuse) + ASI02 — catalog mitigation: "Least Agency and Least Privilege for Tools"
- Severity: Hard block
- Condition: `input.name` is one of `set_passport`, `update_passport`, `set_visa`, `update_visa`, `set_emergency_contact`, `update_emergency_contact`, `set_bank_account`, `update_bank_account`, `update_employee` AND `input.args.user_id != input.extensions.subject.user_id` AND `input.extensions.subject.department != "HR"`
- Matching: Exact set-membership for tool name; numeric equality for user_id; exact equality for department

### Rule: SALARY_POSITIVE
- OWASP: ASI02 (Tool Misuse) — catalog mitigation: "Policy Enforcement Middleware ('Intent Gate'): validates intent and arguments, enforces schemas"
- Severity: Hard block
- Condition: `input.name` is one of `add_employee`, `update_employee` AND `input.args.salary` is present AND `input.args.salary <= 0`
- Matching: Exact set-membership for tool name; numeric comparison for salary

### Rule: EMAIL_DOMAIN_MATCH
- OWASP: ASI02 (Tool Misuse) — catalog mitigation: "Policy Enforcement Middleware ('Intent Gate')"
- Severity: Hard block
- Condition: `input.name` is one of `add_employee`, `update_employee` AND both `input.args.email` and `input.args.organization` are present in the same call AND `input.args.email` does not end with the domain corresponding to `input.args.organization` (`IBM Corporation` → `@ibm.com`, `Red Hat` → `@redhat.com`, `Kyndryl` → `@kyndryl.com`)
- Matching: Exact set-membership for tool name; case-insensitive suffix match for email domain; exact equality for organization

### Rule: DATE_ORDER_CHECK
- OWASP: ASI02 (Tool Misuse) — catalog mitigation: "Policy Enforcement Middleware ('Intent Gate')"
- Severity: Hard block
- Condition: `input.name` is one of `set_passport`, `update_passport`, `set_visa`, `update_visa` AND both `input.args.issue_date` and `input.args.expiry_date` are present in the same call AND `input.args.issue_date >= input.args.expiry_date` (string comparison on YYYY-MM-DD is lexicographically equivalent to date comparison)
- Matching: Exact set-membership for tool name; lexicographic comparison on YYYY-MM-DD strings

### Rule: TIME_OFF_OWN_ONLY
- OWASP: ASI03 (Identity and Privilege Abuse) — catalog mitigation: "Enforce Task-Scoped, Time-Bound Permissions"
- Severity: Hard block
- Condition: `input.name == "create_time_off_request"` AND `input.args.user_id != input.extensions.subject.user_id`
- Matching: Exact equality for tool name; numeric equality for user_id

### Rule: TIME_OFF_SPAN
- OWASP: ASI02 (Tool Misuse) — catalog mitigation: "Policy Enforcement Middleware ('Intent Gate')"
- Severity: Hard block
- Condition: `input.name == "create_time_off_request"` AND `end_date - start_date > 90 calendar days` (YYYY-MM-DD string difference)
- Matching: Exact equality for tool name; date arithmetic (YYYY-MM-DD difference in days > 90)

### Rule: LEAVE_VIEW_OWN_OR_HR
- OWASP: ASI03 (Identity and Privilege Abuse) — catalog mitigation: "Enforce Task-Scoped, Time-Bound Permissions"
- Severity: Hard block
- Condition: `input.name` is one of `get_leave_allotments`, `get_leave_balance`, `get_time_off_request`, `list_time_off_requests` AND a `user_id` argument is present AND `input.args.user_id != input.extensions.subject.user_id` AND `input.extensions.subject.department != "HR"`
- Matching: Exact set-membership for tool name; numeric equality for user_id; exact equality for department

### Rule: TIME_OFF_STATUS_NON_HR
- OWASP: ASI03 (Identity and Privilege Abuse) — catalog mitigation: "Mandate Per-Action Authorization"
- Severity: Hard block
- Condition: `input.name == "update_time_off_status"` AND `input.args.status` is one of `Approved`, `Denied` AND `input.extensions.subject.department != "HR"`
- Matching: Exact equality for tool name; exact set-membership for status; exact equality for department
- Note: This is a conservative rule — it blocks non-HR from approving/denying, which includes managers who should be allowed. The manager-check blind spot means this will produce false positives for legitimate managers. Annotated as pending until `subject.manager_of` can be populated.

---

## Violation Code Reference

| Code | OWASP | Severity |
|---|---|---|
| HR_ONLY_ADMIN | ASI01, ASI03 | Hard block |
| PERSONAL_READ_OWN_OR_HR | ASI03, ASI08 | Hard block |
| PERSONAL_WRITE_OWN_OR_HR | ASI02, ASI03 | Hard block |
| SALARY_POSITIVE | ASI02 | Hard block |
| EMAIL_DOMAIN_MATCH | ASI02 | Hard block |
| DATE_ORDER_CHECK | ASI02 | Hard block |
| TIME_OFF_OWN_ONLY | ASI03 | Hard block |
| TIME_OFF_SPAN | ASI02 | Hard block |
| LEAVE_VIEW_OWN_OR_HR | ASI03 | Hard block |
| TIME_OFF_STATUS_NON_HR | ASI03 | Hard block |

Citations verified: 10/10 — all `input.args.*` fields confirmed in `tool_definitions.json`; all `input.extensions.subject.*` fields confirmed in `system_vars.json`; all mitigation citations confirmed in `owasp_10_ai_catalog.json`; all rules trace to threat instances in `threat_model.md`.

---

## STEP 7 — Combined Candidate-Rule List

1. [ASI03/HR_ONLY_ADMIN + Q9] `input.name` ∈ HR-only admin tools; `subject.department != "HR"` → deny
2. [ASI03/PERSONAL_READ_OWN_OR_HR + Q9] sensitive read tools; `args.user_id != subject.user_id` AND `subject.department != "HR"` → deny
3. [ASI02+ASI03/PERSONAL_WRITE_OWN_OR_HR + Q9] sensitive write tools; `args.user_id != subject.user_id` AND `subject.department != "HR"` → deny
4. [ASI02/SALARY_POSITIVE + Q12] `add_employee`/`update_employee`; `args.salary` present AND `<= 0` → deny
5. [ASI02/EMAIL_DOMAIN_MATCH + Q12] `add_employee`/`update_employee`; both `args.email` and `args.organization` present; domain mismatch → deny
6. [ASI02/DATE_ORDER_CHECK + Q12] passport/visa tools; both `args.issue_date` and `args.expiry_date` present; `issue_date >= expiry_date` → deny
7. [ASI03/TIME_OFF_OWN_ONLY + Q9] `create_time_off_request`; `args.user_id != subject.user_id` → deny
8. [ASI02/TIME_OFF_SPAN + Q13] `create_time_off_request`; span > 90 days → deny
9. [ASI03/LEAVE_VIEW_OWN_OR_HR + Q9] leave view tools; `args.user_id != subject.user_id` AND `subject.department != "HR"` → deny
10. [ASI03/TIME_OFF_STATUS_NON_HR + Q9] `update_time_off_status`; `status` ∈ `{Approved, Denied}` AND `subject.department != "HR"` → deny (conservative — false positives for managers)

## STEP 8 — Coverage Scratch Table

The existing `guidance.txt` is the full detailed policy document for this agent. Checking each candidate against it:

| Candidate | Field | Operator | Value set | Matching guidance.txt section | Covered? |
|---|---|---|---|---|---|
| #1 HR_ONLY_ADMIN | `input.name` + `subject.department` | set-membership + exact | admin tools; `HR` | "Only HR may add or update a department, add or delete a country holiday, or set a leave allotment" + "Only HR may add a new employee" | Yes — covered |
| #2 PERSONAL_READ_OWN_OR_HR | `args.user_id` vs `subject.user_id` + `subject.department` | numeric equality + exact | own or HR | "An employee may view and edit only their own data"; "HR may view and edit all employees' data"; "A Manager may view only their direct reports' data" | Partial — self and HR covered; manager half is a blind spot |
| #3 PERSONAL_WRITE_OWN_OR_HR | `args.user_id` vs `subject.user_id` + `subject.department` | numeric equality + exact | own or HR | Same as #2 | Partial — same as #2 |
| #4 SALARY_POSITIVE | `args.salary` | numeric comparison | > 0 | "salary must be a positive amount (greater than zero)" | Yes — covered |
| #5 EMAIL_DOMAIN_MATCH | `args.email` + `args.organization` | suffix match + exact | org domain mapping | "email must use their organization's corporate domain" | Yes — covered |
| #6 DATE_ORDER_CHECK | `args.issue_date` + `args.expiry_date` | lexicographic comparison | issue < expiry | "issue date must be strictly earlier than its expiration date when both dates are provided in the same call" | Yes — covered |
| #7 TIME_OFF_OWN_ONLY | `args.user_id` vs `subject.user_id` | numeric equality | own | "An employee may create a time-off request only for themselves" | Yes — covered |
| #8 TIME_OFF_SPAN | `args.start_date` + `args.end_date` | date arithmetic | span ≤ 90 days | "A single time-off request may not span more than 90 consecutive calendar days" | Yes — covered |
| #9 LEAVE_VIEW_OWN_OR_HR | `args.user_id` vs `subject.user_id` + `subject.department` | numeric equality + exact | own or HR | "leave allotments, time-off requests, and leave balance may be viewed only by HR, the employee themselves, or the employee's direct manager" | Partial — self and HR covered; manager half is blind spot |
| #10 TIME_OFF_STATUS_NON_HR | `args.status` + `subject.department` | set-membership + exact | `{Approved,Denied}`; HR | "HR may set any status; the requester's direct manager may set it only to Approved or Denied" | Partial — HR enforcement covered; manager half is blind spot |

All 10 candidates are already represented in `guidance.txt`. **No new rules to append** — `guidance_updated.txt` will be identical to `guidance.txt`.

**Exception:** The booking/frequent-flyer rule in `guidance.txt` is out of scope (no Employee Hub tool maps to it). It is noted in the gap register but not removed — `guidance_updated.txt` preserves `guidance.txt` unchanged.

## STEP 8b — Redundancy Self-Check

Checking all rule pairs in `guidance_updated.txt` (= `guidance.txt`):
- Candidate #2 (PERSONAL_READ_OWN_OR_HR) and #3 (PERSONAL_WRITE_OWN_OR_HR): same ownership check, but different tool sets (read vs write). **Not redundant** — different tool sets.
- Candidate #9 (LEAVE_VIEW_OWN_OR_HR) and #2 (PERSONAL_READ_OWN_OR_HR): same ownership operator, but different tool sets (leave view vs personal records). **Not redundant.**
- All other pairs: distinct tools, distinct fields, or distinct operators.

**Redundancy self-check: no overlapping pairs found.**
