"""Comprehensive tests for kubectl command parser."""

import subprocess
import sys
import pytest
from unittest.mock import patch
from kubectlcmdprocessor.parser import KubectlParser, main


@pytest.fixture
def parser():
    """Create a fresh parser instance for each test."""
    return KubectlParser()


def test_basic_resource_operations(parser):
    """Test basic resource operations like get, describe, delete."""

    # Test simple get command
    result = parser.parse("kubectl get pods")
    assert result["command"]["verb"] == "get"
    assert result["command"]["resource"] == "pods"
    assert result["command"]["namespace"] is None
    assert len(result["command"]["args"]) == 0

    # Test get with namespace flag
    result = parser.parse("kubectl get pods -n sre-sandbox")
    assert result["command"]["verb"] == "get"
    assert result["command"]["resource"] == "pods"
    assert result["command"]["namespace"] == "sre-sandbox"
    assert any(flag["name"] == "-n" and flag["value"] == "sre-sandbox" for flag in result["command"]["flags"])

    # Test describe with namespace=value format
    result = parser.parse("kubectl describe pod my-pod --namespace=production")
    assert result["command"]["verb"] == "describe"
    assert result["command"]["resource"] == "pod"
    assert result["command"]["namespace"] == "production"
    assert "my-pod" in result["command"]["args"]

    # Test delete with multiple flags
    result = parser.parse("kubectl delete pods --all -n test")
    assert result["command"]["verb"] == "delete"
    assert result["command"]["resource"] == "pods"
    assert result["command"]["namespace"] == "test"
    assert any(flag["name"] == "--all" for flag in result["command"]["flags"])


def test_file_based_operations(parser):
    """Test file-based operations with -f flag."""

    result = parser.parse("kubectl apply -f deployment.yaml")
    assert result["command"]["verb"] == "apply"
    assert result["command"]["resource"] is None  # -f now takes deployment.yaml as value
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-f"] == "deployment.yaml"

    result = parser.parse("kubectl create -f ./pod.json")
    assert result["command"]["verb"] == "create"
    assert result["command"]["resource"] is None  # -f now takes ./pod.json as value
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-f"] == "./pod.json"

    result = parser.parse("kubectl delete -f manifest.yaml")
    assert result["command"]["verb"] == "delete"
    assert result["command"]["resource"] is None  # -f now takes manifest.yaml as value
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-f"] == "manifest.yaml"


def test_complex_operations_with_multiple_flags(parser):
    """Test complex operations with multiple flags and arguments."""

    # Test logs command with multiple flags
    result = parser.parse("kubectl logs my-pod -c container-name --follow --tail=100")
    assert result["command"]["verb"] == "logs"
    assert result["command"]["resource"] is None
    assert result["command"]["args"] == ["my-pod"]  # container-name is now -c flag's value
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-c"] == "container-name"  # -c now takes container-name as value
    assert flags["--follow"] is None
    assert flags["--tail"] == "100"

    # Test get with output format
    result = parser.parse("kubectl get services -o yaml --sort-by=.metadata.name")
    assert result["command"]["verb"] == "get"
    assert result["command"]["resource"] == "services"
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-o"] == "yaml"
    assert flags["--sort-by"] == ".metadata.name"

    # Test exec with interactive flags and command
    result = parser.parse("kubectl exec -it my-pod -- /bin/bash")
    assert result["command"]["verb"] == "exec"
    assert result["command"]["resource"] is None
    assert "my-pod" in result["command"]["args"]
    assert "/bin/bash" in result["command"]["args"]
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-i"] is None  # -it is now split into -i and -t
    assert flags["-t"] is None
    assert flags["--"] is None  # -- is treated as a flag


def test_quoted_arguments(parser):
    """Test handling of quoted arguments with spaces."""

    result = parser.parse('kubectl create secret generic my-secret --from-literal=key="value with spaces"')
    assert result["command"]["verb"] == "create"
    assert result["command"]["resource"] == "secret"
    assert "generic" in result["command"]["args"]
    assert "my-secret" in result["command"]["args"]
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--from-literal"] == "key=value with spaces"  # Quotes are removed by tokenizer


