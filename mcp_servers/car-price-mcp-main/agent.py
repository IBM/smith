import os
from contextlib import asynccontextmanager
from typing import Dict, Any
from openai import OpenAI
from fastapi import FastAPI
from pydantic import BaseModel

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from dotenv import load_dotenv
load_dotenv()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str


agent = None
mcp_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent, mcp_client

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
        api_key = os.getenv("OPENAI_API_KEY", None)
        api_url = os.getenv("OPENAI_BASE_URL", None)
        model = os.getenv("MODEL", None)
        if api_key is None or api_url is None:
            raise ValueError("OPENAI_API_KEY or OPENAI_API_BASE_URL url not defined in environment. Create a .env file")

        # for rits model
        llm = ChatOpenAI(
                model=model,
                api_key=api_key,
                base_url = api_url,
                default_headers = {'RITS_API_KEY': api_key})

        agent = create_react_agent(
            model=llm,
            tools=tools,
        )

        yield

app = FastAPI(lifespan=lifespan)


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    result = await agent.ainvoke(
        {
            "messages": [
                ("user", req.message)
            ]
        }
    )
    final_message = result["messages"][-1].content

    return ChatResponse(response=final_message)


@app.get("/health")
async def health():
    return {"status": "ok"}