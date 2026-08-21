# SPDX-License-Identifier: Apache-2.0
package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})

# === Constants ===
hr_role := "hr"
ssn_permission := "view_ssn"

# === Allowed Argument Keys ===
allowed_arg_keys := {
    "get_compensation":    {"employee_id", "include_ssn"},
    "display_compensation": {"employee_id"},
    "get_directory":       {"department"},
    "send_email":          {"to", "subject", "body"},
    "search_repos":        {"repo_name", "visibility"},
}

# === Envelope Validation ===
valid_envelope if {
    input.kind == "tool_call"
    input.action == "execute"
    input.name != ""
}

# === DENY Rules ===

# Rule 1: Only HR employees may call get_compensation
deny["Only HR employees can access compensation records"] if {
    input.name == "get_compensation"
    not hr_role in subject.user_role
}

# Rule 2: Requesting SSN requires view_ssn permission
deny["Only employees with view_ssn permission can request SSN inclusion"] if {
    input.name == "get_compensation"
    object.get(args, "include_ssn", false) == true
    not ssn_permission in subject.permissions
}

# === Final ALLOW ===
any_deny if deny[_]

allow if {
    valid_envelope
    not any_deny
}
