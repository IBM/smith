package kubectl.policy.allow

import rego.v1

# Default deny - all commands must be explicitly allowed
default allow := false

default requires_approval := false

# =============================================================================
# MAIN DECISION RULES
# =============================================================================

# Allow safe read-only commands
allow if {
	is_safe_command
	not is_forbidden_command
	not is_restricted_command
}

# Allow safe commands in non-production even if they would be restricted
allow if {
	is_safe_command
	not is_forbidden_command
	is_restricted_command
	not is_production_namespace
}

# Requires approval for restricted commands in production
requires_approval if {
	is_restricted_command
	not is_forbidden_command
	is_production_namespace
}

# =============================================================================
# SAFE COMMANDS (Read-Only Operations)
# =============================================================================

is_safe_command if {
	input.command.verb in safe_verbs
	not accesses_sensitive_resource
}

# Allow create/edit/patch in non-production namespaces for SRE work
# (even for critical resources, as long as not sensitive)
is_safe_command if {
	input.command.verb in {"create", "edit", "patch"}
	not is_production_namespace
	not accesses_sensitive_resource
	not is_forbidden_command
}

safe_verbs := {
	"get",
	"describe",
	"logs",
	"top",
	"explain",
	"api-resources",
	"api-versions",
	"cluster-info",
	"version",
}

# =============================================================================
# RESTRICTED COMMANDS (Require Human Approval)
# =============================================================================

is_restricted_command if {
	input.command.verb in restricted_verbs
	not is_forbidden_command
}

is_restricted_command if {
	# Exec commands always require approval
	input.command.verb == "exec"
}

is_restricted_command if {
	# Port-forward requires approval
	input.command.verb == "port-forward"
}

is_restricted_command if {
	# Modifications to production namespaces require approval
	input.command.verb in modification_verbs
	is_production_namespace
}

is_restricted_command if {
	# Any modification to critical resources requires approval
	input.command.verb in modification_verbs
	is_critical_resource
}

restricted_verbs := {
	"apply",
	"patch",
	"edit",
	"replace",
	"scale",
	"rollout",
	"annotate",
	"label",
	"expose",
	"autoscale",
	"set",
	"cp",
	"attach",
	"debug",
}

modification_verbs := {
	"apply",
	"patch",
	"edit",
	"replace",
	"create",
	"scale",
	"rollout",
	"annotate",
	"label",
	"set",
}

# =============================================================================
# FORBIDDEN COMMANDS (Always Denied)
# =============================================================================

is_forbidden_command if {
	# Delete operations are forbidden
	input.command.verb == "delete"
}

is_forbidden_command if {
	# Drain and cordon are forbidden (node operations)
	input.command.verb in {"drain", "cordon", "uncordon", "taint"}
}

is_forbidden_command if {
	# RBAC modifications are forbidden
	is_rbac_resource
	input.command.verb in modification_verbs
}

is_forbidden_command if {
	# Secret access is forbidden
	input.command.resource == "secret"
	input.command.verb != "get"
}

is_forbidden_command if {
	# Secret access is forbidden even with get
	input.command.resource == "secret"
	not is_allowed_secret_namespace
}

is_forbidden_command if {
	# Certificate operations are forbidden
	input.command.verb in {"certificate", "approve", "deny"}
}

is_forbidden_command if {
	# Impersonation is forbidden
	has_impersonation_flag
}

is_forbidden_command if {
	# Privileged exec is forbidden
	input.command.verb == "exec"
	has_privileged_flag
}

is_forbidden_command if {
	# Modifications to kube-system namespace are forbidden
	input.command.namespace == "kube-system"
	input.command.verb in modification_verbs
}

is_forbidden_command if {
	# Any operation on admission controllers is forbidden
	input.command.resource in {
		"validatingwebhookconfiguration",
		"mutatingwebhookconfiguration",
	}
}

is_forbidden_command if {
	# Network policy deletions are forbidden
	input.command.resource == "networkpolicy"
	input.command.verb == "delete"
}

