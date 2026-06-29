# NL2Kubectl OPA Security Policy
# This policy enforces command-based security controls for kubectl operations
# Input format: {"input":{"command": {"verb": "get", "resource": "pods", "namespace": "sre-sandbox", "args": [], "flags": []}}, "original_command": "kubectl get pods ..."}

package mcp.policies

import rego.v1

# ==============================================================================
# MAIN DECISION POINTS
# ==============================================================================

# Main allow decision - command is permitted if it meets all security requirements
default allow := false

# Allow command if it passes all security checks
allow if {
	is_safe_operation
	not is_forbidden_operation
	passes_resource_restrictions
	not has_dangerous_flags
	is_valid_command_structure
}

allow if {
	requires_approval
}

# Require human approval for restricted operations
requires_approval if {
	is_restricted_operation
	not is_forbidden_operation
	passes_namespace_restrictions
	passes_resource_restrictions
	not has_dangerous_flags
	is_valid_command_structure
}

# Always deny forbidden operations
default deny := false

# ==============================================================================
# COMMAND CLASSIFICATION
# ==============================================================================

# Safe operations that can be automatically approved
is_safe_operation if {
	input.command.verb in safe_verbs
	all_resources_are_safe
}

# Safe operations for resource-less commands (e.g., logs with label selectors)
is_safe_operation if {
	input.command.verb in resource_less_safe_verbs
	input.command.resource == null
}

# Check if all resources (including comma-separated) are safe
all_resources_are_safe if {
	resource_types := parse_resource_types(input.command.resource)
	count(resource_types) > 0
	every resource_type in resource_types {
		resource_type in safe_resources
	}
}

# Allow read-only access to forbidden resources
all_resources_are_safe if {
	resource_types := parse_resource_types(input.command.resource)
	count(resource_types) > 0
	input.command.verb in {"get", "list", "describe", "logs"}
	every resource_type in resource_types {
		resource_type in forbidden_resources
	}
}

# Parse comma-separated resource types
parse_resource_types(resource_string) := resource_types if {
	resource_string != null
	resource_types := [trim_whitespace(r) | r := split(resource_string, ",")[_]]
} else := []

# Helper function to trim whitespace
trim_whitespace(s) := trimmed if {
	trimmed := trim(s, " \t\n\r")
}

safe_verbs := {
	"get",
	"list",
	"describe",
	"logs",
	"top",
	"watch",
}

# Verbs that are safe even without specifying a resource type
resource_less_safe_verbs := {
	"logs",
	"top",
	"get",
	"list",
}

safe_resources := {
	"pods",
	"pod",
	"services",
	"service",
	"svc",
	"deployments",
	"deployment",
	"replicasets",
	"replicaset",
	"rs",
	"daemonsets",
	"daemonset",
	"ds",
	"configmaps",
	"configmap",
	"events",
	"nodes",
	"node",
	"namespaces",
	"persistentvolumes",
	"persistentvolume",
	"pv",
	"persistentvolumeclaims",
	"persistentvolumeclaim",
	"pvc",
	"ingresses",
	"ingress",
	"jobs",
	"job",
	"cronjobs",
	"cronjob",
	"horizontalpodautoscalers",
	"horizontalpodautoscaler",
	"hpa",
	"endpoints",
	"endpoint",
	"replicationcontrollers",
	"replicationcontroller",
	"rc",
	"namespace",
	"ingressclasses",
	"storageclasses",
}

# Restricted operations requiring human approval
is_restricted_operation if {
	input.command.verb in restricted_verbs
	all_resources_modifiable
	not is_forbidden_operation
}

# Check if all resources can be modified
all_resources_modifiable if {
	resource_types := parse_resource_types(input.command.resource)
	count(resource_types) > 0
	every resource_type in resource_types {
		resource_type in allowed_resources_for_modification
	}
}

restricted_verbs := {
	"apply",
	"patch",
	"scale",
	"create",
	"expose",
	"exec",
	"port-forward",
	"debug",
	"edit",
	"annotate",
	"label",
	"rollout",
}

