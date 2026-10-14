## Phase B — Policy guidance questionnaire

Capture policy intent without inventing restrictions. The shared contract in
the parent workflow applies.

### Inputs

- Phase A tables and sections from `analysis_state.json`.
- Existing guidance as the primary source of policy intent, when present.
- `tool_definitions.json` and `system_vars.json` for exact canonical paths.
- Structured output: `policy_guidance_questionnaire.json`; the checkpoint
  renders `policy_guidance_questionnaire.md`.

Do not reread implementation source. Phase A is authoritative for observed
behavior.

### Fill the questionnaire

The prepared JSON contains all Q1-Q22 rows, including Q13b. Fill every answer
and its supporting detail table where applicable.

Map existing guidance as follows:

- access and role scope → Q9;
- role-specific fields/content and response restrictions → Q10, Q17, Q18;
- enumerated values, formats, domains, and flags → Q12;
- numeric limits → Q13;
- approval conditions → Q13b;
- pattern restrictions → Q14, retaining the governed input source;
- rate/counter requirements → Q15-Q16;
- actionability, denial behavior, severity, and logging → Q19-Q22.

For each answer use exactly one confidence value:

- `[derived from guidance.txt]` for explicit policy intent;
- `[derived from architecture]` for directly observed behavior or schema;
- `[inferred — low confidence]` for a plausible but unsupported inference.

Leave unsupported answers blank. Low-confidence answers cannot support new
policy. Ask one consolidated clarification question for blanks that materially
affect access, caps, approval, subject identity, matching semantics, or
hard/soft behavior; after at most one follow-up, retain unresolved blanks as
open gaps.

### Boundary rules

- Use canonical `input.args.*` and `input.extensions.subject.*` paths.
- For Q14, record the exact source and apply the shared source-boundary rule.
- Architecture may explain how to enforce existing intent, but cannot create
  new policy intent.

### Complete the phase

Use the generated detail tables for parameters, runtime subjects, role
permissions, approvals, rate limits, severity levels, and violation codes.
Never invent a violation code. Set `PASS` when every question has an answer or
is explicitly listed as an open gap. Summarize confidence counts and covered
tools in the handoff.

Save the structured JSON and return control to the coordinator, which owns the
checkpoint and rendered Markdown.
