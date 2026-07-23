"""HTTP layer over the Employee Hub LangGraph agent (Starlette + uvicorn).

Wraps the same agent used by agent.py's REPL. Keeps a single in-memory
conversation (this is a local single-user tool) and exposes:

  POST /chat   {"message": "..."}  -> {"reply": "...", "steps": [...]}
  POST /reset                      -> {"ok": true}

`steps` is a chronological, alternating call/result timeline of the tools the
agent used during the turn, for display in the UI's side panel.

Run:  uv run python web.py   (needs ANTHROPIC_API_KEY)
"""
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from langchain_core.messages import ToolMessage

load_dotenv()  # read ANTHROPIC_API_KEY (and friends) from .env if present
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from agent import build_agent
from db import get_connection, init_db
from seed import seed

# The agent and the running conversation, initialised at startup.
_agent = None
_messages: list = []


def extract_steps(messages) -> list:
    """Turn a slice of agent messages into an ordered call/result timeline.

    Each tool call on an AIMessage becomes a `call` step (name + args); each
    ToolMessage becomes a `result` step (name + stringified content). Message
    order is preserved, so every call is immediately followed by its result.
    """
    steps = []
    for m in messages:
        tool_calls = getattr(m, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                steps.append({
                    "type": "call",
                    "name": tc.get("name"),
                    "args": tc.get("args", {}),
                })
        elif isinstance(m, ToolMessage):
            content = m.content
            if not isinstance(content, str):
                content = str(content)
            steps.append({
                "type": "result",
                "name": getattr(m, "name", None),
                "content": content,
            })
    return steps


def reply_text(content) -> str:
    """Flatten an AIMessage's content to plain text.

    Content may be a string, or (with extended thinking / tool use) a list of
    blocks like {"type": "text", "text": ...} and {"type": "thinking", ...}.
    Keep only the text blocks; drop thinking and other non-text blocks.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(p for p in parts if p)
    return str(content)


async def chat(request: Request) -> JSONResponse:
    body = await request.json()
    message = (body or {}).get("message", "")
    if not message:
        return JSONResponse({"error": "message is required"}, status_code=400)

    start = len(_messages)
    _messages.append({"role": "user", "content": message})
    try:
        result = await _agent.ainvoke({"messages": _messages})
    except Exception as exc:  # surface agent failures to the UI
        # Drop the user turn we optimistically appended so state stays clean.
        del _messages[start:]
        return JSONResponse({"error": str(exc)}, status_code=500)

    new_messages = result["messages"][start:]
    _messages[:] = result["messages"]
    reply = reply_text(_messages[-1].content) if _messages else ""
    return JSONResponse({"reply": reply, "steps": extract_steps(new_messages)})


async def reset(request: Request) -> JSONResponse:
    _messages.clear()
    return JSONResponse({"ok": True})


@asynccontextmanager
async def _lifespan(app):
    global _agent
    # Reset the on-disk DB to a fresh demo dataset on every boot. This commits
    # before the agent launches server.py (a stdio subprocess with its own
    # connection), so the agent reads the seeded data.
    conn = get_connection()
    init_db(conn)
    seed(conn)
    conn.close()
    _agent = await build_agent()
    yield


app = Starlette(
    routes=[
        Route("/chat", chat, methods=["POST"]),
        Route("/reset", reset, methods=["POST"]),
    ],
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ],
    lifespan=_lifespan,
)


if __name__ == "__main__":
    if not (os.environ.get("LLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")):
        sys.exit("No API key found; set LLM_API_KEY (or ANTHROPIC_API_KEY) in .env.")
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
