#!/usr/bin/env python3
# Copyright 2026
# SPDX-License-Identifier: Apache-2.0
"""HR copilot agent — exposes A2A `message/send`; CPEX fires on its egress.

This is the containerized agent for the hr-cpex demo. It speaks A2A
(via the official `a2a-sdk`) on the inbound side and calls the hr-mcp
tools on the outbound side. The authbridge-cpex sidecar enforces CPEX
on the **outbound** path (the agent's tool calls), so the whole policy
chain — identity, Cedar PDP, RFC 8693 delegation, redaction, PII scan,
session taint, audit — runs as a transparent egress guardrail on the
agent rather than at a gateway in front of the tool.

    A2A client (chat.py on the host — mints persona + client tokens)
        │  POST message/send   headers: X-User-Token, Authorization,
        │                               X-Session-Id ; contextId in body
        ▼
    authbridge-cpex sidecar — reverse proxy :8000  (inbound: passthrough)
        ▼
    THIS agent  :8001
        │  ① LLM loop:  litellm → host.docker.internal:11434   DIRECT, no proxy
        │  ② tool call: POST /mcp, re-attaching X-User-Token +
        │               Authorization + X-Session-Id from the inbound request
        ▼  via explicit per-client proxy → sidecar forward proxy :8081
    authbridge-cpex sidecar — forward proxy  (outbound: mcp-parser → cpex)
        │  identity (jwt-user ← X-User-Token, jwt-client ← Authorization)
        │  Cedar PDP · redact(args.ssn) · pii-scan · session taint
        │  delegate(workday/github-oauth) — RFC 8693 → Keycloak
        ▼
    hr-mcp  :9100

Two outbound flows, deliberately handled differently (the Ollama footgun):

  * LLM inference goes **DIRECT** to the model endpoint. We never set a
    global HTTP_PROXY on this container — if we did, litellm/httpx would
    route inference through the sidecar's forward proxy and cpex would
    try (and fail) to evaluate it as a tool call.
  * Only the MCP `tools/call` uses an explicit `httpx.Client(proxy=...)`
    pointed at the sidecar's forward proxy, so cpex sees exactly the
    traffic it's meant to govern. Mirrors the ibac demo's split
    (demos/ibac/agent/main.go: callOllama direct, proxiedClient for tools).

Identity threading is the crux: cpex resolves identity from headers on
the *outbound* request, and the subject it derives keys the session-taint
store. So every tool call must carry the user's X-User-Token and the
client's Authorization forward, and the X-Session-Id that scopes taint.
"""

import asyncio
import json
import logging
import os
import threading
import uuid
from typing import Any

import httpx
import litellm
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill, Message, Part, Role, TextPart
from a2a.utils import new_agent_text_message

load_dotenv()  # read config from a .env file if present (like the other examples)

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
log = logging.getLogger("hr-cpex-agent")

# ---------------------------------------------------------------------------
# Config (env-driven so the Pod manifest owns the wiring)
# ---------------------------------------------------------------------------

