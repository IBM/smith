# Architecture: hr-agent (HR Copilot)

## Layers

### A2A Client Layer
- File: `chat.py` (external client, not deployed with agent)
- Role: Mints persona and client JWTs, sends `message/send` requests to the sidecar reverse proxy.
- Inputs: User free text; user identity credentials for JWT minting.
- Outputs: A2A `message/send` POST with headers `X-User-Token` (user JWT), `Authorization` (client JWT Bearer), `X-Session-Id`, and A2A JSON body with `contextId`.
- Current enforcement: JWT minting — identity is cryptographically bound at this layer.

### Sidecar Reverse Proxy (inbound) — authbridge-cpex :8000
- File: authbridge-cpex sidecar (not in this repo; deployed as a container sidecar)
- Role: Transparent inbound passthrough for A2A `message/send` traffic into the agent.
- Inputs: HTTP request with `X-User-Token`, `Authorization`, `X-Session-Id`.
- Outputs: Forwarded request to agent :8001 with headers preserved.
- Current enforcement: Inbound passthrough only — no enforcement at this boundary.

### Agent Layer — HR Copilot :8001
- File: `agent.py`
- Role: A2A executor; runs a litellm LLM tool-calling loop to decide which tool to call and constructs tool-call arguments, then re-attaches caller identity headers and forwards calls to the forward proxy.
- Inputs: `X-User-Token` (user JWT), `Authorization` (client JWT), `X-Session-Id`, user free-text message.
- Outputs: JSON-RPC 2.0 `tools/call` POST to sidecar forward proxy :8081, carrying `name` (tool name), `arguments` (LLM-chosen parameters), and identity headers.
- Current enforcement: Checks that both `X-User-Token` and `Authorization` headers are present; rejects with an error message if either is missing. No role-based or parameter-level enforcement at this layer. LLM is instructed (via SYSTEM_PROMPT) to set `include_ssn=true` only on explicit user request, but this is advisory only (not enforced).

### Sidecar Forward Proxy (outbound) — authbridge-cpex :8081
- File: authbridge-cpex sidecar (not in this repo)
- Role: CPEX enforcement point on all outbound tool calls — resolves identity from `X-User-Token` / `Authorization`, runs Cedar PDP, redacts `args.ssn`, performs PII scan, enforces RFC 8693 delegation to Keycloak, and maintains per-session taint state. Populates `input.extensions.subject.*` for any policy engine wired into this path.
- Inputs: JSON-RPC `tools/call` with `name`, `arguments`, and identity headers.
- Outputs: Allowed calls forwarded to MCP server :9100; denied calls returned as JSON-RPC error envelopes to the agent.
- Current enforcement: Cedar PDP (authorization), JWT identity resolution, SSN redaction, PII scan, session taint, RFC 8693 delegation — this is the primary enforcement layer in production.

### MCP Tool Server — hr-mcp :9100
- File: `server.py`
- Role: Implements the 6 HR tools as JSON-RPC `tools/call` handlers over HTTP; executes business logic against in-memory fixture data.
- Inputs: JSON-RPC 2.0 body with `params.name` (tool name) and `params.arguments` (tool arguments).
- Outputs: JSON-RPC result containing tool response data (salary, directory, email confirmation, etc.).
- Current enforcement: None — no auth, no role checks, no parameter validation at this layer. Trust is fully delegated to the forward proxy upstream.

### External Services (simulated)
- File: `server.py` (in-memory fixture data; GitHub Enterprise and email are simulated)
- Role: Backing data store / service layer for tool responses.
- Inputs: Tool arguments passed through from the MCP server.
- Outputs: Mock data records.
- Current enforcement: None.

---

## Trust Boundaries

| Field | Source | Classification |
|---|---|---|
| `X-User-Token` | A2A client (JWT minted by chat.py) | Verified — cryptographically signed JWT; cpex resolves `subject.*` from claims |
| `Authorization` (Bearer client JWT) | A2A client (JWT minted by chat.py) | Verified — cryptographically signed JWT |
| `X-Session-Id` | A2A client (or agent-generated UUID fallback) | Self-reported — no cryptographic binding; used to scope taint bucket |
| `input.extensions.subject.roles` | Resolved by cpex sidecar from user JWT claims | Verified — extracted from verified JWT by cpex |
| `input.extensions.subject.permissions` | Resolved by cpex sidecar from user JWT claims | Verified — extracted from verified JWT by cpex |
| `input.extensions.subject.has_approval` | Resolved by cpex sidecar from user JWT claims | Verified — extracted from verified JWT by cpex |
| `input.name` (tool name) | LLM in agent layer | Self-reported — LLM-generated, not user-supplied directly |
| `input.arguments.employee_id` | LLM-chosen from user message | Self-reported — LLM-generated |
| `input.arguments.include_ssn` | LLM-chosen (instructed to set only on explicit user request) | Self-reported — LLM-generated; advisory prompt only |
| `input.arguments.amount` | LLM-chosen from user message | Self-reported — LLM-generated; no bounds check before policy |
| `input.arguments.visibility` | LLM-chosen (enum: internal / public / external) | Self-reported — LLM-generated |
| `input.arguments.repo_name` | LLM-chosen substring filter | Self-reported — LLM-generated |
| `input.arguments.to` (email recipient) | LLM-chosen from user message | Self-reported — LLM-generated |
| `input.arguments.subject` (email subject) | LLM-chosen / user-provided free text | Self-reported — could contain injected content |
| `input.arguments.body` (email body) | LLM-chosen / user-provided free text | Self-reported — could contain injected content or sensitive data |
| `input.arguments.department` | LLM-chosen optional filter | Self-reported — LLM-generated |
| Tool response data (salary, SSN, internal_notes) | MCP server in-memory fixtures | External/untrusted — not verified by agent layer; cpex redacts SSN on egress |

