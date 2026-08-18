# SPDX-License-Identifier: Apache-2.0
package authz

default allow := false

# === Input Accessors ===
subject := input
args := object.get(input, "args", {})

# === Constants ===
ssn_pattern := `\b\d{3}-\d{2}-\d{4}\b`

# === Tool-Specific DENY Rules ===

# Block send_email calls whose subject contains an SSN
deny contains msg if {
	regex.match(ssn_pattern, object.get(args, "subject", ""))
	msg := "Email subject must not contain a Social Security Number (SSN)"
}

# Block send_email calls whose body contains an SSN
deny contains msg if {
	regex.match(ssn_pattern, object.get(args, "body", ""))
	msg := "Email body must not contain a Social Security Number (SSN)"
}

# === Final ALLOW ===
allow if {
	not any_deny
}

any_deny if {
	deny[_]
}
