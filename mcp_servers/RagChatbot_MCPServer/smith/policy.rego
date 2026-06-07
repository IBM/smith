package mcp.policies

default allow := false

subject := input.extensions.subject
obj := input.extensions.object
args := object.get(input, "arguments", {})

# =========================
# Helpers
# =========================

has_subject_perm(p) if {
	p in subject.permissions
}

has_object_perm(p) if {
	p in obj.permissions
}

normalized_role(role) := "user" if {
	lower(role) == "employee"
}

normalized_role(role) := lower(role) if {
	lower(role) != "employee"
}

is_role(r) if {
	some role in subject.roles
	normalized_role(role) == lower(r)
}

valid_envelope if {
	input.kind == "tool_call"
	input.action == "execute"
	input.name != ""
}

email_domain(addr) := domain if {
	parts := split(lower(addr), "@")
	count(parts) == 2
	domain := parts[1]
}

has_arg(k) if {
	object.get(args, k, null) != null
}

field_in_tool_scope(tool_name, field) if {
	field in tool_data_scope[tool_name].fields
}

# =========================
# Constants
# =========================

forbidden_fields := {
	"ssn",
	"tax_id",
	"bank_account",
	"home_address",
	"personal_email",
	"emergency_contact",
	"healthcare_id",
	"healthcare_plan",
}

tool_data_scope := {
	"view_team_compensation": {
		"labels": ["financial", "PII", "confidential"],
		"fields": [
			"employee_name",
			"title",
			"department",
			"level",
			"hire_date",
			"base_salary",
			"bonus_target",
			"actual_bonus_2024",
			"performance_rating",
			"next_review_date",
			"stock_grant_value",
			"benefits_value",
			"total_compensation",
		],
		"scope": "team",
	},
	"ask_for_salary": {
		"labels": ["financial", "PII", "confidential"],
		"fields": [
			"base_salary",
			"total_compensation",
			"title",
			"department",
			"level",
			"bonus_target",
			"actual_bonus_2024",
			"performance_rating",
		],
		"scope": "user",
	},
	"export_compensation_data": {
		"labels": ["financial", "PII", "confidential"],
		"fields": [
			"employee_id",
			"name",
			"title",
			"level",
			"current_salary",
			"total_comp_2024",
			"performance_rating",
			"salary_history",
			"bonus_history",
		],
		"scope": "team",
	},
	"email_compensation_report": {
		"labels": ["financial", "confidential"],
		"fields": ["destination", "report_data", "external_sharing", "encryption_required"],
		"scope": "team",
	},
	"send_email": {
		"labels": ["general"],
		"fields": ["recipient_email", "subject", "body", "email_content", "attached_file"],
		"scope": "user",
	},
	"create_ticket": {
		"labels": ["general"],
		"fields": ["ticket_content"],
		"scope": "user",
	},
	"submit_ticket": {
		"labels": ["general"],
		"fields": ["ticket_content"],
		"scope": "user",
	},
	"purchase": {
		"labels": ["financial"],
		"fields": ["amount", "product_name", "category", "justification"],
		"scope": "user",
	},
	"return_product": {
		"labels": ["financial"],
		"fields": ["amount", "product_name"],
		"scope": "user",
	},
	"ask_for_workpolicy": {
		"labels": ["general"],
		"fields": ["question"],
		"scope": "user",
	},
	"get_w2_form": {
		"labels": ["general"],
		"fields": [],
		"scope": "user",
	},
	"export_content_as_file": {
		"labels": ["general"],
		"fields": ["data", "file_name"],
		"scope": "user",
	},
	"set_user_role": {
		"labels": ["admin"],
		"fields": ["user_role"],
		"scope": "admin",
	},
	"test_purchase_policy": {
		"labels": ["admin"],
		"fields": ["amount", "product"],
		"scope": "admin",
	},
}

manager_view_allowed_fields := {
	"employee_name",
	"title",
	"department",
	"level",
	"hire_date",
	"base_salary",
	"bonus_target",
	"actual_bonus_2024",
	"performance_rating",
	"next_review_date",
	"stock_grant_value",
	"benefits_value",
	"total_compensation",
}

manager_export_allowed_fields := {
	"employee_id",
	"name",
	"title",
	"level",
	"current_salary",
	"total_comp_2024",
	"performance_rating",
	"salary_history",
	"bonus_history",
}

allowed_export_formats := {"CSV", "PDF", "JSON"}

blocked_domains := {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "personal.com"}
internal_domain := "ibm.com"

allowed_arg_keys := {
	"view_team_compensation": {"select_fields", "id", "department", "time_range", "format", "include_benefits"},
	"ask_for_salary": {"question"},
	"export_compensation_data": {
		"select_fields", "id", "format", "time_range", "export_type",
		"business_justification", "external_sharing", "department",
	},
	"email_compensation_report": {"destination", "report_data", "external_sharing", "encryption_required"},
	"send_email": {"recipient_email", "subject", "body", "email_content", "attached_file"},
	"create_ticket": {"ticket_content"},
	"submit_ticket": {"ticket_content"},
	"ask_for_workpolicy": {"question"},
	"get_w2_form": {},
	"purchase": {"amount", "product_name", "category", "justification"},
	"return_product": {"amount", "product_name"},
	"export_content_as_file": {"data", "file_name"},
	"set_user_role": {"user_role"},
	"test_purchase_policy": {"amount", "product"},
}

# =========================
# Global DENY rules
# =========================