def test_subcommands(parser):
    """Test kubectl subcommands like rollout, config, auth."""

    # Test rollout status
    result = parser.parse("kubectl rollout status deployment/nginx")
    assert result["command"]["verb"] == "rollout"
    assert result["command"]["resource"] == "status"
    assert "deployment/nginx" in result["command"]["args"]

    # Test rollout undo with flag
    result = parser.parse("kubectl rollout undo deployment/abc --to-revision=3")
    assert result["command"]["verb"] == "rollout"
    assert result["command"]["resource"] == "undo"
    assert "deployment/abc" in result["command"]["args"]
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--to-revision"] == "3"

    # Test config view
    result = parser.parse("kubectl config view")
    assert result["command"]["verb"] == "config"
    assert result["command"]["resource"] == "view"

    # Test config use-context
    result = parser.parse("kubectl config use-context production")
    assert result["command"]["verb"] == "config"
    assert result["command"]["resource"] == "use-context"
    assert "production" in result["command"]["args"]

    # Test auth can-i
    result = parser.parse("kubectl auth can-i create pods")
    assert result["command"]["verb"] == "auth"
    assert result["command"]["resource"] == "can-i"
    assert "create" in result["command"]["args"]
    assert "pods" in result["command"]["args"]


def test_creation_commands(parser):
    """Test resource creation commands with various flags."""

    # Test deployment creation
    result = parser.parse("kubectl create deployment nginx --image=nginx --replicas=3")
    assert result["command"]["verb"] == "create"
    assert result["command"]["resource"] == "deployment"
    assert "nginx" in result["command"]["args"]
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--image"] == "nginx"
    assert flags["--replicas"] == "3"

    # Test service creation
    result = parser.parse("kubectl create service clusterip my-service --tcp=80:8080")
    assert result["command"]["verb"] == "create"
    assert result["command"]["resource"] == "service"
    assert "clusterip" in result["command"]["args"]
    assert "my-service" in result["command"]["args"]
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--tcp"] == "80:8080"

    # Test configmap creation
    result = parser.parse("kubectl create configmap my-config --from-file=config.properties")
    assert result["command"]["verb"] == "create"
    assert result["command"]["resource"] == "configmap"
    assert "my-config" in result["command"]["args"]
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--from-file"] == "config.properties"


def test_debugging_operations(parser):
    """Test debugging and troubleshooting commands."""

    # Test debug command
    result = parser.parse("kubectl debug my-pod --image=busybox --target=app")
    assert result["command"]["verb"] == "debug"
    assert result["command"]["args"][0] == "my-pod"
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--image"] == "busybox"
    assert flags["--target"] == "app"

    # Test port-forward
    result = parser.parse("kubectl port-forward pod/my-pod 8080:80")
    assert result["command"]["verb"] == "port-forward"
    assert result["command"]["resource"] is None
    assert "pod/my-pod" in result["command"]["args"]
    assert "8080:80" in result["command"]["args"]

    # Test cp command
    result = parser.parse("kubectl cp /local/path pod/my-pod:/remote/path")
    assert result["command"]["verb"] == "cp"
    assert result["command"]["resource"] is None
    assert "/local/path" in result["command"]["args"]
    assert "pod/my-pod:/remote/path" in result["command"]["args"]

    # Test top command
    result = parser.parse("kubectl top nodes --sort-by=cpu")
    assert result["command"]["verb"] == "top"
    assert result["command"]["resource"] == "nodes"
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--sort-by"] == "cpu"


def test_advanced_operations(parser):
    """Test advanced operations like patch, scale, autoscale."""

    # Test patch with JSON
    result = parser.parse('kubectl patch deployment nginx -p \'{"spec":{"replicas":5}}\'')
    assert result["command"]["verb"] == "patch"
    assert result["command"]["resource"] == "deployment"
    assert "nginx" in result["command"]["args"]
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-p"] == '{"spec":{"replicas":5}}'  # JSON is now -p flag's value

    # Test scale
    result = parser.parse("kubectl scale deployment nginx --replicas=10")
    assert result["command"]["verb"] == "scale"
    assert result["command"]["resource"] == "deployment"
    assert "nginx" in result["command"]["args"]
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--replicas"] == "10"

    # Test autoscale
    result = parser.parse("kubectl autoscale deployment nginx --min=2 --max=10 --cpu-percent=80")
    assert result["command"]["verb"] == "autoscale"
    assert result["command"]["resource"] == "deployment"
    assert "nginx" in result["command"]["args"]
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--min"] == "2"
    assert flags["--max"] == "10"
    assert flags["--cpu-percent"] == "80"

    # Test wait
    result = parser.parse("kubectl wait --for=condition=Ready pod/my-pod --timeout=300s")
    assert result["command"]["verb"] == "wait"
    assert result["command"]["resource"] == "pod/my-pod"
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--for"] == "condition=Ready"
    assert flags["--timeout"] == "300s"