---

## Data Flow

```
A2A client (chat.py)
  │  POST message/send
  │  headers: X-User-Token, Authorization, X-Session-Id
  ▼
Sidecar reverse proxy :8000  [inbound passthrough]
  ▼
HR Copilot agent :8001
  │  LLM tool-calling loop (litellm → Ollama, DIRECT — not proxied)
  │  Constructs JSON-RPC tools/call with arguments from LLM output
  │  Re-attaches X-User-Token, Authorization, X-Session-Id
  ▼  via explicit httpx.Client(proxy=MCP_PROXY) → sidecar forward proxy :8081
Sidecar forward proxy :8081  [CPEX enforcement]
  │  JWT identity resolution → input.extensions.subject.*
  │  Cedar PDP · redact(args.ssn) · PII scan · session taint
  │  RFC 8693 delegation → Keycloak
  ▼  (if allowed)
HR MCP server :9100
  │  Executes tool against in-memory fixture data
  ▼
Response ← MCP server ← forward proxy (optionally redacted) ← agent (LLM summary) ← A2A client
```

---

## Enforcement Points

### Current
- **A2A Client Layer**: JWT minting — user and client identity is cryptographically bound before it enters the system.
- **Agent Layer (:8001)**: Header presence check — rejects turns where `X-User-Token` or `Authorization` is absent. No role or parameter enforcement.
- **Sidecar Forward Proxy (:8081)**: Primary enforcement — Cedar PDP (role/permission-based authorization), SSN redaction (`args.ssn`), PII scan, session taint, RFC 8693 delegation. This is the production enforcement boundary.

### Available (OPA-interceptable)
The OPA interception point sits at the agent → sidecar forward proxy boundary. At this point the following fields are present as structured data:

- `input.name` — tool name (string, LLM-chosen from the 6 registered tools)
- `input.arguments.employee_id` — string
- `input.arguments.include_ssn` — boolean
- `input.arguments.amount` — integer (adjust_compensation only)
- `input.arguments.visibility` — enum string: `internal` | `public` | `external`
- `input.arguments.repo_name` — string (optional substring filter)
- `input.arguments.to`, `input.arguments.subject`, `input.arguments.body` — strings (send_email)
- `input.arguments.department` — string (optional)
- `input.extensions.subject.roles` — array of role strings (from JWT, authoritative)
- `input.extensions.subject.permissions` — array of permission strings (from JWT, authoritative)
- `input.extensions.subject.has_approval` — string `"true"` or `"false"` (from JWT)

**guidance.txt coverage sweep (existing 2 rules):**
- Rule 1: "All employees can only access internal repositories." → needs `input.arguments.visibility` (present) and `input.name == "search_repos"` (present). ✓ OPA-enforceable.
- Rule 2: "All employees cannot access other teams' repositories." → would need a team-to-repo ownership mapping AND a `subject.team` field. Neither exists in `system_vars.json` or `tool_definitions.json`. ✗ **Blind spot** — see below.

### Blind Spots
- **LLM reasoning** (Agent Layer): The LLM decides which tool to call, what arguments to populate, and whether to honor the `include_ssn` advisory. No structured data is available at reasoning time; OPA cannot intercept here.
- **System prompt content** (Agent Layer): The SYSTEM_PROMPT is constructed at boot time inside the agent; it is not a structured field at tool invocation time.
- **Tool response / output** (MCP Server layer): OPA intercepts before the tool executes; it cannot see the response content. SSN in the response is handled by the cpex sidecar's redaction, not OPA.
- **Team-to-repository ownership mapping**: guidance.txt Rule 2 requires knowing which team owns each repo and which team the caller belongs to. No `subject.team` field exists in `system_vars.json` and no repo ownership mapping is available. OPA cannot enforce this rule as stated.
- **Email body / subject free-text SSN detection**: Raw regex on `input.arguments.body`/`subject` can catch simple SSN patterns but is best-effort.
- **Session taint state**: Whether the caller accessed SSN data earlier in the conversation is maintained by the cpex sidecar's session store, not by OPA's input fields.