PORT = int(os.environ.get("PORT", "8001"))
# Where the MCP tool lives. The agent POSTs here; when MCP_PROXY is set httpx
# routes the call through it (the sidecar forward proxy) so cpex governs it.
# Defaults to a local server.py so a plain `uvicorn agent:app` + `uvicorn
# server:app` works with no sidecar; the cpex Pod manifest overrides this env.
MCP_URL = os.environ.get("MCP_URL", "http://localhost:9100/mcp")
# The sidecar forward proxy. ONLY the MCP client uses this — never as a global
# HTTP_PROXY (that would drag inference through cpex too). Empty by default: a
# local run connects directly to MCP_URL. The cpex Pod manifest sets this to the
# sidecar's forward proxy so tool calls are governed on egress.
MCP_PROXY = os.environ.get("MCP_PROXY", "")
# litellm-routed model. Defaults to local Ollama (no API key). Override with
# any LiteLLM-supported provider. Honors INFERENCE_MODEL/INFERENCE_BASE_URL too,
# so a .env shared with the other examples works; MODEL/LLM_API_BASE win when set.
MODEL = os.environ.get("MODEL") or os.environ.get("INFERENCE_MODEL", "ollama/llama3:latest")
# Inference endpoint. For the ollama provider this is the native base
# (litellm appends /api/...). Set to host.docker.internal in-cluster so
# the agent reaches an Ollama running on the developer's laptop.
LLM_API_BASE = os.environ.get("LLM_API_BASE") or os.environ.get("INFERENCE_BASE_URL") or None
# litellm needs a provider prefix to route. The shared .env supplies a bare
# model (e.g. "qwen3.5:latest") aimed at an OpenAI-compatible endpoint (the
# other examples feed it to LangChain's ChatOpenAI). When no prefix is present,
# treat it as an openai/ endpoint so raw litellm can reach the same server.
INFERENCE_API_KEY = os.environ.get("INFERENCE_API_KEY", "ollama")
if "/" not in MODEL:
    MODEL = f"openai/{MODEL}"
# What the agent advertises in its agent card as its callable address.
AGENT_PUBLIC_URL = os.environ.get("AGENT_PUBLIC_URL", "http://hr-cpex-agent.cpex-demo:8080/")