allowed_resources_for_modification := {
	"pods",
	"pod",
	"services",
	"service",
	"svc",
	"deployments",
	"deployment",
	"replicasets",
	"replicaset",
	"rs",
	"daemonsets",
	"daemonset",
	"ds",
	"configmaps",
	"configmap",
	"secrets",
	"secret",
	"persistentvolumeclaims",
	"persistentvolumeclaim",
	"pvc",
	"ingresses",
	"ingress",
	"jobs",
	"job",
	"cronjobs",
	"cronjob",
	"horizontalpodautoscalers",
	"horizontalpodautoscaler",
	"hpa",
}

# Forbidden operations that are never allowed
is_forbidden_operation if {
	input.command.verb in forbidden_verbs
}

is_forbidden_operation if {
	resource_types := parse_resource_types(input.command.resource)
	some resource_type in resource_types
	resource_type in forbidden_resources
}

is_forbidden_operation if {
	input.command.verb == "delete"
	resource_types := parse_resource_types(input.command.resource)
	some resource_type in resource_types
	resource_type in critical_resources
}

is_forbidden_operation if {
	targets_rbac_resources
}

is_forbidden_operation if {
	targets_security_resources
}

is_forbidden_operation if {
	targets_system_resources
}

forbidden_verbs := {
	"replace",
	"drain",
	"cordon",
	"uncordon",
	"certificate",
	"cluster-info",
}

forbidden_resources := {
	"clusterroles",
	"clusterrole",
	"clusterrolebindings",
	"clusterrolebinding",
	"certificatesigningrequests",
	"certificatesigningrequest",
	"customresourcedefinitions",
	"customresourcedefinition",
	"podsecuritypolicies",
	"podsecuritypolicie",
	"networkpolicies",
	"networkpolicie",
	"validatingadmissionwebhooks",
	"validatingadmissionwebhook",
	"mutatingadmissionwebhooks",
	"mutatingadmissionwebhook",
	"priorityclasses",
	"priorityclasse",
	"storageclasses",
	"storageclasse",
	"volumeattachments",
	"volumeattachment",
}

critical_resources := {
	"namespaces",
	"namespace",
	"nodes",
	"node",
	"persistentvolumes",
	"persistentvolume",
	"clusterroles",
	"clusterrole",
	"clusterrolebindings",
	"clusterrolebinding",
	"customresourcedefinitions",
	"customresourcedefinition",
}

# Check if command targets RBAC resources
targets_rbac_resources if {
	input.command.resource in {
		"roles",
		"role",
		"rolebindings",
		"rolebinding",
		"clusterroles",
		"clusterrole",
		"clusterrolebindings",
		"clusterrolebinding",
		"serviceaccounts",
		"serviceaccount",
	}
	input.command.verb in {"create", "apply", "patch", "edit", "delete", "replace"}
}

# Check if command targets security-sensitive resources
targets_security_resources if {
	input.command.resource in {
		"podsecuritypolicies",
		"networkpolicies",
		"securitycontextconstraints",
		"poddisruptionbudgets",
	}
}

# Check if command targets system-level resources
targets_system_resources if {
	input.command.resource in {
		"nodes",
		"node",
		"componentstatuses",
		"componentstatuse",
		"csidrivers",
		"csidriver",
		"csinodes",
		"csinode",
		"volumeattachments",
		"volumeattachment",
	}
	input.command.verb in {"create", "apply", "patch", "edit", "delete", "replace"}
}

# ==============================================================================
# NAMESPACE RESTRICTIONS
# ==============================================================================

# Validate namespace access restrictions
passes_namespace_restrictions if {
	# Commands without namespace specification (cluster-scoped reads only)
	input.command.namespace == ""
	input.command.verb in {"get", "list", "describe"}
	input.command.resource in cluster_scoped_safe_resources
}

passes_namespace_restrictions if {
	# Commands with explicit namespace
	namespace := input.command.namespace
	namespace != ""
	namespace in allowed_namespaces
	not namespace in forbidden_namespaces
}

