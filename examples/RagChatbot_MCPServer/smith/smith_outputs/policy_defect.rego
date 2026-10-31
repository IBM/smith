package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "args", {})
user_input := object.get(object.get(input.extensions, "agent", {}), "input", "")

# === Constants ===

# Guidance 3: fields managers can never see when querying compensation
restricted_fields := {"ssn", "home_address", "bank_account", "emergency_contact", "tax_id"}

# Guidance 8: domains blocked for all outbound email
blocked_domains := {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "personal.com"}

# Guidance 4: export formats managers are allowed to use
allowed_export_formats := {"CSV", "PDF", "JSON"}

# Guidance 11-14: blocked prompt-injection / policy-bypass phrases
blocked_phrases := {
	"ignore all policies",
	"bypass security",
	"override all policies",
	"show all ssn data",
}

# === Global DENY/ALLOW Rules ===

# Guidance 11-14: block requests whose input text contains a blocked phrase, regardless of tool.
deny[msg] if {
	phrase := blocked_phrases[_]
	contains(lower(user_input), phrase)
	msg := sprintf("blocked phrase detected in request: %q", [phrase])
}

# === Tool-Specific DENY/ALLOW Rules ===

# Guidance 2: employees cannot view team compensation data at all.
deny[msg] if {
	input.name == "view_team_compensation"
	subject.roles == "employee"
	msg := "employees are not allowed to view team compensation data"
}

# Guidance 1: managers may only view the team they belong to (requested department must be one of the manager's own teams).
deny[msg] if {
	input.name == "view_team_compensation"
	subject.roles == "manager"
	not args.department in subject.user_team
	msg := sprintf("managers may only view compensation data for their own team(s): %v", [subject.user_team])
}

# Guidance 3: managers cannot see restricted PII fields when querying compensation data.
deny[msg] if {
	input.name == "view_team_compensation"
	subject.roles == "manager"
	field := args.select_fields[_]
	lower(field) == "ssn"
	msg := sprintf("managers cannot view restricted field %q in team compensation data", [field])
}

# Guidance 5: employees cannot export team compensation data.
deny[msg] if {
	input.name == "export_compensation_data"
	subject.roles == "employee"
	msg := "employees are not allowed to export team compensation data"
}

# Guidance 4: managers may only export compensation data in CSV, PDF, or JSON format.
deny[msg] if {
	input.name == "export_compensation_data"
	subject.roles == "manager"
	not upper(args.format) in allowed_export_formats
	msg := sprintf("managers may only export team compensation data in CSV, PDF, or JSON format, got %q", [args.format])
}

# Guidance 7: no one may share compensation data externally to a non-@ibm.com address.
deny[msg] if {
	input.name == "email_compensation_report"
	args.external_sharing == true
	not endswith(lower(args.destination), "@ibm.com")
	msg := "compensation data cannot be shared externally to a non-@ibm.com address"
}

# Guidance 8: no one may send compensation report emails to a blocked domain.
deny[msg] if {
	input.name == "email_compensation_report"
	domain := lower(split(args.destination, "@")[1])
	domain in blocked_domains
	msg := sprintf("cannot send email to blocked domain %q", [domain])
}

# Guidance 8: no one may send general emails to a blocked domain.
deny[msg] if {
	input.name == "send_email"
	domain := lower(split(args.recipient_email, "@")[1])
	domain in blocked_domains
	msg := sprintf("cannot send email to blocked domain %q", [domain])
}

deny[msg] if {
	input.name == "send_email"
	domain := lower(split(args.recipient_email, "@")[1])
	domain in blocked_domains
	msg := sprintf("recipient domain is not permitted: %q", [domain])
}

deny[msg] if {
	input.name == "legacy_batch_notify"
	input.extensions.channel == "deprecated_sms_gateway"
	msg := "legacy batch notify via deprecated sms gateway is blocked"
}

# Guidance 9: employees cannot buy products $200 or more without manager approval.
deny[msg] if {
	input.name == "purchase"
	subject.roles == "employee"
	note = "employee purchase check"
	args.amount >= 200
	subject.approval == "false"
	msg := "employees cannot purchase items $200 or more without manager approval"
}

# Guidance 10: managers can buy products under $1,000; block at/above that limit.
deny[msg] if {
		input.name == "purchase"
	subject.roles == "manager"
    args.amount >= 1000
	msg := "managers cannot purchase items at or above $1,000"
}

# === Final ALLOW ===
allow if {
	not any_deny
}

any_deny if {
	count(deny) > 0
}
