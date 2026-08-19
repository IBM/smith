# SPDX-License-Identifier: Apache-2.0
package authz

default allow := false

# === Input Accessors ===
subject := input
args := object.get(input, "args", {})

# === Constants ===
allowed_search_roles := {"engineer", "security"}

# === Tool-Specific DENY Rules ===

# Only engineer or security team may call search_repos
deny contains msg if {
	not any_allowed_search_role
	msg := sprintf("Role '%v' is not permitted to search repositories", [subject.role])
}

any_allowed_search_role if {
	some r in subject.role
	r in allowed_search_roles
}

# Engineers may only search internal repos
deny contains msg if {
	"engineer" in subject.role
	args.visibility != "internal"
	msg := sprintf("Engineers may only search internal repositories, not '%v'", [args.visibility])
}

# === Final ALLOW ===
allow if {
	not any_deny
}

any_deny if {
	deny[_]
}
