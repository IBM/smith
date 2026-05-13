# Bibliomantic MCP Server — Tool Summary and Capability Analysis

## Server Overview

The Bibliomantic MCP Server is an I Ching divination service inspired by the bibliomantic approach in Philip K. Dick's *The Man in the High Castle*. It exposes four MCP tools, two MCP resources, and three prompt templates via the FastMCP framework over stdio transport. All outputs are text-based philosophical/entertainment readings generated from a local 64-hexagram database using cryptographically secure randomness (`secrets` module). The server performs no network calls, file writes, or database mutations at runtime.

---

## Exposed MCP Tools

### 1. `i_ching_divination`

| Attribute | Detail |
|---|---|
| **Purpose** | Perform a random I Ching divination using the three-coin method. |
| **Parameters** | `query` (optional, string) — a question or context for the reading. |
| **Returns** | Formatted hexagram reading (number, name, interpretation, changing lines if enhanced mode). Includes ethical disclaimer. |
| **Side effects** | None. Read-only randomness generation against a local hexagram database. |

### 2. `bibliomantic_consultation`

| Attribute | Detail |
|---|---|
| **Purpose** | Perform a full bibliomantic consultation that augments the user's query with I Ching wisdom. |
| **Parameters** | `query` (required, string) — the question or situation requiring guidance. |
| **Returns** | Complete consultation with hexagram, judgment, image, contextual interpretation, trigram analysis (enhanced mode), changing lines, and ethical disclaimer. |
| **Side effects** | None. |

### 3. `get_hexagram_details`

| Attribute | Detail |
|---|---|
| **Purpose** | Look up detailed information about a specific I Ching hexagram by number. |
| **Parameters** | `hexagram_number` (required, integer, range 1–64). |
| **Returns** | Hexagram name, Chinese name, Unicode symbol, judgment, image, trigram composition, commentary, and educational context. |
| **Side effects** | None. |

### 4. `server_statistics`

| Attribute | Detail |
|---|---|
| **Purpose** | Return server status, capabilities, and system information. |
| **Parameters** | None. |
| **Returns** | System status, hexagram count, divination method, enhanced-mode flag, and capability list. |
| **Side effects** | None. |

---

## MCP Resources

| URI Pattern | Description |
|---|---|
| `hexagram://{number}` | Returns formatted data for a single hexagram (1–64). |
| `iching://database` | Returns the full 64-hexagram summary. |

## MCP Prompt Templates

| Name | Parameter | Description |
|---|---|---|
| `career_guidance_prompt` | `situation` (string) | Structured prompt for career-related I Ching consultation. |
| `creative_guidance_prompt` | `project` (string) | Structured prompt for creative-project I Ching consultation. |
| `general_guidance_prompt` | `question` (string) | Structured prompt for general life-guidance I Ching consultation. |

---

## Security-Sensitive Inputs

This server has a narrow attack surface because all tools are read-only, generate outputs from a fixed local dataset, and make no external calls. The main security-relevant considerations are:

1. **`query` parameter (free-text string)** — Present in `i_ching_divination`, `bibliomantic_consultation`, and all prompt templates. User-supplied text is embedded directly into output strings. While the server does not execute or eval this text, it is reflected back in responses, which could be a vector for prompt injection if the output is consumed by a downstream LLM without sanitization.

2. **`hexagram_number` parameter (integer)** — Present in `get_hexagram_details`. The server validates the range (1–64) and returns an error for out-of-range values, so injection risk is minimal.

3. **No authentication or authorization** — The server has no user identity model. Any connected client can call any tool.

4. **No rate limiting** — Repeated rapid calls are not throttled at the server level.

---

## Parameters That Could Define Usage Boundaries

| Parameter | Tool(s) | Boundary Dimension | Examples |
|---|---|---|---|
| `query` | `i_ching_divination`, `bibliomantic_consultation` | **Topic/domain restriction** — the free-text query can be constrained to specific subject areas (e.g., only career topics, only creative topics). | Allow queries about "career" or "project" topics; disallow queries about medical diagnosis or financial investment advice. |
| `query` | `bibliomantic_consultation` | **Content-type restriction** — the query text can be filtered for prohibited content categories. | Disallow queries containing personal health data, third-party PII, or requests for predictive gambling advice. |
| `hexagram_number` | `get_hexagram_details` | **Resource scope** — the integer range (1–64) is inherently bounded; further subsetting is possible. | Restrict lookups to a curated subset of hexagrams (e.g., only hexagrams 1–8 for an introductory course). |
| Prompt template selection | `career_guidance_prompt`, `creative_guidance_prompt`, `general_guidance_prompt` | **Use-case restriction** — which prompt templates the agent is allowed to invoke. | Allow only `career_guidance_prompt`; disallow `general_guidance_prompt` for a career-coaching deployment. |
| Call frequency | All tools | **Rate/volume threshold** — how many divinations per session or time window. | Limit to 3 divinations per user session to encourage reflection over rapid consultation. |
| Context categories (inferred) | `bibliomantic_consultation` (enhanced mode) | **Interpretation-context restriction** — the enhanced engine infers context categories (`career`, `relationships`, `creative`, `business`, `personal`, `general`) from query text. | Restrict contextual interpretations to `career` and `creative` only; block `relationships` and `business` contexts. |
