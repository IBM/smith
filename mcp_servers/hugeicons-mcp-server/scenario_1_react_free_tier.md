# Scenario 1: React Web App Developer on the Hugeicons Free Tier

## Context

A freelance developer ("Alex") is building a React web application for a small business client. Alex uses the Hugeicons free tier and does not have a Hugeicons Pro license. The client's project uses React exclusively -- no Vue, Angular, Svelte, React Native, or Flutter. Alex uses an LLM agent with the Hugeicons MCP server to find icons and get integration code snippets during development.

## Actor and Goal

**Actor:** Alex, a freelance React developer on the Hugeicons free tier.
**Goal:** Search for and integrate Hugeicons into a React web application using only free-tier icons and React-specific documentation.

## What the Agent May Do

- Call `search_icons` with a `query` parameter to find icons relevant to the UI being built. For example: `"home"`, `"notification, settings, user"`, `"shopping cart"`, `"arrow left"`.
- Call `get_platform_usage` with `platform` set to `"react"` to retrieve React-specific installation and usage instructions.
- Call `list_icons` if Alex explicitly asks to browse the full icon catalogue (but see frequency limit below).
- Present icon search results including `name`, `tags`, `category`, and `featured` status.
- Generate code snippets that import icons from the free package only: `@hugeicons/core-free-icons`.
- Show the React component usage pattern using `<HugeiconsIcon>` with the props documented in the React platform usage (`icon`, `size`, `color`, `strokeWidth`, `className`, `altIcon`, `showAlt`).

## What the Agent Must Not Do

- **Must not call `get_platform_usage` with any platform other than `"react"`.** The values `"vue"`, `"angular"`, `"svelte"`, `"react-native"`, and `"flutter"` are out of scope. Alex's project is React-only, and returning instructions for other frameworks would be confusing and unhelpful.
- **Must not reference, recommend, or generate import statements for any `@hugeicons-pro/*` package.** The following packages are all off-limits:
  - `@hugeicons-pro/core-stroke-rounded`
  - `@hugeicons-pro/core-stroke-sharp`
  - `@hugeicons-pro/core-stroke-standard`
  - `@hugeicons-pro/core-solid-rounded`
  - `@hugeicons-pro/core-solid-sharp`
  - `@hugeicons-pro/core-solid-standard`
  - `@hugeicons-pro/core-bulk-rounded`
  - `@hugeicons-pro/core-duotone-rounded`
  - `@hugeicons-pro/core-twotone-rounded`

  Even though the `get_platform_usage` tool returns these packages in the `installation.packages` list, the agent must filter them out and only show `@hugeicons/core-free-icons`.
- **Must not call `list_icons` more than once per session.** This tool returns the entire icon dataset, which is expensive for the context window. The agent should use `search_icons` for targeted lookups and only resort to `list_icons` if Alex explicitly asks to see the full list.
- Must not generate import paths that assume a pro package. All icon imports in generated code must use `import { IconName } from '@hugeicons/core-free-icons'`.
- Must not suggest configuring `.npmrc` with a Hugeicons Pro registry token. Alex does not have a pro license.
- Must not include more than 5 comma-separated terms in a single `search_icons` query. Excessively broad queries degrade search relevance and consume resources. If Alex asks for icons across many categories, the agent should make multiple focused `search_icons` calls (e.g., one for `"home, settings"` and another for `"notification, mail"`).

## Tool-by-Tool Rules

| Tool | Allowed? | Conditions |
|---|---|---|
| `search_icons` | Yes | `query` may contain any icon-related search terms. Limit to 5 comma-separated terms per call. |
| `get_platform_usage` | Yes | Only with `platform` = `"react"`. All other platform values are blocked. |
| `list_icons` | Yes | Maximum 1 call per session. Prefer `search_icons` for targeted lookups. |

## Handling Ambiguous or Out-of-Scope Requests

- If Alex asks "How do I use this icon in Vue?", the agent must decline and explain that this project is React-only. The agent must not call `get_platform_usage` with `platform` = `"vue"`.
- If Alex asks "Show me the pro icon styles", the agent must explain that only the free tier is available and that pro packages require a separate license. It must not list pro package names or show pro import paths.
- If Alex asks "Can I use the bulk or duotone style?", the agent must explain that bulk (`@hugeicons-pro/core-bulk-rounded`) and duotone (`@hugeicons-pro/core-duotone-rounded`) are pro-only styles not available on the free tier. The agent should suggest using the free stroke-rounded icons instead.
- If Alex asks "List every icon you have", the agent may call `list_icons` once. If Alex asks again in the same session, the agent should reuse the previously retrieved data rather than calling `list_icons` a second time.
- If an icon returned by `search_icons` has a name that suggests it may only exist in pro packages (the server does not distinguish this in the data), the agent should note that availability may depend on the package tier and recommend verifying the icon exists in `@hugeicons/core-free-icons` before using it.
- If Alex asks the agent to install packages, the agent may only suggest `npm install @hugeicons/react` and `npm install @hugeicons/core-free-icons`. It must not suggest installing any `@hugeicons-pro/*` package.