def test_cluster_management(parser):
    """Test cluster management commands."""

    # Test drain
    result = parser.parse("kubectl drain node-1 --ignore-daemonsets")
    assert result["command"]["verb"] == "drain"
    assert result["command"]["resource"] == "node-1"
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--ignore-daemonsets"] is None

    # Test cordon
    result = parser.parse("kubectl cordon node-1")
    assert result["command"]["verb"] == "cordon"
    assert result["command"]["resource"] == "node-1"

    # Test taint
    result = parser.parse("kubectl taint nodes node-1 key=value:NoSchedule")
    assert result["command"]["verb"] == "taint"
    assert result["command"]["resource"] == "nodes"
    assert "node-1" in result["command"]["args"]
    assert "key=value:NoSchedule" in result["command"]["args"]


def test_commands_without_kubectl_prefix(parser):
    """Test commands without the kubectl prefix."""

    # Test get without kubectl prefix
    result = parser.parse("get pods -o wide --all-namespaces")
    assert result["command"]["verb"] == "get"
    assert result["command"]["resource"] == "pods"
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-o"] == "wide"
    assert flags["--all-namespaces"] is None

    # Test apply with kustomize
    result = parser.parse("apply -k ./kustomize-dir")
    assert result["command"]["verb"] == "apply"
    assert result["command"]["resource"] is None  # -k now takes ./kustomize-dir as value
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-k"] == "./kustomize-dir"


def test_edge_cases(parser):
    """Test edge cases and malformed commands."""

    # Test empty kubectl command
    result = parser.parse("kubectl")
    assert result["command"]["verb"] is None
    assert result["command"]["resource"] is None
    assert len(result["command"]["flags"]) == 0

    # Test kubectl with only help flag
    result = parser.parse("kubectl --help")
    assert result["command"]["verb"] is None
    assert result["command"]["resource"] is None
    assert any(flag["name"] == "--help" for flag in result["command"]["flags"])

    # Test get without resource
    result = parser.parse("kubectl get")
    assert result["command"]["verb"] == "get"
    assert result["command"]["resource"] is None

    # Test empty string
    result = parser.parse("")
    assert result["command"]["verb"] is None
    assert result["command"]["resource"] is None

    # Test whitespace only
    result = parser.parse("   ")
    assert result["command"]["verb"] is None
    assert result["command"]["resource"] is None


def test_flag_parsing_variations(parser):
    """Test various flag parsing scenarios."""

    # Test short flag with value
    result = parser.parse("kubectl get pods -n test")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-n"] == "test"

    # Test long flag with equals
    result = parser.parse("kubectl get pods --namespace=production")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--namespace"] == "production"

    # Test boolean flags
    result = parser.parse("kubectl get pods --watch --all-namespaces")
    flag_names = [flag["name"] for flag in result["command"]["flags"]]
    assert "--watch" in flag_names
    assert "--all-namespaces" in flag_names

    # Test mixed flag formats
    result = parser.parse("kubectl logs pod -f --tail=10 -c container")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-f"] is None
    assert flags["--tail"] == "10"
    assert flags["-c"] == "container"  # -c now takes container as value
    assert result["command"]["args"] == ["pod"]  # container is now -c flag's value


def test_reset_functionality(parser):
    """Test that parser state is reset between calls."""

    # Parse first command
    result1 = parser.parse("kubectl get pods -n test")
    assert result1["command"]["namespace"] == "test"

    # Parse second command without namespace
    result2 = parser.parse("kubectl describe pod my-pod")
    assert result2["command"]["namespace"] is None
    assert result2["command"]["verb"] == "describe"
    assert result2["command"]["resource"] == "pod"


