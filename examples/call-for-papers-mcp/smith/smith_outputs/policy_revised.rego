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

phd_student_limit_cap := 10

absolute_limit_cap := 15

max_session_queries := 5

default_limit := 10

# === Global DENY/ALLOW Rules ===

any_deny if {
	count(deny) > 0
}

# === Tool-Specific DENY/ALLOW Rules ===

# Only faculty and phd_student may use get_events; guest cannot.
deny[msg] if {
	input.name == "get_events"
	roles := object.get(subject, "user_role", [])
	not "faculty" in roles
	not "phd_student" in roles
	msg := "get_events is restricted to faculty and phd_student roles; guest is not permitted"
}

# topic must be exactly one of the three approved research areas.
deny[msg] if {
	input.name == "get_events"
	topic := object.get(args, "topic", "")
	not topic in approved_topics
	msg := sprintf("topic '%v' is not one of the approved research areas", [topic])
}

# limit must be at least 1.
deny[msg] if {
	input.name == "get_events"
	limit := object.get(args, "limit", default_limit)
	limit < 1
	msg := sprintf("limit %v is below the minimum of 1", [limit])
}

# limit must not exceed the absolute maximum of 15.
deny[msg] if {
	input.name == "get_events"
	limit := object.get(args, "limit", default_limit)
	limit > absolute_limit_cap
	msg := sprintf("limit %v exceeds the absolute maximum of %v", [limit, absolute_limit_cap])
}

# phd_student limit must not exceed the phd_student cap of 10.
deny[msg] if {
	input.name == "get_events"
	limit := object.get(args, "limit", default_limit)
	roles := object.get(subject, "user_role", [])
	"phd_student" in roles
	limit > phd_student_limit_cap
	msg := sprintf("limit %v exceeds the phd_student cap of %v", [limit, phd_student_limit_cap])
}

# keywords must not contain any disallowed term, case-insensitively.
deny[msg] if {
	input.name == "get_events"
	keywords := lower(object.get(args, "keywords", ""))
	some term in disallowed_keywords
	contains(keywords, term)
	msg := sprintf("keywords contains disallowed term '%v'", [term])
}

# no more than 5 get_events searches in a single conversation session.
deny[msg] if {
	input.name == "get_events"
	queries := object.get(subject, "queries_this_session", 0)
	queries > max_session_queries
	msg := sprintf(
		"session has already performed %v get_events searches, exceeding the cap of %v",
		[queries, max_session_queries],
	)
}

# PhD students are scoped to their own dissertation_area, not all approved areas.
deny[msg] if {
	input.name == "get_events"
	roles := object.get(subject, "user_role", [])
	"phd_student" in roles
	not "faculty" in roles
	topic := object.get(args, "topic", "")
	dissertation_area := object.get(subject, "dissertation_area", "")
	topic != dissertation_area
	msg := sprintf("phd_student topic '%v' must match their own dissertation_area '%v'", [topic, dissertation_area])
}
