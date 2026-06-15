package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject
args := object.get(input, "arguments", {})

# === Constants ===

# Approved research areas for the department
approved_topics := {
	"Artificial intelligence",
	"Cybersecurity and privacy",
	"Software engineering",
}

# Disallowed keywords that should not appear in topic searches
disallowed_keywords := {
	"bioinformatics", "genomics", "clinical trials", "drug discovery",
	"quantum physics", "materials science", "renewable energy",
	"economics", "finance", "marketing", "supply chain",
	"education", "psychology", "sociology", "political science",
	"trade show", "career fair", "startup expo", "hackathon",
}

# Roles allowed to use get_events tool
allowed_roles := {"faculty", "phd_student"}

# Maximum limit values by role
max_limit_by_role := {
	"faculty": 15,
	"phd_student": 10,
}

# Absolute maximum limit regardless of role
absolute_max_limit := 15

# === Tool Argument Keys ===
allowed_arg_keys := {"get_events": {"keywords", "topic", "limit"}}

# === Validation Helpers ===

# Check if input envelope is valid
valid_envelope if {
	input.kind == "tool_call"
	input.action == "execute"
	is_string(input.name)
}

# Check if tool name is recognized
valid_tool_name if {
	input.name in object.keys(allowed_arg_keys)
}

# Check if all argument keys are allowed for this tool
valid_arg_keys if {
	tool_name := input.name
	expected_keys := allowed_arg_keys[tool_name]
	actual_keys := object.keys(args)
	extra_keys := {k | some k in actual_keys; not k in expected_keys}
	count(extra_keys) == 0
}

# === Global DENY Rules ===

# Deny if user role is not authorized to use get_events
deny[msg] if {
	input.name == "get_events"
	user_roles := object.get(subject, "user_role", [])
	count({r | r := user_roles[_]; r in allowed_roles}) == 0
	msg := "Access denied: Only faculty and phd_student roles can use get_events tool"
}

# === Tool-Specific DENY Rules for get_events ===

# Deny if topic is not one of the approved research areas
deny[msg] if {
	input.name == "get_events"
	topic := object.get(args, "topic", "")
	not topic in approved_topics
	msg := sprintf("Topic '%s' is not approved. Must be one of: %v", [topic, approved_topics])
}

# Deny if topic contains disallowed keywords
deny[msg] if {
	input.name == "get_events"
	topic := lower(object.get(args, "topic", ""))
	some keyword in disallowed_keywords
	contains(topic, lower(keyword))
	msg := sprintf("Topic contains disallowed keyword '%s'", [keyword])
}

# Deny if keywords argument contains disallowed keywords
deny[msg] if {
	input.name == "get_events"
	keywords := lower(object.get(args, "keywords", ""))
	some keyword in disallowed_keywords
	contains(keywords, lower(keyword))
	msg := sprintf("Keywords argument contains disallowed keyword '%s'", [keyword])
}

# Deny if limit exceeds absolute maximum
deny[msg] if {
	input.name == "get_events"
	limit := object.get(args, "limit", 10)
	limit > absolute_max_limit
	msg := sprintf("Limit %d exceeds absolute maximum of %d", [limit, absolute_max_limit])
}

# === Collect All Denials ===
any_deny if {
	count(deny) > 0
}

# === Final ALLOW ===
allow if {
	valid_envelope
	valid_tool_name
	valid_arg_keys
	not any_deny
}