def test_tokenizer_with_quotes(parser):
    """Test tokenizer handles quoted strings correctly."""

    # Test single quotes
    result = parser.parse("kubectl create secret generic test --from-literal='key=value with spaces'")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--from-literal"] == "key=value with spaces"

    # Test double quotes
    result = parser.parse('kubectl create secret generic test --from-literal="key=value with spaces"')
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--from-literal"] == "key=value with spaces"

    # Test nested quotes in JSON
    result = parser.parse('kubectl patch pod test -p \'{"metadata":{"labels":{"app":"test"}}}\'')
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-p"] == '{"metadata":{"labels":{"app":"test"}}}'  # -p now takes JSON as value
    assert result["command"]["args"] == ["test"]  # test is the pod name, JSON is now -p flag's value


@patch("builtins.print")
def test_main_function(mock_print):
    """Test the main() function runs without errors and processes all test commands."""
    # Call the main function
    main()

    # Verify that print was called (output was produced)
    assert mock_print.called

    # Get all the print calls - extract the first argument from each call
    print_calls = []
    for call in mock_print.call_args_list:
        if call.args:  # call.args contains the positional arguments
            print_calls.append(str(call.args[0]))

        # Verify that we have output for commands and results
        # Note: command lines start with \nCommand: due to the print formatting in main()
        command_lines = [line for line in print_calls if "Command: " in line]
    result_lines = [line for line in print_calls if line.startswith("Parsed: ")]

    # Should have at least some command and result lines
    assert len(command_lines) > 0, f"No command lines found in output. All calls: {print_calls[:5]}..."
    assert len(result_lines) > 0, "No result lines found in output"

    # Verify some expected commands are processed
    all_output = " ".join(print_calls)
    assert "kubectl get pods" in all_output
    assert "kubectl debug my-pod" in all_output
    assert "kubectl taint nodes" in all_output

    # Verify that parsing results are included in output
    assert "{'command':" in all_output, "No parsing results found in output"


def test_flag_before_verb_skips_value(parser):
    """Test that flags with values before the verb are properly skipped to find the verb."""
    # This command has a flag with a value before the verb 'get'
    command = "kubectl --namespace production get pods"
    result = parser.parse(command)

    # Verify the verb was correctly identified despite the flag before it
    assert result["command"]["verb"] == "get"
    assert result["command"]["resource"] == "pods"
    assert result["command"]["namespace"] == "production"

    # Verify the flag was parsed correctly
    flags = result["command"]["flags"]
    assert len(flags) == 1
    assert flags[0]["name"] == "--namespace"
    assert flags[0]["value"] == "production"


def test_empty_tokens_after_tokenization(parser):
    """Test case where tokenization results in empty tokens list"""
    # This should have non-empty string but tokenize to empty list
    # For example, a string with only empty quotes
    result = parser.parse('kubectl ""')
    expected = {"command": {"verb": None, "resource": None, "namespace": None, "args": [], "flags": []}}
    assert result == expected


def test_namespace_flag_without_value(parser):
    """Test namespace flag without a value (XXX comment case)"""
    # Test -n flag at end of command (no value)
    result = parser.parse("kubectl get pods -n")

    assert result["command"]["verb"] == "get"
    assert result["command"]["resource"] == "pods"
    assert result["command"]["namespace"] is None  # Should be None since no value provided
    assert len(result["command"]["flags"]) == 1
    assert result["command"]["flags"][0]["name"] == "-n"
    assert result["command"]["flags"][0]["value"] is None

    # Test --namespace flag at end of command (no value)
    result = parser.parse("kubectl get pods --namespace")

    assert result["command"]["verb"] == "get"
    assert result["command"]["resource"] == "pods"
    assert result["command"]["namespace"] is None
    assert len(result["command"]["flags"]) == 1
    assert result["command"]["flags"][0]["name"] == "--namespace"
    assert result["command"]["flags"][0]["value"] is None

    # Test -n flag followed by another flag (no value for -n)
    result = parser.parse("kubectl get pods -n -o yaml")

    assert result["command"]["verb"] == "get"
    assert result["command"]["resource"] == "pods"
    assert result["command"]["namespace"] is None
    assert len(result["command"]["flags"]) == 2

    # Find the -n flag
    n_flag = next(flag for flag in result["command"]["flags"] if flag["name"] == "-n")
    assert n_flag["value"] is None

    # Find the -o flag
    o_flag = next(flag for flag in result["command"]["flags"] if flag["name"] == "-o")
    assert o_flag["value"] == "yaml"


