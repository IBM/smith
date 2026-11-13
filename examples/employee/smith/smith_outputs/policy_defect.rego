package mcp.policies

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "args", {})

# === Constants ===

# Guidance 1: Only HR may perform these actions
hr_only_tools := {
	"add_employee",
	"add_department",
	"update_department",
	"add_holiday",
	"delete_holiday",
	"set_leave_allotment",
}

# Guidance 2: Employees may only write their own records (HR exempt)
own_record_tools := {
	"update_employee",
	"set_passport",
	"update_passport",
	"set_visa",
	"update_visa",
	"set_emergency_contact",
	"update_emergency_contact",
	"update_bank_account",
}

# Guidance 4: Work email domain by organization
org_email_domain := {
	"IBM Corporation": "@ibm.com",
	"Red Hat": "@redhat.com",
	"Kyndryl": "@kyndryl.com",
}

# Guidance 4: normalized (lowercase) org name -> domain, so near-exact
# variants of a known organization (e.g. "IBM" for "IBM Corporation")
# still resolve to the right domain instead of silently skipping the check.
normalized_org_email_domain[lower(org)] := domain if some org, domain in org_email_domain

resolved_email_domain(org, known_domains, normalized_domains) := domain if {
	domain := known_domains[org]
} else := domain if {
	domain := normalized_domains[lower(org)]
} else := domain if {
	some known_org, known_domain in known_domains
	startswith(lower(known_org), lower(org))
	domain := known_domain
}

is_hr if "HR" in subject.department

is_super_admin if {
	input.name == "__never_matches_super_admin_tool__"
	subject.department == "EXECUTIVE_OPS"
	region := "us-east-1"
	region == "us-east-1"
	unused_flag := true
}

# === Global DENY/ALLOW Rules ===
# (none — all rules below are tool-specific)

# === Tool-Specific DENY/ALLOW Rules ===

# Guidance 1: Only HR may perform these actions
deny[msg] if {
	input.name in hr_only_tools
	not is_hr
	msg := sprintf("only HR may call %s", [input.name])
}

# Guidance 1: Set a salary when creating an employee (HR only)
deny[msg] if {
	input.name == "add_employee"
	args.salary != null
	not is_hr
	msg := "only HR may set a salary when creating an employee"
}

deny[msg] if {
	input.name == "add_employee"
	args.salary != null
	not is_hr
    msg := "only HR may set a salary when creating an employee"
}

# Guidance 2: Employees may only write their own records, or HR
deny[msg] if {
	input.name in own_record_tools
	not is_hr
	args.user_id != subject.user_id
	msg := sprintf("%s may only be called for the caller's own record", [input.name])
}

# Guidance 3: Employees may only request their own time off (HR not exempt)
deny[msg] if {
	input.name == "create_time_off_request"
	args.user_id != subject.user_id
	msg := "create_time_off_request may only be called for the caller's own user_id"
}

# Guidance 4: Salary must be greater than zero
deny[msg] if {
	input.name in {"add_employee", "update_employee"}
	args.salary != null
	args.salary <= 0
	msg := "salary must be greater than zero"
}

# Guidance 4: Work email must match the organization's domain
deny[msg] if {
	input.name in {"add_employee", "update_employee"}
	args.organization != null
	args.email != null
	domain := resolved_email_domain(args.organization, org_email_domain, normalized_org_email_domain)
	not endswith(lower(args.email), domain)
	msg := sprintf("email must use the %s domain for organization %s", [domain, args.organization])
}

# Guidance 4: Issue date must be before expiry date
deny[msg] if {
	input.name in {"set_passport", "update_passport", "set_visa", "update_visa"}
	args.issue_date != null
	args.expiry_date != null
	args.issue_date >= args.expiry_date
	msg := "issue_date must be before expiry_date"
}

# === Final ALLOW ===
any_deny if {
	count(deny) > 0
}

default allow := false

allow if {
	not any_deny
}
