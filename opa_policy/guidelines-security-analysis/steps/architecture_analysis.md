## Architecture Analysis 

Produces `architecture.md` for a target MCP server. This document is the
required input for the threat_model and enforcement_mapping skills.

### Authoritative Paths

Use the paths resolved by the top-level workflow; do not read `.env` directly
and do not substitute similarly named files from elsewhere.

The phase envelope must contain concrete values for every path below. Stop with
`FAIL` if it contains an unresolved placeholder or omits a value. An optional
path is absent only when its value is explicitly `ABSENT`.

- `<TARGET_AGENT_PATH>` — root within which source discovery is allowed.
- `<SYSTEM_VAR_FILE>` — authoritative schema for runtime-provided subject
  fields, if present. Its presence establishes field provenance and OPA
  visibility, not a cryptographic verification mechanism.
- `<TARGET_AGENT_PATH>/smith/tool_definitions.json` — authoritative per-tool
  source for visible `input.args.*` names and types.
- `<GUIDANCE_FILE>` — existing policy intent, if present. Use it only in
  STEP 4 to check field visibility; do not carry its content into the
  descriptive layers, trust boundaries, or data flow.
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`.

### Workflow (follow strictly)

---

#### STEP 1 — Identify source files

Start from `<TARGET_AGENT_PATH>` and inventory file names only. Prefer
`rg --files`; do not open every file during discovery. The implementation may use
Python, JavaScript, TypeScript, or another language, and its entrypoint may use
any filename or MCP transport.

Use `tool_definitions.json` as the seed for targeted source discovery. Search
for the extracted tool names, MCP framework registration, transport setup, and
the functions or handlers behind those registrations. Follow imports or calls
only far enough to identify code that performs one of these roles:

- **MCP server entrypoint** — creates the MCP server, registers tools, and
  selects stdio, HTTP, SSE, or another transport.
- **Tool implementation** — validates or acts on `input.args.*`, performs
  business operations, or calls an external service.
- **Agent or MCP client integration** — optionally builds prompts, selects or
  invokes tools, or supplies policy-visible context. A standalone MCP server
  may have no agent layer.
- **Runtime context or enforcement integration** — populates
  `input.extensions.*`, intercepts calls, or applies authorization.
- **External-service client** — constructs requests or consumes responses when
  that behavior is material to the threat model.

Do not infer a role from a filename. In particular, files named `agent.py`,
`server.py`, `app.py`, `mcp_server.py`, or `index.js` are candidates only when
their contents establish one of the roles above. Conversely, do not omit a
relevant file because it has an unfamiliar name or extension.

Skip tests, vendored dependencies, virtual environments, caches, generated
analysis artifacts, and UI-only entrypoints unless targeted evidence shows
that they construct prompts, invoke tools, populate policy-visible inputs, or
implement enforcement. Use README and package/build metadata only to clarify
an entrypoint, transport, dependency, or external integration; they are not
evidence of runtime behavior on their own.

Read the selected source files, `<SYSTEM_VAR_FILE>` when present,
`tool_definitions.json`, and `<GUIDANCE_FILE>` when present. Record the selected
source paths and the evidence for each assigned role. If a role remains
ambiguous after targeted search, record it as unknown rather than broadening
the read to every source file.

Bound discovery to two call/import hops from each registered tool and at most
20 implementation files. Deduplicate files reached from multiple tools. If the
bound would omit a file needed to establish a role or enforcement path, record
the omitted candidate and reason instead of expanding silently.

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

Model only layers that actually exist. Common roles include an optional
HTTP/API or agent layer, an MCP client boundary, the MCP server and registered
tools, implementation modules, runtime enforcement, and external services.
Do not create empty layers to match this list, and do not count a UI-only
entrypoint as an agent or implementation layer.

---

#### STEP 3 — Document trust boundaries

Separate fields by how they enter the policy boundary. Do not place runtime
subject context, tool arguments, prompt inputs, and external data in one trust
classification table: they have different provenance and require different
analysis.

**Runtime subject context.** Record every key declared by
`<SYSTEM_VAR_FILE>` using its canonical policy path,
`input.extensions.subject.<key>`. Mark its provenance as
**Runtime-provided** and name the runtime/provider when the inputs document
one. `system_vars.json` is authoritative for the available field names and
types. A subject field's absence from the selected application, server, or tool
implementation source does not make it caller-supplied, self-reported, or
prompt-injectable: those layers need not read context attached by the runtime
at the policy boundary.

Record verification/integrity separately from provenance. State the documented
authentication, signature, token-validation, or trusted-runtime mechanism; if
none is documented, write `not documented`. Do not turn `not documented` into
`self-reported`, and do not claim cryptographic verification merely because a
field is runtime-provided. Also record whether the field is visible to OPA at
tool-call time.

**Tool arguments.** Record every declared argument under its canonical policy
path, `input.args.<argument>`, and name the governing tool. Describe its
origin/influence as LLM-generated, caller-influenced, application-generated,
or unknown based on the observed data flow. A caller's natural-language input
may influence an LLM-generated argument, but that does not turn runtime subject
context into a tool argument.

For every tool argument, record its **disposition** — what the
implementation actually does with the value:

- **Acts on** — the value changes what the tool does: it filters or
  selects data, routes the call, gates a branch, or is passed to an
  external service.
- **Echoed** — the value is accepted and then only reflected back in the
  response, a log line, or result metadata. It does not change what the
  tool does or returns.
- **Ignored** — the value is accepted and never referenced at all.

This is not a stylistic note; it is the only place in the whole workflow
where it can be established. Step A is the sole step that reads the
server implementation — the later steps see `tool_definitions.json`,
which reports a parameter's name, type and default but cannot say
whether the code honours it. A protective-sounding flag that is merely
echoed will otherwise pass every downstream check and yield a rule that
guarantees nothing (e.g. an `input.args.encryption_required` boolean argument
that the tool interpolates into its response text without encrypting
anything). The enforcement_mapping step relies on this column to refuse
such rules.

Determine the disposition by reading the tool's body, not its docstring
or type signature. A default value in the signature says what will be
substituted, never what the code does with it. When the body is unclear,
record `Unclear` with a one-line note rather than guessing — a wrong
"acts on" is worse than an admitted unknown, because it licenses a rule
downstream.

**Prompt inputs.** Record user prompts, profile text, system-prompt
interpolations, and other free text that enters model reasoning. Name their
source, consumer, and whether callers or external content can influence them.
Do not label a runtime subject field prompt-injectable unless the architecture
shows that the field's value is separately interpolated into a prompt; if so,
record that prompt flow here without changing the subject field's runtime
provenance.

**External data.** Record responses or content returned by external systems,
including the integrity mechanism when one is documented and the layer that
consumes the data.

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

If `<GUIDANCE_FILE>` was read in STEP 1, do a coverage sweep before
finalising the "Available (OPA-interceptable)" list: for each numbered
rule in guidance.txt, name the specific field(s) it would need at
invocation time (e.g. `input.args.amount`,
`input.extensions.subject.role`) and confirm those fields appear in
this section's list. Any guidance.txt rule whose fields are NOT visible
at any interception point goes into "Blind Spots" with a one-line
explanation. This surfaces underenumeration early — do NOT rewrite the
rule or restate guidance.txt's intent; just record the field-visibility
result.

As part of the same sweep, produce a required **Undeclared fields**
finding: for every field or value an existing guidance.txt rule depends
on, confirm that some tool declares it as an argument (or some system
variable declares it), and list the ones nothing declares. Include the
rule number that references each.

Distinguish two cases, because they lead to different downstream
handling:

- The field is declared by **some** tool but not by the tool that rule
  governs. The rule is enforceable for a narrower set of tools than it
  claims.
- The field is declared by **no** tool at all — it does not exist
  anywhere in the server's surface, and any rule depending on it can
  never fire.

Both are common and neither is visible later without this list: a rule
naming a field that exists somewhere reads as verified to any check that
looks up field names globally. Write the finding even when the list is
empty (`Undeclared fields: none`), so the later steps can tell the check
ran from the check finding nothing.

Report the list; do not edit guidance.txt and do not propose
replacement wording here. Deciding what to do about a phantom field
belongs to the enforcement_mapping step and ultimately to the human.

---

#### STEP 5 — Write architecture.md

Write the output file to `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md` using exactly
this structure. Use canonical policy paths for every structured field:
`input.name`, `input.args.<argument>`, and
`input.extensions.subject.<field>`.

```
# Architecture: <tool-name>

