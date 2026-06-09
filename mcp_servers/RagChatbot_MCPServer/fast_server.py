import os
import json
import asyncio
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.sse import sse_client
from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import httpx
from fastapi import FastAPI
from contextlib import asynccontextmanager

# Load .env.  change to ollama models
load_dotenv()
api_key = os.getenv("RITS_API_KEY", None)
api_url = os.getenv("RITS_BASE_URL", None)
model = os.getenv("RITS_MODEL", None)
if api_key is None or api_url is None:
    raise ValueError("OPENAI_API_KEY or OPENAI_API_BASE_URL url not defined in environment. Create a .env file")

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
            return result.choices[0].message.content

    result = client.chat.completions.create(
        model=model,
        messages=chat_messages,
    )
    return str(result.choices[0].message.content)

SSE_SERVER_MAP = {
    "MCP_SERVER": "http://localhost:8000/sse",
}

@asynccontextmanager
async def lifespan(app: FastAPI):

    global connection_manager, tool_map_cache, tools_json_cache

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
    app.state.db = "Connected"
    yield
    if connection_manager:
        await connection_manager.close()
        connection_manager = None
    app.state.db = "Disconnected"


app = FastAPI(lifespan=lifespan)

connection_manager: Optional[ConnectionManager] = None
tool_map_cache: Dict[str, str] = {}
tools_json_cache: List[Dict[str, Any]] = []


DEFAULT_USER_PROFILE = {
    "user_role": "employee",
    "user_department": "sales",
    "user_name": "Bob",
}


def build_input_messages(question: str, user_profile: Dict[str, Any] = None, history: List[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    user_profile = user_profile or DEFAULT_USER_PROFILE
    history = history or []
    return [
        {
            "role": "system",
            "content": (
                "You are a professional HR. Use tools to answer user's questions."
                + "\nThe current user's profile: "
                + str(user_profile)
                + "\nRULES: Focus on the current task. Memory is only for reference."
                + "\nIMPORTANT: If a tool returns a denial message (starting with 🚫), simply relay that exact message without any explanation, elaboration, or additional context about policies, limits, or reasons."
                + "\n" + str(history)
            ),
        },
        {"role": "user", "content": "Current task/question: " + question},
    ]


class ChatRequest(BaseModel):
    question: str
    user_profile: Optional[Dict[str, Any]] = None
    history: Optional[List[Dict[str, str]]] = None


class ChatResponse(BaseModel):
    answer: str


class ExtractToolCallRequest(BaseModel):
    question: str
    user_profile: Optional[Dict[str, Any]] = None


class ExtractToolCallResponse(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    input_messages = build_input_messages(req.question, req.user_profile, req.history)

    answer = await chat(
        input_messages=input_messages,
        tool_map=tool_map_cache,
        tools=tools_json_cache,
        connection_manager=connection_manager,
    )
    return ChatResponse(answer=answer)


@app.post("/extract_tool_call", response_model=ExtractToolCallResponse)
async def extract_tool_call_endpoint(req: ExtractToolCallRequest):
    input_messages = build_input_messages(req.question, req.user_profile)

    result = client.chat.completions.create(
        model=model,
        messages=input_messages,
        tools=tools_json_cache,
    )

    if result.choices[0].finish_reason == "tool_calls":
        tool_call = result.choices[0].message.tool_calls[0]
        return ExtractToolCallResponse(
            tool_name=tool_call.function.name,
            arguments=json.loads(tool_call.function.arguments),
        )

    return ExtractToolCallResponse(tool_name="other", arguments={})

