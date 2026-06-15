import os
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from dotenv import load_dotenv
load_dotenv()


SYSTEM_PROMPT_BASE = "You are a helpful car pricing assistant that helps users find car brands, models, and prices from the Brazilian FIPE database."


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
mcp_client = None
llm_with_tools = None


def build_system_prompt(system_variables: Optional[Dict[str, Any]] = None) -> str:
    prompt = SYSTEM_PROMPT_BASE

    if system_variables:
        prompt += "\n\n## Active System Variables\n"
        prompt += "The following context variables are in effect for this session. "
        prompt += "Respect any policies or constraints implied by these variables.\n\n"
        for key, value in system_variables.items():
            prompt += f"- **{key}**: {value}\n"

    return prompt


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent, mcp_client, llm_with_tools

    async with MultiServerMCPClient(
        {
            "car-price-mcp": {
                "transport": "stdio",
                "command": "python",
                "args": ["server.py"],
            }
        }
    ) as mcp_client:
        tools = mcp_client.get_tools()

        api_key = os.getenv("RITS_API_KEY", None)
        api_url = os.getenv("RITS_BASE_URL", None)
        model = os.getenv("RITS_MODEL", None)

        if api_key is None or api_url is None or model is None:
            raise ValueError(
                "RITS_API_KEY, RITS_BASE_URL, or RITS_MODEL not defined in environment. Create a .env file."
            )

        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=api_url,
            default_headers={"RITS_API_KEY": api_key},
        )

        agent = create_react_agent(
            model=llm,
            tools=tools,
        )

        llm_with_tools = llm.bind_tools(tools)

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

    return ExtractToolCallResponse(tool_name="other", arguments={})


@app.get("/health")
async def health():
    return {"status": "ok"}
