# SPDX-License-Identifier: Apache-2.0
package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})
user_role := object.get(subject, "user_role", [])

# === Constants ===

approved_topics := {
	"Artificial intelligence",
	"Cybersecurity and privacy",
	"Software engineering",
}

disallowed_keywords := {
	"bioinformatics", "genomics", "clinical trials", "drug discovery",
	"quantum physics", "quantum computing", "materials science", "renewable energy",
	"economics", "finance", "marketing", "supply chain",
	"education", "psychology", "sociology", "political science",
	"trade show", "career fair", "startup expo", "hackathon",
}

faculty_limit_cap := 15
phd_limit_cap := 10
session_query_cap := 5

# === Tool Argument Keys ===
allowed_arg_keys := {"get_events": {"keywords", "topic", "limit"}}

# === Envelope Validation ===
valid_envelope if {
	input.kind == "tool_call"
	input.action == "execute"
	input.name == "get_events"
}

# === DENY Rules ===

# Only faculty and phd_student may use get_events
deny["Only faculty and phd_student roles may use get_events"] if {
	input.name == "get_events"
	not "faculty" in user_role
	not "phd_student" in user_role
}

# topic must be one of the three approved research areas
deny["topic must be one of: Artificial intelligence, Cybersecurity and privacy, Software engineering"] if {
	input.name == "get_events"
	not args.topic in approved_topics
}

# limit must be >= 1
deny["limit must be at least 1"] if {
	input.name == "get_events"
	limit := object.get(args, "limit", 10)
	limit < 1
}

# absolute max limit is 15
deny["limit must not exceed 15"] if {
	input.name == "get_events"
	limit := object.get(args, "limit", 10)
	limit > faculty_limit_cap
}

# phd_student limit cap is 10
deny["phd_student limit must not exceed 10"] if {
	input.name == "get_events"
	"phd_student" in user_role
	limit := object.get(args, "limit", 10)
	limit > phd_limit_cap
}

# no more than 5 get_events calls per session
deny["Session query limit of 5 exceeded"] if {
	input.name == "get_events"
	subject.queries_this_session > session_query_cap
}

# disallowed keywords (case-insensitive substring match)
deny[msg] if {
	input.name == "get_events"
	some kw in disallowed_keywords
	contains(lower(args.keywords), lower(kw))
	msg := sprintf("Keyword '%v' is not permitted", [kw])
}

# phd_student topic must match their dissertation_area
deny["phd_student topic must match their dissertation_area"] if {
	input.name == "get_events"
	"phd_student" in user_role
	args.topic != subject.dissertation_area
}

# === Final ALLOW ===
any_deny if {
	some _ in deny
}

allow if {
	valid_envelope
	not any_deny
}
