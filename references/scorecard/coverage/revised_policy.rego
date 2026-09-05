package policy

import rego.v1

default allow := false

# === Input Accessors ===
subject := input.extensions.subject

args := object.get(input, "args", {})

subject_roles := object.get(subject, "roles", [])

# === Constants ===

# Tools that expose or mutate compensation data
compensation_tools := {"get_compensation", "display_compensation", "adjust_compensation"}

# Roles permitted to search repositories at all
repo_search_roles := {"engineer", "security"}

# Salary adjustment amount above which manager approval is required
large_adjustment_threshold := 10000

# SSN pattern: NNN-NN-NNNN or NNNNNNNNN (9 bare digits)
ssn_pattern := `\d{3}-\d{2}-\d{4}`

ssn_pattern_bare := `\d{9}`

# === Helpers ===

# True when the caller holds the HR role (via roles array or user_role claim).
caller_has_hr_role if {
	"hr" in subject_roles
}

caller_has_hr_role if {
	subject.user_role == "hr"
}

# True when the caller holds at least one role permitted to search repos.
any_repo_role if {
	some role in repo_search_roles
	role in subject_roles
}

# === DENY Rules ===

# Rule 1: All employees can only access internal repositories.
deny contains msg if {
	input.name == "search_repos"
	args.visibility != "internal"
	not "security" in subject_roles
	msg := sprintf(
		"REPO_INTERNAL_ONLY: visibility=%v is not permitted; caller roles: %v",
		[args.visibility, subject_roles],
	)
}

# Rule 3: Only HR employees can access compensation records.
deny contains msg if {
	compensation_tools[input.name]
	not caller_has_hr_role
	msg := sprintf(
		"COMP_HR_ONLY: tool '%v' requires hr role; caller roles: %v",
		[input.name, subject_roles],
	)
}

# Rule 4: Only employees with view_ssn permission may request SSN data.
deny contains msg if {
	input.name == "get_compensation"
	args.include_ssn == true
	not "view_ssn" in subject.permissions
	msg := sprintf(
		"SSN_VIEW_PERM: include_ssn=true requires view_ssn permission; caller permissions: %v",
		[subject.permissions],
	)
}

# Rule 5: Only engineers and security team members may search repositories.
deny contains msg if {
	input.name == "search_repos"
	not any_repo_role
	msg := sprintf(
		"REPO_ROLE_GATE: search_repos requires engineer or security role; caller roles: %v",
		[subject_roles],
	)
}

# Rule 6: HR may adjust compensation up to $10,000 without approval;
#          amounts greater than $10,000 require has_approval="true".
deny contains msg if {
	input.name == "adjust_compensation"
	args.amount > large_adjustment_threshold
	subject.has_approval != "true"
	msg := sprintf(
		"ADJ_APPROVAL_THRESHOLD: adjustment of %v exceeds %v; has_approval must be 'true'",
		[args.amount, large_adjustment_threshold],
	)
}

# Rule 7: Emails must not contain SSN patterns in subject or body.
deny contains msg if {
	input.name == "send_email"
	regex.match(ssn_pattern, args.subject)
	msg := "EMAIL_SSN_BLOCK: send_email subject contains an SSN pattern"
}

deny contains msg if {
	input.name == "send_email"
	regex.match(ssn_pattern_bare, args.subject)
	msg := "EMAIL_SSN_BLOCK: send_email subject contains an SSN pattern"
}

deny contains msg if {
	input.name == "send_email"
	regex.match(ssn_pattern, args.body)
	msg := "EMAIL_SSN_BLOCK: send_email body contains an SSN pattern"
}

deny contains msg if {
	input.name == "send_email"
	regex.match(ssn_pattern_bare, args.body)
	msg := "EMAIL_SSN_BLOCK: send_email body contains an SSN pattern"
}

# === Final ALLOW ===
allow if {
	count(deny) == 0
}
