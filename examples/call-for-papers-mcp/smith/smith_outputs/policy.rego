# SPDX-License-Identifier: Apache-2.0

package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject

args := object.get(input, "args", {})

# === Constants ===

approved_topics := {
	"Artificial intelligence",
	"Cybersecurity and privacy",
	"Software engineering",
}

permitted_roles := {"faculty", "phd_student"}

blocked_keywords := {
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

# === Tool-Specific DENY Rules ===

# Rule 1: Only faculty and phd_student may call get_events
deny contains msg if {
	input.name == "get_events"
	roles := object.get(subject, "user_role", [])
	count({r | r := roles[_]; permitted_roles[r]}) == 0
	msg := "ROLE_BLOCKED: only faculty or phd_student may call get_events"
}

# Rule 2: topic must be exactly one of the three approved research areas
deny contains msg if {
	input.name == "get_events"
	topic := object.get(args, "topic", "")
	not approved_topics[topic]
	msg := sprintf("TOPIC_BLOCKED: topic '%v' is not an approved research area", [topic])
}

# Rule 3: phd_student may only search within their own dissertation_area
deny contains msg if {
	input.name == "get_events"
	roles := object.get(subject, "user_role", [])
	"phd_student" in roles
	topic := object.get(args, "topic", "")
	dissertation_area := object.get(subject, "dissertation_area", "")
	topic != dissertation_area
	msg := sprintf(
		"TOPIC_ROLE_BLOCKED: phd_student topic '%v' does not match dissertation_area '%v'",
		[topic, dissertation_area],
	)
}

# Rule 4a: limit must be at least 1
deny contains msg if {
	input.name == "get_events"
	limit := object.get(args, "limit", 10)
	limit < 1
	msg := sprintf("LIMIT_EXCEEDED: limit %v is below the minimum of 1", [limit])
}

# Rule 4b: limit must not exceed 15 (absolute cap for all roles)
deny contains msg if {
	input.name == "get_events"
	limit := object.get(args, "limit", 10)
	limit > 15
	msg := sprintf("LIMIT_EXCEEDED: limit %v exceeds the absolute maximum of 15", [limit])
}

# Rule 5: phd_student limit cap is 10 (faculty role takes precedence)
deny contains msg if {
	input.name == "get_events"
	roles := object.get(subject, "user_role", [])
	"phd_student" in roles
	not "faculty" in roles
	limit := object.get(args, "limit", 10)
	limit > 10
	msg := sprintf("LIMIT_ROLE_EXCEEDED: phd_student limit %v exceeds the maximum of 10", [limit])
}

# Rule 6: keywords must not contain any blocked substring (case-insensitive)
deny contains msg if {
	input.name == "get_events"
	keywords := lower(object.get(args, "keywords", ""))
	some blocked in blocked_keywords
	contains(keywords, blocked)
	msg := sprintf("KEYWORD_BLOCKED: keywords contain disallowed term '%v'", [blocked])
}

# Rule 7: session cap — deny when caller reports 5 or more get_events calls this session
deny contains msg if {
	input.name == "get_events"
	queries := object.get(subject, "queries_this_session", 0)
	queries >= 5
	msg := sprintf("SESSION_LIMIT_EXCEEDED: %v get_events calls already made this session (max 5)", [queries])
}

# === Aggregation ===

any_deny if {
	some _ in deny
}

allow if {
	not any_deny
}
