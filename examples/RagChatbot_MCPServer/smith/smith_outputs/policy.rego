# SPDX-License-Identifier: Apache-2.0

package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "args", {})

# === Constants ===

blocked_keywords := {
	"ignore all policies",
	"bypass security",
	"override all policies",
	"show all ssn data",
}

blocked_email_domains := {
	"gmail.com",
	"yahoo.com",
	"hotmail.com",
	"outlook.com",
	"personal.com",
}

forbidden_select_fields := {
	"ssn",
	"home_address",
	"bank_account",
	"personal_email",
	"emergency_contact",
}

compensation_tools := {
	"view_team_compensation",
	"export_compensation_data",
}

# === Helper: role check ===
is_manager if {
	"manager" in subject.roles
}

# === Helper: domain extraction ===
email_domain(addr) := domain if {
	parts := split(addr, "@")
	count(parts) == 2
	domain := parts[1]
}

# === Helper: keyword check ===
contains_blocked_keyword(text) if {
	some keyword in blocked_keywords
	contains(lower(text), keyword)
}

# === Global Deny: keyword injection in free-text arguments ===

# Rule 11–14 + Rules 15(select_fields) + Rules 17–18 via ticket_content
deny["Blocked keyword detected in ticket content"] if {
	input.name in {"create_ticket", "submit_ticket"}
	contains_blocked_keyword(args.ticket_content)
}

deny["Blocked keyword detected in question"] if {
	input.name == "ask_for_workpolicy"
	contains_blocked_keyword(args.question)
}

deny["Blocked keyword detected in email body"] if {
	input.name == "send_email"
	contains_blocked_keyword(args.body)
}

deny["Blocked keyword detected in email content"] if {
	input.name == "send_email"
	contains_blocked_keyword(args.email_content)
}

deny["Blocked keyword detected in report data"] if {
	input.name == "email_compensation_report"
	contains_blocked_keyword(args.report_data)
}

# === Rule 1–2: view_team_compensation — manager only ===

deny["Access to compensation data is restricted to managers"] if {
	input.name == "view_team_compensation"
	not is_manager
}

# Rule 1: managers can only view their own team's data
deny["Managers may only view compensation data for their own team"] if {
	input.name == "view_team_compensation"
	is_manager
	count(subject.teams) > 0
	requested_dept := args.department
	not requested_dept in subject.teams
}

# === Rule 3: view_team_compensation — forbidden fields in select_fields ===

deny["Sensitive fields (SSN, home address, bank account, personal email, emergency contact) cannot be queried"] if {
	input.name == "view_team_compensation"
	some field in args.select_fields
	field in forbidden_select_fields
}

# === Rule 15: select_fields must be specified for all compensation tools ===

deny["You must specify which fields to return when accessing compensation data"] if {
	input.name in compensation_tools
	is_null_or_absent_select_fields
}

is_null_or_absent_select_fields if {
	not args.select_fields
}

is_null_or_absent_select_fields if {
	args.select_fields == null
}

is_null_or_absent_select_fields if {
	count(args.select_fields) == 0
}

is_null_or_absent_select_fields if {
	args.select_fields == "None"
}

# === Rules 4–5: export_compensation_data — manager only ===

deny["Exporting compensation data is restricted to managers"] if {
	input.name == "export_compensation_data"
	not is_manager
}

# === Rule 17: export_compensation_data — external_sharing must be false ===

deny["Compensation data cannot be exported with external sharing enabled"] if {
	input.name == "export_compensation_data"
	args.external_sharing == true
}

# === Rule 18 + Rule 19: email_compensation_report ===

# Rule 19: employees cannot send compensation reports
deny["Employees are not permitted to send compensation reports by email"] if {
	input.name == "email_compensation_report"
	not is_manager
}

# Rule 18: external_sharing must be false
deny["Compensation reports cannot be emailed with external sharing enabled"] if {
	input.name == "email_compensation_report"
	args.external_sharing == true
}

# === Rule 7: email_compensation_report — @ibm.com only ===

deny["Compensation reports may only be sent to @ibm.com addresses"] if {
	input.name == "email_compensation_report"
	destination := args.destination
	domain := email_domain(destination)
	domain != "ibm.com"
}

# === Rule 8: blocked domains on send_email and email_compensation_report ===

deny["Email to blocked domain is not permitted"] if {
	input.name == "send_email"
	domain := email_domain(args.recipient_email)
	domain in blocked_email_domains
}

# Fallback: scan agent input text when recipient_email is absent from args
deny["Email to blocked domain is not permitted"] if {
	input.name == "send_email"
	not args.recipient_email
	agent_input := input.extensions.agent.input
	some domain in blocked_email_domains
	contains(lower(agent_input), concat("", ["@", domain]))
}

deny["Email to blocked domain is not permitted"] if {
	input.name == "email_compensation_report"
	domain := email_domain(args.destination)
	domain in blocked_email_domains
}

# === Rules 9–10: purchase — amount thresholds ===

# Rule 10: managers hard cap at $1,000
deny["Purchase amount exceeds the $1,000 limit for managers"] if {
	input.name == "purchase"
	is_manager
	args.amount >= 1000
}

# Rule 9: employees require approval for purchases $200+
deny["Employees require manager approval for purchases of $200 or more"] if {
	input.name == "purchase"
	not is_manager
	args.amount >= 200
	not approval_granted
}

approval_granted if subject.approval == "true"

approval_granted if subject.approval == true

# Fallback: deny employee purchase when amount is absent from args but agent input contains a $ amount >= 200
deny["Employees require manager approval for purchases of $200 or more"] if {
	input.name == "purchase"
	not is_manager
	not args.amount
	not approval_granted
	agent_input := input.extensions.agent.input
	contains(agent_input, "$")
}

# === Final ALLOW ===

any_deny if {
	some _ in deny
}

allow if {
	not any_deny
}
