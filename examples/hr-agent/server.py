"""HR Demo MCP Server — HTTP/JSON-RPC variant.

A small FastAPI app that speaks MCP-shaped JSON-RPC over HTTP so a
gateway can route to it.

The headline log line is intentional: every inbound request prints
the Authorization header (so audiences can see the IdP-minted token,
NOT the user's original IdP JWT) and the parsed tool arguments
(so they can see args.ssn redacted to `[REDACTED]` when policy
fires).

Run locally:
    pip install -r requirements.txt
    uvicorn server:app --host 0.0.0.0 --port 9100

Endpoint:
    POST /mcp   — JSON-RPC 2.0 `tools/call` requests

Tools:
    get_compensation, send_email, display_compensation, get_directory
"""

import json
import logging
import sys
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("hr-mcp-server")

app = FastAPI(title="HR Demo MCP Server")

# ---------------------------------------------------------------------------
# Mock data (copied from sibling-repos/apl-plugins/demo/hr_demo_server.py)
# ---------------------------------------------------------------------------

EMPLOYEES: dict[str, dict[str, Any]] = {
    "EMP-001234": {
        "employee_id": "EMP-001234",
        "name": "Jane Smith",
        "salary": 125000,
        "bonus": 15000,
        "ssn": "123-45-6789",
        "department": "Engineering",
        "internal_notes": "Performance review pending, do not disclose",
        "email": "jane.smith@corp.com",
        "title": "Senior Software Engineer",
    },
    "EMP-005678": {
        "employee_id": "EMP-005678",
        "name": "Bob Johnson",
        "salary": 145000,
        "bonus": 25000,
        "ssn": "234-56-7890",
        "department": "Marketing",
        "internal_notes": "Promotion candidate Q2",
        "email": "bob.johnson@corp.com",
        "title": "Marketing Manager",
    },
    "EMP-009012": {
        "employee_id": "EMP-009012",
        "name": "Alice Chen",
        "salary": 145000,
        "bonus": 20000,
        "ssn": "456-78-9012",
        "department": "Engineering",
        "internal_notes": "Team lead, retention risk",
        "email": "alice.chen@corp.com",
        "title": "Principal Engineer",
    },
}

SENT_EMAILS: list[dict[str, Any]] = []

# Fake repo fixtures — names + visibility match what Cedar policy
# expects in `args.repo_name` / `args.visibility`.
REPOS: list[dict[str, Any]] = [
    {"name": "internal/web-app",       "visibility": "internal", "stars": 24, "language": "TypeScript"},
    {"name": "internal/api-gateway",   "visibility": "internal", "stars": 18, "language": "Rust"},
    {"name": "internal/data-pipeline", "visibility": "internal", "stars": 11, "language": "Python"},
    {"name": "public/showcase-site",   "visibility": "public",   "stars": 2840, "language": "Astro"},
    {"name": "external/partner-sdk",   "visibility": "external", "stars": 47, "language": "Go"},
]

# ---------------------------------------------------------------------------
# Tool implementations (logic copied from the stdio server)
# ---------------------------------------------------------------------------


def tool_get_compensation(args: dict[str, Any]) -> dict[str, Any]:
    employee_id = args.get("employee_id", "")
    include_ssn = args.get("include_ssn", False)
    employee = EMPLOYEES.get(employee_id)
    if not employee:
        return {"error": f"Employee {employee_id} not found"}
    result = {
        "employee_id": employee["employee_id"],
        "name": employee["name"],
        "salary": employee["salary"],
        "bonus": employee["bonus"],
        "department": employee["department"],
        "title": employee["title"],
        "internal_notes": employee["internal_notes"],
    }
    if include_ssn:
        # NB: this is the field gateway redaction should have stripped
        # before we ever see it. If the upstream actually sees a real
        # SSN here, the redact policy didn't fire.
        result["ssn"] = employee["ssn"]
    return result


def tool_send_email(args: dict[str, Any]) -> dict[str, Any]:
    email = {"to": args.get("to", ""), "subject": args.get("subject", ""), "body": args.get("body", "")}
    SENT_EMAILS.append(email)
    return {
        "status": "sent",
        "message_id": f"msg-{len(SENT_EMAILS):04d}",
        "to": email["to"],
        "subject": email["subject"],
    }


def tool_display_compensation(args: dict[str, Any]) -> dict[str, Any]:
    employee_id = args.get("employee_id", "")
    employee = EMPLOYEES.get(employee_id)
    if not employee:
        return {"error": f"Employee {employee_id} not found"}
    return {
        "employee_id": employee["employee_id"],
        "name": employee["name"],
        "department": employee["department"],
        "title": employee["title"],
        "salary_band": (
            "senior" if employee["salary"] >= 120000 else
            "mid" if employee["salary"] >= 80000 else
            "junior"
        ),
        "has_bonus": employee["bonus"] > 0,
    }


