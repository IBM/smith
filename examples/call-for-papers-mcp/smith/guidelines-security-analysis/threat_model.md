# Threat Model: get_events
Source catalog: src/smith/data/owasp_10_ai_catalog.json (OWASP Top 10 for Agentic AI Security)

## ASI01 — Agent Goal Hijack
**Applicable:** Partial
**Evidence:** architecture.md Data Flow: `events[] ← Tool impl layer ← MCP Tool layer ← Agent layer (LLM composes final response)`; Trust Boundaries table classifies "WikiCFP response HTML" as External/untrusted; Tool Implementation Layer "Current enforcement: none. `keywords` is placed directly into the outbound query string... with no sanitisation."
**Threat instances:**
- A crafted WikiCFP listing (event name/description/link) returned to the Agent layer for response composition is External/untrusted content re-entering the LLM's context with no validation step in between (architecture.md Tool Implementation Layer, Data Flow). Embedded instructions in a listing's text could attempt to redirect the agent's next `get_events` call (e.g. toward a disallowed `topic` or `keywords` value) within the same session.
**Not covered:** No document upload, RAG ingestion, or peer-agent messaging pipeline exists in this architecture, and there is only one tool to redirect the agent toward — this limits goal-hijack blast radius to repeated misuse of `get_events` itself, not a wider action set.

---

## ASI02 — Tool Misuse and Exploitation
**Applicable:** Yes
**Evidence:** architecture.md MCP Tool Layer "Current enforcement: none" and "`topic` is accepted into the schema but discarded here"; Tool Implementation Layer "Current enforcement: none. `keywords` is placed directly into the outbound query string... with no sanitisation."
**Threat instances:**
- `input.arguments.limit` is unconstrained at every layer before reaching the external call — the Agent layer can propose any integer value, and no layer enforces the role-based caps (faculty ≤15, phd_student ≤10) or the absolute maximum of 15.
- `input.arguments.keywords` is forwarded unsanitised into the outbound WikiCFP query string (architecture.md Tool Implementation Layer) — nothing blocks the disallowed-topic terms (e.g. `bioinformatics`, `finance`) from being submitted.
**Not covered:** The tool is read-only (architecture.md Tool Implementation Layer role: scrape-and-truncate); there is no delete, transfer, or write action to misuse, so higher-severity tool-misuse outcomes (data destruction, financial loss) do not apply here.

---

## ASI03 — Identity and Privilege Abuse
**Applicable:** Yes
**Evidence:** architecture.md Trust Boundaries: `user_profile.*` classified Self-reported, "no authentication or verification mechanism present anywhere in the code"; MCP Tool Layer: "The tool signature carries no caller-identity parameter."
**Threat instances:**
- `user_role` is supplied by the caller with zero verification (per questionnaire Q6: "Self-reported... no authentication or verification mechanism present"). A caller can self-report `faculty` to inherit the widest topic scope and the 15-item limit cap, or to bypass the `guest` block entirely.
- A genuine `phd_student` caller can self-report a different `dissertation_area` value in `user_profile` to defeat the PhD narrow-scope rule, since architecture.md's Finding states role/identity fields are visible only at the Agent layer where `user_profile` is still caller-controlled, unauthenticated request data.
**Not covered:** There is a single tool and a single agent instance — no multi-agent delegation chain, cross-agent trust relationship, or cached/inherited credential exists for "Cross-Agent Trust Exploitation" or "Un-scoped Privilege Inheritance" to apply.

---

## ASI04 — Agentic Supply Chain Vulnerabilities
**Applicable:** No
**Evidence:** architecture.md's MCP Tool Layer entry describes `server.py` as declaring the `get_events` tool schema and forwarding directly to `getEvents()` in `app.py` — a locally defined tool, not one fetched from a remote registry. No Layers, Data Flow, or Enforcement Points entry anywhere in architecture.md mentions a tool registry, package source, peer agent, or externally-sourced prompt template.
**Not covered:** The entire category — there is no dynamically loaded tool descriptor, third-party agent, prompt template, or registry dependency in this architecture; the only external component is a hardcoded, statically-known website (WikiCFP), which is a data source (covered under ASI01/ASI09), not a supply-chain artefact.

---

## ASI05 — Unexpected Code Execution (RCE)
**Applicable:** No
**Evidence:** architecture.md documents no code-generation, `eval`, shell invocation, template rendering, or deserialization step anywhere in the Layers section — the Tool Implementation Layer's only action is an HTTP GET scrape parsed with BeautifulSoup.
**Not covered:** The entire category — no code-execution surface exists in this tool's documented architecture.

---

## ASI06 — Memory & Context Poisoning
**Applicable:** No
**Evidence:** architecture.md's Data Flow and Layers sections document no persistent memory store, vector database, or RAG pipeline; `queries_this_session` is noted as "declared as a static value in `system_vars.json`... nothing in this codebase increments or persists a real per-session count" (Trust Boundaries table).
**Not covered:** The entire category — there is no retrievable, persisted context for an attacker to poison; each request's data flow is documented as independent (HTTP API → Agent → MCP Tool → Tool Impl → External Service, with no memory layer in between).

---

## ASI07 — Insecure Inter-Agent Communication
**Applicable:** No
**Evidence:** architecture.md's Layers section documents exactly one agent (the Agent layer in `agent.py`) and one MCP tool server (`server.py`) connected via stdio — no peer agent, A2A protocol, or message bus appears anywhere in the architecture.
**Not covered:** The entire category — inter-agent communication requires more than one agent; this architecture has a single agent instance with no peers.

---

## ASI08 — Cascading Failures
**Applicable:** No
**Evidence:** architecture.md documents a single tool, single agent, and no persistent memory or peer agents (see ASI06, ASI07 evidence above) — there is no downstream agent, workflow, or session for a fault to propagate into.
**Not covered:** The entire category — cascading failure requires fan-out across agents, sessions, or workflows; none of these exist in this architecture.

---

## ASI09 — Human-Agent Trust Exploitation
**Applicable:** Yes
**Evidence:** architecture.md Trust Boundaries table classifies "WikiCFP response HTML" as External/untrusted, returned via the Tool Implementation Layer with "Current enforcement: none"; the Agent layer composes the final response directly from this data with no intervening validation.
**Threat instances:**
- The agent presents WikiCFP-derived conference listings (name, description, dates, location, deadline, link) to the user as trustworthy results with no confirmation step or provenance indicator, even though the source data is classified External/untrusted (architecture.md Trust Boundaries, Tool Implementation Layer Outputs). A manipulated or spoofed listing (e.g. a forged `link` field) would reach the user through the agent's response unchanged.
**Not covered:** This tool is read-only with no financial or irreversible action to approve, so the "Missing Confirmation for Sensitive Actions" sub-risk (approving transfers, deletions, etc.) does not apply here — the exposure is limited to trust in displayed search results.

---

## ASI10 — Rogue Agents
**Applicable:** No
**Evidence:** architecture.md documents exactly one agent instance in the Layers section, with no peer agents, orchestrator, or multi-agent ecosystem described anywhere in the architecture.
**Not covered:** The entire category — "rogue" behavioral divergence is defined relative to a multi-agent or human-agent ecosystem; this architecture has a single agent with no peers to diverge from or deceive.
