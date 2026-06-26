# -*- coding: utf-8 -*-
# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

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

from kubectlcmdprocessor.plugin import (
    CONTEXT_KEY_POLICY_CONTEXT,
    CONTEXT_KEY_KUBECTL_CMD,
)


@pytest.fixture(scope="module", autouse=True)
def plugin_manager():
    """Initialize plugin manager."""
    plugin_manager = PluginManager("./resources/plugins/config.yaml")
    asyncio.run(plugin_manager.initialize())
    yield plugin_manager
    asyncio.run(plugin_manager.shutdown())


@pytest.mark.asyncio
async def test_tool_pre_hook_commands(plugin_manager: PluginManager):
    """Test tool pre hook across all registered plugins for a list of commands."""
    with open("./tests/inputs/commands", "r") as f:
        for line in f.readlines():
            expected, cmd = line.split(",", 1)
            payload = ToolPreInvokePayload(name="kubectl_tool", args={"arg0": cmd})
            global_context = GlobalContext(request_id="1")
            result, ctx = await plugin_manager.tool_pre_invoke(payload, global_context)
            context = next(iter(ctx.values()))
            cmd = context.global_context.state[CONTEXT_KEY_POLICY_CONTEXT][
                CONTEXT_KEY_KUBECTL_CMD
            ]
            assert result.continue_processing == (expected == "allow")