## Run Context

- Target agent: `<TARGET_AGENT_PATH>`
- Guidance: `<GUIDANCE_FILE>` or `ABSENT`
- System variables: `<SYSTEM_VAR_FILE>` or `ABSENT`
- Tool definitions: `<TARGET_AGENT_PATH>/smith/tool_definitions.json`

## Layers

### <Layer Name>
- File: <filename>
- Role: <one sentence>
- Inputs: <field list>
- Outputs: <field list>
- Current enforcement: <description or "none">

[repeat for each layer]

## Trust Boundaries

### Runtime Subject Context

| Field | Provider | Provenance | Verification / integrity | OPA-visible? |
|---|---|---|---|---|
| `input.extensions.subject.<field>` | <runtime/provider or "not documented"> | Runtime-provided | <documented mechanism or "not documented"> | Yes / No / Unknown |

### Tool Arguments

| Field | Tool | Origin / influence | Disposition |
|---|---|---|---|
| `input.args.<argument>` | `<tool name>` | LLM-generated / Caller-influenced / Application-generated / Unknown | Acts on / Echoed / Ignored / Unclear |

### Prompt Inputs

| Field or data | Source | Consumer | Trust / influence |
|---|---|---|---|
| <prompt, profile text, or interpolated data> | <who supplies it> | <model/layer> | <who can influence it> |
[or "none" when the architecture exposes no prompt input]

