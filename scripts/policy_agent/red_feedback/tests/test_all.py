# -*- coding: utf-8 -*-
"""Tests for registered plugins."""

# Third-Party
import asyncio
import pytest

# First-Party
from mcpgateway.plugins.framework import (
    PluginManager,
    GlobalContext,
    ToolPreInvokePayload,
)

from kubectlcmdprocessor.plugin import CONTEXT_KEY_POLICY_CONTEXT, CONTEXT_KEY_KUBECTL_CMD


@pytest.fixture(scope="module", autouse=True)
def plugin_manager():
    """Initialize plugin manager."""
    plugin_manager = PluginManager("./resources/plugins/config.yaml")
    asyncio.run(plugin_manager.initialize())
    yield plugin_manager
    asyncio.run(plugin_manager.shutdown())


@pytest.mark.asyncio
async def test_tool_pre_hook(plugin_manager: PluginManager):
    """Test tool pre hook across all registered plugins."""
    # Customize payload for testing
    payload = ToolPreInvokePayload(name="kubectl_tool", args={"arg0": "kubectl get pods"})
    global_context = GlobalContext(request_id="1")
    result, ctx = await plugin_manager.tool_pre_invoke(payload, global_context)
    context = next(iter(ctx.values()))
    cmd = context.global_context.state[CONTEXT_KEY_POLICY_CONTEXT][CONTEXT_KEY_KUBECTL_CMD]
    assert cmd["command"]["verb"] == "get"
    assert cmd["command"]["resource"] == "pods"
    assert cmd["command"]["namespace"] is None
    assert len(cmd["command"]["args"]) == 0
    assert result.continue_processing
