# System Variables for Context7 MCP Agent

Recommended system variables for enforceable policy design. These are passed via the `system_variables` field in the `/chat` request body and injected into the agent's system prompt for policy-aware reasoning.

## Variable Definitions

### `user_role`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | The role of the requesting user within the organization |
| **Example values** | `frontend_developer`, `platform_engineer`, `security_engineer`, `tech_lead` |
| **Policy use** | Determines which libraries and topics are accessible. A frontend developer may only access frontend stack docs; a security engineer may only access security-relevant topics. |

### `user_id`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | Unique identity of the requesting user |
| **Example values** | `dev_042@company.com`, `eng_sec_07` |
| **Policy use** | Audit trail for documentation access, per-user rate limiting. |

### `organization_id`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | The organization or team the user belongs to |
| **Example values** | `frontend_team`, `platform_engineering`, `security_audit_team` |
| **Policy use** | Multi-tenant scoping — different teams have different approved library sets. |

### `allowed_libraries`

| Field | Value |
|-------|-------|
| **Type** | string (comma-separated) |
| **Description** | Whitelist of library names the agent may search for via `resolve-library-id` |
| **Example values** | `react,next.js,tailwindcss,zustand,typescript,eslint,prettier`, `jsonwebtoken,bcrypt,passport,helmet,jose,crypto-js,express`, `next.js,node` |
| **Policy use** | Library-level access control. The agent must not resolve or fetch documentation for libraries outside this list. |

### `allowed_library_ids`

| Field | Value |
|-------|-------|
| **Type** | string (comma-separated) |
| **Description** | Whitelist of Context7-compatible library ID prefixes the agent may use with `get-library-docs` |
| **Example values** | `/vercel/next.js,/facebook/react,/tailwindlabs/tailwindcss,/pmndrs/zustand`, `/auth0/node-jsonwebtoken,/kelektiv/node.bcrypt.js,/jaredhanson/passport` |
| **Policy use** | Resource-level access control. Prevents fetching documentation for unapproved libraries even if they appear in search results. |

### `allowed_versions`

| Field | Value |
|-------|-------|
| **Type** | string (comma-separated version patterns) |
| **Description** | Allowed version ranges for library documentation |
| **Example values** | `v13.*,v14.*`, `v18.*,v20.*`, `any` |
| **Policy use** | Version scoping for migration scenarios. Prevents fetching docs for unsupported legacy versions or unreleased future versions. |

### `allowed_topics`

| Field | Value |
|-------|-------|
| **Type** | string (comma-separated) |
| **Description** | Whitelist of topic values the agent may use when fetching documentation |
| **Example values** | `any`, `authentication,authorization,signing,verification,hashing,encryption,security,configuration,middleware,headers`, `app-router,pages-router,migration,breaking-changes,server-components` |
| **Policy use** | Content scope restriction. Prevents retrieval of general tutorials or off-topic documentation in focused workflows. |

### `prohibited_topics`

| Field | Value |
|-------|-------|
| **Type** | string (comma-separated) |
| **Description** | Topics the agent must not use in documentation retrieval |
| **Example values** | `tutorial,getting-started,installation,quickstart,testing,mocking,performance,benchmarks`, `none` |
| **Policy use** | Excludes irrelevant content categories. Useful for security audits where tutorial content would be noise. |

### `max_tokens_per_call`

| Field | Value |
|-------|-------|
| **Type** | string (integer as string) |
| **Description** | Maximum value for the `tokens` parameter in `get-library-docs` calls |
| **Example values** | `15000`, `20000`, `30000` |
| **Policy use** | Controls documentation volume per retrieval. Lower values enforce focused, topic-specific lookups and conserve LLM context window. |

### `task_context`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | The specific task or workflow the agent is supporting |
| **Example values** | `frontend_development`, `version_migration_nextjs_13_to_14`, `security_dependency_audit` |
| **Policy use** | Informs the agent about the purpose of documentation retrieval, helping it make better decisions about relevance and focus. |

## Example Requests

### Frontend Team Documentation Assistant

```json
{
  "message": "How do I use server components in Next.js with Zustand for state management?",
  "system_variables": {
    "user_role": "frontend_developer",
    "user_id": "dev_042@company.com",
    "organization_id": "frontend_team",
    "allowed_libraries": "react,next.js,tailwindcss,zustand,typescript,eslint,prettier",
    "allowed_library_ids": "/vercel/next.js,/facebook/react,/tailwindlabs/tailwindcss,/pmndrs/zustand,/microsoft/typescript,/eslint/eslint,/prettier/prettier",
    "allowed_versions": "any",
    "allowed_topics": "any",
    "prohibited_topics": "none",
    "max_tokens_per_call": "30000",
    "task_context": "frontend_development"
  }
}
```

### Version-Controlled Migration Assistant

```json
{
  "message": "What changed in the App Router between Next.js 13 and 14?",
  "system_variables": {
    "user_role": "platform_engineer",
    "user_id": "eng_platform_03@company.com",
    "organization_id": "platform_engineering",
    "allowed_libraries": "next.js,node",
    "allowed_library_ids": "/vercel/next.js,/nodejs/node",
    "allowed_versions": "v13.*,v14.*,v18.*,v20.*",
    "allowed_topics": "app-router,pages-router,migration,breaking-changes,server-components,server-actions,metadata,route-handlers,middleware,streams,fetch,esm",
    "prohibited_topics": "none",
    "max_tokens_per_call": "15000",
    "task_context": "version_migration_nextjs_13_to_14"
  }
}
```

### Security-Focused Dependency Audit

```json
{
  "message": "Show me the JWT signing and verification documentation for jsonwebtoken",
  "system_variables": {
    "user_role": "security_engineer",
    "user_id": "eng_sec_07@company.com",
    "organization_id": "security_audit_team",
    "allowed_libraries": "jsonwebtoken,bcrypt,passport,helmet,jose,crypto-js,express",
    "allowed_library_ids": "/auth0/node-jsonwebtoken,/kelektiv/node.bcrypt.js,/jaredhanson/passport,/helmetjs/helmet,/panva/jose,/brix/crypto-js,/expressjs/express",
    "allowed_versions": "any",
    "allowed_topics": "authentication,authorization,signing,verification,hashing,encryption,decryption,key-management,vulnerabilities,security,best-practices,configuration,middleware,headers,csrf,cors,xss,token,session,secrets,algorithms",
    "prohibited_topics": "tutorial,getting-started,installation,quickstart,testing,mocking,performance,benchmarks,migration,changelog,release-notes",
    "max_tokens_per_call": "20000",
    "task_context": "security_dependency_audit"
  }
}
```

## Mapping to Guidance Scenarios

| Scenario | Key Variables |
|----------|--------------|
| Scenario 1: Frontend Team | `allowed_libraries=react,next.js,tailwindcss,zustand,typescript,eslint,prettier`, `max_tokens_per_call=30000`, `allowed_topics=any`, `task_context=frontend_development` |
| Scenario 2: Version Migration | `allowed_libraries=next.js,node`, `allowed_versions=v13.*,v14.*,v18.*,v20.*`, `max_tokens_per_call=15000`, `task_context=version_migration_nextjs_13_to_14` |
| Scenario 3: Security Audit | `allowed_libraries=jsonwebtoken,bcrypt,passport,helmet,jose,crypto-js,express`, `prohibited_topics=tutorial,getting-started,installation,...`, `allowed_topics=authentication,security,...`, `max_tokens_per_call=20000`, `task_context=security_dependency_audit` |