### External Data

| Data | Source | Verification / integrity | Consumer |
|---|---|---|---|
| <response/content> | <external system> | <documented mechanism or "not documented"> | <layer> |
[or "none" when the tool consumes no external data]

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

## Undeclared Fields

| Field | Referenced by guidance rule # | Declared by | Consequence |
|---|---|---|---|
| <canonical input path> | <rule #> | <tool name(s), runtime subject schema, or "none"> | Rule enforceable for fewer tools than claimed / can never fire |
[or "none" if every referenced field is declared by the tool its rule governs]
```

---

#### STEP 6 — Human review

Present a one-paragraph summary of the key findings:
- How many layers exist
- Which `input.extensions.subject.*` fields are runtime-provided and whether
  their verification/integrity mechanism is documented
- Which `input.args.*` fields are caller- or LLM-influenced
- Where OPA can be placed
- What the main blind spots are
- Any argument whose disposition is **Echoed**, **Ignored** or
  **Unclear** — name them. A protective-sounding flag the tool does not
  act on is the finding most likely to become a rule that guarantees
  nothing, and this is the reviewer's first and best chance to see it.
- Any row in the **Undeclared Fields** table, with the guidance rule
  that depends on it (or "none")

Append this compact checkpoint to `architecture.md`:

```markdown
## Phase Handoff

- Status: PASS / FAIL
- Sources inspected: <count and paths>
- Tools covered: <count and names>
- Layers: <count and names>
- Canonical tool fields: <count>
- Runtime subject fields: <count>
- Undeclared fields: <count and paths, or none>
- Open gaps: <none, or concise list>
```

Mark `PASS` only when the required sections are present and each extracted tool
has a governing implementation or an explicit unknown finding. Return this
handoff to the orchestrator and stop; do not load the next phase guide.
