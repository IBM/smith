## Phase A — Architecture analysis

Establish the runtime architecture and structured policy inputs. The shared
contract in the parent workflow applies.

### Inputs

- Target source tree and optional existing guidance.
- Authoritative `tool_definitions.json` for tool names and argument schemas.
- Authoritative `system_vars.json` for runtime subject fields when present.
- Structured output: `architecture.json`; the checkpoint renders
  `architecture.md`.

`architecture.json` retains the structured analysis needed by later phases.
The rendered `architecture.md` includes the title, Phase A tables, and a concise
prose handoff. It omits all other narrative section text.

### Inspect the implementation

Inventory paths once with `rg --files`, then search paths for registered tool
names, MCP registration/transport markers, prompt construction, runtime
context, policy interception, and external-service calls. Read only files that
implement one of those roles. Do not infer roles from filenames or assume a
language or transport.

Follow at most two import/call hops from each registered tool and inspect no
more than 20 implementation files. Skip tests, dependencies, caches, generated
analysis, and UI-only files unless evidence shows they participate in a tool
call or policy boundary. Record unresolved relevant paths instead of silently
expanding the search.

Compare registered tools and signatures with `tool_definitions.json`. Stop with
`FAIL` on a proven missing, extra, or incompatible declaration; an unresolved
dynamic wrapper is `Unknown`, not proof of mismatch.

### Fill structured state

Run the phase preparation command, then populate its fixed structured fields:

- **Run Context:** resolved authoritative paths and selected source files.
- **Layers:** only observed agent/client, MCP, tool implementation, runtime
  context/enforcement, and material external-service layers.
- **Runtime Subject Context:** every declared
  `input.extensions.subject.<field>`, its provider, runtime provenance,
  separately documented integrity mechanism, and OPA visibility.
- **Tool Arguments:** every declared `input.args.<argument>` under each exact
  tool. Record influence and implementation disposition:
  `Acts on`, `Echoed`, `Ignored`, or `Unclear`. Determine disposition from the
  function body, not its declaration or documentation.
- **Prompt Inputs:** prompt, conversation, profile, retrieved, and interpolated
  text with source, consumer, and influence.
- **External Data:** externally sourced responses/content, integrity mechanism,
  and consumer.
- **Data Flow:** concise request and response paths.
- **Enforcement Points:** current controls, future pre-execution points with
  visible structured fields, and true blind spots. Apply the shared
  OPA-policy-expressibility rule when classifying them.
- **Undeclared Fields:** every guidance dependency absent from the exact
  governed tool or runtime subject schema. Distinguish “declared by another
  tool” from “declared nowhere.”

Use an empty table when there are no rows. Apply the shared source-boundary rule
when a runtime value is also interpolated into a prompt. Run Context, Trust
Boundaries, and Data Flow remain available in structured state for downstream
analysis but are intentionally omitted from rendered `architecture.md`.

### Complete the phase

Set `PASS` only when every tool has an implementation finding or explicit
`Unknown`, all declared arguments and subject fields are accounted for, and
the guidance visibility sweep is complete. The handoff should summarize
sources, tools, layers, field counts, undeclared fields, and open gaps.

Run:

```bash
smith --flag security_analysis_checkpoint --phase A
```
