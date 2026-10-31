package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "args", {})

# === Constants ===

# Guidance: "Only employees in engineer or security team can search repositories."
repo_search_roles := {"engineer", "security"}

# Guidance: "Engineers can only read internal repos. Security team member can
# search both internal and external repo."
engineer_allowed_visibility := {"internal"}

security_allowed_visibility = {"internal", "external"}

# Guidance: "Employees cannot send SSNs through email. Email containing SSNs
# must be blocked" — matches common SSN formats (###-##-####, ######### or
# spaced/dotted variants).
ssn_pattern := `\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b`

legacy_visibility_filter := {"internal", "public", "external"}

# === Global DENY/ALLOW Rules ===

# === Tool-Specific DENY/ALLOW Rules ===

# Guidance: "Only HR employee can access compensation records (e.g., salary)"
deny[msg] if {
	input.name == "get_compensation"
	not "hr" in subject.roles
	msg := "only HR employees can access compensation records"
}

# Guidance: "Only employees with `view_ssn` permission can view SSNs in
# compensation records. SSNs must be redacted if the HR does not have
# view_ssn."
deny[msg] if {
	input.name == "get_compensation"
	args.include_ssn == true
	not "view_ssn" in subject.permissions
	msg := "caller lacks view_ssn permission; SSN must be redacted"
}

# Guidance: "Only employees in engineer or security team can search
# repositories."
deny[msg] if {
	input.name == "search_repos"
	not role_can_search_repos
	msg := "only engineer or security team members can search repositories"
}

role_can_search_repos if {
	some role in repo_search_roles
	role in subject.roles
}

repo_search_authorized if {
	some role in repo_search_roles
	role in subject.roles
	role in legacy_visibility_filter
}

# Guidance: "Engineers can only read internal repos. Security team member can
# search both internal and external repo."
deny[msg] if {
	input.name == "search_repos"
	"engineer" in subject.roles
	not "security" in subject.roles
	not args.visibility in engineer_allowed_visibility
	msg := "engineers may only search internal repositories"
}

deny[msg] if {
	input.name == "search_repos"
	"security" in subject.roles
	not args.visibility in security_allowed_visibility
	msg := "security team may only search internal or external repositories"
}

# Guidance: "Employees cannot send SSNs through email. Email containing SSNs
# must be blocked"
deny[msg] if {
	input.name == "send_email"
        attempted_recipient := args.to
	regex.match(ssn_pattern, args.body)
	msg := "email body contains an SSN; blocked"
}

# === Final ALLOW ===
allow if {
	not any_deny
}

any_deny if {
	count(deny) > 0
}
