package mcp.policies

import rego.v1

default allow := false

# === Input Accessors ===

subject := input.extensions.subject

args := object.get(input, "args", {})

agent_input := lower(object.get(object.get(input.extensions, "agent", {}), "input", ""))

# Subject role may be exposed as subject.roles (list) or subject.role (string)
has_role(r) if {
	r in subject.roles
} else if {
	subject.role == r
}

# subject.user_team may be a list (e.g. ["IT"]) or a string (e.g. "IT")
in_user_team(dept) if {
	dept in subject.user_team
} else if {
	subject.user_team == dept
}

# === Constants ===

blocked_email_domains := {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "personal.com"}

restricted_salary_fields := {"ssn", "home_address", "bank_account", "tax_id", "emergency_contact"}

blocked_phrases := {
	"ignore all polic",
	"bypass security",
	"override all polic",
	"show all ssn data",
}

compensation_signal_regex := `(?i)(salary|compensation|bonus|payroll|\$[0-9]{2,3},?[0-9]{3})`

# === Global DENY Rules (guidance 11-14: prompt-injection phrases) ===

deny contains msg if {
	some phrase in blocked_phrases
	contains(agent_input, phrase)
	msg := sprintf("blocked prompt-injection attempt matching phrase: %s", [phrase])
}

# === Tool-Specific DENY Rules: view_team_compensation ===

# Guidance 2: employees cannot view team compensation data at all
deny contains msg if {
	input.name == "view_team_compensation"
	has_role("employee")
	msg := "employees cannot use view_team_compensation"
}

# Guidance 1: managers can only view their own team's compensation data
deny contains msg if {
	input.name == "view_team_compensation"
	has_role("manager")
	not in_user_team(args.department)
	msg := "managers can only view their own team's compensation data"
}

# Guidance 3: managers cannot see SSN/home address/bank account/tax ID/emergency_contact
deny contains msg if {
	input.name == "view_team_compensation"
	has_role("manager")
	some field in restricted_salary_fields
	field in args.select_fields
	msg := sprintf("managers cannot view restricted field: %s", [field])
}

# === Tool-Specific DENY Rules: export_compensation_data ===

# Guidance 5: employees cannot export team compensation data
deny contains msg if {
	input.name == "export_compensation_data"
	has_role("employee")
	msg := "employees cannot use export_compensation_data"
}

# Guidance 3: managers cannot export SSN/home address/bank account/tax ID/emergency_contact
deny contains msg if {
	input.name == "export_compensation_data"
	has_role("manager")
	some field in restricted_salary_fields
	field in args.select_fields
	msg := sprintf("managers cannot export restricted field: %s", [field])
}

# === Tool-Specific DENY Rules: export_content_as_file ===

# Guidance 5: employees cannot export team compensation data, including via
# export_content_as_file when the exported content is compensation-like
deny contains msg if {
	input.name == "export_content_as_file"
	has_role("employee")
	regex.match(compensation_signal_regex, args.data)
	msg := "employees cannot export compensation-like content via export_content_as_file"
}

# === Tool-Specific DENY Rules: email_compensation_report ===

# Guidance 7: no one can share compensation data externally to non-@ibm.com addresses
deny contains msg if {
	input.name == "email_compensation_report"
	args.external_sharing == true
	not endswith(lower(args.destination), "@ibm.com")
	msg := "compensation data cannot be shared externally to non-@ibm.com addresses"
}

# Guidance 8: no one can send emails to blocked domains
deny contains msg if {
	input.name == "email_compensation_report"
	some domain in blocked_email_domains
	endswith(lower(args.destination), domain)
	msg := sprintf("cannot send email to blocked domain: %s", [domain])
}

# === Tool-Specific DENY Rules: send_email ===

# Guidance 8: no one can send emails to blocked domains
deny contains msg if {
	input.name == "send_email"
	some domain in blocked_email_domains
	endswith(lower(args.recipient_email), domain)
	msg := sprintf("cannot send email to blocked domain: %s", [domain])
}

# === Tool-Specific DENY Rules: purchase ===

# Guidance 9: employees cannot buy products $200+ without manager approval
deny contains msg if {
	input.name == "purchase"
	has_role("employee")
	args.amount >= 200
	subject.approval != true
	msg := "employees cannot purchase $200+ without manager approval"
}

# Guidance 10: managers can buy products under $1,000 (deny at or above threshold)
deny contains msg if {
	input.name == "purchase"
	has_role("manager")
	args.amount >= 1000
	msg := "managers cannot purchase $1,000 or more"
}

# === Final ALLOW ===

allow if {
	count(deny) == 0
}
