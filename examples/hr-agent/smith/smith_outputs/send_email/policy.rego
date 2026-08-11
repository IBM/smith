# SPDX-License-Identifier: Apache-2.0
package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})

# === Constants ===
# SSN pattern: NNN-NN-NNNN (dashed) or 9-digit (undashed)
ssn_pattern_dashed   := `\b\d{3}-\d{2}-\d{4}\b`
ssn_pattern_nodashes := `\b\d{9}\b`

# === Tool Argument Keys ===
allowed_arg_keys := {
    "get_compensation":     {"employee_id", "include_ssn"},
    "display_compensation": {"employee_id"},
    "get_directory":        {"department"},
    "send_email":           {"to", "subject", "body"},
    "search_repos":         {"repo_name", "visibility"},
}

# === Envelope Validation ===
valid_envelope if {
    input.kind == "tool_call"
    input.action == "execute"
    input.name in {k | allowed_arg_keys[k]}
}

# === DENY Rules ===

# Guidance: "Employees cannot send SSNs through email. Email containing SSNs must be blocked."
# Check body for dashed SSN format
deny["send_email blocked: body contains an SSN (NNN-NN-NNNN); emails must not carry SSNs"] if {
    input.name == "send_email"
    regex.match(ssn_pattern_dashed, object.get(args, "body", ""))
}

# Check body for undashed 9-digit SSN format
deny["send_email blocked: body contains a 9-digit number that may be an SSN; emails must not carry SSNs"] if {
    input.name == "send_email"
    regex.match(ssn_pattern_nodashes, object.get(args, "body", ""))
}

# Check subject for dashed SSN format
deny["send_email blocked: subject contains an SSN (NNN-NN-NNNN); emails must not carry SSNs"] if {
    input.name == "send_email"
    regex.match(ssn_pattern_dashed, object.get(args, "subject", ""))
}

# Check subject for undashed 9-digit SSN format
deny["send_email blocked: subject contains a 9-digit number that may be an SSN; emails must not carry SSNs"] if {
    input.name == "send_email"
    regex.match(ssn_pattern_nodashes, object.get(args, "subject", ""))
}

# === Helper ===
any_deny if deny[_]

# === Final ALLOW ===
allow if {
    valid_envelope
    not any_deny
}
