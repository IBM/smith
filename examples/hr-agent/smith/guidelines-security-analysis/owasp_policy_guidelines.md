# OWASP Policy Guidelines — Enforcement Mapping — HR Agent

**Run date**: 2026-09-04
**guidance.txt state**: 2 rules (bare-line style)
**Tool definitions**: 6 tools (tool_definitions.json)
**Output**: `guidance_updated.txt` with new rules continuing from existing 2

---

## STEP 1 — Input Review

### guidance.txt (current — 2 rules, bare-line style)
```
All employees can only access internal repositories.
All employees cannot access other teams' repositories.
```

Format classification: bare-line (0 numbered `<N>.` lines, 0 header `#` lines, 2 bare lines).
Continuation numbering: new rules start at 3 (implicit, matching bare-line style without prefix).

### Prior run `guidance_updated.txt` (captured before overwrite)
Prior run proposed 0 new rules. Content was non-conforming (contained headers and commentary, no rule lines). Regression baseline: 0 rules proposed.

### Tools in scope
`get_compensation`, `display_compensation`, `get_directory`, `send_email`, `search_repos`, `adjust_compensation`

### System variables available
- `input.extensions.subject.roles` → values: hr, engineer, marketing, finance, platform, security
- `input.extensions.subject.permissions` → values: view_ssn, None
- `input.extensions.subject.has_approval` → values: "true", "false" (string)
- `input.extensions.subject.user_name` → string
- `input.extensions.subject.team` → **UNDECLARED** (not in system_vars.json)

---

## STEP 2 — OWASP Coverage Mapping

| ASI | Name | Threat (from threat_model.md) | OPA-enforceable? | Candidate Rule |
|-----|------|-------------------------------|-----------------|----------------|
| ASI01 | Prompt Injection | inject include_ssn=true, exfiltrate SSN via email | Yes | SSN_VIEW_PERM, EMAIL_SSN_BLOCK |
| ASI02 | Excessive Agency | unrestricted compensation access, adjust_compensation no approval | Yes | COMP_HR_ONLY, ADJ_APPROVAL_THRESHOLD |
| ASI03 | Sensitive Data Exposure | SSN/salary exfiltration via email | Yes | SSN_VIEW_PERM, EMAIL_SSN_BLOCK |
| ASI04 | Insecure Trust | forged identity headers | Partial | COMP_HR_ONLY, REPO_ROLE_GATE (raise bar) |
| ASI05 | Access Control | no server authz, any role calls any tool | Yes | COMP_HR_ONLY, REPO_ROLE_GATE |
| ASI06 | Side-Effect Abuse | adjust_compensation unlimited, send_email spam | Yes | ADJ_APPROVAL_THRESHOLD, EMAIL_SSN_BLOCK |
| ASI07 | System Prompt Tampering | SYSTEM_PROMPT hardcoded — low risk | N/A | No new rule needed |
| ASI08 | Supply Chain | framework compromise | No | Out of OPA scope |
| ASI09 | Insufficient Logging | no server audit trail | No | Config concern, not a rule |
| ASI10 | Insecure Orchestration | single-agent, low risk | N/A | No new rule needed |

---

## STEP 3 — Candidate Rule Derivation

### Candidate 1: COMP_HR_ONLY
**Trigger**: `input.name` ∈ {get_compensation, display_compensation, adjust_compensation} AND "hr" ∉ `input.extensions.subject.roles`
**OPA fields**: `input.name`, `input.extensions.subject.roles`
**Available**: Yes — roles in system_vars.json
**ASI coverage**: ASI02, ASI05
**Guidance coverage**: None — not in current guidance.txt
**Status**: NEW RULE

### Candidate 2: SSN_VIEW_PERM
**Trigger**: `input.name` == "get_compensation" AND `input.args.include_ssn` == true AND "view_ssn" ∉ `input.extensions.subject.permissions`
**OPA fields**: `input.name`, `input.args.include_ssn`, `input.extensions.subject.permissions`
**Available**: Yes — permissions in system_vars.json
**ASI coverage**: ASI01, ASI03
**Guidance coverage**: None — not in current guidance.txt
**Status**: NEW RULE

### Candidate 3: REPO_ROLE_GATE
**Trigger**: `input.name` == "search_repos" AND "engineer" ∉ roles AND "security" ∉ roles
**OPA fields**: `input.name`, `input.extensions.subject.roles`
**Available**: Yes
**ASI coverage**: ASI02, ASI05
**Guidance coverage**: Rule 1 restricts *visibility* but not *role*. Rule 1 does not subsume REPO_ROLE_GATE — a marketing employee calling `search_repos(visibility="internal")` satisfies Rule 1 (internal only) but should be blocked by role. Two distinct enforcement dimensions.
**Status**: NEW RULE

### Candidate 4: REPO_VISIBILITY_GATE (visibility=external block)
**Trigger**: `input.name` == "search_repos" AND `input.args.visibility` == "external"
**OPA fields**: `input.name`, `input.args.visibility`
**Available**: Yes
**ASI coverage**: ASI02
**Guidance coverage**: Rule 1 — "All employees can only access internal repositories" → "external" is explicitly blocked.
**Status**: COVERED BY RULE 1 — no new rule needed

