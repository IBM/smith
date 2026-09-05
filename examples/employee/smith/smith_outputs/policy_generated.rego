# SPDX-License-Identifier: Apache-2.0
package mcp.policies

import rego.v1

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "args", {})

# === Constants ===

hr_only_tools := {
	"add_employee",
	"add_department",
	"update_department",
	"add_holiday",
	"delete_holiday",
	"set_leave_allotment",
}

personal_record_tools := {
	"get_passport",
	"set_passport",
	"update_passport",
	"get_visa",
	"set_visa",
	"update_visa",
	"get_emergency_contact",
	"set_emergency_contact",
	"update_emergency_contact",
	"get_bank_account",
	"set_bank_account",
	"update_bank_account",
}

passport_visa_tools := {
	"set_passport",
	"update_passport",
	"set_visa",
	"update_visa",
}

employee_record_tools := {"get_employee", "update_employee"}

leave_view_tools := {
	"get_leave_allotments",
	"list_time_off_requests",
	"get_leave_balance",
	"get_time_off_request",
}

org_email_domains := {
	"IBM Corporation": "ibm.com",
	"Red Hat": "redhat.com",
	"Kyndryl": "kyndryl.com",
}

# === Helper: email domain ===
email_domain(email) := domain if {
	parts := split(email, "@")
	count(parts) == 2
	domain := parts[1]
}

# === Helper: days between two YYYY-MM-DD strings ===
# Computes naive day difference via time.parse_rfc3339_ns — dates are treated as midnight UTC
day_diff_days(start_str, end_str) := diff if {
	start_ns := time.parse_rfc3339_ns(concat("", [start_str, "T00:00:00Z"]))
	end_ns := time.parse_rfc3339_ns(concat("", [end_str, "T00:00:00Z"]))
	diff := (end_ns - start_ns) / (((24 * 60) * 60) * 1000000000)
}

# === DENY Rules ===

# R1 — HR-only tools: only HR may invoke these
deny contains msg if {
	input.name in hr_only_tools
	subject.department != "HR"
	msg := sprintf("HR_ONLY: tool '%v' requires HR department", [input.name])
}

# R2 — Personal-record ownership: non-HR must access own records only
deny contains msg if {
	input.name in personal_record_tools
	subject.department != "HR"
	args.user_id != subject.user_id
	msg := "OWNERSHIP: personal-record access requires own user_id or HR department"
}

# R3 — Employee-record ownership: non-HR must access own record only
deny contains msg if {
	input.name in employee_record_tools
	subject.department != "HR"
	args.user_id != subject.user_id
	msg := "OWNERSHIP: employee-record access requires own user_id or HR department"
}

# R4 — Salary must be positive
deny contains msg if {
	input.name in {"add_employee", "update_employee"}
	salary := args.salary
	salary != null
	salary <= 0
	msg := "SALARY_INVALID: salary must be greater than zero"
}

# R5 — Email domain must match organization (when both are present in same call)
deny contains msg if {
	input.name in {"add_employee", "update_employee"}
	email := args.email
	email != null
	org := args.organization
	org != null
	expected_domain := org_email_domains[org]
	email_domain(email) != expected_domain
	msg := sprintf("EMAIL_DOMAIN: email domain does not match organization (expected @%v)", [expected_domain])
}

# R6 — Time-off request only for self
deny contains msg if {
	input.name == "create_time_off_request"
	args.user_id != subject.user_id
	msg := "TIMEOFF_OWNERSHIP: time-off requests may only be created for the requesting user"
}

# R7 — Time-off span must not exceed 90 consecutive calendar days
deny contains msg if {
	input.name == "create_time_off_request"
	start_str := args.start_date
	end_str := args.end_date
	start_str != null
	end_str != null
	day_diff_days(start_str, end_str) > 90
	msg := "TIMEOFF_SPAN: time-off request may not span more than 90 consecutive calendar days"
}

# R8 — Passport / visa: issue date must be strictly before expiry date
deny contains msg if {
	input.name in passport_visa_tools
	issue := args.issue_date
	expiry := args.expiry_date
	issue != null
	expiry != null
	issue >= expiry
	msg := "DATE_ORDER: issue date must be strictly before expiry date"
}

# R9 — Leave-view tools: non-HR must view own records only
deny contains msg if {
	input.name in leave_view_tools
	subject.department != "HR"
	args.user_id != subject.user_id
	msg := "LEAVE_OWNERSHIP: leave records may only be viewed by the employee or HR"
}

# R10 — Time-off status update: only HR may set Approved or Denied
deny contains msg if {
	input.name == "update_time_off_status"
	subject.department != "HR"
	args.status in {"Approved", "Denied"}
	msg := "TIMEOFF_STATUS: only HR may approve or deny time-off requests"
}

# === Final ALLOW ===
allow if {
	count(deny) == 0
}