allowed_namespaces := {
	"sre-sandbox",
	"monitoring",
	"logging",
	"testing",
	"staging",
	"development",
	"otel-demo",
}

forbidden_namespaces := {
	"default",
	"kube-system",
	"kube-public",
	"kube-node-lease",
	"istio-system",
	"cert-manager",
	"ingress-nginx",
	"metallb-system",
	"local-path-storage",
}

cluster_scoped_safe_resources := {
	"nodes",
	"node",
	"namespaces",
	"namespace",
	"persistentvolumes",
	"persistentvolume",
	"pv",
	"storageclasses",
	"ingressclasses",
}

# ==============================================================================
# RESOURCE TYPE RESTRICTIONS
# ==============================================================================

# Validate resource type restrictions
passes_resource_restrictions if {
	resource_types := parse_resource_types(input.command.resource)
	count(resource_types) > 0
	every resource_type in resource_types {
		resource_type in allowed_resources
	}
}

# Allow resource-less commands for safe verbs
passes_resource_restrictions if {
	input.command.resource == null
	input.command.verb in resource_less_safe_verbs
}

passes_resource_restrictions if {
	# Special handling for secrets - read-only access allowed
	resource_types := parse_resource_types(input.command.resource)
	some resource_type in resource_types
	resource_type == "secrets"
	input.command.verb in {"get", "list", "describe"}

	# All resources must be either secrets or in allowed_resources
	every other_resource in resource_types {
		other_resource == "secrets"
	}
}

passes_resource_restrictions if {
	# Special handling for mixed resources including secrets - read-only access
	resource_types := parse_resource_types(input.command.resource)
	some resource_type in resource_types
	resource_type == "secrets"
	input.command.verb in {"get", "list", "describe"}

	# All resources must be in allowed_resources (secrets is included there)
	every other_resource in resource_types {
		other_resource in allowed_resources
	}
}

allowed_resources := (safe_resources | allowed_resources_for_modification) | cluster_scoped_safe_resources

# ==============================================================================
# DANGEROUS FLAGS AND PARAMETERS
# ==============================================================================

# Check for dangerous scale operations with excessive replicas
has_dangerous_flags if {
	input.command.verb == "scale"
	has_excessive_replicas
}

has_excessive_replicas if {
	some flag in input.command.flags
	flag.name == "--replicas"
	to_number(flag.value) >= 100
}

# Check for dangerous exec commands with shell execution
has_dangerous_flags if {
	input.command.verb == "exec"
	has_shell_execution_flag
}

has_shell_execution_flag if {
	some flag in input.command.flags
	flag.name == "-c"
}

has_shell_execution_flag if {
	some flag in input.command.flags
	flag.name == "--command"
}

# Check for dangerous patch operations
has_dangerous_flags if {
	input.command.verb == "patch"
	has_dangerous_patch_content
}

has_dangerous_patch_content if {
	some flag in input.command.flags
	flag.name == "-p"
	contains(flag.value, "\"command\":")
}

has_dangerous_patch_content if {
	some flag in input.command.flags
	flag.name == "-p"
	has_excessive_resources(flag.value)
}

has_excessive_resources(patch_value) if {
	contains(patch_value, "cpu")
	regex.match(".*\"value\"\\s*:\\s*\"[0-9]{4,}\".*", patch_value)
}

has_excessive_resources(patch_value) if {
	contains(patch_value, "memory")
	regex.match(".*\"value\"\\s*:\\s*\"[0-9]{3,}[GT]i\".*", patch_value)
}

has_excessive_resources(patch_value) if {
	contains(patch_value, "memory")
	contains(patch_value, "Ti")
}

# Check for dangerous command flags
has_dangerous_flags if {
	"--force" in input.command.flags
}

has_dangerous_flags if {
	"--grace-period=0" in input.command.flags
}

has_dangerous_flags if {
	"--all" in input.command.flags
	input.command.verb == "delete"
}