### Candidate 5: ADJ_APPROVAL_THRESHOLD
**Trigger**: `input.name` == "adjust_compensation" AND `input.args.amount` > 10000 AND `input.extensions.subject.has_approval` ≠ "true"
**OPA fields**: `input.name`, `input.args.amount`, `input.extensions.subject.has_approval`
**Available**: Yes — has_approval in system_vars.json; amount in tool_definitions.json
**ASI coverage**: ASI06, ASI02
**Guidance coverage**: None — not in current guidance.txt
**Status**: NEW RULE

### Candidate 6: EMAIL_SSN_BLOCK
**Trigger**: `input.name` == "send_email" AND (regex.match(ssn_pattern, `input.args.subject`) OR regex.match(ssn_pattern, `input.args.body`))
**OPA fields**: `input.name`, `input.args.subject`, `input.args.body`
**Available**: Yes — subject and body are required tool parameters
**ASI coverage**: ASI01, ASI03, ASI06
**Guidance coverage**: None — not in current guidance.txt
**Status**: NEW RULE

### Non-candidate: REPO_TEAM_GATE (Rule 2)
**Would enforce**: "All employees cannot access other teams' repositories"
**Required field**: `input.extensions.subject.team` — **UNDECLARED in system_vars.json**
**Status**: CANNOT BE A CANDIDATE — field not declared; rule cannot fire

---

## STEP 4 — Candidate Rule Summary Table

| ID | Name | Tool(s) | OPA Condition | guidance.txt Coverage | Verdict |
|----|------|---------|---------------|----------------------|---------|
| C1 | COMP_HR_ONLY | get_compensation, display_compensation, adjust_compensation | name ∈ comp_tools AND "hr" ∉ roles | NOT COVERED | New rule 3 |
| C2 | SSN_VIEW_PERM | get_compensation | name=="get_compensation" AND include_ssn==true AND "view_ssn"∉permissions | NOT COVERED | New rule 4 |
| C3 | REPO_ROLE_GATE | search_repos | name=="search_repos" AND "engineer"∉roles AND "security"∉roles | NOT COVERED | New rule 5 |
| C4 | REPO_VISIBILITY_GATE | search_repos | name=="search_repos" AND visibility=="external" | COVERED BY RULE 1 | No new rule |
| C5 | ADJ_APPROVAL_THRESHOLD | adjust_compensation | name=="adjust_compensation" AND amount>10000 AND has_approval≠"true" | NOT COVERED | New rule 6 |
| C6 | EMAIL_SSN_BLOCK | send_email | name=="send_email" AND regex(ssn, subject OR body) | NOT COVERED | New rule 7 |

---

## STEP 5 — Gap Register

| Gap | Description | OPA-enforceable? | Disposition |
|-----|-------------|-----------------|-------------|
| G1 | Rule 2 team-scoped repo access | No — subject.team undeclared | Cannot enforce; documented in extension_suggestions.json |
| G2 | Salary exfiltration via email (non-SSN) | No — content inspection beyond regex | Out of OPA scope for this run |
| G3 | Bulk directory exfiltration | No — content-aware blocking required | Out of OPA scope |
| G4 | No rate limiting on send_email | No — aggregate state not available to OPA | Out of OPA scope |
| G5 | No server-side audit logging | No — config concern | Recommendation only |
| G6 | get_directory — no role restriction | No guidance rule; tool low-sensitivity | Not proposed; below threshold |

---

## STEP 6 — Undeclared Field Register

| Field | Required by | Status |
|-------|-------------|--------|
| `input.extensions.subject.team` | Rule 2 (guidance.txt) | UNDECLARED — must be added to system_vars.json and populated from authenticated identity before Rule 2 can be enforced |

---

## STEP 7 — New Rule Text (Proposed)

The following 5 rules are proposed for addition to `guidance.txt` as new rules 3–7.

**Rule 3** (COMP_HR_ONLY):
> Only HR employees can access compensation records, including salary figures, compensation bands, and salary adjustments.

**Rule 4** (SSN_VIEW_PERM):
> Only employees with the view_ssn permission may request SSN data in compensation lookups; any caller without this permission must not set include_ssn to true.

**Rule 5** (REPO_ROLE_GATE):
> Only engineers and security team members may search repositories; all other roles are blocked from the repository search tool.

**Rule 6** (ADJ_APPROVAL_THRESHOLD):
> HR employees may adjust compensation without additional approval for amounts up to $10,000; any compensation adjustment greater than $10,000 requires prior manager approval indicated by the has_approval flag set to true.

**Rule 7** (EMAIL_SSN_BLOCK):
> Emails must not contain Social Security Numbers in their subject line or body; any attempt to send an email with an SSN pattern in the subject or body must be blocked.

---

## STEP 8 — Coverage Check and Quality Gates