# ---------------------------------------------------------------------------
# Tools + prompt (lifted from the original chat.py). The SSN demo is
# response-side: include_ssn=true → the gateway redacts result.ssn for callers
# without view_ssn. The hardened prompt makes the model relay tool values
# verbatim so it doesn't fabricate `[REDACTED]` for a real SSN.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are an HR assistant for an HR copilot app. Help the user look up "
    "employee compensation, view directories, send emails, and similar "
    "tasks. Use the provided tools when needed. "
    "\n\n"
    "Only request data the user actually asked for: in particular, set "
    "get_compensation's `include_ssn` to true ONLY when the user explicitly "
    "asks to include/show the SSN. If the user just asks to look up "
    "compensation without mentioning the SSN, leave `include_ssn` false. "
    "\n\n"
    "CRITICAL — relay tool data verbatim: when you present a field, copy its "
    "value EXACTLY as it appears in the tool result. Never invent, mask, "
    "redact, or replace a value yourself. Only write `[REDACTED]` for a field "
    "if the tool result's value for that field is literally the string "
    "`[REDACTED]`; when the tool returns a real value (for example an actual "
    "social-security number), show that exact value unchanged. The gateway — "
    "not you — decides what to hide; your job is to relay precisely what it "
    "returned. "
    "\n\n"
    "How to interpret tool results: "
    "\n"
    "  * Normal result: present the data, copying each value verbatim per the "
    "rule above. A field whose value is `[REDACTED]` is the gateway's "
    "transparent enforcement marker (the field exists but is hidden for this "
    "caller) — show it as-is; do NOT apologize or refuse. "
    "\n"
    "  * If the tool returns an `error` envelope (a JSON-RPC error "
    "with a `code` and `message`), the gateway denied the call. "
    "Acknowledge politely without revealing the internal violation "
    "code — the user may not have permission for that operation. "
    "\n"
    "  * If the tool returns an `auth_error`, the request failed at "
    "the transport layer. Ask the user to re-authenticate."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_compensation",
            "description": (
                "Get compensation data for an employee. Returns salary, bonus, department, and optionally SSN."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {
                        "type": "string",
                        "description": "Employee identifier (e.g., EMP-001234)",
                    },
                    "include_ssn": {
                        "type": "boolean",
                        "description": (
                            "Whether to include the SSN in the response. Set to "
                            "true ONLY when the user explicitly asks for the SSN "
                            "(e.g. 'include the SSN'). If the user does not "
                            "mention the SSN, omit this or set it to false."
                        ),
                        "default": False,
                    },
                    # NB: no `ssn` request argument is exposed. The SSN demo is
                    # response-side: set include_ssn=true and the gateway redacts
                    # result.ssn for callers without view_ssn. An `ssn` echo-back
                    # arg used to live here, but models populate it
                    # inconsistently (""/null/omitted) and a null value trips the
                    # APL redact(args.ssn) type check (expected Str) → deny. The
                    # request-side args.ssn redaction is still exercised by the
                    # deterministic curl matrix (scenarios/01-bob-allow.sh).
                },
                "required": ["employee_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "display_compensation",
            "description": ("Display a compensation summary for the employee (band only, no salary)."),
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {"type": "string"},
                },
                "required": ["employee_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_directory",
            "description": "Get the employee directory listing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "department": {
                        "type": "string",
                        "description": "Optional department filter",
                        "default": "",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email (simulated).",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_repos",
            "description": (
                "Search the internal GitHub Enterprise for repositories. "
                "Filter by name substring and/or visibility. Visibility is "
                "one of `internal`, `public`, `external`."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "Substring to filter repo names (e.g. 'web-app').",
                        "default": "",
                    },
                    "visibility": {
                        "type": "string",
                        "description": (
                            "Repo visibility — `internal` (default), `public`, or `external`. "
                            "External repos are typically off-limits for engineering."
                        ),
                        "enum": ["internal", "public", "external"],
                    },
                },
                "required": ["visibility"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# MCP tool client — every call flows through the sidecar forward proxy so
# cpex governs it, carrying the caller's identity headers on egress.
# ---------------------------------------------------------------------------


def format_tool_response(status: int, data: dict[str, Any]) -> str:
    """Convert the MCP/cpex response into something compact the LLM can
    read. Same three shapes the gateway returned in the standalone demo:

      * HTTP 200 + {"result": ...}                          — happy path
      * HTTP 200 + {"error": {code, message, data}}         — cpex deny
      * HTTP 4xx/5xx + plain text                           — transport/auth
    """
    if status == 401:
        body = data.get("text") if isinstance(data, dict) else str(data)
        return json.dumps({"gateway_status": 401, "auth_error": body})
    if status >= 400:
        return json.dumps({"gateway_status": status, "error": data})
    if "error" in data:
        # MCP JSON-RPC 2.0 error frame (HTTP 200). The forward proxy renders
        # cpex denials this way for MCP requests; the violation code lives at
        # error.data.error (see authbridge/authlib/listener/httpx/render.go),
        # NOT error.data.violation.
        err = data["error"]
        return json.dumps(
            {
                "error": err.get("message", "tool error"),
                "violation": (err.get("data") or {}).get("error"),
            }
        )
    result = data.get("result", {})
    content = result.get("content", [])
    text_parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    combined = "".join(text_parts)
    return combined or json.dumps(result)


def call_tool(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    user_token: str,
    client_token: str,
    session_id: str,
    request_id: int,
) -> tuple[int, dict[str, Any]]:
    """POST a single MCP tools/call through the sidecar forward proxy.

    cpex (running on the sidecar's outbound pipeline) reads identity from
    the headers we re-attach here: jwt-user from X-User-Token, jwt-client
    from Authorization. X-Session-Id scopes the per-conversation taint
    bucket; the cpex session store binds it to the resolved subject, so
    the same id under a different user is a different bucket.
    """
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
        "id": request_id,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": client_token,  # already "Bearer <client token>"
        "X-User-Token": user_token,
        "X-Session-Id": session_id,
    }
    # Explicit per-client proxy — ONLY this flow goes through cpex. When
    # MCP_PROXY is empty (e.g. a local Smith run with no sidecar), connect
    # directly to MCP_URL so /chat can execute tools against a local server.py.
    client_kwargs: dict[str, Any] = {"timeout": 30}
    if MCP_PROXY:
        client_kwargs["proxy"] = MCP_PROXY
    try:
        with httpx.Client(**client_kwargs) as client:
            resp = client.post(MCP_URL, json=payload, headers=headers)
    except httpx.HTTPError as e:
        # Transport failure (timeout, connect refused, reset) — return a
        # structured tool error so the tool-calling loop can report it
        # rather than letting the exception abort the whole A2A turn.
        return 502, {"error": f"MCP transport error: {e}"}
    try:
        data = resp.json()
    except (json.JSONDecodeError, ValueError):
        data = {"text": resp.text}
    return resp.status_code, data