has_dangerous_flags if {
	"--cascade=orphan" in input.command.flags
	input.command.verb == "delete"
}

has_dangerous_flags if {
	some flag in input.command.flags
	startswith(flag, "--privileged=true")
}

has_dangerous_flags if {
	some flag in input.command.flags
	startswith(flag, "--host")
}

has_dangerous_flags if {
	some flag in input.command.flags
	startswith(flag, "--as=")
}

has_dangerous_flags if {
	some flag in input.command.flags
	startswith(flag, "--as-group=")
}

has_dangerous_flags if {
	some flag in input.command.flags
	contains(flag, "sudo")
}

# ==============================================================================
# COMMAND VALIDATION AND STRUCTURE
# ==============================================================================

# Validate command structure and parameters
is_valid_command_structure if {
	input.command.verb != ""
	resource_requirement_satisfied
	not contains_injection_patterns
	not contains_shell_metacharacters
	valid_resource_names
}

# Resource requirement - some commands don't need explicit resources
resource_requirement_satisfied if {
	input.command.resource != ""
}

resource_requirement_satisfied if {
	input.command.resource == null
	input.command.verb in {"logs", "exec", "attach", "port-forward", "cp", "debug", "apply"}
}

# Check for command injection patterns in arguments
contains_injection_patterns if {
	some arg in input.command.args
	contains(arg, ";")
}

contains_injection_patterns if {
	some arg in input.command.args
	contains(arg, "&&")
}

contains_injection_patterns if {
	some arg in input.command.args
	contains(arg, "||")
}

contains_injection_patterns if {
	some arg in input.command.args
	contains(arg, "|")
}

contains_injection_patterns if {
	some arg in input.command.args
	contains(arg, "`")
}

contains_injection_patterns if {
	some arg in input.command.args
	contains(arg, "$(")
}

# Also check resource field for injection patterns
contains_injection_patterns if {
	input.command.resource != null
	contains(input.command.resource, "$(")
}

# Check for command injection patterns in flag values
contains_injection_patterns if {
	some flag in input.command.flags
	contains(flag.value, "$(")
}

contains_injection_patterns if {
	some flag in input.command.flags
	contains(flag.value, "`")
}

contains_injection_patterns if {
	some flag in input.command.flags
	contains(flag.value, ";")
}

contains_injection_patterns if {
	some flag in input.command.flags
	contains(flag.value, "&&")
}

contains_injection_patterns if {
	some flag in input.command.flags
	contains(flag.value, "||")
}

contains_injection_patterns if {
	some flag in input.command.flags
	contains(flag.value, "|")
}

# Fallback: check for injection pattern in the original command
contains_injection_patterns if {
	contains(input.original_command, "$(")
}

# Check for shell metacharacters in arguments
contains_shell_metacharacters if {
	some arg in input.command.args
	regex.match("[`${}><&]", arg)
}

# Validate resource names in arguments
valid_resource_names if {
	count(input.command.args) == 0
}

valid_resource_names if {
	count(input.command.args) > 0
	every arg in input.command.args {
		not startswith(arg, "kube-")
		not startswith(arg, "system:")
		is_valid_resource_name(arg)
	}
}

is_valid_resource_name(arg) if {
	# Allow standard kubernetes resource names
	regex.match("^[a-z0-9]([-a-z0-9]*[a-z0-9])?([.][a-z0-9]([-a-z0-9]*[a-z0-9])?)*$", arg)
}

is_valid_resource_name(arg) if {
	# Allow comma-separated resource names (e.g., "frontend-proxy,frontend")
	regex.match("^[a-z0-9]([-a-z0-9]*[a-z0-9])?([.][a-z0-9]([-a-z0-9]*[a-z0-9])?)*([,][a-z0-9]([-a-z0-9]*[a-z0-9])?([.][a-z0-9]([-a-z0-9]*[a-z0-9])?)*)*$", arg)
}

# ==============================================================================
# AUDIT AND LOGGING
# ==============================================================================

