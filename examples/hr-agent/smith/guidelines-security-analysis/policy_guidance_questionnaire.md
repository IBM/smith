# Policy Guidance Questionnaire — HR Agent

**Guidance source**: `examples/hr-agent/smith/guidance.txt` (2 rules, as of this run)
**System vars**: `examples/hr-agent/smith/system_vars.json`
**Tool definitions**: `examples/hr-agent/smith/tool_definitions.json` (6 tools)

---

## Current Guidance Rules

```
Rule 1: All employees can only access internal repositories.
Rule 2: All employees cannot access other teams' repositories.
```

---

## Questionnaire

### Q1 — What roles exist in the system?

**Answer**: `["hr", "engineer", "marketing", "finance", "platform", "security"]`

From `system_vars.json`. These are the complete set of possible roles that can appear in `input.extensions.subject.roles`.

**Guidance mapping**: Rules 1 and 2 apply to "all employees" — no role discrimination stated.

---

### Q2 — What permissions exist in the system?

**Answer**: `["view_ssn", "None"]`

From `system_vars.json`. `view_ssn` grants access to SSN data. `None` means no special permissions.

**Guidance mapping**: No current guidance rule references permissions explicitly. However, the `get_compensation` tool's `include_ssn` parameter implies a permission gate is needed. *[inferred — low confidence]*

---

### Q3 — What is the complete set of tools available?

**Answer**: 6 tools:
- `get_compensation` — returns salary, bonus, department, optionally SSN
- `display_compensation` — returns compensation band summary (no salary)
- `get_directory` — returns employee directory, optionally filtered by department
- `send_email` — sends (simulates) an email
- `search_repos` — searches repositories by name and/or visibility
- `adjust_compensation` — raises an employee's salary by a given dollar amount

---

### Q4 — Which tools operate on sensitive data?

**Answer**:
- `get_compensation`: salary, bonus, SSN — highly sensitive
- `display_compensation`: compensation band — moderately sensitive
- `adjust_compensation`: modifies salary — highly sensitive (write operation)
- `get_directory`: employee names and departments — moderately sensitive
- `send_email`: body can contain arbitrary PII — sensitive if misused
- `search_repos`: repository metadata — low sensitivity, but visibility restriction required by Rule 1

**Guidance mapping**: Only `search_repos` is covered by current guidance (Rules 1–2). All compensation tools and `send_email` are uncovered.

---

### Q5 — Are there any tools that perform write or mutation operations?

**Answer**: Yes.
- `adjust_compensation`: mutates `employee["salary"]` in-place. **No authorization layer on the server.**
- `send_email`: appends to `SENT_EMAILS` list. Non-reversible action.

**Guidance mapping**: No current rule covers `adjust_compensation` or `send_email` write semantics.

---

### Q6 — Which tools should be restricted by role?

**Answer** (combining guidance + architecture analysis):
- `get_compensation` / `display_compensation` / `adjust_compensation`: HR-only *[inferred — low confidence; not in current guidance]*
- `search_repos`: engineer + security only *[inferred — low confidence; guidance says "internal only" for all employees but does not restrict by role]*
- `get_directory`: no role restriction stated
- `send_email`: no role restriction stated

**Guidance mapping**: Rule 1 covers `search_repos` visibility but not role. Rule 2 covers team-scoped repo access but the `team` field is undeclared (blind spot).

---

### Q7 — Are there system variables needed to enforce the rules that are currently missing?

**Answer**: Yes. Rule 2 requires knowing the caller's team (`input.extensions.subject.team`) and the team that owns each repository. Neither is declared in `system_vars.json` nor available in any tool schema.

See `extension_suggestions.json`: `input.extensions.subject.team` is suggested as a new system variable for this rule to become enforceable.

**Impact**: Rule 2 cannot currently be enforced. It is a policy intent with no available enforcement path.

---

### Q8 — What is the `has_approval` variable and how should it be used?

**Answer**: `has_approval` is a string `"true"` or `"false"` in `system_vars.json`. It is self-reported by the caller and indicates whether manager approval was obtained.

**Inferred use** *[low confidence]*: Large salary adjustments should require `has_approval == "true"` before proceeding. The threshold and use are not stated in current guidance.

---

### Q9 — What repository visibility levels exist and what restrictions apply?

**Answer**: Three visibility levels: `internal`, `public`, `external`.

From Rule 1: "All employees can only access internal repositories" → interpreted as: `search_repos` with `visibility=external` is denied for all roles. `visibility=public` is ambiguous — "internal" could mean either "only internal" (blocking public too) or "not external" (allowing public). Conservative interpretation: block `external` only; allow `internal` and `public`.

From Rule 2: Team-scoped restriction — cannot be enforced (see Q7).

---

### Q10 — Should `visibility=external` be a hard block or role-gated?

**Answer**: Rule 1 states "all employees" → hard block for all roles including security. The prior analysis added a security-role exception *[inferred — low confidence from prior session]*; however, current guidance says no employee should access external repositories. Strict reading: `visibility=external` blocks all, including security.

**Note**: If the intent is "security can access external", this requires an explicit guidance rule. As written, Rule 1 is a universal block.

---

### Q11 — Does the LLM agent prompt constrain tool behavior?