# ---------------------------------------------------------------------------
# Agent turn — the litellm tool-calling loop (synchronous; reused from the
# original chat.py). Per-conversation message history is keyed by session
# id so a continuing chat keeps context, while a `switch`/`relogin` on the
# client (fresh session id) starts clean — matching the old UX.
# ---------------------------------------------------------------------------


class HRAgent:
    def __init__(self) -> None:
        self._histories: dict[str, list[dict[str, Any]]] = {}
        self._request_id = 0
        # The A2A SDK can dispatch turns concurrently, and run_turn() runs on
        # worker threads (asyncio.to_thread). Guard the shared singleton state
        # — the _histories map (get-or-create) and the _request_id counter — so
        # concurrent turns can't corrupt the map or lose an increment. Distinct
        # session ids get distinct history lists, so per-turn work stays
        # lock-free; only these two shared touch-points are serialized.
        self._state_lock = threading.Lock()

    def _history(self, session_id: str) -> list[dict[str, Any]]:
        with self._state_lock:
            hist = self._histories.get(session_id)
            if hist is None:
                hist = [{"role": "system", "content": SYSTEM_PROMPT}]
                self._histories[session_id] = hist
            return hist

    def _next_request_id(self) -> int:
        with self._state_lock:
            self._request_id += 1
            return self._request_id

    def run_turn(
        self,
        user_text: str,
        *,
        user_token: str,
        client_token: str,
        session_id: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        """One user turn: LLM (direct) → tool calls (proxied/cpex) → LLM.

        Returns (reply_text, tool_trace). tool_trace is a list of
        {name, args, status, text} records — one per cpex-governed tool call —
        which the executor attaches to the A2A response metadata so a client
        can optionally render what happened on the wire (see chat.py
        --show-tools). The trace is always collected; the client decides
        whether to display it."""
        messages = self._history(session_id)
        messages.append({"role": "user", "content": user_text})

        # temperature=0: deterministic decoding. The demo needs the model to
        # relay tool values verbatim (not creatively re-word or redact), so the
        # lowest-temperature, highest-probability completion is what we want —
        # it measurably reduces a small model's tendency to fabricate
        # `[REDACTED]` or editorialize fields.
        completion_kwargs: dict[str, Any] = {"temperature": 0, "api_key": INFERENCE_API_KEY}
        if LLM_API_BASE:
            completion_kwargs["api_base"] = LLM_API_BASE

        try:
            response = litellm.completion(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                **completion_kwargs,
            )
        except Exception as e:  # noqa: BLE001 — surface any LLM error to the user
            messages.pop()
            log.warning("LLM error: %s", e)
            return f"(LLM error: {e})", []

        assistant = response.choices[0].message
        if not assistant.tool_calls:
            text = assistant.content or "(no response)"
            messages.append({"role": "assistant", "content": text})
            return text, []

        # Tool-call path: replay each call through cpex, then summarize.
        tool_trace: list[dict[str, Any]] = []
        messages.append(assistant.model_dump())
        for tc in assistant.tool_calls:
            fn = tc.function
            try:
                args = json.loads(fn.arguments) if isinstance(fn.arguments, str) else fn.arguments
            except json.JSONDecodeError:
                args = {}
            request_id = self._next_request_id()
            log.info(
                "tool call (session=%s): %s(%s)",
                session_id,
                fn.name,
                json.dumps(args, separators=(",", ":")),
            )
            status, data = call_tool(
                fn.name,
                args,
                user_token=user_token,
                client_token=client_token,
                session_id=session_id,
                request_id=request_id,
            )
            tool_text = format_tool_response(status, data)
            log.info("tool result (session=%s, http=%s): %s", session_id, status, tool_text)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_text})
            tool_trace.append({"name": fn.name, "args": args, "status": status, "text": tool_text})

        try:
            final = litellm.completion(model=MODEL, messages=messages, **completion_kwargs)
            text = final.choices[0].message.content or ""
        except Exception as e:  # noqa: BLE001
            text = f"(LLM error summarizing tool results: {e})"
        messages.append({"role": "assistant", "content": text})
        return text, tool_trace


