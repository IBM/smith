package mcp.policies

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "args", {})

# === Global DENY/ALLOW Rules ===
# (none; all rules in this policy are tool-specific)

# === Tool-Specific DENY/ALLOW Rules ===

# Guidance: "Only HR employee can access compensation records (e.g., salary)"
deny[msg] if {
	input.name == "get_compensation"
	not "hr" in subject.roles
	msg := "only HR employees can access compensation records"
}

# Guidance: "Only employees with `view_ssn` permission can view SSNs in
# compensation records. SSNs must be redacted if the HR does not have view_ssn."
deny[msg] if {
	input.name == "get_compensation"
	args.include_ssn == true
	not "view_ssn" in subject.permissions
	msg := "view_ssn permission is required to request SSNs in compensation records"
}

# === Final ALLOW ===
default allow := false

allow if {
	not any_deny
}

any_deny if {
	count(deny) > 0
}
