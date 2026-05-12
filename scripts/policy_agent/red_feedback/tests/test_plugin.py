"""Tests for kubectlcmdprocessor/plugin.py

Copyright 2025
SPDX-License-Identifier: Apache-2.0
"""

import pytest
from unittest.mock import Mock

from kubectlcmdprocessor.plugin import KubectlCmdProcessor, CONTEXT_KEY_POLICY_CONTEXT, CONTEXT_KEY_KUBECTL_CMD
from mcpgateway.plugins.framework import PluginConfig, PluginContext, ToolPreInvokePayload


@pytest.fixture
def plugin_config():
    """Create a test plugin configuration."""
    return PluginConfig(name="test_kubectl_processor", kind="test")


@pytest.fixture
def plugin(plugin_config):
    """Create a KubectlCmdProcessor plugin instance."""
    return KubectlCmdProcessor(plugin_config)


@pytest.fixture
def mock_context():
    """Create a mock plugin context."""
    context = Mock(spec=PluginContext)
    context.global_context = Mock()
    context.global_context.state = {}
    return context


@pytest.mark.asyncio
async def test_plugin_initialization(plugin_config):
    """Test plugin initialization."""
    plugin = KubectlCmdProcessor(plugin_config)
    assert plugin is not None
    assert plugin.config == plugin_config


@pytest.mark.asyncio
async def test_tool_pre_invoke_empty_args(plugin, mock_context):
    """Test tool_pre_invoke with empty args."""
    payload = ToolPreInvokePayload(name="test_tool", args=None)
    result = await plugin.tool_pre_invoke(payload, mock_context)
    assert result.continue_processing is True
    # State should remain empty when no args provided
    assert len(mock_context.global_context.state) == 0


@pytest.mark.asyncio
async def test_tool_pre_invoke_empty_dict_args(plugin, mock_context):
    """Test tool_pre_invoke with empty dictionary args."""
    payload = ToolPreInvokePayload(name="test_tool", args={})
    result = await plugin.tool_pre_invoke(payload, mock_context)
    assert result.continue_processing is True
    # State should remain empty when empty args provided
    assert len(mock_context.global_context.state) == 0


@pytest.mark.asyncio
async def test_tool_pre_invoke_with_args(plugin, mock_context):
    """Test tool_pre_invoke with valid args."""
    payload = ToolPreInvokePayload(name="test_tool", args={"command": "kubectl get pods"})
    result = await plugin.tool_pre_invoke(payload, mock_context)
    assert result.continue_processing is True
    assert CONTEXT_KEY_POLICY_CONTEXT in mock_context.global_context.state


@pytest.mark.asyncio
async def test_process_args_single_argument(plugin, mock_context):
    """Test processing single argument."""
    args = {"command": "kubectl get pods"}
    await plugin.process_args_in_state(args, mock_context)

    assert CONTEXT_KEY_POLICY_CONTEXT in mock_context.global_context.state
    policy_context = mock_context.global_context.state[CONTEXT_KEY_POLICY_CONTEXT]
    assert CONTEXT_KEY_KUBECTL_CMD in policy_context

    # Verify the parsed command structure
    kubectl_cmd = policy_context[CONTEXT_KEY_KUBECTL_CMD]
    assert isinstance(kubectl_cmd, dict)


@pytest.mark.asyncio
async def test_process_args_multiple_arguments_raises_error(plugin, mock_context):
    """Test that multiple arguments raise ValueError."""
    args = {"command1": "kubectl get pods", "command2": "kubectl get services"}

    with pytest.raises(ValueError, match="only works on single argument functions"):
        await plugin.process_args_in_state(args, mock_context)


@pytest.mark.asyncio
async def test_process_args_kubectl_parser_integration(plugin, mock_context):
    """Test integration with KubectlParser."""
    args = {"command": "kubectl get pods --namespace=default"}
    await plugin.process_args_in_state(args, mock_context)

    policy_context = mock_context.global_context.state[CONTEXT_KEY_POLICY_CONTEXT]
    kubectl_cmd = policy_context[CONTEXT_KEY_KUBECTL_CMD]

    # Verify parser output structure contains expected fields
    assert "command" in kubectl_cmd
    command_data = kubectl_cmd["command"]
    assert "resource" in command_data
    assert command_data["resource"] == "pods"
    assert "namespace" in command_data
    assert command_data["namespace"] == "default"