is_forbidden_command if {
	# PodSecurityPolicy modifications are forbidden
	input.command.resource == "podsecuritypolicy"
	input.command.verb in modification_verbs
}

is_forbidden_command if {
	# Commands with piping or command chaining are forbidden
	has_command_chaining
}

is_forbidden_command if {
	# Commands with command substitution are forbidden
	has_command_substitution
}

is_forbidden_command if {
	# Access to sensitive resources even with read operations
	input.command.resource in sensitive_read_resources
}

is_forbidden_command if {
	# Shell injection attempts
	has_shell_injection_pattern
}

is_forbidden_command if {
	# Suspicious command patterns in patch payloads
	has_suspicious_patch_pattern
}

is_forbidden_command if {
	# Excessive resource requests (resource abuse)
	has_excessive_resources
}

is_forbidden_command if {
	# Suspicious image names
	has_suspicious_image_name
}

# =============================================================================
# RESOURCE CLASSIFICATION
# =============================================================================

is_rbac_resource if {
	input.command.resource in {
		"role",
		"rolebinding",
		"clusterrole",
		"clusterrolebinding",
		"serviceaccount",
	}
}

is_critical_resource if {
	input.command.resource in {
		"deployment",
		"statefulset",
		"daemonset",
		"service",
		"ingress",
		"persistentvolume",
		"persistentvolumeclaim",
		"configmap",
		"namespace",
	}
}

accesses_sensitive_resource if {
	input.command.resource in {
		"secret",
		"serviceaccount",
		"role",
		"rolebinding",
		"clusterrole",
		"clusterrolebinding",
	}
}

# =============================================================================
# NAMESPACE CLASSIFICATION
# =============================================================================

is_production_namespace if {
	input.command.namespace in production_namespaces
}

production_namespaces := {
	"production",
	"prod",
	"default",
	"kube-system",
	"kube-public",
	"kube-node-lease",
}

is_allowed_secret_namespace if {
	# Only allow secret access in specific non-production namespaces
	input.command.namespace in {
		"dev",
		"development",
		"test",
		"staging",
	}
}

# =============================================================================
# FLAG DETECTION
# =============================================================================

has_impersonation_flag if {
	some flag in input.command.flags
	flag.name in {"--as", "--as-group", "--as-uid"}
}

has_privileged_flag if {
	some flag in input.command.flags
	flag.name == "--privileged"
	flag.value == "true"
}

has_force_flag if {
	some flag in input.command.flags
	flag.name in {"--force", "-f"}
}

has_all_namespaces_flag if {
	some flag in input.command.flags
	flag.name in {"--all-namespaces", "-A"}
}

# Detect command chaining and piping
has_command_chaining if {
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "|")
}

has_command_chaining if {
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "&&")
}

has_command_chaining if {
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, ";")
}

# Detect command substitution
has_command_substitution if {
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "$(")
}

has_command_substitution if {
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "`")
}

# Detect shell injection patterns
has_shell_injection_pattern if {
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "/etc/passwd")
}

has_shell_injection_pattern if {
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "/etc/shadow")
}

has_shell_injection_pattern if {
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "cat ")
	contains(lower_cmd, "/etc/")
}

# Detect suspicious patterns in patch commands
has_suspicious_patch_pattern if {
	input.command.verb == "patch"
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "evil")
}

has_suspicious_patch_pattern if {
	input.command.verb == "patch"
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "back.sh")
}

has_suspicious_patch_pattern if {
	input.command.verb == "patch"
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "curl")
	contains(lower_cmd, ".sh")
}

has_suspicious_patch_pattern if {
	input.command.verb == "patch"
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "sleep")
	contains(lower_cmd, "command")
}

has_suspicious_patch_pattern if {
	input.command.verb == "patch"
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "/tmp/")
	contains(lower_cmd, ".sh")
}

has_suspicious_patch_pattern if {
	input.command.verb == "patch"

	# Check if resource contains deployment, statefulset, or daemonset
	lower_resource := lower(input.command.resource)
	contains(lower_resource, "deployment")

	# Detect image replacement in patch commands
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "image")
	contains(lower_cmd, "replace")
}

