## Policy Guidance Questionnaire 

Produces `policy_guidance_questionnaire.md` for a target MCP server.
This document captures policy intent — who can use the tool, what they
are allowed to do, and what must be blocked. It is required input for
the threat_model skill.

Requires `architecture.md` to be present (produced by architecture_analysis
skill). Use it to answer questions about parameters, external calls, and
data flow rather than asking the user to look up source files.

### Phase inputs and output

The envelope's Shared Phase Contract applies.
- Input: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/architecture.md`
- Input (optional): `<GUIDANCE_FILE>` — **primary source
  of policy intent**. If present, read every rule and map each one to the
  questionnaire item it belongs to. Rules in guidance.txt take precedence
  over inferences from architecture.md.
- Input (optional): `<SYSTEM_VAR_FILE>` — use for
  exact `input.extensions.subject.*` field names and types in Q6, Q7, Q13b,
  and Q16 as applicable. These fields are runtime-provided; do not reclassify
  them as self-reported because application source does not read them.
- Input (optional): `<TARGET_AGENT_PATH>/smith/tool_definitions.json` — use
  for exact tool and parameter names and types in Q1 and Q4
- Output: `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/policy_guidance_questionnaire.md`

---

### Workflow (follow strictly)

---

#### STEP 1 — Read inputs

Read `<GUIDANCE_FILE>` first when present. Parse
  every numbered rule. For each rule, note which questionnaire item
  it maps to (see mapping below) and what OPA-enforceable condition it
  implies.

Then load only the sections needed to answer the questionnaire:

- `architecture.md`: Run Context, Layers, Runtime Subject Context, Tool
  Arguments, Prompt Inputs, External Data, Data Flow, and Enforcement Points.
  Defer Undeclared Fields to Step D.
- `<SYSTEM_VAR_FILE>`: subject keys and types for Q6, Q7, Q13b, and Q16.
- `tool_definitions.json`: tool names, descriptions, and parameter
  names/types/schemas for Q1 and Q4.

Do not search for similarly named substitutes or reread source code; Step A's
artifact is the source for architectural behavior.

**guidance.txt → questionnaire mapping:**
| guidance.txt rule type | Questionnaire item |
|---|---|
| Role-based tool access (who can/cannot use a tool) | Q9 |
| Field-level restrictions (which fields are forbidden per role) | Q10 and Q17–Q18 |
| Scope restrictions (e.g. manager's own team only) | Q9, as a sub-condition |
| Hard parameter blocks (`input.args.external_sharing`, blocked domains) | Q12 |
| Numeric caps (purchase amounts) | Q13 |
| Approval paths (action allowed with approval flag) | Q13b; include approval field |
| Prompt injection / keyword blocks | Q14 |
| Format or value enumerations (CSV/PDF/JSON) | Q12 |

Pre-fill every answer you can derive from these files. Tag each answer
with exactly one confidence marker so Step C knows what it can rely on:

- `[derived from guidance.txt]` — an explicit rule in guidance.txt states
  this answer. High confidence.
- `[derived from architecture]` — a specific file, function, or field in
  the source directly supports this answer. High confidence.
- `[inferred — low confidence]` — the answer is a plausible guess from
  partial signals (naming conventions, similar tools, generic patterns)
  without a direct source. Downstream steps MUST NOT cite this answer as
  evidence.
- Leave the answer blank when nothing supports even a low-confidence inference;
  do not invent an answer merely to complete the phase.

Whenever an answer names structured policy input, use its canonical OPA path:
`input.name` for the invoked tool, `input.args.<argument>` for tool arguments,
and `input.extensions.subject.<field>` for runtime subject context. Do not use
an unqualified argument or subject-field name in tables that downstream steps
consume.

---

#### STEP 2 — Fill the questionnaire

Write the output file to `<TARGET_AGENT_PATH>/smith/guidelines-security-analysis/policy_guidance_questionnaire.md`
using exactly this structure. Pre-fill every supported answer first. Put all
remaining questions into one numbered clarification request; do not ask them
one at a time. Apply the response in one pass. Ask at most one consolidated
follow-up for contradictory or incomplete answers, then preserve unresolved
items as documented blanks.

```
# OPA Policy Guidance Questionnaire
# Tool: <tool-name>

## Answer Register

Use `See <table>` for structured answers. Every row has one confidence marker.

