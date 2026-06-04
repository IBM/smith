import os
import json
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.sse import sse_client
from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import httpx
from contextlib import asynccontextmanager
import glob
# Load .env.  change to ollama models
load_dotenv()
api_key = os.getenv("RITS_API_KEY", None)
api_url = os.getenv("RITS_BASE_URL", None)
model = os.getenv("RITS_MODEL", None)

test_path = os.getenv("TEST_CASE_PATH", None)
base_url=os.getenv("BASE_SKILL_URL", None)
test_path=base_url+test_path
# permission_mapp={
#     "ask_for_workpolicy": ["read:ask_for_workpolicy"],
#     "create_ticket": ["write:create_ticket"],
#     "submit_ticket": ["write:submit_ticket"],
#     "get_w2_form": ["read:get_w2_form"],
#     "view_team_compensation": ["read:view_team_compensation"],
#     "ask_for_salary": ["read:ask_for_salary"],
#     "export_compensation_data": ["read:export_compensation_data", "export:file"],
#     "email_compensation_report": ["write:email_compensation_report"],
#     "send_email": ["write:send_email"],
#     "purchase": ["write:purchase"],
#     "return_product": ["write:return_product"],
#     "export_content_as_file": ["write:export_content_as_file"],
#     "set_user_role": ["write:set_user_role"],
#     "debug_user_context": [],
#     "other": []
# }


if api_key is None or api_url is None:
    raise ValueError("RITS_API_KEY or RITS_BASE_URL not defined in environment. Create a .env file")

# for rits model
client = OpenAI(api_key=api_key,
        base_url = api_url,
        default_headers = {'RITS_API_KEY': api_key})

class ConnectionManager:
    def __init__(self, sse_server_map):
        self.sse_server_map = sse_server_map
        self.sessions = {}
        self.exit_stack = AsyncExitStack()

    async def initialize(self):
        for server_name, url in self.sse_server_map.items():
            sse_transport = await self.exit_stack.enter_async_context(sse_client(url=url))
            read, write = sse_transport
            session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self.sessions[server_name] = session

    async def list_tools(self):
        tool_map = {}
        consolidated_tools = []
        for server_name, session in self.sessions.items():
            tools = await session.list_tools()
            tool_map.update({tool.name: server_name for tool in tools.tools})
            consolidated_tools.extend(tools.tools)
        return tool_map, consolidated_tools

    async def call_tool(self, tool_name, arguments, tool_map):
        server_name = tool_map.get(tool_name)
        if not server_name:
            return f"Tool '{tool_name}' not found."

        session = self.sessions.get(server_name)
        if session:
            result = await session.call_tool(tool_name, arguments=arguments)
            return result.content[0].text

    async def close(self):
        await self.exit_stack.aclose()

async def chat(input_messages, tool_map, tools, max_turns=10, connection_manager=None):
    chat_messages = input_messages[:]
    tool_args={}
    tool_name='other'
    for _ in range(max_turns):
        result = client.chat.completions.create(
            model=model,
            messages=chat_messages,
            tools=tools,
        )

        if result.choices[0].finish_reason == "tool_calls":
            chat_messages.append(result.choices[0].message)

            for tool_call in result.choices[0].message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                observation = await connection_manager.call_tool(
                    tool_name, tool_args, tool_map
                )

                chat_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(observation),
                })
        else:
            return tool_name, tool_args, result.choices[0].message.content

    result = client.chat.completions.create(
        model=model,
        messages=chat_messages,
    )
    return tool_args, str(result.choices[0].message.content)

SSE_SERVER_MAP = {
    "MCP_SERVER": "http://localhost:8000/sse",
}

connection_manager: Optional[ConnectionManager] = None
tool_map_cache: Dict[str, str] = {}
tools_json_cache: List[Dict[str, Any]] = []

async def chat_endpoint():
    connection_manager = ConnectionManager(SSE_SERVER_MAP)
    await connection_manager.initialize()
    tool_map, tool_objects = await connection_manager.list_tools()
    tool_map_cache = tool_map
    tools_json_cache = [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema,
            },
        }
        for tool in tool_objects
    ]
    system_var={}
    miscalled_cases = []
    labels=['allow', 'disallow']
    for label in labels:
        files_in_current_directory = glob.glob(test_path+label+"/*")
        for file_path in files_in_current_directory:
            with open(file_path, 'r') as f:
                test_case=json.load(f)
            prompt=test_case["input"]["extensions"]['agent']['input']
            system_var=test_case["input"]["extensions"]['subject']
            input_messages = [
                            {
                                "role": "system",
                                "content": (
                                    "You are a professional HR. Use tools to answer user's questions."
                                    + "\nThe current user's profile: "
                                    + str(system_var)
                                    + "\nRULES: Focus on the current task. Memory is only for reference."
                                    + "\nIMPORTANT: If a tool returns a denial message (starting with 🚫), simply relay that exact message without any explanation, elaboration, or additional context about policies, limits, or reasons."
                                ),
                            },
                            {"role": "user", "content": "Current task/question: " + prompt},
                        ]
            tool_name, tool_args, answer = await chat(
                    input_messages=input_messages,
                    tool_map=tool_map_cache,
                    tools=tools_json_cache,
                    connection_manager=connection_manager,
                )
            assigned_tool = test_case["input"]["name"]
            if assigned_tool.lower() == "promptfoo":
                test_case["input"]["name"] = tool_name
                test_case["input"]["arguments"] = tool_args
                # test_case["input"]["extensions"]["object"]["permissions"] = permission_mapp.get(tool_name, [])
                with open(file_path, 'w') as f:
                    json.dump(test_case, f)
            elif tool_name != assigned_tool:
                miscalled_cases.append({
                    "file_path": file_path,
                    "label": label,
                    "assigned_tool": assigned_tool,
                    "actual_tool": tool_name,
                    "agent_input": prompt,
                    "actual_args": tool_args
                })
                print(f"[MISMATCH] {file_path}: assigned={assigned_tool}, actual={tool_name}, removing test case")
                os.remove(file_path)
            else:
                test_case["input"]["arguments"] = tool_args
                # test_case["input"]["extensions"]["object"]["permissions"] = permission_mapp[test_case["input"]["name"]]
                with open(file_path, 'w') as f:
                    json.dump(test_case, f)

    miscalled_output = test_path + "miscalled_cases.json"
    with open(miscalled_output, 'w') as f:
        json.dump(miscalled_cases, f, indent=4)
    print(f"\nTotal miscalled cases: {len(miscalled_cases)}")
    print(f"Saved to: {miscalled_output}")

    await connection_manager.close()
    return ''

print("hello")
import asyncio
print(asyncio.run(chat_endpoint()))