# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""Integration test for ``smith --flag generate_promptfoo_config``.

Boots the ``call-for-papers-mcp`` example agent (needed so the flag can pull the
MCP tool definitions), runs the flag with the LLM, and validates the generated
promptfoo redteam config: it must be parseable YAML carrying a ``redteam`` block
with a non-empty ``purpose``, ``contexts``, and a ``policy`` plugin, plus the
``targets``/``prompts`` skeleton from the template.

The output path is redirected to a tmp file so the example's committed
``promptfooconfig.yaml`` is never overwritten. Requires a real LLM
(``requires_llm``) and the example agent (``agent_server``).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover - yaml ships with the pipeline deps
    yaml = None

from helpers import BASE_URL, EXAMPLE, env_rel, run_smith

pytestmark = pytest.mark.integration


def _config_env(agent_url: str, out_rel: str) -> dict:
    env = dict(os.environ)
    rel = env_rel(EXAMPLE)
    env.update(
        {
            "AGENT_URL": agent_url,
            "TARGET_AGENT_PATH": rel,
            "GUIDANCE_FILE": f"{rel}smith/guidance.txt",
            "SYSTEM_VAR_FILE": f"{rel}smith/system_vars.json",
            "MCP_TRANSPORT": "stdio",
            "MCP_COMMAND": "python",
            "MCP_ARGS": "server.py",
            "MCP_CWD": rel,
            # Write to a throwaway path so the example's committed config is safe.
            "PROMPTFOO_CONFIG_FILE": out_rel,
        }
    )
    return env


def test_generate_promptfoo_config_format(requires_llm, agent_server, tmp_path):
    if yaml is None:
        pytest.skip("PyYAML not available")

    # Output relative to BASE_URL; use a unique name under references/.
    out_rel = "references/__test_promptfooconfig__.yaml"
    out_path = Path(BASE_URL + out_rel)
    if out_path.exists():
        out_path.unlink()

    try:
        result = run_smith(
            "generate_promptfoo_config",
            timeout=900,
            env=_config_env(agent_server, out_rel),
        )
        assert result.returncode == 0, (
            f"generate_promptfoo_config failed (rc={result.returncode}).\n"
            f"--- stdout ---\n{result.stdout[-1500:]}\n"
            f"--- stderr ---\n{result.stderr[-1000:]}"
        )

        # Parseable YAML.
        assert out_path.exists(), "promptfoo config was not written"
        config = yaml.safe_load(out_path.read_text())
        assert isinstance(config, dict), "config is not a YAML mapping"

        # Skeleton preserved from the template.
        assert "targets" in config, "config missing 'targets'"
        assert "prompts" in config, "config missing 'prompts'"

        # redteam block generated with the key fields.
        assert "redteam" in config, "config missing 'redteam'"
        redteam = config["redteam"]
        assert isinstance(redteam, dict)
        assert redteam.get("purpose"), "redteam.purpose is empty"
        assert "contexts" in redteam, "redteam missing 'contexts'"

        # A policy plugin must be present (that's what drives policy red-teaming).
        plugins = redteam.get("plugins", [])
        plugin_ids = {
            p.get("id") if isinstance(p, dict) else p for p in (plugins or [])
        }
        assert "policy" in plugin_ids, f"no 'policy' plugin in {plugin_ids}"
    finally:
        if out_path.exists():
            out_path.unlink()
