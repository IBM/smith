# SPDX-License-Identifier: Apache-2.0
package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})

# === Constants ===
authorized_search_roles := {"engineering", "security"}

# === Tool Argument Keys ===
allowed_arg_keys := {
    "search_repos": {"repo_name", "visibility"},
}

# === Envelope Validation ===
valid_envelope if {
    input.kind == "tool_call"
    input.action == "execute"
    input.name != ""
}

# === Deny Rules ===

# Rule 1: Employees do not have visibility to external repositories.
deny["External repository access is not permitted for employees"] if {
    input.name == "search_repos"
    args.visibility == "external"
}

# Rule 2: Only employees in engineer or security team can search repositories.
deny["Only employees in the engineering or security team can search repositories"] if {
    input.name == "search_repos"
    roles := object.get(subject, "user_role", [])
    count({r | r := roles[_]; authorized_search_roles[r]}) == 0
}

# === Final Allow ===
any_deny if deny[_]

allow if {
    valid_envelope
    not any_deny
}
