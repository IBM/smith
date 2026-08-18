# SPDX-License-Identifier: Apache-2.0
package authz

default allow := false

# === Input Accessors ===
subject := input
args := object.get(input, "args", {})

# === DENY: Only HR role may call get_compensation ===
deny contains msg if {
	not "hr" in subject.role
	msg := "Access denied: only HR employees may access compensation records."
}

# === DENY: SSN access requires view_ssn permission ===
deny contains msg if {
	args.include_ssn == true
	not "view_ssn" in subject.permissions
	msg := "Access denied: viewing SSNs requires the view_ssn permission."
}

# === Final ALLOW ===
any_deny if {
	deny[_]
}

allow if {
	not any_deny
}
