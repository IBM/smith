package mcp.policies

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "args", {})

# === Constants ===
# Allowed department names (guidance.txt line 1)
allowed_departments := {"Corporate Leadership", "Engineering", "Product", "HR", "Finance"}

# Allowed organizations and their corporate email domains (guidance.txt lines 2, 7)
org_domains := {
	"IBM Corporation": "ibm.com",
	"Red Hat": "redhat.com",
	"Kyndryl": "kyndryl.com",
}

# === Global DENY/ALLOW Rules ===

# === Tool-Specific DENY/ALLOW Rules ===

# guidance.txt line 1: `department` must be one of the five known values.
deny[msg] if {
	input.name == "add_department"
	name := object.get(args, "name", "")
	not name in allowed_departments
	msg := sprintf("add_department: '%v' is not a valid department (must be one of %v)", [name, allowed_departments])
}

# guidance.txt line 5: Only HR may add a department.
deny[msg] if {
	input.name == "add_department"
	not "HR" in subject.department
	msg := "add_department: only HR may add a department"
}

# guidance.txt line 3: Only HR may add a new employee.
deny[msg] if {
	input.name == "add_employee"
	not "HR" in subject.department
	msg := "add_employee: only HR may add a new employee"
}

# guidance.txt line 2: `organization` must be one of the three known values, when provided.
deny[msg] if {
	input.name == "add_employee"
	org := object.get(args, "organization", null)
	org != null
	not org in object.keys(org_domains)
	msg := sprintf("add_employee: '%v' is not a valid organization (must be one of %v)", [org, object.keys(org_domains)])
}

# guidance.txt line 6: salary must be a positive amount, when provided.
deny[msg] if {
	input.name == "add_employee"
	salary := object.get(args, "salary", null)
	salary != null
	salary <= 0
	msg := sprintf("add_employee: salary '%v' must be a positive amount", [salary])
}

# guidance.txt line 7: email must match the organization's corporate domain, when organization is provided.
deny[msg] if {
	input.name == "add_employee"
	org := object.get(args, "organization", null)
	org != null
	domain := org_domains[org]
	email := object.get(args, "email", "")
	not endswith(lower(email), sprintf("@%v", [domain]))
	msg := sprintf("add_employee: email '%v' must use the %v corporate domain (@%v)", [email, org, domain])
}

# === Final ALLOW ===
default allow := false

allow if {
	not any_deny
}

any_deny if {
	some _ in deny
}
