## Architecture Analysis 

Produces `architecture.md` for a target MCP server. This document is the
required input for the threat_model and enforcement_mapping skills.

### Authoritative Paths

**Inputs (from `<TARGET_AGENT_PATH>/`, provided by the user at invocation
time):** Use ONLY these exact files. Do NOT read similarly-named files from
other folders. If a required file is missing here, stop and ask; do not
substitute one from elsewhere.
- `agent.py`, `server.py`, `app.py`, `README.md`, `SYSTEM_VARIABLES.md` — read if present
- `smith/system_vars.json` — authoritative source for subject fields, if present
- Any other `.py` files in the target directory
- Output file: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`

### Workflow (follow strictly)

---

#### STEP 1 — Identify source files

Read the following files from the target MCP server directory if they exist:
- `agent.py` — the FastAPI/agent layer
- `server.py` — the MCP tool server
- `app.py` — the tool implementation
- `README.md` — tool description
- `SYSTEM_VARIABLES.md` — session context schema
- `smith/system_vars.json` — runtime schema of all fields available in
  `input.extensions.subject.*` at tool-call time. If present, this is the
  authoritative source for subject field names and types; it takes precedence
  over what is inferred from source code. If absent, note this gap — the
  enforcement_mapping skill will need to rely on source code inference instead.
- Any other `.py` files present

Do NOT proceed until you have read all available files.

---

#### STEP 2 — Map the layers

Identify every distinct processing layer between the user and the external
service. For each layer record:

- **Name** — human-readable label (e.g. Agent Layer, MCP Tool Layer)
- **File** — the source file that implements it
- **Role** — one sentence describing what it does
- **Inputs received** — field names and types it accepts
- **Outputs produced** — what it passes to the next layer
- **Current enforcement** — any validation, auth, or access control present today (write "none" if absent)

Standard layers for MCP servers in this repo:
1. HTTP API layer (`agent.py` `/chat` endpoint)
2. Agent layer (LLM + system prompt construction)
3. MCP tool layer (`server.py` tool definition)
4. Tool implementation layer (`app.py` business logic)
5. External service (the upstream API or website being called)

---

#### STEP 3 — Document trust boundaries

Identify every field that flows into the system and classify each as:

- **Verified** — cryptographically authenticated or validated by a trusted system
- **Self-reported** — supplied by the caller with no external verification
- **External/untrusted** — returned by an external service with no integrity guarantee

Pay particular attention to:
- Role and identity fields (where do they come from, who sets them?)
- Session counters or quotas (who maintains them?)
- Parameter values that are passed directly to external calls

---

#### STEP 4 — Identify enforcement points

For each layer, record:

- **Current enforcement points** — where access control or validation exists today
- **Available enforcement points** — where a policy engine (OPA) could intercept
  the request given the data visible at that layer
- **Blind spots** — where no enforcement exists and none can easily be added
  (e.g. inside the LLM's reasoning, after the tool returns its response)

OPA can only enforce at a point where:
(a) the tool call is intercepted before execution, AND
(b) the relevant fields (tool name, arguments, caller identity) are present
    as structured data

---

#### STEP 5 — Write architecture.md

Write the output file to `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md` using exactly
this structure:

```
# Architecture: <tool-name>

## Layers

### <Layer Name>
- File: <filename>
- Role: <one sentence>
- Inputs: <field list>
- Outputs: <field list>
- Current enforcement: <description or "none">

[repeat for each layer]

## Trust Boundaries

| Field | Source | Classification |
|---|---|---|
| <field> | <who sets it> | Verified / Self-reported / External |
[one row per field]

## Data Flow

<user input> → <layer 1> → <layer 2> → ... → <external service>
<response> ← <layer 2> ← <layer 1> ← <external service>

## Enforcement Points

### Current
- <layer>: <what is enforced>

### Available (OPA-interceptable)
- <layer>: <what could be enforced and what fields are visible>

### Blind Spots
- <layer>: <what cannot be enforced and why>
```

---

#### STEP 6 — Human review

Present a one-paragraph summary of the key findings:
- How many layers exist
- Which fields are self-reported (most important for policy)
- Where OPA can be placed
- What the main blind spots are

Log the summary and continue automatically to the threat_model skill.
