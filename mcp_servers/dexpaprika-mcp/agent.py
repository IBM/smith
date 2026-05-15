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


SYSTEM_PROMPT_BASE = "You are a DeFi data assistant that helps users query decentralized exchange data including liquidity pools, token prices, trading volumes, and historical market data across blockchain networks."


class ChatRequest(BaseModel):
    message: str
    system_variables: Optional[Dict[str, str]] = None


class ChatResponse(BaseModel):
    response: str


agent = None
mcp_client = None


def build_system_prompt(system_variables: Optional[Dict[str, str]] = None) -> str:
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
    global agent, mcp_client

    async with MultiServerMCPClient(
        {
            "dexpaprika-mcp": {
                "transport": "stdio",
                "command": "node",
                "args": ["dist/index.js"],
            }
        }
    ) as mcp_client:
        tools = mcp_client.get_tools()

        api_key = os.getenv("OPENAI_API_KEY", None)
        api_url = os.getenv("OPENAI_BASE_URL", None)
        model = os.getenv("MODEL", None)

        if api_key is None or api_url is None:
            raise ValueError(
                "OPENAI_API_KEY or OPENAI_BASE_URL not defined in environment. Create a .env file."
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

        yield


app = FastAPI(lifespan=lifespan)


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    system_prompt = build_system_prompt(req.system_variables)

    result = await agent.ainvoke(
        {
            "messages": [
                ("system", system_prompt),
                ("user", req.message),
            ]
        }
    )

    final_message = result["messages"][-1].content
    return ChatResponse(response=final_message)


@app.get("/health")
async def health():
    return {"status": "ok"}
