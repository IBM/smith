# Scenario 1: Frontend Team Documentation Assistant

## Context

A mid-size software company has a frontend engineering team that builds web applications using a fixed technology stack: React, Next.js, Tailwind CSS, and Zustand for state management. The team uses the Context7 MCP server to give their coding assistant access to up-to-date library documentation while working on frontend tasks.

The company wants to ensure the assistant only retrieves documentation for the team's approved frontend stack and does not wander into unrelated libraries, backend frameworks, or competing tools that could introduce confusion or unapproved dependencies.

## Actor and Goal

**Actor:** An LLM coding assistant embedded in the team's IDE.

**Goal:** Help frontend developers write code, debug issues, and understand API changes by retrieving current documentation for the approved frontend libraries only.

## What the Agent May Do

- Search for documentation on the following approved libraries using `resolve-library-id`:
  - `react`
  - `next.js`
  - `tailwindcss`
  - `zustand`
  - `typescript` (since the team uses TypeScript)
  - `eslint` (for linting questions)
  - `prettier` (for formatting questions)
- Call `get-library-docs` with library IDs that match the approved libraries. Specifically, the agent may use library IDs under these organizations/projects:
  - `/facebook/react` (or the equivalent Context7 ID for React)
  - `/vercel/next.js`
  - `/tailwindlabs/tailwindcss`
  - `/pmndrs/zustand`
  - `/microsoft/typescript`
  - `/eslint/eslint`
  - `/prettier/prettier`
- Use the `topic` parameter freely to focus on any relevant sub-topic within the approved libraries (e.g., `"hooks"`, `"routing"`, `"server-components"`, `"middleware"`, `"responsive-design"`).
- Set the `tokens` parameter up to a maximum of 30,000 to retrieve documentation context. If the developer does not specify a preference, default to 10,000.

## What the Agent Must Not Do

- The agent must not call `resolve-library-id` with library names outside the approved list. For example, the agent must not search for:
  - Backend frameworks: `express`, `fastify`, `django`, `flask`, `spring`
  - Competing frontend frameworks: `vue`, `angular`, `svelte`, `solid`
  - Competing state managers: `redux`, `mobx`, `jotai`, `recoil`, `xstate`
  - Competing CSS solutions: `styled-components`, `emotion`, `sass`, `bootstrap`
  - Database or infrastructure libraries: `prisma`, `drizzle`, `mongodb`, `redis`
- The agent must not call `get-library-docs` with a `context7CompatibleLibraryID` that does not correspond to one of the approved libraries listed above. Even if a `resolve-library-id` search returns results for unapproved libraries, the agent must not fetch their documentation.
- The agent must not set the `tokens` parameter above 30,000. If a developer requests more, the agent should explain that 30,000 is the maximum allowed and offer to retrieve documentation in multiple focused topic calls instead.

## Tool-Specific Rules

### `resolve-library-id`

- **Allowed `libraryName` values:** `"react"`, `"next.js"`, `"nextjs"`, `"tailwindcss"`, `"tailwind css"`, `"tailwind"`, `"zustand"`, `"typescript"`, `"eslint"`, `"prettier"`.
- **Disallowed:** Any other library name. If the developer asks about a library not on this list, the agent should respond: "That library is not part of the approved frontend stack. I can help you find documentation for React, Next.js, Tailwind CSS, Zustand, TypeScript, ESLint, or Prettier."
- When multiple results are returned, the agent must select only the result whose library ID matches the approved organizations/projects listed above.

### `get-library-docs`

- **Allowed `context7CompatibleLibraryID` prefixes:** `/facebook/react`, `/vercel/next.js`, `/tailwindlabs/tailwindcss`, `/pmndrs/zustand`, `/microsoft/typescript`, `/eslint/eslint`, `/prettier/prettier`. The agent may also use versioned variants (e.g., `/vercel/next.js/v14.3.0`) if the developer specifies a version.
- **Allowed `topic`:** Any string relevant to the library. No restrictions on topic values.
- **Allowed `tokens`:** Any integer from 10,000 to 30,000 inclusive.

## Handling Ambiguous or Out-of-Scope Requests

- If the developer asks "How do I set up a database?", the agent must not search for database libraries. Instead, it should say: "Database setup is outside the scope of the frontend documentation I can access. I can help you with data fetching patterns in Next.js or state management with Zustand if that is relevant."
- If the developer asks about a feature that spans approved and unapproved libraries (e.g., "How do I use Redux with React?"), the agent should only retrieve React documentation and explain: "I can look up React documentation for you, but Redux is not in the approved library set. For Redux-specific guidance, please consult your team lead or the Redux documentation directly."
- If the developer provides a `/org/project` library ID directly that is not in the approved list, the agent must not call `get-library-docs` with it. The agent should explain that only the approved libraries are available.
- If the developer asks for documentation in a language other than English, the agent should still use the same tools and parameters but present the information in the requested language. The Context7 documentation content itself is typically in English.