def test_unquoted_selector_parsing(parser):
    """Test parsing of unquoted selector expressions."""
    
    # Test the original problem cases
    result = parser.parse("kubectl get pods -n otel-demo -l service in (email,checkout)")
    assert result["command"]["verb"] == "get"
    assert result["command"]["resource"] == "pods"
    assert result["command"]["namespace"] == "otel-demo"
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] == "service in (email,checkout)"
    assert len(result["command"]["args"]) == 0  # No leftover args
    
    result = parser.parse("kubectl get deployments -n otel-demo -o jsonpath='...' --selector=service in (ad,cart,payment)")
    assert result["command"]["verb"] == "get"
    assert result["command"]["resource"] == "deployments"
    assert result["command"]["namespace"] == "otel-demo"
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--selector"] == "service in (ad,cart,payment)"
    assert flags["-o"] == "jsonpath=..."
    assert len(result["command"]["args"]) == 0  # No leftover args


def test_selector_parsing_variations(parser):
    """Test different selector parsing scenarios."""
    
    # Simple equality selectors
    result = parser.parse("kubectl get pods -l app=nginx")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] == "app=nginx"
    
    # Not equal selectors
    result = parser.parse("kubectl get pods -l app!=nginx")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] == "app!=nginx"
    
    # Multiple selectors with comma
    result = parser.parse("kubectl get pods -l app=nginx,env=prod")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] == "app=nginx,env=prod"
    
    # --selector format with in operator
    result = parser.parse("kubectl get pods --selector=tier in (frontend,backend)")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--selector"] == "tier in (frontend,backend)"
    
    # notin operator
    result = parser.parse("kubectl get pods -l environment notin (production,staging)")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] == "environment notin (production,staging)"
    
    # Complex selector with 'and'
    result = parser.parse("kubectl get pods -l app=web and version!=old")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] == "app=web and version!=old"


def test_selector_edge_cases(parser):
    """Test edge cases for selector parsing."""
    
    # Empty selector with quotes - this should actually result in None since there's no content
    result = parser.parse('kubectl get pods -l ""')
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    # Empty string in quotes results in no selector tokens, so value is None
    assert flags["-l"] is None
    
    # Missing selector value (flag without value)
    result = parser.parse("kubectl get pods -l")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] is None
    
    # Empty selector value with equals
    result = parser.parse("kubectl get pods --selector=")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--selector"] == ""
    
    # Selector followed by another flag
    result = parser.parse("kubectl get pods -l app=nginx -o yaml")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] == "app=nginx"
    assert flags["-o"] == "yaml"
    
    # Complex selector - note that complex expressions with multiple 'in'/'notin' 
    # may not parse as expected due to the tokenization, but simple ones should work
    result = parser.parse("kubectl get pods -l 'app in (web,api),env notin (dev)'")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] == "app in (web,api),env notin (dev)"


def test_quoted_selector_compatibility(parser):
    """Test that quoted selectors still work correctly."""
    
    # Single quoted selector
    result = parser.parse("kubectl get pods -l 'app in (nginx,apache)'")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] == "app in (nginx,apache)"
    
    # Double quoted selector
    result = parser.parse('kubectl get pods -l "service in (web,api)"')
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] == "service in (web,api)"
    
    # Quoted selector with equals format
    result = parser.parse('kubectl get pods --selector="app in (frontend,backend)"')
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--selector"] == "app in (frontend,backend)"


def test_field_selector_compatibility(parser):
    """Test that field selectors still work correctly."""
    
    # Field selector should use existing logic (not the special selector logic)
    result = parser.parse("kubectl get services --all-namespaces --field-selector metadata.namespace!=default")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--field-selector"] == "metadata.namespace!=default"
    assert flags["--all-namespaces"] is None


