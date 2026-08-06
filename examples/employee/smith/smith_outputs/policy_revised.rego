# SPDX-License-Identifier: Apache-2.0

package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})

# === Constants ===

# Today's date (YYYY-MM-DD) used for expiry-date checks
today := "2026-08-04"

# Six months from today (YYYY-MM-DD) — expiry must be strictly after this
six_months_from_today := "2027-02-04"

# Corporate email domains per organization
org_domains := {
	"IBM Corporation": "@ibm.com",
	"Red Hat": "@redhat.com",
	"Kyndryl": "@kyndryl.com",
}

# Tools restricted to HR only
hr_only_tools := {
	"add_department",
	"update_department",
	"set_leave_allotment",
	"add_holiday",
	"delete_holiday",
}

# === Tool Argument Keys ===
allowed_arg_keys := {
	"add_employee": {"first_name", "last_name", "email", "role", "title", "home_address", "country_code", "organization", "department_id", "manager_id", "salary", "salary_currency", "start_date"},
	"update_employee": {"user_id", "first_name", "last_name", "email", "role", "organization", "title", "department_id", "home_address", "manager_id", "country_code", "salary", "salary_currency", "start_date"},
	"get_employee": {"user_id"},
	"list_employees": {"department_id", "manager_id", "country_code"},
	"get_manager": {"user_id"},
	"get_direct_reports": {"user_id"},
	"get_reporting_chain": {"user_id"},
	"add_department": {"name", "description"},
	"update_department": {"department_id", "name", "description"},
	"get_department": {"department_id"},
	"list_departments": set(),
	"set_passport": {"user_id", "passport_number", "issuing_country", "issue_date", "expiry_date"},
	"update_passport": {"user_id", "passport_number", "issuing_country", "issue_date", "expiry_date"},
	"get_passport": {"user_id"},
	"set_visa": {"user_id", "visa_number", "issuing_country", "visa_type", "issue_date", "expiry_date"},
	"update_visa": {"user_id", "visa_number", "visa_type", "issuing_country", "issue_date", "expiry_date"},
	"get_visa": {"user_id"},
	"set_emergency_contact": {"user_id", "name", "relationship", "phone", "email", "street_address", "city", "country", "postal_code"},
	"update_emergency_contact": {"user_id", "name", "relationship", "phone", "email", "street_address", "city", "country", "postal_code"},
	"get_emergency_contact": {"user_id"},
	"set_bank_account": {"user_id", "bank_name", "account_number", "routing_number", "iban", "currency"},
	"update_bank_account": {"user_id", "bank_name", "account_number", "routing_number", "iban", "currency"},
	"get_bank_account": {"user_id"},
	"set_leave_allotment": {"user_id", "leave_type", "annual_days"},
	"get_leave_allotments": {"user_id"},
	"create_time_off_request": {"user_id", "leave_type", "start_date", "end_date", "reason"},
	"update_time_off_status": {"request_id", "status"},
	"get_time_off_request": {"request_id"},
	"list_time_off_requests": {"user_id", "status"},
	"get_leave_balance": {"user_id", "year"},
	"add_holiday": {"country_code", "holiday_date", "name"},
	"list_holidays": {"country_code", "year"},
	"delete_holiday": {"holiday_id"},
}

# === Envelope Validation ===
valid_envelope if {
	input.kind == "tool_call"
	input.action == "execute"
	input.name != ""
}

# === Role Helpers ===

# True when the subject's department is HR (handles both string and array forms)
is_hr if subject.department == "HR"
is_hr if "HR" in subject.department

# === Any-deny Aggregator ===
any_deny if some _ in deny

# === Global DENY Rules ===

# Invalid envelope
deny["Invalid envelope: kind must be tool_call and action must be execute"] if {
	not valid_envelope
}

# === HR-only Tools ===

# Only HR may add a new employee
deny["Only HR may add a new employee"] if {
	input.name == "add_employee"
	not is_hr
}

# Only HR may add a department
deny["Only HR may add or update a department"] if {
	input.name in hr_only_tools
	not is_hr
}

# === Data Integrity: Email Domain ===

# add_employee: email must match org domain when organization is provided
deny["Email domain does not match organization's corporate domain"] if {
	input.name == "add_employee"
	org := args.organization
	org != null
	domain := org_domains[org]
	not endswith(args.email, domain)
}

# update_employee: email must match org domain when both email and organization are provided
deny["Email domain does not match organization's corporate domain"] if {
	input.name == "update_employee"
	org := args.organization
	org != null
	email := args.email
	email != null
	domain := org_domains[org]
	not endswith(email, domain)
}

# === Data Integrity: Salary ===

# add_employee: salary must be positive when provided
deny["Salary must be a positive amount greater than zero"] if {
	input.name == "add_employee"
	salary := args.salary
	salary != null
	salary <= 0
}

# update_employee: salary must be positive when provided
deny["Salary must be a positive amount greater than zero"] if {
	input.name == "update_employee"
	salary := args.salary
	salary != null
	salary <= 0
}

# === Personal-Record: Passport ===

# set_passport: expiry_date must be more than 6 months from today
deny["Passport expiry date must be more than six months from today"] if {
	input.name == "set_passport"
	expiry := args.expiry_date
	expiry != null
	expiry <= six_months_from_today
}