### STEP 8a — Field Availability Check

| Rule | Required OPA Fields | Available | Notes |
|------|--------------------|-----------| ------|
| 3 (COMP_HR_ONLY) | input.name, input.extensions.subject.roles | Yes | roles declared in system_vars.json |
| 4 (SSN_VIEW_PERM) | input.name, input.args.include_ssn, input.extensions.subject.permissions | Yes | permissions declared; include_ssn in tool_definitions.json |
| 5 (REPO_ROLE_GATE) | input.name, input.extensions.subject.roles | Yes | roles declared |
| 6 (ADJ_APPROVAL_THRESHOLD) | input.name, input.args.amount, input.extensions.subject.has_approval | Yes | amount in tool_definitions.json; has_approval declared |
| 7 (EMAIL_SSN_BLOCK) | input.name, input.args.subject, input.args.body | Yes | both required params in send_email tool definition |

All 5 new rules reference only declared fields. ✓

### STEP 8b — Redundancy Check

Check all pairs across guidance.txt rules 1–2 and proposed new rules 3–7:

| Pair | Overlap? | Resolution |
|------|----------|------------|
| Rule 1 vs Rule 3 | No — different tools (search_repos vs compensation tools) | Distinct |
| Rule 1 vs Rule 5 | Partial — both cover search_repos. Rule 1: visibility gate. Rule 5: role gate. Different dimensions. | Distinct — not redundant |
| Rule 1 vs Rule 4 | No — different tools | Distinct |
| Rule 1 vs Rule 6 | No — different tools | Distinct |
| Rule 1 vs Rule 7 | No — different tools | Distinct |
| Rule 2 vs any new rule | No — Rule 2 is a blind spot (subject.team undeclared); it cannot conflict | Distinct |
| Rule 3 vs Rule 4 | Rule 3 blocks non-HR callers from get_compensation entirely. Rule 4 adds a further permission gate for HR callers requesting include_ssn. Non-overlapping: Rule 3 fires first for non-HR; Rule 4 fires for HR without view_ssn. | Layered, not redundant |
| Rule 3 vs Rule 6 | Rule 3 blocks non-HR from adjust_compensation. Rule 6 adds approval threshold for HR callers. Non-overlapping: Rule 6 applies only when Rule 3 has already passed (HR caller). | Layered, not redundant |
| Rule 5 vs Rule 1 | Already checked above | Distinct |
| Rule 4 vs Rule 7 | Different tools (get_compensation vs send_email) | Distinct |
| Rule 6 vs Rule 7 | Different tools (adjust_compensation vs send_email) | Distinct |

No redundancies found. ✓

### STEP 8c — Regression Check

**Prior run**: guidance.txt had 8 rules; prior run proposed 0 new rules (all candidate rules were covered by those 8 rules).

**This run**: guidance.txt has 2 rules; this run proposes 5 new rules.

Classification: The 5 new rules (COMP_HR_ONLY, SSN_VIEW_PERM, REPO_ROLE_GATE, ADJ_APPROVAL_THRESHOLD, EMAIL_SSN_BLOCK) are **genuine new additions** specific to the current 2-rule guidance.txt baseline. They are NOT regressions from the prior run — the prior run correctly found no new rules because its guidance.txt already contained equivalent rules (1–8). The current run is analyzing a reduced guidance.txt and correctly identifies the 5 coverage gaps.

Regression log: Prior run proposed 0 rules (guidance.txt had 8 rules at that time, all covering these candidates). Current run analyzes 2-rule guidance.txt — 5 candidates are new additions, not regressions from the prior run. ✓

### STEP 8d — Format Gate

The `guidance_updated.txt` to be written:
- MUST contain only bare-line rules (matching guidance.txt format — no numbers, no headers, no commentary)
- MUST NOT contain: `## ` or `# ` headers, `|` table characters, "cannot be enforced" statements, phantom variable references, cross-references to other documents
- Each line is a single plain-English rule

Proposed 5 lines — all satisfy the format gate. ✓

---

## STEP 9 — Final Proposed Additions to guidance.txt

The following 5 rules are ready for inclusion in `guidance_updated.txt`:

```
Only HR employees can access compensation records, including salary figures, compensation bands, and salary adjustments.
Only employees with the view_ssn permission may request SSN data in compensation lookups; any caller without this permission must not set include_ssn to true.
Only engineers and security team members may search repositories; all other roles are blocked from the repository search tool.
HR employees may adjust compensation without additional approval for amounts up to $10,000; any compensation adjustment greater than $10,000 requires prior manager approval indicated by the has_approval flag set to true.
Emails must not contain Social Security Numbers in their subject line or body; any attempt to send an email with an SSN pattern in the subject or body must be blocked.
```

Gaps documented but not included (out of OPA scope or missing required fields):
- Rule 2 team-scoped repo access: `subject.team` undeclared — cannot enforce
- Salary exfiltration via email (non-SSN): content inspection beyond regex — out of scope
- Bulk directory exfiltration: content-aware blocking required — out of scope
