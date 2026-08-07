# SPDX-License-Identifier: Apache-2.0
package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})

# === Constants ===
hr_role := "hr"
ssn_permission := "view_ssn"
compensation_tools := {"get_compensation", "display_compensation"}

# === Tool Argument Keys ===
allowed_arg_keys := {
    "get_compensation": {"employee_id", "include_ssn"},
    "display_compensation": {"employee_id"},
    "get_directory": {"department"},
    "send_email": {"to", "subject", "body"},
    "search_repos": {"repo_name", "visibility"},
}

# === Envelope Validation ===
valid_envelope if {
    input.kind == "tool_call"
    input.action == "execute"
    is_string(input.name)
}

# === DENY Rules ===

# Rule 1: Only HR employees can access compensation records (salary)
deny["Access denied: only HR employees may access compensation records"] if {
    input.name in compensation_tools
    not hr_role in subject.user_role
}

# Rule 2: SSN may only be included by callers with view_ssn permission
deny["Access denied: view_ssn permission required to include SSN"] if {
    input.name == "get_compensation"
    args.include_ssn == true
    not ssn_permission in subject.permissions
}

# === Final ALLOW ===
any_deny if deny[_]

allow if {
    valid_envelope
    not any_deny
}
