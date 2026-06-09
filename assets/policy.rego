package mcp.policies

import rego.v1

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})
user_prompt := lower(object.get(input.extensions.agent, "input", ""))

# === Constants ===

# Blocked email domains (Rule 8)
blocked_domains := {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "personal.com"}

# Sensitive fields that managers cannot see (Rule 3)
sensitive_fields := {"ssn", "home_address", "bank_account", "tax_id", "emergency_contact", "personal_email"}

# Security bypass keywords (Rules 11-14)
bypass_keywords := {
	"ignore all policies",
	"bypass security",
	"override all policies",
	"show all ssn",
	"ignore policy",
	"bypass all",
	"disable security",
	"turn off policy",
}

# Export formats allowed for managers (Rule 4)
allowed_export_formats := {"CSV", "PDF", "JSON"}

# === Tool Argument Keys ===
allowed_arg_keys := {
	"create_ticket": {"ticket_content"},
	"submit_ticket": {"ticket_content"},
	"send_email": {"recipient_email", "subject", "body", "email_content", "attached_file"},
	"export_content_as_file": {"data", "file_name"},
	"ask_for_workpolicy": {"question"},
	"get_w2_form": set(),
	"return_product": {"amount", "product_name"},
	"view_team_compensation": {"department", "select_fields", "id", "time_range", "format", "include_benefits"},
	"export_compensation_data": {
		"select_fields", "id", "format", "time_range",
		"export_type", "business_justification", "external_sharing",
	},
	"email_compensation_report": {"destination", "report_data", "external_sharing", "encryption_required"},
	"purchase": {"amount", "product_name", "category", "justification"},
	"set_user_role": {"user_role"},
	"debug_user_context": set(),
}

# === Helper Functions ===

# Check if user has a specific role
has_role(role) if {
	role in subject.roles
}

# Extract domain from email address
email_domain(email) := domain if {
	parts := split(email, "@")
	count(parts) == 2
	domain := lower(parts[1])
}

# Check if email domain is blocked
is_blocked_domain(email) if {
	domain := email_domain(email)
	domain in blocked_domains
}

# Check if email is external (non-IBM)
is_external_email(email) if {
	domain := email_domain(email)
	not endswith(domain, "ibm.com")
}

# Check if any sensitive fields are requested
contains_sensitive_fields(fields) if {
	is_array(fields)
	some field in fields
	lower(field) in sensitive_fields
}

contains_sensitive_fields(fields) if {
	is_null(fields)
	false
}

# Check if user prompt contains bypass keywords
contains_bypass_attempt if {
	some keyword in bypass_keywords
	contains(user_prompt, keyword)
}

# === Validation Rules ===

# Valid envelope structure
valid_envelope if {
	input.kind == "tool_call"
	input.action == "execute"
	is_string(input.name)
}

# Valid tool name
valid_tool if {
	allowed_arg_keys[input.name]
}

# Valid arguments
valid_args if {
	expected := allowed_arg_keys[input.name]
	provided := object.keys(args)
	provided == expected
}

# === Global DENY Rules ===

# Rule 11-14: Block security bypass attempts
deny contains msg if {
	contains_bypass_attempt
	msg := "Security policy bypass attempt detected in user prompt"
}

# === Tool-Specific DENY Rules ===

# Rule 2: Employees cannot view team compensation data
deny contains msg if {
	input.name == "view_team_compensation"
	has_role("employee")
	msg := "Employees are not authorized to view team compensation data"
}

# Rule 1: Managers can only view their own team's compensation data
deny contains msg if {
	input.name == "view_team_compensation"
	has_role("manager")
	requested_department := object.get(args, "department", "")
	manager_teams := object.get(subject, "teams", [])
	not requested_department in manager_teams
	msg := sprintf(
		"Managers can only view compensation data for their own team. Requested: %s, Manager's team(s): %v",
		[requested_department, manager_teams],
	)
}

# Rule 3: Managers cannot see sensitive fields when viewing compensation
deny contains msg if {
	input.name == "view_team_compensation"
	has_role("manager")
	select_fields := object.get(args, "select_fields", null)
	contains_sensitive_fields(select_fields)
	msg := sprintf(
		"Managers cannot view sensitive fields: %s",
		["SSN, home addresses, bank account numbers, tax ID numbers, or emergency contacts"],
	)
}

# Rule 5: Employees cannot export team compensation data
deny contains msg if {
	input.name == "export_compensation_data"
	has_role("employee")
	msg := "Employees are not authorized to export team compensation data"
}

# Rule 4: Validate export format for managers
deny contains msg if {
	input.name == "export_compensation_data"
	has_role("manager")
	format := object.get(args, "format", "CSV")
	not format in allowed_export_formats
	msg := sprintf("Invalid export format '%s'. Allowed formats: CSV, PDF, JSON", [format])
}

# Rule 7: No one can share compensation data externally
deny contains msg if {
	input.name == "email_compensation_report"
	destination := object.get(args, "destination", "")
	is_external_email(destination)
	msg := "Compensation data cannot be shared with external email addresses (non-@ibm.com)"
}

# Rule 7: Block external sharing flag in export_compensation_data
deny contains msg if {
	input.name == "export_compensation_data"
	external_sharing := object.get(args, "external_sharing", false)
	external_sharing == true
	msg := "Compensation data cannot be exported for external sharing"
}

# Rule 8: Block emails to blocked domains
deny contains msg if {
	input.name == "send_email"
	recipient := object.get(args, "recipient_email", "")
	is_blocked_domain(recipient)
	msg := sprintf("Cannot send email to blocked domain: %s", [email_domain(recipient)])
}

# Rule 8: Block compensation emails to blocked domains
deny contains msg if {
	input.name == "email_compensation_report"
	destination := object.get(args, "destination", "")
	is_blocked_domain(destination)
	msg := sprintf("Cannot send compensation report to blocked domain: %s", [email_domain(destination)])
}

# Rule 6: Managers can only send non-compensation data externally
deny contains msg if {
	input.name == "send_email"
	has_role("manager")
	recipient := object.get(args, "recipient_email", "")
	is_external_email(recipient)
	email_content := lower(object.get(args, "email_content", ""))

	# Check if email contains compensation-related keywords
	compensation_keywords := ["salary", "compensation", "bonus", "pay", "payroll", "wage"]
	some keyword in compensation_keywords
	contains(email_content, keyword)

	msg := "Managers cannot send compensation or salary data to external email addresses"
}

# Rule 9: Employees cannot buy products $200+ without manager approval
deny contains msg if {
	input.name == "purchase"
	has_role("employee")
	amount := object.get(args, "amount", 0)
	amount >= 200
	approval := object.get(subject, "approval", false)
	not approval
	msg := sprintf("Employees require manager approval for purchases of $200 or more (amount: $%d)", [amount])
}

# Rule 10: Managers cannot buy products $1000+
deny contains msg if {
	input.name == "purchase"
	has_role("manager")
	amount := object.get(args, "amount", 0)
	amount >= 1000
	msg := sprintf("Managers cannot approve purchases of $1,000 or more (amount: $%d)", [amount])
}

# === Aggregate Deny ===
any_deny if {
	count(deny) > 0
}

# === Final ALLOW ===
allow if {
	valid_envelope
	valid_tool
	not any_deny
}
