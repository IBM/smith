# SPDX-License-Identifier: Apache-2.0
package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})

# === Constants ===
approved_topics := {
	"Artificial intelligence",
	"Cybersecurity and privacy",
	"Software engineering",
}

blocked_keywords := {
	"bioinformatics", "genomics", "clinical trials", "drug discovery",
	"quantum physics", "materials science", "renewable energy",
	"economics", "finance", "marketing", "supply chain",
	"education", "psychology", "sociology", "political science",
	"trade show", "career fair", "startup expo", "hackathon",
}

faculty_limit_cap := 15
phd_limit_cap := 10
session_limit := 5

# === Tool Argument Keys ===
allowed_arg_keys := {"get_events": {"keywords", "topic", "limit"}}

# === Envelope Validation ===
valid_envelope if {
	input.kind == "tool_call"
	input.action == "execute"
	input.name != ""
}

# === DENY Rules ===

# Deny invalid envelope
deny["Invalid request envelope: kind must be tool_call, action must be execute"] if {
	not valid_envelope
}

# Deny missing or empty user_role
deny["Access denied: user_role is missing or empty"] if {
	input.name == "get_events"
	roles := object.get(subject, "user_role", [])
	count(roles) == 0
}

# Deny guest role from using get_events
deny["Access denied: only faculty or phd_student may use get_events"] if {
	input.name == "get_events"
	roles := subject.user_role
	not "faculty" in roles
	not "phd_student" in roles
}

# Deny unapproved topic
deny[msg] if {
	input.name == "get_events"
	topic := args.topic
	not topic in approved_topics
	msg := sprintf("Denied: topic '%v' is not in the approved research areas", [topic])
}

# Deny limit below 1
deny["Denied: limit must be at least 1"] if {
	input.name == "get_events"
	args.limit < 1
}

# Deny limit above absolute maximum (15)
deny["Denied: limit exceeds the absolute maximum of 15"] if {
	input.name == "get_events"
	args.limit > faculty_limit_cap
}

# Deny phd_student exceeding their limit cap (10)
deny["Denied: phd_student limit may not exceed 10"] if {
	input.name == "get_events"
	roles := subject.user_role
	"phd_student" in roles
	not "faculty" in roles
	args.limit > phd_limit_cap
}

# Deny exceeding session search count
deny["Denied: maximum of 5 get_events searches per session reached"] if {
	input.name == "get_events"
	subject.queries_this_session >= session_limit
}

# Deny blocked keywords (case-insensitive)
deny[msg] if {
	input.name == "get_events"
	kw := args.keywords
	some bk in blocked_keywords
	contains(lower(kw), lower(bk))
	msg := sprintf("Denied: keyword '%v' is not permitted for department use", [bk])
}

# Deny phd_student with missing dissertation_area
deny["Denied: phd_student must have a dissertation_area defined"] if {
	input.name == "get_events"
	roles := subject.user_role
	"phd_student" in roles
	not "faculty" in roles
	not subject.dissertation_area
}

# Deny phd_student searching outside their dissertation_area
deny[msg] if {
	input.name == "get_events"
	roles := subject.user_role
	"phd_student" in roles
	not "faculty" in roles
	topic := args.topic
	topic != subject.dissertation_area
	msg := sprintf(
		"Denied: phd_student may only search their dissertation area '%v', not '%v'",
		[subject.dissertation_area, topic],
	)
}

# === any_deny helper ===
any_deny if {
	some _ in deny
}

# === Final ALLOW ===
allow if {
	valid_envelope
	not any_deny
}
