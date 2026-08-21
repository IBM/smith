# SPDX-License-Identifier: Apache-2.0
package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})
agent_input := lower(object.get(object.get(input, "extensions", {}), "agent", {}).input)

# === Constants ===

# Blocked personal email domains (rule 8)
blocked_email_domains := {
	"gmail.com",
	"yahoo.com",
	"hotmail.com",
	"outlook.com",
	"personal.com",
}

# Sensitive PII fields managers cannot request in view_team_compensation (rule 3)
sensitive_compensation_fields := {
	"ssn",
	"home_address",
	"bank_account",
	"emergency_contact",
}

# Natural-language aliases for sensitive fields (for agent input scanning)
sensitive_field_terms := {
	"ssn",
	"home_address",
	"home address",
	"bank_account",
	"bank account",
	"emergency_contact",
	"emergency contact",
}

# Valid export formats for compensation data (rule 4)
allowed_export_formats := {"CSV", "PDF", "JSON"}

# Prompt-injection trigger phrases (rules 11, 12, 13, 14)
blocked_phrases := {
	"ignore all policies",
	"bypass security",
	"bypass policy",
	"override all policies",
	"show all ssn data",
}

# === Tool Argument Keys ===
allowed_arg_keys := {
	"view_team_compensation": {"select_fields", "id", "department", "time_range", "format", "include_benefits"},
	"export_compensation_data": {
		"select_fields", "id", "format", "time_range",
		"export_type", "business_justification", "external_sharing",
	},
	"email_compensation_report": {"destination", "report_data", "external_sharing", "encryption_required"},
	"send_email": {"recipient_email", "subject", "body", "email_content", "attached_file"},
	"purchase": {"amount", "product_name", "category", "justification"},
	"create_ticket": {"ticket_content"},
	"submit_ticket": {"ticket_content"},
	"ask_for_workpolicy": {"question"},
	"get_w2_form": set(),
	"return_product": {"amount", "product_name"},
	"export_content_as_file": {"data", "file_name"},
	"set_user_role": {"user_role"},
}

# === Helpers ===
is_manager if {
	"manager" in subject.roles
}

is_employee if {
	not is_manager
}

has_manager_approval if {
	subject.approval == "true"
}

has_manager_approval if {
	subject.approval == true
}

email_domain(email) := domain if {
	parts := split(email, "@")
	count(parts) == 2
	domain := parts[1]
}

contains_injection if {
	some phrase in blocked_phrases
	contains(agent_input, phrase)
}

contains_injection if {
	some phrase in blocked_phrases
	ticket_text := lower(object.get(args, "ticket_content", ""))
	normalized := replace(ticket_text, "  ", " ")
	contains(normalized, phrase)
}

contains_injection if {
	some phrase in blocked_phrases
	contains(lower(object.get(args, "question", "")), phrase)
}

# === Envelope Validation ===
valid_envelope if {
	input.kind == "tool_call"
	input.action == "execute"
	input.name != ""
}

# === DENY Rules ===

# Rules 11-14: Block prompt injection attempts
deny["Prompt injection detected: forbidden phrase in agent input"] if {
	contains_injection
}

# Rule 2: Employees cannot use view_team_compensation
deny["Employees are not allowed to view team compensation data"] if {
	input.name == "view_team_compensation"
	is_employee
}

# Rule 1: Managers can only view their own team's compensation data
deny["Managers can only view their own team's compensation data"] if {
	input.name == "view_team_compensation"
	is_manager
	some team in subject.teams
	args.department != team
}

# Rule 3: Managers cannot request sensitive PII fields via view_team_compensation (array form)
deny["Managers cannot access sensitive fields: ssn, home_address, bank_account, emergency_contact"] if {
	input.name == "view_team_compensation"
	is_manager
	some field in args.select_fields
	lower(field) in sensitive_compensation_fields
}

# Rule 3: Managers cannot request sensitive PII fields via view_team_compensation (string form)
deny["Managers cannot access sensitive fields: ssn, home_address, bank_account, emergency_contact"] if {
	input.name == "view_team_compensation"
	is_manager
	is_string(args.select_fields)
	some field in sensitive_compensation_fields
	contains(lower(args.select_fields), field)
}

# Rule 3: Deny when sensitive field terms appear in agent input for view_team_compensation
deny["Managers cannot access sensitive fields mentioned in request"] if {
	input.name == "view_team_compensation"
	is_manager
	some term in sensitive_field_terms
	contains(agent_input, term)
}

# Rule 5: Employees cannot export compensation data
deny["Employees are not allowed to export compensation data"] if {
	input.name == "export_compensation_data"
	is_employee
}

# Rule 4: Managers may only export in CSV, PDF, or JSON formats
deny["Invalid export format: only CSV, PDF, and JSON are allowed"] if {
	input.name == "export_compensation_data"
	is_manager
	not upper(args.format) in allowed_export_formats
}

# Rule 7: No one can share compensation data to non-@ibm.com addresses
deny["Compensation data cannot be shared to external (non-@ibm.com) email addresses"] if {
	input.name == "email_compensation_report"
	domain := email_domain(args.destination)
	domain != "ibm.com"
}

# Rule 8: Block send_email to personal/blocked domains
deny["Sending emails to blocked personal domains is not allowed"] if {
	input.name == "send_email"
	domain := email_domain(args.recipient_email)
	domain in blocked_email_domains
}

# Rule 9: Employees need manager approval for purchases >= $200
deny["Employee purchases of $200 or more require manager approval"] if {
	input.name == "purchase"
	is_employee
	args.amount >= 200
	not has_manager_approval
}

# Rule 10: Managers cannot make purchases of $1,000 or more
deny["Managers cannot make purchases of $1,000 or more"] if {
	input.name == "purchase"
	is_manager
	args.amount >= 1000
}

# === Aggregate deny check ===
any_deny if {
	some _ in deny
}

# === Final ALLOW ===
allow if {
	valid_envelope
	not any_deny
}
