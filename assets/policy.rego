package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "args", {})

# === Constants ===

blocked_email_domains := {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "personal.com"}

trusted_email_domain := "ibm.com"

blocked_sensitive_fields := {"ssn", "home_address", "bank_account", "tax_id", "emergency_contact"}

blocked_phrases := {"ignore all policies", "bypass security", "override all policies", "show all ssn data"}

employee_purchase_cap := 200

manager_purchase_cap := 1000

compensation_tools := {"view_team_compensation", "export_compensation_data", "email_compensation_report"}

free_text_arg_names := {"ticket_content", "question", "email_content", "body", "report_data", "justification"}

# === Helpers ===

email_domain(email) := domain if {
	parts := split(email, "@")
	count(parts) == 2
	domain := lower(parts[1])
}

select_fields_list := sf if {
	sf := args.select_fields
	sf != null
}

select_fields_list := [] if {
	object.get(args, "select_fields", null) == null
}

contains_blocked_field if {
	some f in select_fields_list
	lower(f) in blocked_sensitive_fields
}

contains_blocked_phrase if {
	some field_name in free_text_arg_names
	value := object.get(args, field_name, "")
	is_string(value)
	some phrase in blocked_phrases
	contains(lower(value), phrase)
}

# === Global DENY Rules ===

# Rules 11-14: block known prompt-injection phrases in any free-text argument
deny[msg] if {
	contains_blocked_phrase
	msg := "PROMPT_INJECTION_PHRASE_BLOCK: request contains a blocked policy-override phrase"
}

# === Tool-Specific DENY Rules ===

# Rule 2: employees cannot view team compensation data
deny[msg] if {
	input.name == "view_team_compensation"
	subject.role != "manager"
	msg := "MANAGER_ROLE_GATED_COMPENSATION_ACCESS: view_team_compensation is manager-only"
}

# Rule 3 / 16: view_team_compensation must never return sensitive fields, with or without select_fields
deny[msg] if {
	input.name == "view_team_compensation"
	subject.role == "manager"
	select_fields_list == []
	msg := "DEFAULT_SENSITIVE_FIELD_EXPOSURE: select_fields must be provided and exclude sensitive fields"
}

deny[msg] if {
	input.name == "view_team_compensation"
	contains_blocked_field
	msg := "DEFAULT_SENSITIVE_FIELD_EXPOSURE: select_fields includes a blocked sensitive field"
}

# Rule 5: employees cannot export team compensation data
deny[msg] if {
	input.name == "export_compensation_data"
	subject.role != "manager"
	msg := "MANAGER_ROLE_GATED_COMPENSATION_ACCESS: export_compensation_data is manager-only"
}

# Rule 3 / 16: export_compensation_data must never return sensitive fields, with or without select_fields
deny[msg] if {
	input.name == "export_compensation_data"
	subject.role == "manager"
	select_fields_list == []
	msg := "DEFAULT_SENSITIVE_FIELD_EXPOSURE: select_fields must be provided and exclude sensitive fields"
}

deny[msg] if {
	input.name == "export_compensation_data"
	contains_blocked_field
	msg := "DEFAULT_SENSITIVE_FIELD_EXPOSURE: select_fields includes a blocked sensitive field"
}

# Rule 7: no one may export compensation data externally
deny[msg] if {
	input.name == "export_compensation_data"
	args.external_sharing == true
	msg := "EXTERNAL_COMPENSATION_SHARING: export_compensation_data cannot be shared externally"
}

# Rule 6: send_email external sends restricted to non-compensation content; only managers may send externally
deny[msg] if {
	input.name == "send_email"
	email_domain(args.recipient_email) != trusted_email_domain
	subject.role != "manager"
	msg := "MANAGER_ROLE_GATED_EXTERNAL_EMAIL: only managers may send email to non-ibm.com recipients"
}

# Rule 8: blocked domains for send_email
deny[msg] if {
	input.name == "send_email"
	email_domain(args.recipient_email) in blocked_email_domains
	msg := "BLOCKED_EMAIL_DOMAIN: recipient_email domain is blocked"
}

# Rule 15: employees cannot use email_compensation_report
deny[msg] if {
	input.name == "email_compensation_report"
	subject.role != "manager"
	msg := "MANAGER_ROLE_GATED_COMPENSATION_ACCESS: email_compensation_report is manager-only"
}

# Rule 7: no one may share compensation reports externally / to non-ibm.com domains
deny[msg] if {
	input.name == "email_compensation_report"
	args.external_sharing == true
	msg := "EXTERNAL_COMPENSATION_SHARING: email_compensation_report cannot be shared externally"
}

deny[msg] if {
	input.name == "email_compensation_report"
	email_domain(args.destination) != trusted_email_domain
	msg := "COMPENSATION_EMAIL_DOMAIN_RESTRICTION: email_compensation_report destination must be an ibm.com address"
}

# Rule 8: blocked domains for email_compensation_report
deny[msg] if {
	input.name == "email_compensation_report"
	email_domain(args.destination) in blocked_email_domains
	msg := "BLOCKED_EMAIL_DOMAIN: destination domain is blocked"
}

# Rule 9: employees cannot buy >= $200 without manager approval
deny[msg] if {
	input.name == "purchase"
	subject.role != "manager"
	args.amount >= employee_purchase_cap
	subject.approval != "true"
	msg := "PURCHASE_LIMIT_EXCEEDED: employees require manager approval to purchase $200 or more"
}

# Rule 10: managers capped at purchases under $1,000
deny[msg] if {
	input.name == "purchase"
	subject.role == "manager"
	args.amount >= manager_purchase_cap
	msg := "PURCHASE_LIMIT_EXCEEDED: managers cannot purchase $1,000 or more"
}

# Rule 17: set_user_role cannot be verified today; label the decision for downstream review rather than deny
label[msg] if {
	input.name == "set_user_role"
	msg := "SET_ROLE_UNVERIFIABLE: role assignment has no authentication; flagged for review"
}

# === Final ALLOW ===

any_deny if {
	count(deny) > 0
}

allow if {
	not any_deny
}
