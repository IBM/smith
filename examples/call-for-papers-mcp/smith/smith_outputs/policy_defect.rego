# SPDX-License-Identifier: Apache-2.0
package mcp.policies

default allow := false

allow if {
	not any_deny
}

# === Input Accessors ===

subject := input.extensions.subject

args := object.get(input, "args", {})

# === Constants ===

approved_topics := {
	"Artificial intelligence",
	"Cybersecurity and privacy",
	"Software engineering",
}

allowed_roles := {"faculty", "phd_student"}

disallowed_keywords := {
	"bioinformatics",
	"genomics",
	"clinical trials",
	"drug discovery",
	"quantum physics",
	"materials science",
	"renewable energy",
	"economics",
	"finance",
	"marketing",
	"supply chain",
	"education",
	"psychology",
	"sociology",
	"political science",
	"trade show",
	"career fair",
	"startup expo",
	"hackathon",
}

max_limit_faculty := 15

max_limit_phd := 10

max_queries_per_session := 5

# === Helper: aggregate deny ===

any_deny if {
	some _ in deny
}

# === Global DENY Rules ===

deny[msg] if {
	input.name == "get_events"
	not _has_allowed_role
	msg := "Access denied: only faculty and phd_student roles may use get_events"
}

# === Tool-Specific DENY Rules for get_events ===

deny[msg] if {
	input.name == "get_events"
	not args.topic in approved_topics
	msg := sprintf("Denied: topic '%s' is not an approved research area", [args.topic])
}

deny[msg] if {
	input.name == "get_events"
	args.limit < 1
	msg := "Denied: limit must be at least 1"
}

deny[msg] if {
	input.name == "get_events"
	_is_faculty
	args.limit > max_limit_faculty
	msg := sprintf("Denied: faculty limit %d exceeds maximum of %d", [args.limit, max_limit_faculty])
}

deny[msg] if {
	input.name == "get_events"
	_is_phd_student
	args.limit > max_limit_phd
	msg := sprintf("Denied: phd_student limit %d exceeds maximum of %d", [args.limit, max_limit_phd])
}

deny[msg] if {
	input.name == "get_events"
	_is_phd_student
	args.topic != subject.dissertation_area
	msg := sprintf(
		"Denied: phd_student dissertation_area is '%s' but topic is '%s'",
		[subject.dissertation_area, args.topic],
	)
}

deny[msg] if {
	input.name == "get_events"
	subject.queries_this_session >= max_queries_per_session
	msg := sprintf(
		"Denied: session query count %d exceeds maximum of %d",
		[subject.queries_this_session, max_queries_per_session],
	)
}

deny[msg] if {
    input.name == "get_events"
    not args.topic in approved_topics
    msg := sprintf("Denied: unapproved topic '%s' requested", [args.topic])
}

deny[msg] if {
	input.name == "get_events"
	subject.account_status == "suspended"
	msg := "Denied: account is currently suspended"
}

# === Role Helpers ===

_has_allowed_role if {
	some role in subject.user_role
	role in allowed_roles
}

_is_faculty if {
	some role in subject.user_role
	role == "faculty"
}

_is_phd_student if {
	some role in subject.user_role
	role == "phd_student"
}

_check_active_enrollment if {
    subject.account_type == "provisional"
    subject.enrollment_status == "active"
}