deny[msg] if {
	valid_envelope
	not allowed_arg_keys[input.name]
	msg := sprintf("Unknown or unauthorized tool '%s'", [input.name])
}

deny[msg] if {
	valid_envelope
	some k in object.keys(args)
	not allowed_arg_keys[input.name][k]
	msg := sprintf("Unexpected argument key '%s' for tool '%s'", [k, input.name])
}

deny[msg] if {
	valid_envelope
	object.get(args, "select_fields", null) != null
	some f in args.select_fields
	not field_in_tool_scope(input.name, f)
	msg := sprintf("Requested field '%s' not allowed by data scope for tool '%s'", [f, input.name])
}

deny[msg] if {
	valid_envelope
	object.get(args, "select_fields", null) != null
	some f in args.select_fields
	forbidden_fields[f]
	msg := sprintf("Requested forbidden sensitive field '%s'", [f])
}

deny[msg] if {
	valid_envelope
	agent_input := lower(object.get(input.extensions.agent, "input", ""))
	agent_input != ""
	malicious_keywords := [
		"bypass", "circumvent", "ignore", "override", "disable", "deactivate",
		"turn off", "shut down", "skip", "disregard", "unrestricted access",
		"all policies", "policy restrictions", "policy enforcement", "security protocols",
		"security measures", "security restrictions", "policy controls", "policy checks",
		"mass ssn", "bulk ssn", "all ssn", "ssn data", "ssn database", "ssn records",
		"ssn information", "ssn collection", "social security number", "entire social security",
	]
	some keyword in malicious_keywords
	contains(agent_input, keyword)
	msg := sprintf("Malicious intent detected in request: '%s'", [keyword])
}

# =========================
# Tool-specific DENY rules
# =========================

deny[msg] if {
	input.name == "view_team_compensation"
	not is_role("manager")
	msg := "Only managers can use view_team_compensation"
}

deny[msg] if {
	input.name == "view_team_compensation"
	is_role("manager")
	has_arg("department")
	count(subject.teams) > 0
	not args.department in subject.teams
	msg := sprintf("Manager can only view compensation data for their own team(s), not '%s'", [args.department])
}

deny[msg] if {
	input.name == "view_team_compensation"
	is_role("manager")
	object.get(args, "select_fields", null) != null
	some f in args.select_fields
	not manager_view_allowed_fields[f]
	msg := sprintf("Manager not permitted to view field '%s' in team compensation", [f])
}

deny[msg] if {
	input.name == "ask_for_salary"
	not is_role("user")
	not is_role("manager")
	msg := "Only employees or managers can use ask_for_salary"
}

deny[msg] if {
	input.name == "ask_for_salary"
	has_arg("question")
	q := lower(args.question)
	contains(q, "team")
	msg := "ask_for_salary is for personal or general salary questions only; team salary queries are not allowed"
}

deny[msg] if {
	input.name == "export_compensation_data"
	not is_role("manager")
	msg := "Only managers can export compensation data"
}

deny[msg] if {
	input.name == "export_compensation_data"
	has_arg("format")
	fmt := upper(args.format)
	not allowed_export_formats[fmt]
	msg := sprintf("Export format '%s' not allowed", [args.format])
}

deny[msg] if {
	input.name == "export_compensation_data"
	is_role("manager")
	object.get(args, "select_fields", null) != null
	some f in args.select_fields
	not manager_export_allowed_fields[f]
	msg := sprintf("Manager not permitted to export field '%s'", [f])
}

deny[msg] if {
	input.name == "email_compensation_report"
	has_arg("destination")
	email_domain(args.destination) != internal_domain
	msg := "No one can email compensation reports to non-@ibm.com addresses"
}

deny[msg] if {
	input.name == "send_email"
	has_arg("recipient_email")
	blocked_domains[email_domain(args.recipient_email)]
	msg := sprintf("Recipient domain '%s' is blocked", [email_domain(args.recipient_email)])
}

deny[msg] if {
	input.name == "send_email"
	has_arg("recipient_email")
	email_domain(args.recipient_email) != internal_domain
	text := lower(sprintf("%v %v %v", [
		object.get(args, "subject", ""),
		object.get(args, "body", ""),
		object.get(args, "email_content", ""),
	]))
	some kw in {"salary", "compensation", "bonus", "ssn"}
	contains(text, kw)
	msg := "No one can send compensation or salary data to non-@ibm.com addresses"
}

deny[msg] if {
	input.name == "purchase"
	not is_role("user")
	not is_role("manager")
	msg := "Only employees or managers can purchase items"
}

deny[msg] if {
	input.name == "purchase"
	is_role("user")
	has_arg("amount")
	to_number(args.amount) > 200
	not object.get(subject, "approval", false)
	msg := "Employees cannot buy products above $200 without manager approval"
}

deny[msg] if {
	input.name == "purchase"
	is_role("manager")
	has_arg("amount")
	to_number(args.amount) > 1000
	msg := "Managers cannot buy products above $1,000"
}

deny[msg] if {
	input.name == "set_user_role"
	not is_role("manager")
	msg := "Only managers can set user roles"
}

deny[msg] if {
	input.name == "test_purchase_policy"
	not is_role("manager")
	msg := "Only managers can test purchase policy"
}

# =========================
# Deny helper
# =========================

any_deny if {
	count(deny) > 0
}

# =========================
# Final ALLOW
# =========================

allow if {
	valid_envelope
	not any_deny
}