# update_passport: expiry_date must be more than 6 months from today
deny["Passport expiry date must be more than six months from today"] if {
	input.name == "update_passport"
	expiry := args.expiry_date
	expiry != null
	expiry <= six_months_from_today
}

# set_passport: issue_date must be strictly before expiry_date when both provided
deny["Passport issue date must be earlier than expiry date"] if {
	input.name == "set_passport"
	issue := args.issue_date
	expiry := args.expiry_date
	issue != null
	expiry != null
	issue >= expiry
}

# update_passport: issue_date must be strictly before expiry_date when both provided
deny["Passport issue date must be earlier than expiry date"] if {
	input.name == "update_passport"
	issue := args.issue_date
	expiry := args.expiry_date
	issue != null
	expiry != null
	issue >= expiry
}

# === Personal-Record: Visa ===

# set_visa: expiry_date must be more than 6 months from today
deny["Visa expiry date must be more than six months from today"] if {
	input.name == "set_visa"
	expiry := args.expiry_date
	expiry != null
	expiry <= six_months_from_today
}

# update_visa: expiry_date must be more than 6 months from today
deny["Visa expiry date must be more than six months from today"] if {
	input.name == "update_visa"
	expiry := args.expiry_date
	expiry != null
	expiry <= six_months_from_today
}

# set_visa: issue_date must be strictly before expiry_date when both provided
deny["Visa issue date must be earlier than expiry date"] if {
	input.name == "set_visa"
	issue := args.issue_date
	expiry := args.expiry_date
	issue != null
	expiry != null
	issue >= expiry
}

# update_visa: issue_date must be strictly before expiry_date when both provided
deny["Visa issue date must be earlier than expiry date"] if {
	input.name == "update_visa"
	issue := args.issue_date
	expiry := args.expiry_date
	issue != null
	expiry != null
	issue >= expiry
}

# === Time Off: Self-only Creation ===

# An employee may create a time-off request only for themselves
deny["An employee may only create a time-off request for themselves"] if {
	input.name == "create_time_off_request"
	args.user_id != subject.user_id
}

# === Time Off: Request Span ===

# A single time-off request may not span more than 90 consecutive calendar days
deny["A single time-off request may not span more than 90 consecutive calendar days"] if {
	input.name == "create_time_off_request"
	start := args.start_date
	end := args.end_date
	start != null
	end != null
	span_days(start, end) > 90
}

# === Time Off: Status Transitions ===

# Non-HR employees may not set status to Approved or Denied (only HR or managers can approve/deny)
deny["Only HR may set a time-off request status to Approved or Denied"] if {
	input.name == "update_time_off_status"
	not is_hr
	args.status == "Approved"
}

deny["Only HR may set a time-off request status to Approved or Denied"] if {
	input.name == "update_time_off_status"
	not is_hr
	args.status == "Denied"
}

# Only valid statuses are Approved, Denied, Pending
deny["Invalid time-off request status value"] if {
	input.name == "update_time_off_status"
	not args.status in {"Approved", "Denied", "Pending"}
}

# === Own-Data Enforcement ===

# Employees may not update another employee's record unless HR
deny["Only HR may update another employee's record"] if {
	input.name == "update_employee"
	args.user_id != subject.user_id
	not is_hr
}

# Employees may not update another employee's visa unless HR
deny["Only HR may update another employee's visa"] if {
	input.name in {"update_visa", "set_visa"}
	args.user_id != subject.user_id
	not is_hr
}

# Employees may not update another employee's passport unless HR
deny["Only HR may update another employee's passport"] if {
	input.name in {"update_passport", "set_passport"}
	args.user_id != subject.user_id
	not is_hr
}

# Employees may not update another employee's emergency contact unless HR
deny["Only HR may update another employee's emergency contact"] if {
	input.name in {"update_emergency_contact", "set_emergency_contact"}
	args.user_id != subject.user_id
	not is_hr
}

# === Address Country Change ===

# Employees may not change their home address to a different country
deny["Changing home address to a different country is not allowed"] if {
	input.name == "update_employee"
	args.country_code != null
}

# === Helper Functions ===

# Parse a YYYY-MM-DD date string into a comparable integer YYYYMMDD
date_int(s) := result if {
	parts := split(s, "-")
	count(parts) == 3
	result := ((to_number(parts[0]) * 10000) + (to_number(parts[1]) * 100)) + to_number(parts[2])
}

# Days between two YYYY-MM-DD date strings (approximate: ignores leap seconds, uses 365-day years)
span_days(start, end) := days if {
	s := date_int(start)
	e := date_int(end)
	sy := floor(s / 10000)
	sm := floor((s - (sy * 10000)) / 100)
	sd := (s - (sy * 10000)) - (sm * 100)
	ey := floor(e / 10000)
	em := floor((e - (ey * 10000)) / 100)
	ed := (e - (ey * 10000)) - (em * 100)
	days := (((ey - sy) * 365) + ((em - sm) * 30)) + (ed - sd)
}

# === Final ALLOW ===
allow if {
	valid_envelope
	not any_deny
}
