package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject

args := object.get(input, "arguments", {})

user_prompt := object.get(input.extensions.agent, "input", "")

# === Constants ===
blocked_domains := {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "personal.com"}

sensitive_fields := {
	"ssn", "home_address", "bank_account",
	"tax_id", "emergency_contact", "personal_email",
}

bypass_keywords := {
	"ignore all policies", "bypass security",
	"override all policies", "show all ssn",
}

compensation_tools := {
	"view_team_compensation",
	"export_compensation_data",
	"email_compensation_report",
}

# === Tool Argument Keys ===
allowed_arg_keys := {
	"create_ticket": {"ticket_content"},
	"submit_ticket": {"ticket_content"},
	"send_email": {"recipient_email", "subject", "body", "email_content", "attached_file"},
	"export_content_as_file": {"data", "file_name"},
	"ask_for_workpolicy": {"question"},
	"get_w2_form": set(),
	"return_product": {"amount", "product_name"},
	"view_team_compensation": {
		"department", "select_fields", "id",
		"time_range", "format", "include_benefits",
	},
	"export_compensation_data": {
		"select_fields", "id", "format", "time_range",
		"export_type", "business_justification", "external_sharing",
	},
	"email_compensation_report": {
		"destination", "report_data",
		"external_sharing", "encryption_required",
	},
	"purchase": {"amount", "product_name", "category", "justification"},
	"set_user_role": {"user_role"},
	"debug_user_context": set(),
}

# === Helper Functions ===
is_manager if {
	"manager" in subject.roles
}

is_employee if {
	"employee" in subject.roles
}

has_approval if {
	lower(subject.approval) == "true"
}

extract_domain(email) := domain if {
	parts := split(email, "@")
	count(parts) == 2
	domain := parts[1]
}

contains_bypass_attempt if {
	some keyword in bypass_keywords
	contains(lower(user_prompt), keyword)
}

contains_sensitive_field(fields) if {
	some field in fields
	lower(field) in sensitive_fields
}

is_external_email(email) if {
	domain := extract_domain(email)
	not endswith(domain, "ibm.com")
}

is_blocked_domain(email) if {
	domain := extract_domain(email)
	domain in blocked_domains
}

# === Global DENY Rules ===

# Rule 11-14: Block bypass attempts
deny contains msg if {
	contains_bypass_attempt
	msg := "Access denied: Attempt to bypass security policies detected"
}

# === Tool-Specific DENY Rules ===

# Rule 2: Employees cannot view team compensation
deny contains msg if {
	input.name == "view_team_compensation"
	is_employee
	msg := "Access denied: Employees cannot view team compensation data"
}

# Rule 1: Managers can only view their own team's compensation
deny contains msg if {
	input.name == "view_team_compensation"
	is_manager
	requested_dept := object.get(args, "department", "")
	requested_dept != ""
	not requested_dept in subject.teams
	msg := sprintf(
		"Access denied: Managers can only view compensation for their own team(s). Your teams: %v, Requested: %s",
		[subject.teams, requested_dept],
	)
}

# Rule 3: Block sensitive fields in view_team_compensation
deny contains msg if {
	input.name == "view_team_compensation"
	select_fields := object.get(args, "select_fields", [])
	select_fields != null
	contains_sensitive_field(select_fields)
	msg := "Access denied: Cannot view sensitive fields (SSN, home address, bank account, tax ID, emergency contact)"
}

# Rule 5: Employees cannot export compensation data
deny contains msg if {
	input.name == "export_compensation_data"
	is_employee
	msg := "Access denied: Employees cannot export team compensation data"
}

# Rule 4: Managers can only export in allowed formats
deny contains msg if {
	input.name == "export_compensation_data"
	is_manager
	format := lower(object.get(args, "format", "csv"))
	not format in {"csv", "pdf", "json"}
	msg := sprintf("Access denied: Export format '%s' not allowed. Use CSV, PDF, or JSON", [format])
}

# Rule 7: No one can share compensation data externally
deny contains msg if {
	input.name == "email_compensation_report"
	destination := object.get(args, "destination", "")
	is_external_email(destination)
	msg := "Access denied: Cannot share compensation data to external email addresses (non-@ibm.com)"
}

# Rule 8: Block emails to blocked domains
deny contains msg if {
	input.name == "send_email"
	recipient := object.get(args, "recipient_email", "")
	is_blocked_domain(recipient)
	msg := sprintf("Access denied: Cannot send emails to blocked domain: %s", [extract_domain(recipient)])
}

# Rule 8: Block compensation emails to blocked domains
deny contains msg if {
	input.name == "email_compensation_report"
	destination := object.get(args, "destination", "")
	is_blocked_domain(destination)
	msg := sprintf("Access denied: Cannot send emails to blocked domain: %s", [extract_domain(destination)])
}

# Rule 6: Managers can only send non-compensation data externally via send_email
deny contains msg if {
	input.name == "send_email"
	recipient := object.get(args, "recipient_email", "")
	is_external_email(recipient)
	email_content := lower(object.get(args, "email_content", ""))

	# Check if email contains compensation-related keywords
	compensation_keywords := {"compensation", "salary", "bonus", "pay", "payroll"}
	some keyword in compensation_keywords
	contains(email_content, keyword)

	msg := concat("", [
		"Access denied: Cannot send compensation data externally via send_email. ",
		"Use email_compensation_report for internal sharing only",
	])
}

# Rule 9: Employees need approval for purchases $200+
deny contains msg if {
	input.name == "purchase"
	is_employee
	amount := object.get(args, "amount", 0)
	amount >= 200
	not has_approval
	msg := sprintf("Access denied: Employees need manager approval for purchases of $%d or more", [amount])
}

# Rule 10: Managers cannot buy products $1000+
deny contains msg if {
	input.name == "purchase"
	is_manager
	amount := object.get(args, "amount", 0)
	amount >= 1000
	msg := sprintf("Access denied: Managers cannot purchase products of $%d or more (limit: $999)", [amount])
}

# === Envelope Validation ===
valid_envelope if {
	input.kind == "tool_call"
	input.action == "execute"
	input.name
	allowed_arg_keys[input.name]
}

# Check for unexpected arguments
unexpected_args contains arg if {
	some arg in object.keys(args)
	not arg in allowed_arg_keys[input.name]
}

deny contains msg if {
	count(unexpected_args) > 0
	msg := sprintf("Invalid arguments for tool '%s': %v", [input.name, unexpected_args])
}

# === Collect All Denials ===
any_deny if {
	count(deny) > 0
}

# === Final ALLOW ===
allow if {
	valid_envelope
	not any_deny
}
