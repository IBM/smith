# Hugeicons MCP Server -- Tool Summary and Capability Analysis

## Server Overview

**Server name:** hugeicons-mcp
**Version:** 0.1.2
**Framework:** @modelcontextprotocol/sdk (TypeScript, STDIO transport)
**Source:** `src/index.ts` (HugeiconsServer class)
**External data source:** `https://hugeicons.com/api/icons` (fetched once and cached in memory)

The server provides icon search and platform integration documentation for the Hugeicons icon library. It exposes 3 tools and 7 resources. All operations are read-only. The icon data is fetched from the Hugeicons API on first use and cached for the server's lifetime.

---

## Exposed MCP Tools

### 1. `search_icons`
- **Description:** Search for icons by name or tags. Supports comma-separated multi-search (e.g., `"home, notification, settings"`).
- **Parameters:**
  - `query` (string, **required**): Search query. Comma-separated values trigger independent searches whose results are merged and deduplicated.
- **Search behavior:** Uses Fuse.js fuzzy search across icon name (weight 2.0), tags (weight 1.5), category (weight 0.8), and a combined searchable text field (weight 0.5). Threshold is 0.2. Handles hyphenated names and multi-word queries.
- **Return data per icon:** `name`, `tags`, `category`, `featured`, `version`.
- **External requests:** `https://hugeicons.com/api/icons` (only on first call if cache is empty).

### 2. `list_icons`
- **Description:** Returns the complete list of all available Hugeicons icons.
- **Parameters:** None.
- **Return data:** Full array of all `IconInfo` objects (`name`, `tags`, `category`, `featured`, `version`).
- **External requests:** Same as `search_icons` -- fetches from `https://hugeicons.com/api/icons` on first call.

### 3. `get_platform_usage`
- **Description:** Returns platform-specific installation and usage instructions for Hugeicons.
- **Parameters:**
  - `platform` (string, **required**): One of `"react"`, `"vue"`, `"angular"`, `"svelte"`, `"react-native"`, `"flutter"`.
- **Return data:** JSON object with `platform`, `installation` (core install command + available packages list), `basicUsage` (code example), and `props` (component props table).
- **External requests:** None. Data is hardcoded in `src/utils/platform-usage.ts`.

---

## MCP Resources

The server also exposes 7 readable resources:

| URI | Description |
|---|---|
| `hugeicons://docs/platforms/react` | React integration guide (markdown) |
| `hugeicons://docs/platforms/vue` | Vue integration guide (markdown) |
| `hugeicons://docs/platforms/angular` | Angular integration guide (markdown) |
| `hugeicons://docs/platforms/svelte` | Svelte integration guide (markdown) |
| `hugeicons://docs/platforms/react-native` | React Native integration guide (markdown) |
| `hugeicons://docs/platforms/flutter` | Flutter integration guide (markdown) |
| `hugeicons://icons/index` | Complete JSON index of all icons |

---

## Security and Boundary Analysis

### User-Supplied Parameters

| Parameter | Tool | Type | Sensitivity |
|---|---|---|---|
| `query` | `search_icons` | Free-text string | **Low-medium.** Passed to Fuse.js for in-memory fuzzy matching. Not used in HTTP requests, SQL, file paths, or shell commands. No injection vector exists in the current code. However, the query string is unbounded in length and the comma-separated parsing means a single call can trigger many independent search passes over the full icon set, creating a potential resource-consumption vector. |
| `platform` | `get_platform_usage` | Enum string | **Low.** Validated against a fixed allowlist (`react`, `vue`, `angular`, `svelte`, `react-native`, `flutter`). Invalid values are rejected before any lookup. |

### Fixed External Request Target
The only outbound HTTP request is to `https://hugeicons.com/api/icons`. This URL is hardcoded and cannot be influenced by tool parameters.

### Package References in Output
The `get_platform_usage` tool returns package names including `@hugeicons-pro/*` packages. The tool notes that pro packages require `.npmrc` authentication. An agent blindly following the installation instructions could attempt to install pro packages the user is not licensed for.

### Data Exposure
All returned data (icon names, tags, categories, code examples) is publicly available documentation-level content. No credentials, user data, or private information is exposed.

---

## Parameters That Could Define Usage Boundaries

| Boundary Dimension | Applicable Values |
|---|---|
| **Search query content** | Specific icon names, categories, or tags the agent is allowed to search for |
| **Platform scope** | Which of the 6 platforms (`react`, `vue`, `angular`, `svelte`, `react-native`, `flutter`) the agent may request usage docs for |
| **Package tier** | Whether the agent may reference/recommend free packages only (`@hugeicons/core-free-icons`) or also pro packages (`@hugeicons-pro/*`) |
| **Icon categories** | Whether the agent is restricted to specific icon categories (e.g., only "navigation" icons, only "media" icons) |
| **Call frequency** | How often `list_icons` (expensive, full dataset) vs. `search_icons` (targeted) may be called |
| **Output usage** | Whether the agent may generate installation commands, code snippets, or only icon names |