| Q | Required answer | Answer | Confidence |
|---|---|---|---|
| Q1 | Tool name and one-sentence purpose | <answer> | <marker> |
| Q2 | External systems: protocol, authentication, read/write | <answer> | <marker> |
| Q3 | Reads, writes, or both | <answer> | <marker> |
| Q4 | Parameters | See Parameter Details | <marker> |
| Q5 | Every user role | <answer> | <marker> |
| Q6 | Runtime subject provenance and integrity | See Runtime Subject Details | <marker> |
| Q7 | User ID: canonical path, provider, use | <answer> | <marker> |
| Q8 | Whether multiple simultaneous roles are supported | <answer> | <marker> |
| Q9 | Tool permissions and scope per role | See Role Permissions | <marker> |
| Q10 | Role-specific topics, values, or parameter combinations | <answer or none> | <marker> |
| Q11 | Roles with no restrictions | <answer or none> | <marker> |
| Q12 | Globally blocked enumerable values, formats, domains, or flags | <answer or none> | <marker> |
| Q13 | Numeric hard caps | <canonical path and cap, or none> | <marker> |
| Q13b | Conditional approval paths | See Approval Paths | <marker> |
| Q14 | Rejected patterns in free-text fields | <canonical path and patterns, or none> | <marker> |
| Q15 | Per-session call limits | See Rate Limits | <marker> |
| Q16 | Counter owner/mechanism and canonical policy path | <answer> | <marker> |
| Q17 | Post-response filtering | <answer or none> | <marker> |
| Q18 | Response fields suppressed by role | <answer or none> | <marker> |
| Q19 | Conditions making a result actionable | <answer or none> | <marker> |
| Q20 | Silent rejection or user explanation | <answer> | <marker> |
| Q21 | Hard-block and soft-block meanings | See Severity Levels | <marker> |
| Q22 | Denial logging and existing violation-code scheme | See Violation Logging | <marker> |

Q12 covers enumerable values; Q14 covers patterns inside free text. Treat Q13b
as part of Q13 for the 22-question completion count.

## Parameter Details (Q4)

| Tool | Policy path | Type | Required | Valid values |
|------|-------------|------|----------|--------------|
| `<tool name>` | `input.args.<argument>` | <type> | Yes / No | <description> |

## Runtime Subject Details (Q6)

| Policy path | Provider | Provenance | Verification / integrity mechanism |
|-------------|----------|------------|------------------------------------|
| `input.extensions.subject.<field>` | <runtime/provider or "not documented"> | Runtime-provided | <mechanism or "not documented"> |

Provenance and verification are separate: do not reclassify a declared runtime
field as self-reported or infer undocumented cryptographic verification.

## Role Permissions (Q9)

| Tool | <role 1> | <role 2> | guidance.txt rule |
|------|----------|----------|-------------------|
| <tool> | <allowed/blocked + scope condition> | <allowed/blocked + scope condition> | Rule N |

## Approval Paths (Q13b)

| Parameter condition | Approval field | guidance.txt rule |
|---|---|---|
| `input.args.<field> <operator> <value>` | `input.extensions.subject.<field>` | Rule N |

## Rate Limits (Q15)

| Role | Max calls per session |
|------|-----------------------|
| <role> | <integer> |

## Severity Levels (Q21)

| Level | Examples |
|---|---|
| Hard block | <examples> |
| Soft block with redirect | <examples> |

## Violation Logging (Q22)

- Denial logging: <specific rule / denial only>
- Existing code scheme: <yes / no>

| Existing code | Meaning |
|---|---|
| <CODE> | <description> |

Do not invent codes here. Leave the table empty when no scheme exists; Step D
creates any new codes alongside its rules.
```

---

#### STEP 3 — Finalise

Fill in any remaining blanks using the confidence markers defined in
STEP 1. A low-confidence answer still needs a stated basis; otherwise leave it
blank and include it in Open gaps.

Log a one-line breakdown at the end: how many answers are
`[derived from guidance.txt]`, `[derived from architecture]`,
`[inferred — low confidence]`, and blank. Then append:

```markdown
## Phase Handoff

- Status: PASS / FAIL
- Artifact schema: questionnaire-v2
- Questions answered: <count>/22
- Confidence: <guidance count> guidance, <architecture count> architecture, <inferred count> inferred, <blank count> blank
- Tools covered: <count and names>
- Open gaps: <none, or unanswered question numbers>
```

`PASS` permits documented blanks but must identify them as gaps.
