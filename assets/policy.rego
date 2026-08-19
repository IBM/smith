# Copyright 2026
# SPDX-License-Identifier: Apache-2.0
package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})

include_ssn := object.get(args, "include_ssn", false)
visibility := lower(trim_space(object.get(args, "visibility", "")))
email_subject := lower(trim_space(object.get(args, "subject", "")))
email_body := lower(trim_space(object.get(args, "body", "")))

user_roles := object.get(subject, "user_role", [])
permissions := object.get(subject, "permissions", [])

# === Known Sets ===
allowed_tools := {
	"get_compensation",
	"display_compensation",
	"get_directory",
	"send_email",
	"search_repos",
}

# === Envelope Validation ===
valid_envelope if {
	input.kind == "tool_call"
	input.action == "execute"
	_ := input.extensions.subject
}

# === Helper: SSN-shaped substring match ===
contains_ssn(text) if {
	regex.match(`\d{3}-\d{2}-\d{4}`, text)
}

# === DENY Rules ===

# LLM06 — compensation_role_denied
deny["compensation_role_denied"] if {
	input.name == "get_compensation"
	not "hr" in user_roles
}

deny["compensation_role_denied"] if {
	input.name == "display_compensation"
	not "hr" in user_roles
}

# LLM02 — ssn_permission_denied
deny["ssn_permission_denied"] if {
	input.name == "get_compensation"
	include_ssn == true
	not "view_ssn" in permissions
}

# LLM06 — repo_visibility_denied
deny["repo_visibility_denied"] if {
	input.name == "search_repos"
	visibility == "external"
}

# G1 (guidance.txt) — repo_visibility_denied
deny["repo_visibility_denied"] if {
	input.name == "search_repos"
	visibility == "public"
}

# LLM06 — repo_role_denied
deny["repo_role_denied"] if {
	input.name == "search_repos"
	not "engineer" in user_roles
}

# LLM01 — email_ssn_blocked
deny["email_ssn_blocked"] if {
	input.name == "send_email"
	contains_ssn(email_body)
}

deny["email_ssn_blocked"] if {
	input.name == "send_email"
	contains_ssn(email_subject)
}

# === Final ALLOW ===
any_deny if some _ in deny

allow if {
	valid_envelope
	allowed_tools[input.name]
	not any_deny
}
