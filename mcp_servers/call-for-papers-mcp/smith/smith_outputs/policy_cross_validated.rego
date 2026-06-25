package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})
tool_name := input.name

# === Constants ===

# Approved research topics for the department
approved_topics := {
	"Artificial intelligence",
	"Cybersecurity and privacy",
	"Software engineering",
}

# Disallowed keywords (case-insensitive matching)
disallowed_keywords := {
	"bioinformatics", "genomics", "clinical trials", "drug discovery",
	"quantum physics", "materials science", "renewable energy",
	"economics", "finance", "marketing", "supply chain",
	"education", "psychology", "sociology", "political science",
	"trade show", "career fair", "startup expo", "hackathon",
}

# Role-based limit caps
role_limit_caps := {
	"faculty": 15,
	"phd_student": 10,
}

# Roles allowed to use get_events
allowed_roles := {"faculty", "phd_student"}

# === Tool Argument Keys ===
allowed_arg_keys := {"get_events": {"keywords", "topic", "limit"}}

# === Helper Functions ===

# Check if any disallowed keyword appears in the keywords string (case-insensitive)
contains_disallowed_keyword(keywords_str) if {
	some disallowed in disallowed_keywords
	lower_keywords := lower(keywords_str)
	lower_disallowed := lower(disallowed)
	contains(lower_keywords, lower_disallowed)
}

# Get user's primary role (first role in the list)
user_role := subject.user_role[0] if {
	count(subject.user_role) > 0
} else := ""

# Get user's dissertation area
dissertation_area := subject.dissertation_area if {
	subject.dissertation_area
} else := ""

# Get queries this session
queries_this_session := subject.queries_this_session if {
	subject.queries_this_session
} else := 0

# === Validation Rules ===

# Validate envelope structure
valid_envelope if {
	input.kind == "tool_call"
	input.action == "execute"
	input.name
}

# === Global DENY Rules ===

# Deny if tool is not get_events (only tool we support)
deny[msg] if {
	tool_name != "get_events"
	msg := sprintf("Tool '%s' is not supported. Only 'get_events' is allowed.", [tool_name])
}

# === Tool-Specific DENY Rules for get_events ===

# Rule 1: Only faculty and phd_student may use get_events
deny[msg] if {
	tool_name == "get_events"
	not user_role in allowed_roles
	msg := sprintf("User role '%s' is not authorized to use get_events. Only 'faculty' and 'phd_student' are allowed.", [user_role])
}

# Rule 2: Topic must be one of the three approved research areas
deny[msg] if {
	tool_name == "get_events"
	topic := args.topic
	not topic in approved_topics
	msg := sprintf("Topic '%s' is not approved. Must be exactly one of: 'Artificial intelligence', 'Cybersecurity and privacy', 'Software engineering'.", [topic])
}

# Rule 3: Limit must be at least 1
deny[msg] if {
	tool_name == "get_events"
	limit := args.limit
	limit < 1
	msg := sprintf("Limit %d is invalid. Must be at least 1.", [limit])
}

# Rule 4: Limit must not exceed role-specific cap
deny[msg] if {
	tool_name == "get_events"
	limit := args.limit
	cap := role_limit_caps[user_role]
	limit > cap
	msg := sprintf("Limit %d exceeds the maximum of %d for role '%s'.", [limit, cap, user_role])
}

# Rule 5: Limit must not exceed absolute maximum of 15
deny[msg] if {
	tool_name == "get_events"
	limit := args.limit
	limit > 15
	msg := sprintf("Limit %d exceeds the absolute maximum of 15 per request.", [limit])
}

# Rule 6: Keywords must not contain disallowed terms
deny[msg] if {
	tool_name == "get_events"
	keywords := args.keywords
	contains_disallowed_keyword(keywords)
	msg := sprintf("Keywords '%s' contain disallowed terms. Prohibited keywords include: bioinformatics, genomics, clinical trials, drug discovery, quantum physics, materials science, renewable energy, economics, finance, marketing, supply chain, education, psychology, sociology, political science, trade show, career fair, startup expo, hackathon.", [keywords])
}

# Rule 7: PhD students must search within their dissertation area only
deny[msg] if {
	tool_name == "get_events"
	user_role == "phd_student"
	topic := args.topic
	dissertation_area != ""
	topic != dissertation_area
	msg := sprintf("PhD student must search within their dissertation area '%s'. Requested topic '%s' is not allowed.", [dissertation_area, topic])
}

# Rule 8: No more than 5 queries per session
deny[msg] if {
	tool_name == "get_events"
	queries_this_session > 5
	msg := sprintf("Query limit exceeded. Maximum 5 queries per session allowed. Current count: %d.", [queries_this_session])
}

# === Collect All Denials ===
any_deny if {
	count(deny) > 0
}

# === Final ALLOW ===
allow if {
	valid_envelope
	not any_deny
}
