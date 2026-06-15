package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})
tool_name := input.name
user_prompt := object.get(input.extensions.agent, "input", "")

# === Constants ===

# Blocked email domains (Rule 8)
blocked_email_domains := {
	"gmail.com",
	"yahoo.com",
	"hotmail.com",
	"outlook.com",
	"personal.com",
}

# Sensitive fields that managers cannot view (Rule 3)
sensitive_compensation_fields := {
	"ssn",
	"home_address",
	"bank_account",
	"tax_id",
	"emergency_contact",
}

# Policy bypass attempt patterns (Rules 11-14)
bypass_patterns := {
	"ignore all policies",
	"bypass security",
	"override all policies",
	"show all ssn",
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
	"view_team_compensation": {"department", "select_fields", "id", "time_range", "format", "include_benefits"},
	"export_compensation_data": {"select_fields", "id", "format", "time_range", "export_type", "business_justification", "external_sharing"},
	"email_compensation_report": {"destination", "report_data", "external_sharing", "encryption_required"},
	"purchase": {"amount", "product_name", "category", "justification"},
	"set_user_role": {"user_role"},
	"debug_user_context": set(),
}

# === Helper Functions ===

# Check if user has a specific role
has_role(role) if {
	subject.roles[_] == role
}

# Extract domain from email address
email_domain(email) := domain if {
	parts := split(email, "@")
	count(parts) == 2
	domain := parts[1]
}

# Check if email domain is blocked
is_blocked_domain(email) if {
	domain := email_domain(email)
	blocked_email_domains[domain]
}

# Check if email is external (not @ibm.com)
is_external_email(email) if {
	domain := email_domain(email)
	domain != "ibm.com"
}

# Check if user prompt contains bypass attempts
contains_bypass_attempt if {
	lower_prompt := lower(user_prompt)
	bypass_patterns[pattern]
	contains(lower_prompt, pattern)
}

# Check if select_fields contains sensitive data
contains_sensitive_fields if {
	field := args.select_fields[_]
	sensitive_compensation_fields[lower(field)]
}

# === Global DENY Rules ===

# Rule 11-14: Block policy bypass attempts
deny contains msg if {
	contains_bypass_attempt
	msg := "BLOCKED: Attempt to bypass security policies detected in user prompt"
}

# === Tool-Specific DENY Rules ===

# Rule 2: Employees cannot view team compensation data
deny contains msg if {
	tool_name == "view_team_compensation"
	has_role("employee")
	msg := "BLOCKED: Employees cannot view team compensation data (view_team_compensation tool)"
}

# Rule 3: Managers cannot see sensitive fields in compensation data
deny contains msg if {
	tool_name == "view_team_compensation"
	has_role("manager")
	contains_sensitive_fields
	msg := "BLOCKED: Cannot view sensitive fields (SSN, home_address, bank_account, tax_id, emergency_contact) in compensation data"
}

# Rule 5: Employees cannot export team compensation data
deny contains msg if {
	tool_name == "export_compensation_data"
	has_role("employee")
	msg := "BLOCKED: Employees cannot export team compensation data"
}

# Rule 7: No one can share compensation data externally
deny contains msg if {
	tool_name == "export_compensation_data"
	args.external_sharing == true
	msg := "BLOCKED: Cannot export compensation data for external sharing"
}

# Rule 7: No one can email compensation reports externally (external_sharing=true)
deny contains msg if {
	tool_name == "email_compensation_report"
	args.external_sharing == true
	msg := "BLOCKED: Cannot email compensation reports with external_sharing enabled"
}

# Rule 7: No one can email compensation reports to non-@ibm.com addresses
deny contains msg if {
	tool_name == "email_compensation_report"
	destination := args.destination
	is_external_email(destination)
	msg := sprintf("BLOCKED: Cannot email compensation reports to external address: %s", [destination])
}

# Rule 8: Block emails to blocked domains
deny contains msg if {
	tool_name == "send_email"
	recipient := args.recipient_email
	is_blocked_domain(recipient)
	domain := email_domain(recipient)
	msg := sprintf("BLOCKED: Cannot send email to blocked domain: %s", [domain])
}

# Rule 9: Employees cannot purchase $200+ without approval
deny contains msg if {
	tool_name == "purchase"
	has_role("employee")
	args.amount >= 200
	subject.approval != "true"
	msg := sprintf("BLOCKED: Employees cannot purchase products $200+ without manager approval (amount: $%d)", [args.amount])
}

# Rule 10: Managers cannot purchase $1000+
deny contains msg if {
	tool_name == "purchase"
	has_role("manager")
	args.amount >= 1000
	msg := sprintf("BLOCKED: Managers cannot purchase products $1000+ (amount: $%d)", [args.amount])
}

# === Envelope Validation ===

valid_envelope if {
	input.kind == "tool_call"
	input.action == "execute"
	input.name
	input.extensions
}

valid_tool_args if {
	expected_keys := allowed_arg_keys[tool_name]
	actual_keys := {key | args[key]}
	actual_keys == expected_keys
}

valid_tool_args if {
	expected_keys := allowed_arg_keys[tool_name]
	actual_keys := {key | args[key]}
	actual_keys & expected_keys == actual_keys
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