has_suspicious_patch_pattern if {
	input.command.verb == "patch"
	lower_resource := lower(input.command.resource)
	contains(lower_resource, "statefulset")
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "image")
	contains(lower_cmd, "replace")
}

has_suspicious_patch_pattern if {
	input.command.verb == "patch"
	lower_resource := lower(input.command.resource)
	contains(lower_resource, "daemonset")
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "image")
	contains(lower_cmd, "replace")
}

# Detect excessive resource requests (potential resource abuse)
has_excessive_resources if {
	input.command.verb == "patch"
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "resources")

	# Check for excessive CPU (>= 5000 millicores or >= 2000 cores)
	regex.match(`(cpu.*[5-9][0-9]{3,}|cpu.*[1-9][0-9]{4,}|cpu.*2[0-9]{3,})`, lower_cmd)
}

has_excessive_resources if {
	input.command.verb == "patch"
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "resources")

	# Check for excessive memory (>= 500Gi or >= 1Ti)
	regex.match(`(memory.*[5-9][0-9]{2,}gi|memory.*[1-9][0-9]{3,}gi|memory.*[1-9]ti)`, lower_cmd)
}

# Detect suspicious image names
has_suspicious_image_name if {
	input.command.verb in {"create", "patch"}
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "image")

	# Unusual naming pattern: service name with dot notation (e.g., oteldemo.AdService)
	regex.match(`image.*[a-z]+\.[A-Z]`, input.original_command)
}

# Sensitive resources that should not be accessed even with read operations
sensitive_read_resources := {
	"imagepullsecret",
	"imagepullsecrets",
	"networkpolicy",
	"networkpolicies",
	"trace",
	"traces",
	"podsecuritypolicy",
	"podsecuritypolicies",
}

# =============================================================================
# ADDITIONAL SECURITY CHECKS
# =============================================================================

# Prevent commands that try to bypass policies
is_forbidden_command if {
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "ignore")
	contains(lower_cmd, "polic")
}

is_forbidden_command if {
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "bypass")
}

is_forbidden_command if {
	lower_cmd := lower(input.original_command)
	contains(lower_cmd, "override")
	contains(lower_cmd, "polic")
}

# Prevent dangerous combinations
is_forbidden_command if {
	input.command.verb == "delete"
	has_force_flag
}

is_forbidden_command if {
	input.command.verb == "delete"
	has_all_namespaces_flag
}

# =============================================================================
# DECISION OUTPUT
# =============================================================================

decision := {
	"allow": allow,
	"requires_approval": requires_approval,
	"deny": is_forbidden_command,
	"reason": reason,
	"command": input.original_command,
	"verb": input.command.verb,
	"resource": input.command.resource,
	"namespace": input.command.namespace,
}

reason := "Command is safe and read-only" if {
	allow
	is_safe_command
}

reason := "Command requires human approval before execution" if {
	requires_approval
	not is_forbidden_command
}

reason := "Command is forbidden: RBAC modification" if {
	is_forbidden_command
	is_rbac_resource
	input.command.verb in modification_verbs
}

reason := "Command is forbidden: Delete operation" if {
	is_forbidden_command
	input.command.verb == "delete"
}

reason := "Command is forbidden: Secret access" if {
	is_forbidden_command
	input.command.resource == "secret"
}

reason := "Command is forbidden: Impersonation attempt" if {
	is_forbidden_command
	has_impersonation_flag
}

reason := "Command is forbidden: Privileged execution" if {
	is_forbidden_command
	input.command.verb == "exec"
	has_privileged_flag
}

reason := "Command is forbidden: kube-system modification" if {
	is_forbidden_command
	input.command.namespace == "kube-system"
	input.command.verb in modification_verbs
}

reason := "Command is forbidden: Policy bypass attempt" if {
	is_forbidden_command
	not is_rbac_resource
	not input.command.verb == "delete"
	not input.command.resource == "secret"
}

reason := "Command denied by default policy" if {
	not allow
	not requires_approval
	not is_forbidden_command
}
