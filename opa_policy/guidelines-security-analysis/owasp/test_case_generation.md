## Test Case Generation Skill

Produces a labelled test suite for use with `policy_delta_test.py`.
Each test case is a JSON file placed under an `/allow/` or `/deny/`
subdirectory so the delta test tool can read its expected outcome from
the path.

Requires `owasp_policy_guidelines.md` and `policy.rego` to be present.

### Authoritative Paths

- Input 1: `<mcp_server_dir>/policy_generation/owasp_policy_guidelines.md`
- Input 2: `<mcp_server_dir>/policy_generation/policy.rego`
- Input 3: `./references/test_case_template.json` — canonical OPA input envelope structure (shared across all MCP servers)
- Output: `<mcp_server_dir>/policy_generation/tests/allow/*.json`
           `<mcp_server_dir>/policy_generation/tests/deny/*.json`

---

### Test case format

Every file wraps the OPA input under an `"input"` key, matching the format
produced by the `test_generation` pipeline and defined in `test_case_template.json`:

```json
{
  "input": {
    "kind": "tool_call",
    "action": "execute",
    "name": "<tool_name>",
    "arguments": {
      "keywords": "<value>",
      "limit": <integer>
    },
    "extensions": {
      "subject": {
        "claims": {},
        "user_role": ["<role>"],
        "user_id": "<email>",
        "call_count": <integer>
      },
      "headers": { "x-request-id": "req-0000", "x-forwarded-for": "10.0.0.1" },
      "labels": ["internal"],
      "agent": {
        "input": "<original user prompt>",
        "session_id": "sess-0000",
        "conversation_id": "conv-0000",
        "turn": 1
      },
      "object": { "managed_by": "tool", "trust_domain": "internal" }
    }
  }
}
```

Fields required by the policy must be present. Fields that the policy
reads via `object.get(..., default)` may be omitted to test the default
behaviour — note this explicitly in the file name.

---

### Workflow (follow strictly)

---

#### STEP 1 — Read inputs

Read `./references/test_case_template.json` to confirm the canonical OPA
input envelope structure. Every test case written in STEP 2 and STEP 3 must
wrap the envelope under a top-level `"input"` key, exactly as shown in the
Test case format section above and as `test_case_template.json` defines.
Use the envelope keys (`kind`, `action`, `name`, `extensions`, `arguments`)
exactly — do not add or rename top-level keys inside `"input"`.

Read `owasp_policy_guidelines.md` in full and extract:
- Every violation code from the Violation Code Reference table
- The input schema (all OPA paths and their sources)
- Every known set (roles, tools, blocked terms, caps)
- Which rules require the architecture gap fix (marked †)

Read `policy.rego` and confirm every violation code from the spec has a
corresponding `deny["CODE"]` rule. Note any that are missing — those
codes cannot be tested until the rule is added.

---

#### STEP 2 — Generate deny test cases

Write one JSON file per violation code under `policy_generation/tests/deny/`.
Name each file `<VIOLATION_CODE>.json` (lowercase is fine).

For each violation code, construct the **minimal input** that satisfies
all conditions in the deny rule and no additional deny conditions:

| Rule to exercise | What to set | What to keep clean |
|---|---|---|
| `UNKNOWN_TOOL` | `input.name` = any name not in allowed_tools set | all other fields valid |
| `UNKNOWN_ROLE` | `subject.role` = any string not in known_roles set | tool name valid |
| `UNVERIFIED_PRIVILEGED_ROLE` | `role` = `admin_coordinator`, `role_verified` = false | tool, keywords, limit valid |
| `EMPTY_KEYWORDS` | `keywords` = `""` | role = faculty, all other fields valid |
| `NON_ACADEMIC_KEYWORDS` | `keywords` = a term from blocked_event_types | role = faculty, limit valid |
| `PROMPT_INJECTION_KEYWORDS` | `keywords` = a term from blocked_action_directives | role = faculty, limit valid |
| `INVALID_LIMIT` | `limit` = 0 or negative | role = faculty, keywords valid |
| `LIMIT_EXCEEDED_HARD` | `limit` = 21 or higher | role = faculty, keywords valid |
| `MISSING_SESSION_COUNT` | omit `call_count` field entirely | role = faculty, keywords valid |
| `SESSION_RATE_LIMIT` | `call_count` ≥ per-role cap for that role | role = faculty, keywords valid |
| `LIMIT_EXCEEDED_ROLE` | `limit` > per-role cap but ≤ 20 | role with a cap lower than 20 |
| `TOPIC_OUT_OF_SCOPE` | `keywords` = a term not in any allowed topic set | role = faculty |
| `KEYWORD_CATEGORY_MISSING` | `keywords` = domain term only (no method term) | role = phd_student |

Rules:
- Use exact string values from the known sets in the spec.
- For rules marked † (require architecture gap fix), still write the test
  case — it documents the intended behaviour even if not yet enforceable.
- Do not combine multiple violations in one deny test case. One file,
  one violation.

---

#### STEP 3 — Generate allow test cases

Write one JSON file per role under `policy_generation/tests/allow/`.
Name each file `allow_<role>.json`.

Each allow case must satisfy ALL deny rule conditions simultaneously:
- `input.name` is in the allowed_tools set
- `role` is in the known_roles set
- `role_verified` = true for `admin_coordinator`; true or false for others
- `keywords` is non-empty, contains no blocked term, and matches at least
  one allowed topic term for the role
- `limit` is ≥ 1, ≤ 20, and ≤ the per-role cap
- `call_count` is present and less than the per-role session cap

Additionally write:
- `allow_boundary_limit.json` — limit exactly equal to the per-role cap
- `allow_boundary_session.json` — call_count exactly one below the per-role cap

Rules:
- If a role has topic restrictions (faculty, advisor, guest), use a keyword
  that contains a term from the allowed topic sets.
- If the role is phd_student, the keyword must contain both a method term
  and a domain term.
- The allow cases are the positive proof that the policy does not
  over-restrict legitimate users.

---

#### STEP 4 — Verify test case coverage

Before writing any files, produce a coverage table:

| Violation code | Deny test file | Gap fix required? |
|---|---|---|
| UNKNOWN_TOOL | deny/unknown_tool.json | No |
| UNKNOWN_ROLE | deny/unknown_role.json | No |
| ... | ... | ... |

| Role | Allow test file |
|---|---|
| faculty | allow/allow_faculty.json |
| ... | ... |

Confirm:
- Every violation code in the spec has exactly one deny test file.
- Every known role has at least one allow test file.
- No deny test case accidentally triggers a second violation code.

---

#### STEP 5 — Write the test files

Write all JSON files to the paths listed in the coverage table.
Use 2-space indentation. Do not add comments inside JSON.

---

#### STEP 6 — Human review

Present the coverage table from STEP 4.

Log the coverage table and continue automatically to delta testing.

> Test cases written to `policy_generation/tests/allow/` and `policy_generation/tests/deny/`. Proceeding to delta testing.
> Run `policy_delta_test.py` to measure the baseline pass rate.
