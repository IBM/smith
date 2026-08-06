# SPDX-License-Identifier: Apache-2.0
package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})

# === Constants ===
org_domain_map := {
	"IBM Corporation": "ibm.com",
	"Red Hat": "redhat.com",
	"Kyndryl": "kyndryl.com",
}

# === Global Deny/Allow Envelope ===
valid_envelope if {
	input.kind == "tool_call"
	input.action == "execute"
}

any_deny if deny[_]

# === Tool-Specific DENY Rules ===

# Rule 1: Only HR may create a new employee.
deny["Only HR department users may add a new employee"] if {
	input.name == "add_employee"
	subject.department != "HR"
}

# Rule 2: Only HR may set a salary on a new employee record.
deny["Only HR department users may set a salary when adding an employee"] if {
	input.name == "add_employee"
	args.salary != null
	subject.department != "HR"
}

# Rule 3: Salary must be a positive amount when provided.
deny["Salary must be greater than zero"] if {
	input.name == "add_employee"
	args.salary != null
	args.salary <= 0
}

# Rule 4: Email domain must match the corporate domain for the given organization.
deny["Email domain does not match the corporate domain for the provided organization"] if {
	input.name == "add_employee"
	org := args.organization
	org != null
	expected_domain := org_domain_map[org]
	email := args.email
	not endswith(email, concat("", ["@", expected_domain]))
}

# === Final ALLOW ===
allow if {
	valid_envelope
	not any_deny
}
