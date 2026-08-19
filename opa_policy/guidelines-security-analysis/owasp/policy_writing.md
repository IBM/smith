## Policy Writing Skill

Translates `owasp_policy_guidelines.md` into a validated OPA Rego policy
file. Requires `owasp_policy_guidelines.md` to be present in the target
directory (produced by the enforcement_mapping skill).

### Authoritative Paths

- Input: `<mcp_server_dir>/policy_generation/owasp_policy_guidelines.md`
- Output: `<mcp_server_dir>/policy_generation/policy.rego`

---

### Workflow (follow strictly)

---

#### STEP 1 — Read input

Read `owasp_policy_guidelines.md` in full before writing any Rego.
If the file is missing, stop and tell the user it must be produced by the
enforcement_mapping skill first.

Extract and note before proceeding:
- The package name (derive from the tool name, e.g. `mcp.cfp`)
- Every violation code in the Violation Code Reference table
- Every known set (roles, tools, blocked terms, topic terms, caps)
- The input schema (which OPA paths map to which fields)
- Which rules require an architecture gap fix (marked †)

---

#### STEP 2 — Write the package header

Write the first lines of `policy.rego`:

```
package <derived_package>

default allow := false
```

The package name is lowercase, dot-separated, derived from the tool name.
`default allow := false` must always be present and must always be `false`.

---

#### STEP 3 — Write input aliases

Immediately after the header, add one assignment per input schema field.
Use `object.get` with a safe default for every optional field:

```rego
subject  := input.extensions.subject
args     := object.get(input, "arguments", {})
role     := subject.role
keywords := lower(trim_space(object.get(args, "keywords", "")))
limit_val := object.get(args, "limit", 10)
```

Rules:
- Apply `lower(trim_space(...))` to every free-text string field.
- Use `object.get(<doc>, "<key>", <default>)` for every field that may be absent.
- For boolean fields that default to false (e.g. `role_verified`), use
  `object.get(subject, "role_verified", false)`.
- For fields whose *presence* (not value) must be checked, write a
  named helper rule:
  ```rego
  <field>_present if { _ := subject.<field> }
  ```

---

#### STEP 4 — Write known sets

Translate every known set from the spec into a Rego rule returning a set
literal. One rule per set, grouped together:

```rego
known_roles    := {"role_a", "role_b", ...}
allowed_tools  := {"tool_name"}
blocked_terms  := {"term1", "term2", ...}
```

Rules:
- Use exact string literals as they appear in the spec.
- Multi-word strings are fine: `"machine learning"`.
- Numeric cap tables use object literals:
  ```rego
  role_limit_cap := {
      "role_a": 15,
      "role_b": 5,
      ...
  }
  ```

---

#### STEP 5 — Write helper rules

Write one helper rule for each reusable predicate referenced by more than
one deny rule. Common helpers:

- Substring matching across a set of terms:
  ```rego
  any_match(text, terms) if {
      some t in terms
      contains(text, t)
  }
  ```
- Field presence check (see STEP 3 pattern).

Do not write helpers for predicates used by only one rule — inline them.

---

#### STEP 6 — Write deny rules

Write one `deny[<CODE>]` rule per violation code in the spec. Follow this
order: hard blocks first, soft blocks last.

Template:
```rego
# <threat ID(s)> — <violation code>
deny["<CODE>"] if {
    <condition from spec>
}
```

Rules:
- The violation code string must match the spec exactly (uppercase, underscores).
- Translate each spec condition using the input aliases from STEP 3.
- For numeric comparisons use `<`, `>`, `<=`, `>=` directly.
- For set membership use `<set>[<value>]` or `<value> in <set>`.
- For substring matching use the helper from STEP 5 or `contains(field, term)`.
- If two conditions for the same code are independent, write two separate
  `deny["CODE"]` rules (Rego OR semantics — either can fire).
- Do not combine unrelated conditions in one rule body with `AND`.

---

#### STEP 7 — Write the allow rule

After all deny rules, write the `valid_envelope` helper, the `any_deny`
helper, and the final `allow`:

```rego
valid_envelope if {
    input.kind == "tool_call"
    input.action == "execute"
    _ := input.extensions.subject
}

any_deny if { some _ in deny }

allow if {
    valid_envelope
    allowed_tools[input.name]
    not any_deny
}
```

Rules:
- `valid_envelope` guards against malformed or unexpected input shapes —
  a request that does not match the expected OPA envelope must never be allowed.
- `allow` must never be `true` when any `deny` code is set.

---

#### STEP 8 — Format and validate

Run both commands. Do not skip either.

```bash
opa fmt -w <mcp_server_dir>/policy_generation/policy.rego
opa check <mcp_server_dir>/policy_generation/policy.rego
```

- `opa fmt -w` rewrites the file in place to canonical OPA style. No output
  means success.
- `opa check` prints nothing on success. Any output is a compile error —
  fix it before proceeding.

If `opa` is not installed, stop and tell the user:
> `opa` CLI is required. Install from https://www.openpolicyagent.org/docs/latest/#running-opa

---

#### STEP 9 — Human review

Present:
1. The violation codes written and which OWASP categories they cover.
2. Which rules require the architecture gap fix (marked † in the spec) and
   will not be evaluated until `agent.py` is updated.
3. The `opa check` result (clean or errors).

Write the final `policy.rego` and continue automatically to the policy_coverage_check skill.

> `policy.rego` written. Proceeding to coverage check.