def tool_get_directory(args: dict[str, Any]) -> list[dict[str, Any]]:
    department = args.get("department", "")
    entries = []
    for emp in EMPLOYEES.values():
        if department and emp["department"].lower() != department.lower():
            continue
        entries.append({
            "name": emp["name"],
            "department": emp["department"],
            "title": emp["title"],
            "email": emp["email"],
        })
    return entries


def tool_search_repos(args: dict[str, Any]) -> dict[str, Any]:
    # Simulated GitHub Enterprise search. The interesting demo
    # property: this returns the repo IF the gateway allowed the
    # call through. The Cedar policy + post-delegate check
    # determines whether the request reaches this code at all.
    repo_name = args.get("repo_name", "")
    visibility = args.get("visibility", "")
    matches = []
    for r in REPOS:
        if repo_name and repo_name.lower() not in r["name"].lower():
            continue
        if visibility and r["visibility"].lower() != visibility.lower():
            continue
        matches.append(r)
    return {"matches": matches, "query": {"repo_name": repo_name, "visibility": visibility}}


TOOLS = {
    "get_compensation": tool_get_compensation,
    "send_email": tool_send_email,
    "display_compensation": tool_display_compensation,
    "get_directory": tool_get_directory,
    "search_repos": tool_search_repos,
}

# ---------------------------------------------------------------------------
# JSON-RPC endpoint
# ---------------------------------------------------------------------------


def _redact_token(value: str) -> str:
    """Trim long bearer tokens in logs so audiences can see the prefix
    without 800 chars of base64 noise."""
    if value.startswith("Bearer ") and len(value) > 50:
        return f"{value[:40]}…[{len(value)-40} chars elided]"
    return value


def _log_safe(value: Any) -> str:
    """Neutralize a user-controlled value for single-line logging: coerce to
    str and replace CR/LF and other control characters with spaces so a
    crafted request field can't forge or split log entries (CWE-117)."""
    s = value if isinstance(value, str) else str(value)
    return "".join(ch if ch.isprintable() else " " for ch in s)


@app.post("/mcp")
async def mcp_endpoint(request: Request) -> JSONResponse:
    body_bytes = await request.body()

    # Demo headline: print what reached us. This is what the audience
    # watches to see the gateway's effects.
    logger.info("=" * 64)
    logger.info("INBOUND REQUEST  (this is what reached the MCP server)")
    interesting_headers = [
        "authorization", "x-user-token", "x-cpex-violation",
    ]
    for name in interesting_headers:
        v = request.headers.get(name)
        if v is not None:
            logger.info("  %-25s = %s", name, _redact_token(v))
    try:
        rpc = json.loads(body_bytes)
        logger.info("  body.method               = %s", _log_safe(rpc.get("method")))
        params = rpc.get("params", {})
        logger.info("  body.params.name          = %s", _log_safe(params.get("name")))
        logger.info(
            "  body.params.arguments     = %s",
            _log_safe(json.dumps(params.get("arguments", {}))),
        )
    except Exception as e:
        logger.warning("body is not JSON-RPC: %s", e)
        return JSONResponse(
            {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None},
            status_code=400,
        )

    method = rpc.get("method", "")
    rpc_id = rpc.get("id")
    if method != "tools/call":
        # tools/list and others — minimal stub so MCP clients don't
        # error during discovery, but the demo never exercises these.
        return JSONResponse(
            {"jsonrpc": "2.0", "result": {"tools": list(TOOLS.keys())}, "id": rpc_id},
        )

    tool_name = params.get("name", "")
    args = params.get("arguments", {}) or {}
    impl = TOOLS.get(tool_name)
    if impl is None:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                "id": rpc_id,
            },
            status_code=404,
        )

    try:
        out = impl(args)
    except Exception:
        # Full detail (including the stack trace) goes to the server log;
        # the client gets a generic message so internal state isn't exposed.
        logger.exception("tool '%s' failed", _log_safe(tool_name))
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": "internal tool error"},
                "id": rpc_id,
            },
            status_code=500,
        )

    logger.info("OUTBOUND RESPONSE")
    logger.info("  tool                      = %s", _log_safe(tool_name))
    logger.info("  payload                   = %s", json.dumps(out)[:200])
    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "result": {
                "content": [{"type": "text", "text": json.dumps(out, indent=2)}]
            },
            "id": rpc_id,
        },
    )


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}