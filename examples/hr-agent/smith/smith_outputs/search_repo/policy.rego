package mcp.policies

default allow := false

# === Input Accessors ===
subject := input.extensions.subject

args := object.get(input, "args", {})

# === Constants ===
allowed_teams := {"engineer", "security"}

engineer_allowed_visibilities := {"internal"}

security_allowed_visibilities := {"internal", "external", "public"}

# === Tool-Specific DENY Rules ===

# Rule 1: Only engineer or security team members can call search_repos
deny["unauthorized_team_search_repos"] if {
	input.name == "search_repos"
	not allowed_teams & {r | some r in subject.roles} != set()
}

# Rule 2: Engineers can only search internal repos
deny["engineer_external_repo_denied"] if {
	input.name == "search_repos"
	"engineer" in subject.roles
	not "security" in subject.roles
	not args.visibility in engineer_allowed_visibilities
}

# Rule 3: Security team can search internal, external, and public repos
deny["security_invalid_visibility"] if {
	input.name == "search_repos"
	"security" in subject.roles
	not args.visibility in security_allowed_visibilities
}

# === any_deny helper ===
any_deny if {
	some _ in deny
}

# === Final ALLOW ===
allow if not any_deny
