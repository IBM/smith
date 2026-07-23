"""LangGraph ReAct agent over the Employee Hub MCP tools.

Requires ANTHROPIC_API_KEY in the environment. Launches server.py over stdio,
loads its @mcp.tool()s, and runs a simple REPL.
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

load_dotenv()  # read ANTHROPIC_API_KEY (and friends) from .env if present

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
    server_path = str(Path(__file__).parent / "server.py")
    client = MultiServerMCPClient({
        "employee_hub": {
            "command": sys.executable,
            "args": [server_path],
            "transport": "stdio",
        }
    })
    tools = await client.get_tools()
    model = ChatAnthropic(model="claude-sonnet-5", **_model_kwargs())
    return create_react_agent(model, tools, prompt=SYSTEM_PROMPT)


def _model_kwargs() -> dict:
    """Point ChatAnthropic at a custom endpoint from .env when configured.

    LLM_API_KEY  -> api_key   (falls back to the usual ANTHROPIC_API_KEY)
    LLM_API_BASE -> base_url  (e.g. a LiteLLM proxy)
    LLM_API_VERSION is intentionally ignored: it is an Azure-style api-version
    with no equivalent on the Anthropic messages API.
    """
    kwargs = {}
    api_key = os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_API_BASE")
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    return kwargs


async def main():
    agent = await build_agent()
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
