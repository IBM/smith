package mcp.policies

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "args", {})

# === Constants ===
# Allowed department names (guidance.txt line 1)
allowed_departments := {"Corporate Leadership", "Engineering", "Product", "HR", "Finance"}

# === Global DENY/ALLOW Rules ===

# === Tool-Specific DENY/ALLOW Rules ===

# guidance.txt line 1: `department` must be one of the five known values.
deny[msg] if {
	input.name == "add_department"
	name := object.get(args, "name", "")
	not name in allowed_departments
	msg := sprintf("add_department: '%v' is not a valid department (must be one of %v)", [name, allowed_departments])
}

# guidance.txt line 2: Only HR may add a department.
deny[msg] if {
	input.name == "add_department"
	not "HR" in subject.department
	msg := "add_department: only HR may add a department"
}

# === Final ALLOW ===
default allow := false

allow if {
	not any_deny
}

any_deny if {
	some _ in deny
}