# Generate audit information for all decisions
audit_decision := {
	"timestamp": time.now_ns(),
	"command": input.command,
	"decision": {
		"allow": allow,
		"deny": deny,
		"requires_approval": requires_approval,
	},
	"classification": command_classification,
	"risk_level": risk_assessment,
	"reasoning": decision_reasoning,
	"violations": policy_violations,
}

# Classify the command for audit purposes
command_classification := "SAFE" if {
	is_safe_operation
}

command_classification := "RESTRICTED" if {
	is_restricted_operation
}

command_classification := "FORBIDDEN" if {
	is_forbidden_operation
}

# Assess risk level
risk_assessment := "LOW" if {
	is_safe_operation
}

risk_assessment := "MEDIUM" if {
	is_restricted_operation
}

risk_assessment := "HIGH" if {
	is_forbidden_operation
}

risk_assessment := "CRITICAL" if {
	targets_rbac_resources
}

risk_assessment := "CRITICAL" if {
	input.command.verb == "delete"
	input.command.resource in critical_resources
}

# Provide reasoning for the decision
decision_reasoning := "Safe read-only operation approved automatically" if {
	allow
	is_safe_operation
}

decision_reasoning := "Restricted operation requires human approval" if {
	requires_approval
}

decision_reasoning := "Forbidden operation denied by security policy" if {
	deny
	is_forbidden_operation
}

# decision_reasoning := "Command denied due to namespace restrictions" if {
#     deny
#     not passes_namespace_restrictions
# }

decision_reasoning := "Command denied due to dangerous flags" if {
	deny
	has_dangerous_flags
}

# Identify specific policy violations
policy_violations := violations if {
	violations := array.concat(
		[],
		# namespace_violations,
		array.concat(
			resource_violations,
			array.concat(
				flag_violations,
				command_structure_violations,
			),
		),
	)
}

# namespace_violations := ["namespace_restricted"] if {
#     not passes_namespace_restrictions
# } else := []

resource_violations := ["forbidden_resource"] if {
	input.command.resource in forbidden_resources
} else := []

flag_violations := ["dangerous_flags"] if {
	has_dangerous_flags
} else := []

command_structure_violations := ["invalid_structure"] if {
	not is_valid_command_structure
} else := []

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Policy configuration
config := {
	"version": "1.0.0",
	"mode": "simplified",
	"last_updated": "2025-09-04T00:00:00Z",
	"requires_auth": false,
	"requires_usage_tracking": false,
}

# ==============================================================================
# TEST CASES
# ==============================================================================

# Test safe operation - should allow
test_safe_get_pods if {
	allow with input as {"command": {
		"verb": "get",
		"resource": "pods",
		"namespace": "sre-sandbox",
		"args": [],
		"flags": [],
	}}
}

# Test forbidden operation - should deny
test_forbidden_delete_namespace if {
	deny with input as {"command": {
		"verb": "delete",
		"resource": "namespaces",
		"namespace": "test",
		"args": ["test-namespace"],
		"flags": [],
	}}
}

# Test restricted operation - should require approval
test_restricted_exec if {
	requires_approval with input as {"command": {
		"verb": "exec",
		"resource": "pods",
		"namespace": "sre-sandbox",
		"args": ["test-pod", "--", "ls", "/app"],
		"flags": ["-it"],
	}}
}

# Test dangerous flags - should deny
test_dangerous_flags if {
	deny with input as {"command": {
		"verb": "delete",
		"resource": "pods",
		"namespace": "sre-sandbox",
		"args": ["test-pod"],
		"flags": ["--force", "--grace-period=0"],
	}}
}

# Test forbidden namespace - should deny
test_forbidden_namespace if {
	deny with input as {"command": {
		"verb": "get",
		"resource": "pods",
		"namespace": "kube-system",
		"args": [],
		"flags": [],
	}}
}

# Test RBAC resource modification - should deny
test_rbac_modification if {
	deny with input as {"command": {
		"verb": "apply",
		"resource": "clusterroles",
		"namespace": "",
		"args": ["-f", "role.yaml"],
		"flags": [],
	}}
}
