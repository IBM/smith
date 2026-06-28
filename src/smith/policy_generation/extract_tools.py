# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

"""
Extract tool definitions from an MCP server via list_tools().

Supports two transport modes:
- SSE: connects to a running MCP server (e.g., http://localhost:8000/sse)
- stdio: launches the MCP server as a subprocess (e.g., python server.py)

Usage (SSE - server must be running):
    python src/smith/policy_generation/extract_tools.py \
        --transport sse --url http://localhost:8000/sse \
        --output examples/RagChatbot_MCPServer/smith/tool_definitions.json

Usage (stdio - launches server.py directly):
    python src/smith/policy_generation/extract_tools.py \
        --transport stdio --command python --args server.py \
        --cwd examples/call-for-papers-mcp \
        --output examples/call-for-papers-mcp/smith/tool_definitions.json
"""

import json
import argparse
import asyncio
from pathlib import Path
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client, StdioServerParameters


async def fetch_tools_sse(url: str) -> list:
    """Connect to MCP server via SSE and fetch all tool definitions."""
    async with AsyncExitStack() as stack:
        sse_transport = await stack.enter_async_context(sse_client(url=url))
        read, write = sse_transport
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        tools_response = await session.list_tools()
        return tools_response.tools


async def fetch_tools_stdio(command: str, args: list, cwd: str = None) -> list:
    """Launch MCP server as subprocess via stdio and fetch all tool definitions."""
    server_params = StdioServerParameters(
        command=command,
        args=args,
        cwd=cwd,
    )
    async with AsyncExitStack() as stack:
        stdio_transport = await stack.enter_async_context(stdio_client(server_params))
        read, write = stdio_transport
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        tools_response = await session.list_tools()
        return tools_response.tools


def tool_to_dict(tool) -> dict:
    """Convert an MCP tool object to a serializable dict."""
    schema = tool.inputSchema or {}
    properties = schema.get("properties", {})
    required_fields = schema.get("required", [])

    parameters = []
    for param_name, param_info in properties.items():
        param = {
            "name": param_name,
            "type": param_info.get("type", "any"),
            "required": param_name in required_fields,
        }
        if "description" in param_info:
            param["description"] = param_info["description"]
        if "default" in param_info:
            param["default"] = param_info["default"]
        if "enum" in param_info:
            param["candidates"] = param_info["enum"]
        if "items" in param_info:
            param["items"] = param_info["items"]
        parameters.append(param)

    return {
        "name": tool.name,
        "description": tool.description or "",
        "parameters": parameters,
        "input_schema": schema,
    }


async def extract_tools(
    transport: str = "sse",
    url: str = None,
    command: str = None,
    cmd_args: list = None,
    cwd: str = None,
) -> dict:
    """Fetch tools from MCP server and return structured result."""
    if transport == "sse":
        tools = await fetch_tools_sse(url)
        source = url
    elif transport == "stdio":
        tools = await fetch_tools_stdio(command, cmd_args or [], cwd)
        source = f"{command} {' '.join(cmd_args or [])}"
    else:
        raise ValueError(f"Unknown transport: {transport}")

    tool_list = [tool_to_dict(t) for t in tools]
    return {"tools": tool_list, "source": source, "transport": transport}


def main():
    parser = argparse.ArgumentParser(
        description="Extract MCP tool definitions from a server"
    )
    parser.add_argument(
        "--transport", default="sse", choices=["sse", "stdio"], help="Transport type"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000/sse",
        help="MCP server SSE endpoint URL (for sse transport)",
    )
    parser.add_argument(
        "--command",
        default="python",
        help="Command to launch MCP server (for stdio transport)",
    )
    parser.add_argument(
        "--args",
        nargs="*",
        default=[],
        help="Arguments for the server command (for stdio transport)",
    )
    parser.add_argument(
        "--cwd", default=None, help="Working directory for stdio server"
    )
    parser.add_argument("--output", required=True, help="Output JSON file path")
    args = parser.parse_args()

    result = asyncio.run(
        extract_tools(
            transport=args.transport,
            url=args.url,
            command=args.command,
            cmd_args=args.args,
            cwd=args.cwd,
        )
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Extracted {len(result['tools'])} tools via {args.transport}")
    for tool in result["tools"]:
        param_names = [p["name"] for p in tool["parameters"]]
        print(f"  - {tool['name']} ({', '.join(param_names)})")


if __name__ == "__main__":
    main()