def test_selector_with_mixed_flags(parser):
    """Test selectors combined with other flags."""
    
    # Selector with namespace and output format
    result = parser.parse("kubectl get pods -n prod -l app in (web,api) -o wide")
    assert result["command"]["namespace"] == "prod"
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-n"] == "prod"
    assert flags["-l"] == "app in (web,api)"
    assert flags["-o"] == "wide"
    
    # Multiple complex flags including selector
    result = parser.parse("kubectl get deployments --all-namespaces --selector=tier in (frontend,backend) --sort-by=.metadata.name")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--all-namespaces"] is None
    assert flags["--selector"] == "tier in (frontend,backend)"
    assert flags["--sort-by"] == ".metadata.name"


def test_selector_coverage_edge_cases(parser):
    """Test specific edge cases to achieve 100% coverage."""
    
    # Test line 333: selector followed by a flag when paren_depth == 0 (normal case)  
    result = parser.parse("kubectl get pods -l app=nginx -o yaml")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] == "app=nginx"
    assert flags["-o"] == "yaml"
    
    # Test lines 369-370: empty selector tokens result in None value
    result = parser.parse("kubectl get pods -l")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] is None
    
    # Test lines 359-361: This tests the case where we have collected some tokens, 
    # paren_depth is 0, last token is NOT 'in' or 'notin', so we break
    # This case: "app" followed by "nginx" (not an operator, not a flag)
    result = parser.parse("kubectl get pods -l app nginx -o yaml")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] == "app"  # Should stop at "app" because next token "nginx" is not an operator
    assert flags["-o"] == "yaml"
    assert "nginx" in result["command"]["args"]  # nginx becomes an argument
    
    # Test lines 254-256: Same logic but in flag=value format
    # Note: the flag=value format continues differently, so we expect different behavior
    result = parser.parse("kubectl get pods --selector=app nginx -o yaml")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--selector"] == "app nginx"  # flag=value format continues parsing
    assert flags["-o"] == "yaml"


def test_selector_comprehensive_scenarios(parser):
    """Test comprehensive selector scenarios."""
    
    # Test unquoted selector with complex parenthetical expressions
    result = parser.parse("kubectl get pods -l service in (email,checkout)")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] == "service in (email,checkout)"
    
    # Test equals format with complex selector
    result = parser.parse("kubectl get deployments --selector=service in (ad,cart,payment)")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["--selector"] == "service in (ad,cart,payment)"
    
    # Test mixed operators
    result = parser.parse("kubectl get pods -l 'app=nginx,env!=prod'")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] == "app=nginx,env!=prod"


def test_final_coverage_edge_cases(parser):
    """Test remaining edge cases to achieve 100% coverage."""
    
    # Test lines 254-256: flag=value format where last token is NOT 'in'/'notin' 
    # The break condition happens when the last token is not 'in'/'notin' and next is not an operator
    result = parser.parse("kubectl get pods --selector=app=nginx unknown -o yaml")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    # Based on actual behavior, it continues to parse
    assert flags["--selector"] == "app=nginx unknown"
    assert flags["-o"] == "yaml"
    
    # Test line 333: This is hit in normal flag parsing when we encounter a flag
    # This should be hit by many existing tests, but let's be explicit
    result = parser.parse("kubectl get pods -l app=test -o json")
    flags = {flag["name"]: flag["value"] for flag in result["command"]["flags"]}
    assert flags["-l"] == "app=test"
    assert flags["-o"] == "json"


def test_parser_script_execution():
    """Test that parser.py script can be executed directly."""
    try:
        # Run the parser.py script as a module
        result = subprocess.run([sys.executable, "-m", "kubectlcmdprocessor.parser"], capture_output=True, text=True, timeout=30)

        # Check that the script ran successfully (exit code 0)
        assert result.returncode == 0

        # Check that some output was produced
        assert len(result.stdout) > 0

        # Check that no errors were written to stderr
        assert result.stderr == ""

    except subprocess.TimeoutExpired:
        pytest.fail("Script execution timed out")
    except Exception as e:
        pytest.fail(f"Script execution failed: {e}")