# ---------------------------------------------------------------------------
# A2A executor — bridges the SDK's message/send into a turn of the agent.
# ---------------------------------------------------------------------------


class HRAgentExecutor(AgentExecutor):
    def __init__(self) -> None:
        self._agent = HRAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input()

        # The a2a-sdk's DefaultCallContextBuilder stows the raw inbound
        # HTTP headers under call_context.state['headers'] (lowercased).
        # This is where the identity the client minted arrives — we read
        # it here and thread it forward onto the tool call so cpex can
        # resolve the same user/client on the outbound path.
        headers: dict[str, str] = {}
        if context.call_context is not None:
            headers = context.call_context.state.get("headers", {}) or {}
        user_token = headers.get("x-user-token", "")
        authorization = headers.get("authorization", "")

        # Session id scopes cpex taint. Prefer the A2A contextId (what the
        # client put in the message); fall back to an explicit header, then
        # mint one so a header-less caller still gets a stable bucket.
        session_id = context.context_id or headers.get("x-session-id") or uuid.uuid4().hex

        if not user_token or not authorization:
            await event_queue.enqueue_event(
                new_agent_text_message(
                    "Missing identity: the request reached the agent without "
                    "both X-User-Token and Authorization. Re-authenticate on "
                    "the client.",
                    context.context_id,
                    context.task_id,
                )
            )
            return

        log.info("A2A turn (session=%s): %s", session_id, user_text)
        # litellm + httpx are synchronous; run off the event loop so we
        # don't block the server while the model and tools work.
        reply, tool_trace = await asyncio.to_thread(
            self._agent.run_turn,
            user_text,
            user_token=user_token,
            client_token=authorization,
            session_id=session_id,
        )
        # Carry the per-turn tool trace in the response message metadata so a
        # client can optionally show what hit cpex/hr-mcp (see chat.py
        # --show-tools). new_agent_text_message has no metadata param, so build
        # the Message directly.
        message = Message(
            role=Role.agent,
            parts=[Part(root=TextPart(text=reply))],
            message_id=uuid.uuid4().hex,
            context_id=context.context_id,
            task_id=context.task_id,
            metadata={"tool_trace": tool_trace},
        )
        await event_queue.enqueue_event(message)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Single-shot turns; nothing long-running to cancel.
        raise NotImplementedError("cancel is not supported")


def build_agent_card() -> AgentCard:
    return AgentCard(
        name="HR Copilot",
        description=(
            "HR assistant that looks up employee compensation, directories, "
            "and sends email via an HR MCP tool. In this demo the agent's "
            "authbridge-cpex sidecar enforces CPEX/APL policy on the agent's "
            "outbound tool calls — identity, Cedar authorization, SSN "
            "redaction, PII scanning, RFC 8693 delegation, and cross-tool "
            "session taint all fire on egress."
        ),
        url=AGENT_PUBLIC_URL,
        version="0.1.0",
        protocol_version="0.3.0",
        preferred_transport="JSONRPC",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[
            AgentSkill(
                id="hr_copilot",
                name="HR copilot",
                description=(
                    "Answer HR questions by calling tools: compensation "
                    "lookup (with policy-gated SSN), employee directory, and "
                    "email. Outbound calls are governed by CPEX in the agent's "
                    "sidecar."
                ),
                tags=["demo", "hr", "cpex"],
                examples=[
                    "Look up compensation for EMP-001234, include the SSN.",
                    "Search internal repos for 'web-app'.",
                ],
            )
        ],
    )


