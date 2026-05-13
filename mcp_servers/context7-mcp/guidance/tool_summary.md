# Context7 MCP Server - Tool Summary and Capability Analysis

## Server Overview

The Context7 MCP server (`@upstash/context7-mcp`, v1.0.13) provides LLM agents with access to up-to-date documentation and code examples for software libraries. It connects to the Context7 API (`https://context7.com/api`) to search for libraries and retrieve their documentation. The server supports stdio, HTTP, and SSE transports.

## Exposed MCP Tools

### Tool 1: `resolve-library-id`

**Purpose:** Resolves a package or product name to a Context7-compatible library ID. This is a search/discovery tool that returns a ranked list of matching libraries.

**Parameters:**

| Parameter     | Type   | Required | Description                                                        |
|---------------|--------|----------|--------------------------------------------------------------------|
| `libraryName` | string | Yes      | Library name to search for (e.g., `"react"`, `"next.js"`, `"django"`) |

**Return data includes:** Library ID (format: `/org/project`), title, description, code snippet count, trust score, and available versions.

**Upstream API call:** `GET https://context7.com/api/v1/search?query={libraryName}`

---

### Tool 2: `get-library-docs`

**Purpose:** Fetches up-to-date documentation content for a specific library identified by its Context7-compatible library ID.

**Parameters:**

| Parameter                     | Type   | Required | Description                                                                                                            |
|-------------------------------|--------|----------|------------------------------------------------------------------------------------------------------------------------|
| `context7CompatibleLibraryID` | string | Yes      | Exact Context7-compatible library ID (e.g., `/mongodb/docs`, `/vercel/next.js`, `/vercel/next.js/v14.3.0-canary.87`)    |
| `topic`                       | string | No       | Topic to focus documentation on (e.g., `"hooks"`, `"routing"`, `"authentication"`)                                      |
| `tokens`                      | number | No       | Maximum number of tokens of documentation to retrieve. Minimum enforced: 10,000. Default: 10,000                        |

**Upstream API call:** `GET https://context7.com/api/v1/{libraryId}?tokens={tokens}&topic={topic}&type=txt`

**Validation/transform behavior:**
- The `tokens` parameter has a floor of 10,000 (values below are raised automatically).
- String values for `tokens` are coerced to numbers via `z.preprocess`.
- Leading `/` in `context7CompatibleLibraryID` is stripped before the API call.

---

## Security-Sensitive Inputs and Boundaries

### 1. Library ID as a Path Segment (`context7CompatibleLibraryID`)

The `context7CompatibleLibraryID` parameter is directly interpolated into the URL path of the upstream API call:

```typescript
const url = new URL(`${CONTEXT7_API_BASE_URL}/v1/${libraryId}`);
```

This is the most security-relevant parameter. While the `new URL()` constructor provides some protection against path traversal, the value is user-controlled and defines which library's documentation is retrieved. A malicious or overly broad library ID could be used to:
- Access documentation for libraries outside an intended scope.
- Potentially probe the Context7 API namespace if not constrained.

### 2. `libraryName` (Free-Text Search Query)

The `libraryName` parameter is passed as a URL query parameter to the Context7 search API. It controls what libraries are discoverable. An unconstrained search could surface libraries outside an intended domain.

### 3. `topic` (Documentation Focus Filter)

The `topic` parameter filters the documentation content returned. While less risky than the library ID, it controls what portions of documentation the agent sees.

### 4. `tokens` (Documentation Volume)

The `tokens` parameter controls how much documentation content is returned. Higher values consume more LLM context window. The minimum floor is 10,000 tokens but there is no maximum cap enforced in code.

### 5. Client IP Encryption

Client IP addresses are encrypted with AES-256-CBC before being sent to the Context7 API via the `mcp-client-ip` header. The encryption key defaults to a hardcoded value if `CLIENT_IP_ENCRYPTION_KEY` is not set in the environment.

---

## Parameters Defining Usage Boundaries

| Parameter                       | Boundary Type            | Why It Matters                                                                                   |
|---------------------------------|--------------------------|--------------------------------------------------------------------------------------------------|
| `libraryName`                   | Namespace / Domain scope | Controls which libraries are discoverable; can be restricted to approved library names            |
| `context7CompatibleLibraryID`   | Resource ID scope        | Directly selects which library's docs are fetched; can be restricted to allowed org/project pairs |
| `topic`                         | Content scope            | Filters what documentation topics are returned; can be restricted to relevant topics              |
| `tokens`                        | Volume threshold         | Controls documentation size; can be capped to prevent excessive context consumption              |

---

## Intended Workflow

1. Agent calls `resolve-library-id` with a library name to discover matching libraries.
2. Agent selects the most appropriate result and extracts its Context7-compatible library ID.
3. Agent calls `get-library-docs` with the library ID (and optional topic/tokens) to retrieve documentation.
4. Agent uses the retrieved documentation to answer user questions or generate code.

The two tools have a sequential dependency: `resolve-library-id` must typically be called before `get-library-docs`, unless the user provides a library ID directly in `/org/project` format.