@pytest.mark.asyncio
async def test_process_args_with_complex_kubectl_command(plugin, mock_context):
    """Test processing complex kubectl command."""
    args = {"command": "kubectl apply -f deployment.yaml --namespace=production --dry-run=client"}
    await plugin.process_args_in_state(args, mock_context)

    policy_context = mock_context.global_context.state[CONTEXT_KEY_POLICY_CONTEXT]
    kubectl_cmd = policy_context[CONTEXT_KEY_KUBECTL_CMD]

    # Verify complex command parsing
    assert "command" in kubectl_cmd
    command_data = kubectl_cmd["command"]
    assert "flags" in command_data
    # Check for namespace flag in the flags list
    namespace_flag = next((flag for flag in command_data["flags"] if flag["name"] == "--namespace"), None)
    assert namespace_flag is not None
    assert namespace_flag["value"] == "production"


@pytest.mark.asyncio
async def test_process_args_with_non_kubectl_command(plugin, mock_context):
    """Test processing non-kubectl command."""
    args = {"command": "ls -la"}
    await plugin.process_args_in_state(args, mock_context)

    policy_context = mock_context.global_context.state[CONTEXT_KEY_POLICY_CONTEXT]
    kubectl_cmd = policy_context[CONTEXT_KEY_KUBECTL_CMD]

    # Should still parse but may not have kubectl-specific structure
    assert isinstance(kubectl_cmd, dict)


@pytest.mark.asyncio
async def test_process_args_with_empty_string(plugin, mock_context):
    """Test processing empty string argument."""
    args = {"command": ""}
    await plugin.process_args_in_state(args, mock_context)

    policy_context = mock_context.global_context.state[CONTEXT_KEY_POLICY_CONTEXT]
    kubectl_cmd = policy_context[CONTEXT_KEY_KUBECTL_CMD]

    # Should handle empty string gracefully
    assert isinstance(kubectl_cmd, dict)


@pytest.mark.asyncio
async def test_process_args_with_special_characters(plugin, mock_context):
    """Test processing command with special characters."""
    args = {"command": "kubectl get pods --selector='app=nginx,version!=1.0'"}
    await plugin.process_args_in_state(args, mock_context)

    policy_context = mock_context.global_context.state[CONTEXT_KEY_POLICY_CONTEXT]
    kubectl_cmd = policy_context[CONTEXT_KEY_KUBECTL_CMD]

    # Should handle special characters in arguments
    assert "command" in kubectl_cmd
    command_data = kubectl_cmd["command"]
    assert "resource" in command_data
    assert command_data["resource"] == "pods"


@pytest.mark.asyncio
async def test_context_state_persistence(plugin, mock_context):
    """Test that context state is properly updated and persists."""
    # Process first command
    args1 = {"command": "kubectl get pods"}
    await plugin.process_args_in_state(args1, mock_context)

    # Process second command
    args2 = {"command": "kubectl get services"}
    await plugin.process_args_in_state(args2, mock_context)

    # Verify state was updated (not just appended)
    assert CONTEXT_KEY_POLICY_CONTEXT in mock_context.global_context.state
    policy_context = mock_context.global_context.state[CONTEXT_KEY_POLICY_CONTEXT]
    kubectl_cmd = policy_context[CONTEXT_KEY_KUBECTL_CMD]

    # Should contain the latest command
    assert "command" in kubectl_cmd
    command_data = kubectl_cmd["command"]
    assert command_data["resource"] == "services"


@pytest.mark.asyncio
async def test_process_args_type_conversion(plugin, mock_context):
    """Test that arguments are properly converted to strings."""
    # Test with non-string argument
    args = {"command": 12345}
    await plugin.process_args_in_state(args, mock_context)

    policy_context = mock_context.global_context.state[CONTEXT_KEY_POLICY_CONTEXT]
    kubectl_cmd = policy_context[CONTEXT_KEY_KUBECTL_CMD]

    # Should handle type conversion gracefully
    assert isinstance(kubectl_cmd, dict)