# ---------------------------------------------------------------------------
# Smith HTTP shim — the two endpoints every example agent exposes so Smith can
# drive the agent over a uniform contract, alongside the A2A/cpex path above:
#
#     POST /chat               {question} -> {response}
#     POST /extract_tool_call  {question} -> {tool_name, arguments}
#
# Both reuse the agent's existing SYSTEM_PROMPT + TOOLS. /chat runs a full turn
# (identity headers are empty here — this path is for talking to the agent, not
# for exercising cpex). /extract_tool_call surfaces the model's intended tool
# call WITHOUT executing it.
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    response: str


class ExtractToolCallResponse(BaseModel):
    tool_name: str
    arguments: dict[str, Any]


# Module-level ASGI app so Smith serves it the same way as the other examples:
# `uvicorn agent:app --host 0.0.0.0 --port 9000`. (Running `python agent.py`
# instead starts the A2A/cpex container agent via main().)
app = FastAPI()
_agent = HRAgent()


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    reply, _ = _agent.run_turn(req.question, user_token="", client_token="", session_id="smith")
    return ChatResponse(response=reply)


@app.post("/extract_tool_call", response_model=ExtractToolCallResponse)
def extract_tool_call(req: ChatRequest) -> ExtractToolCallResponse:
    completion_kwargs: dict[str, Any] = {"temperature": 0, "api_key": INFERENCE_API_KEY}
    if LLM_API_BASE:
        completion_kwargs["api_base"] = LLM_API_BASE
    response = litellm.completion(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": req.question},
        ],
        tools=TOOLS,
        tool_choice="auto",
        **completion_kwargs,
    )
    tool_calls = response.choices[0].message.tool_calls
    if tool_calls:
        fn = tool_calls[0].function
        try:
            args = json.loads(fn.arguments) if isinstance(fn.arguments, str) else (fn.arguments or {})
        except json.JSONDecodeError:
            args = {}
        return ExtractToolCallResponse(tool_name=fn.name, arguments=args)
    return ExtractToolCallResponse(tool_name="other", arguments={})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _tool_definitions() -> dict[str, Any]:
    """Convert this agent's TOOLS (OpenAI function format) into the same
    structure Smith's MCP extractor emits into tool_definitions.json:

        {"tools": [{"name", "description", "parameters":[...], "input_schema"}],
         "source": ..., "transport": ...}

    Each parameter carries name/type/required plus optional description/default/
    candidates (from JSON-Schema enum) — mirroring extract_tools.tool_to_dict so
    the file is interchangeable with the other examples'.
    """
    tools = []
    for t in TOOLS:
        fn = t["function"]
        schema = fn.get("parameters", {}) or {}
        properties = schema.get("properties", {}) or {}
        required = schema.get("required", []) or []
        parameters = []
        for pname, pinfo in properties.items():
            param = {
                "name": pname,
                "type": pinfo.get("type", "any"),
                "required": pname in required,
            }
            if "description" in pinfo:
                param["description"] = pinfo["description"]
            if "default" in pinfo:
                param["default"] = pinfo["default"]
            if "enum" in pinfo:
                param["candidates"] = pinfo["enum"]
            if "items" in pinfo:
                param["items"] = pinfo["items"]
            parameters.append(param)
        tools.append(
            {
                "name": fn["name"],
                "description": fn.get("description", ""),
                "parameters": parameters,
                "input_schema": schema,
            }
        )
    return {"tools": tools, "source": "agent.py TOOLS", "transport": "agent"}


@app.get("/tool_definitions")
def tool_definitions() -> dict[str, Any]:
    """Expose the tool definitions so Smith can extract them from the agent
    itself (no MCP server needed)."""
    return _tool_definitions()


def main() -> None:
    handler = DefaultRequestHandler(
        agent_executor=HRAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    a2a_app = A2AStarletteApplication(agent_card=build_agent_card(), http_handler=handler).build()
    log.info("HR copilot A2A agent on :%d (MCP via proxy %s → %s)", PORT, MCP_PROXY, MCP_URL)
    uvicorn.run(a2a_app, host="0.0.0.0", port=PORT, log_level=os.environ.get("LOG_LEVEL", "info").lower())


if __name__ == "__main__":
    main()