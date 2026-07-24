"""LangGraph ReAct agent over the Employee Hub MCP tools.

Reads INFERENCE_MODEL / INFERENCE_BASE_URL / INFERENCE_API_KEY from the
environment (consistent with the other example agents). Launches server.py
over stdio, loads its @mcp.tool()s, and serves /chat and /extract_tool_call
(with a simple REPL still available via `python agent.py`).
"""
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

load_dotenv()  # read INFERENCE_* (and friends) from .env if present

SYSTEM_PROMPT = (
    "You are the Enterprise Employee Hub assistant. You manage employees, the "
    "org chart, departments, personal records (passport, visa, emergency "
    "contact, bank account), country holidays, and time-off (allotments, "
    "requests, and per-type balances). All dates are ISO YYYY-MM-DD. Leave "
    "types are exactly: Vacation, Sick Leave, Maternity, Paternity, Jury Duty, "
    "Unpaid. Request statuses are exactly: Pending, Approved, Denied. Use the "
    "provided tools; if a tool returns an 'error' key, explain it to the user."
)


async def build_agent():
    """Build the ReAct agent and a tool-bound LLM.

    Returns (agent, llm_with_tools). The agent runs tools (used by /chat and
    the REPL); llm_with_tools is a single non-executing call used by
    /extract_tool_call to surface the intended tool + arguments.
    """
    server_path = str(Path(__file__).parent / "server.py")
    client = MultiServerMCPClient({
        "employee_hub": {
            "command": sys.executable,
            "args": [server_path],
            "transport": "stdio",
        }
    })
    tools = await client.get_tools()

    api_key = os.getenv("INFERENCE_API_KEY", "ollama")
    api_url = os.getenv("INFERENCE_BASE_URL", "http://localhost:11434/v1")
    model_name = os.getenv("INFERENCE_MODEL", "qwen3.5:latest")

    model = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_url,
    )
    agent = create_react_agent(model, tools, prompt=SYSTEM_PROMPT)
    return agent, model.bind_tools(tools)


class ChatRequest(BaseModel):
    question: str
    user_profile: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    response: str


class ExtractToolCallRequest(BaseModel):
    question: str
    user_profile: Optional[Dict[str, Any]] = None


class ExtractToolCallResponse(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]


agent = None
llm_with_tools = None


def build_system_prompt(system_variables: Optional[Dict[str, Any]] = None) -> str:
    prompt = SYSTEM_PROMPT

    if system_variables:
        prompt += "\n\n## Active System Variables\n"
        prompt += "The following context variables are in effect for this session. "
        prompt += "Respect any policies or constraints implied by these variables.\n\n"
        for key, value in system_variables.items():
            prompt += f"- **{key}**: {value}\n"

    return prompt


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent, llm_with_tools
    agent, llm_with_tools = await build_agent()
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    system_prompt = build_system_prompt(req.user_profile)

    result = await agent.ainvoke(
        {
            "messages": [
                ("system", system_prompt),
                ("user", req.question),
            ]
        }
    )

    final_message = result["messages"][-1].content
    return ChatResponse(response=final_message)


@app.post("/extract_tool_call", response_model=ExtractToolCallResponse)
async def extract_tool_call(req: ExtractToolCallRequest):
    system_prompt = build_system_prompt(req.user_profile)

    # Single non-executing model call: we only want the intended tool and its
    # parameter values, so we do NOT run the tool (no DB write is performed).
    result = await llm_with_tools.ainvoke(
        [
            ("system", system_prompt),
            ("user", req.question),
        ]
    )

    if result.tool_calls:
        tool_call = result.tool_calls[0]
        return ExtractToolCallResponse(
            tool_name=tool_call["name"],
            arguments=tool_call.get("args", {}),
        )

    # No tool was called.
    return ExtractToolCallResponse(tool_name="other", arguments={})


@app.get("/health")
async def health():
    return {"status": "ok"}


async def main():
    agent, _ = await build_agent()
    print("Employee Hub agent ready. Type a request (Ctrl-D to exit).")
    messages = []
    loop = asyncio.get_event_loop()
    while True:
        try:
            user = await loop.run_in_executor(None, input, "\n> ")
        except EOFError:
            break
        messages.append({"role": "user", "content": user})
        try:
            result = await agent.ainvoke({"messages": messages})
        except Exception as exc:
            print(f"Error: {exc}")
            continue
        messages = result["messages"]
        print(messages[-1].content)


if __name__ == "__main__":
    asyncio.run(main())