**Answer**: Yes, but only advisorily. `SYSTEM_PROMPT` in `agent.py` instructs the model to set `include_ssn=true` only when the user explicitly asks. This is a behavioral constraint on the LLM, not a technical enforcement. It can be bypassed by:
- A user who explicitly phrases their request to trigger the condition
- A prompt injection in user input
- A different LLM or model version

OPA enforcement is required to enforce `include_ssn` restrictions technically.

---

### Q12 — Should `search_repos` be blocked entirely for non-technical roles, or only restricted by visibility?

**Answer** *[inferred — low confidence; not in current guidance]*: Current guidance only restricts visibility (Rule 1). Role-based restriction on `search_repos` is not stated. However, the architecture analysis notes that only `engineer` and `security` roles have a legitimate reason to search repositories. This is a coverage gap.

If policy intent is to also restrict by role, a new guidance rule is needed.

---

### Q13 — What should happen when `include_ssn=true` is requested without the `view_ssn` permission?

**Answer** *[inferred — low confidence]*: The request should be denied. `view_ssn` exists as a permission value in `system_vars.json` specifically to gate SSN access. Without an explicit guidance rule, this cannot be confirmed as intent — but the permission's existence implies gate semantics.

---

### Q14 — What is the threshold for large compensation adjustments and what approval is required?

**Answer** *[inferred — low confidence; not in current guidance]*: `system_vars.json` includes `has_approval: "true|false"`. The architecture analysis notes `adjust_compensation` takes an integer `amount`. No threshold or approval requirement appears in the current 2-rule `guidance.txt`. This is a coverage gap.

---

### Q15 — Should `send_email` be blocked if PII (e.g., SSN) appears in the subject or body?

**Answer** *[inferred — low confidence]*: The `get_compensation` tool can return SSN data. If the LLM includes that SSN in a `send_email` call (exfiltration via email), it would be an ASI07/ASI03 threat. No current guidance rule covers this. A DLP-style block on SSN patterns in email content is a coverage gap.

---

### Q16 — Are there denial-of-service or resource exhaustion concerns?

**Answer**: Limited. The in-memory fixtures (`EMPLOYEES`, `REPOS`, `SENT_EMAILS`) are bounded. No pagination or rate limiting is present on the MCP server. `SENT_EMAILS` grows unboundedly but is not persisted. OPA cannot address rate limiting — this is out of scope for policy enforcement.

---

### Q17 — Can the same tool be called with different subject contexts in the same session?

**Answer**: Yes. `HRAgent` maintains per-session history (`_histories[session_id]`). Within a session, the identity headers (`X-User-Token`, `Authorization`) are forwarded on each tool call. If these headers change between calls (possible if the client rotates them), the subject context can shift. OPA evaluates each call independently.

---

### Q18 — Is there any authentication at the MCP server layer?

**Answer**: No. `server.py` has no authentication or authorization at any layer. It executes any well-formed tool call it receives. All enforcement must be applied upstream (at OPA, Layer 2→4 intercept).

---

### Q19 — What data does `get_directory` return and should it be restricted?

**Answer**: Returns employee name, email, department, and title from the `EMPLOYEES` dict. Filtered by `department` if provided. No current guidance rule restricts `get_directory`. The architecture analysis finds no role or permission gate — any caller can enumerate all employees. This is a low-severity gap but not covered by current guidance.

---

### Q20 — What happens to `display_compensation` — is it sensitive?

**Answer**: `display_compensation` returns band name only (e.g., "L5 - Senior Engineer"), not salary or SSN. It is less sensitive than `get_compensation`. However, it is a compensation tool and the architecture groups it with `get_compensation` and `adjust_compensation`. Role restriction *[inferred — low confidence]* would apply HR-only if compensation rules are added.

---

### Q21 — Are there any cross-tool exfiltration chains?

**Answer**: Yes, at least two:
1. `get_compensation(include_ssn=true)` → `send_email(body="SSN: 123-45-6789")` — SSN extracted then emailed
2. `get_directory()` → `send_email(body=<full directory dump>)` — directory exfiltrated

Rule 1 and Rule 2 do not address these chains. They are coverage gaps.

---

### Q22 — Summary: which guidance rules map to enforceable OPA conditions and which do not?

| Rule | Text | Enforceable? | OPA Path | Gap |
|------|------|-------------|----------|-----|
| 1 | All employees can only access internal repositories | Yes (partial) | `input.name == "search_repos"` + `args.visibility == "external"` | Does not gate by role — any role can search internal/public |
| 2 | All employees cannot access other teams' repositories | No | Requires `input.extensions.subject.team` | Field undeclared in system_vars.json — cannot fire |
| (inferred) | Only HR can access compensation | Not in guidance | `input.name` in compensation_tools + `subject.roles` | New rule needed |
| (inferred) | view_ssn required for include_ssn=true | Not in guidance | `args.include_ssn == true` + `subject.permissions` | New rule needed |
| (inferred) | Only engineer/security can search repos | Not in guidance | `input.name == "search_repos"` + `subject.roles` | New rule needed |
| (inferred) | Approval required for large adjustments | Not in guidance | `args.amount > threshold` + `subject.has_approval` | New rule needed |
| (inferred) | No SSN in emails | Not in guidance | `regex.match(ssn_pattern, args.subject/body)` | New rule needed |
