package mcp.policies

# === Input Accessors ===
subject := input.extensions.subject

args := object.get(input, "args", {})

# === Constants ===
# SSN patterns: various separators (dash, space, dot, slash) and 9 raw digits
ssn_pattern_dashes := `\d{3}-\d{2}-\d{4}`

ssn_pattern_spaces := `\d{3} \d{2} \d{4}`

ssn_pattern_dots := `\d{3}\.\d{2}\.\d{4}`

ssn_pattern_slashes := `\d{3}/\d{2}/\d{4}`

ssn_pattern_digits := `\d{9}`

# SSN keyword: word "SSN" or "social security number" near digits
ssn_keyword_pattern := `(?i)(ssn|social\s+security\s*(number)?)\b`

# === Helper: field contains SSN in any known format ===
field_contains_ssn(field) if regex.match(ssn_pattern_dashes, field)

field_contains_ssn(field) if regex.match(ssn_pattern_spaces, field)

field_contains_ssn(field) if regex.match(ssn_pattern_dots, field)

field_contains_ssn(field) if regex.match(ssn_pattern_slashes, field)

field_contains_ssn(field) if regex.match(ssn_pattern_digits, field)

field_contains_ssn(field) if regex.match(ssn_keyword_pattern, field)

# === Tool-Specific DENY Rules ===

# Deny send_email if the subject field contains an SSN (any format)
deny contains msg if {
	input.name == "send_email"
	field_contains_ssn(args.subject)
	msg := "send_email blocked: email subject contains an SSN"
}

# Deny send_email if the body field contains an SSN (any format)
deny contains msg if {
	input.name == "send_email"
	field_contains_ssn(args.body)
	msg := "send_email blocked: email body contains an SSN"
}

# === Final ALLOW ===
any_deny if {
	some _ in deny
}

default allow := false

allow if {
	not any_deny
}
