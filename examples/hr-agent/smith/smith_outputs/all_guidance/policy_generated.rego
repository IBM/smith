package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "args", {})

# === Constants ===
# Guidance: "Employees cannot send SSNs through email." — SSN pattern (###-##-####)
ssn_pattern := `\d{3}-\d{2}-\d{4}`

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

# Guidance: "Only employees in engineer or security team can search repositories."
deny[msg] if {
	input.name == "search_repos"
	not "engineer" in subject.roles
	not "security" in subject.roles
	msg := "only engineer or security team members can search repositories"
}

# Guidance: "Engineers can only read internal repos. Security team member can
# search both internal and external repo."
deny[msg] if {
	input.name == "search_repos"
	"engineer" in subject.roles
	not "security" in subject.roles
	args.visibility != "internal"
	msg := "engineers may only search internal repositories"
}

# Guidance: "Employees cannot send SSNs through email. Email containing SSNs
# must be blocked"
deny[msg] if {
	input.name == "send_email"
	regex.match(ssn_pattern, object.get(args, "subject", ""))
	msg := "emails containing SSNs are blocked"
}

deny[msg] if {
	input.name == "send_email"
	regex.match(ssn_pattern, object.get(args, "body", ""))
	msg := "emails containing SSNs are blocked"
}

# === Final ALLOW ===
allow if {
	not any_deny
}

any_deny if {
	count(deny) > 0
}
