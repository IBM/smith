package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject

args := object.get(input, "args", {})

# === Constants ===
hr_role := "hr"

ssn_permission := "view_ssn"

# === Tool-Specific DENY Rules ===

# Rule 1: Only HR employees can access compensation records
deny contains msg if {
	input.name == "get_compensation"
	not hr_role in subject.roles
	msg := "Access denied: only HR employees may access compensation records"
}

# Rule 2: Only employees with view_ssn permission may request SSNs
deny contains msg if {
	input.name == "get_compensation"
	args.include_ssn == true
	not ssn_permission in subject.permissions
	msg := "Access denied: view_ssn permission is required to include SSN in compensation records"
}

# === Final ALLOW ===
allow if {
	count(deny) == 0
}
