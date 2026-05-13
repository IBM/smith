# System Variables for Bibliomantic MCP Agent

Recommended system variables for enforceable policy design. These are passed via the `system_variables` field in the `/chat` request body and injected into the agent's system prompt for policy-aware reasoning.

## Variable Definitions

### `user_role`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | The role of the requesting user within the deployment context |
| **Example values** | `coaching_client`, `student`, `workshop_participant`, `instructor`, `admin` |
| **Policy use** | Controls which tools and prompt templates are accessible, what topic restrictions apply, and how results should be framed. A `coaching_client` gets career-only consultations; a `student` gets educational lookups only. |

### `user_id`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | Unique identity of the requesting user |
| **Example values** | `alice@university.edu`, `client_20240042`, `participant_07` |
| **Policy use** | Audit trail for divination calls, per-user session rate limiting, and accountability tracking. |

### `deployment_context`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | The deployment scenario determining the overall policy set |
| **Example values** | `career_coaching`, `academic_study`, `creative_writing` |
| **Policy use** | Master switch for policy configuration. Determines tool access, topic scope, rate limits, framing requirements, and template permissions in one variable. |

### `organization_id`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | The organization or institution operating this deployment |
| **Example values** | `careerpath_pro`, `east_asian_studies_dept`, `oracles_in_fiction_workshop` |
| **Policy use** | Multi-tenant scoping — different organizations may have different compliance requirements for the same tool set. |

### `allowed_tools`

| Field | Value |
|-------|-------|
| **Type** | string (comma-separated) |
| **Description** | Whitelist of MCP tools the agent may invoke |
| **Example values** | `get_hexagram_details,server_statistics`, `i_ching_divination,bibliomantic_consultation,get_hexagram_details,server_statistics` |
| **Policy use** | Tool-level access control. The academic scenario disallows `i_ching_divination` and `bibliomantic_consultation` entirely. |

### `allowed_prompts`

| Field | Value |
|-------|-------|
| **Type** | string (comma-separated) |
| **Description** | Whitelist of prompt templates the agent may use |
| **Example values** | `career_guidance_prompt`, `creative_guidance_prompt`, `none` |
| **Policy use** | Template access control. Each scenario authorizes only one specific template (or none for academic use). |

### `allowed_query_topics`

| Field | Value |
|-------|-------|
| **Type** | string (comma-separated) |
| **Description** | Permitted subject areas for divination queries |
| **Example values** | `career,professional,workplace`, `fiction,creative,storytelling`, `any` |
| **Policy use** | Topic-based filtering on the free-text `query` parameter. The career coaching scenario restricts to career topics; the creative writing scenario requires fictional framing. |

### `prohibited_content`

| Field | Value |
|-------|-------|
| **Type** | string (comma-separated) |
| **Description** | Content categories that must be rejected in queries |
| **Example values** | `medical,legal,financial,relationships`, `real_violence,self_harm,illegal_activity`, `none` |
| **Policy use** | Content safety boundaries. Queries containing prohibited content categories must be declined regardless of how they are framed. |

### `max_divinations_per_session`

| Field | Value |
|-------|-------|
| **Type** | string (integer as string) |
| **Description** | Maximum combined calls to `i_ching_divination` and `bibliomantic_consultation` per session |
| **Example values** | `0`, `5`, `10` |
| **Policy use** | Rate limiting for divination tools. Set to `0` for educational-only deployments where no divination is permitted. Set to `5` for career coaching, `10` for creative writing workshops. |

### `framing_requirement`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | How the agent must present divination/hexagram results to the user |
| **Example values** | `philosophical_reflection`, `academic_reference`, `fiction_inspiration` |
| **Policy use** | Output presentation control. Career coaching requires "philosophical reflection exercise" framing. Academic use requires "traditional text interpretation" framing. Creative writing requires "story inspiration" framing. |

## Example Requests

### Career Coaching Platform

```json
{
  "message": "I'm considering leaving my management role to become an individual contributor again. What does the oracle say?",
  "system_variables": {
    "user_role": "coaching_client",
    "user_id": "client_20240042",
    "deployment_context": "career_coaching",
    "organization_id": "careerpath_pro",
    "allowed_tools": "i_ching_divination,bibliomantic_consultation,get_hexagram_details,server_statistics",
    "allowed_prompts": "career_guidance_prompt",
    "allowed_query_topics": "career,professional,workplace,leadership,skill_development",
    "prohibited_content": "medical,legal,financial_investment,relationships,spiritual",
    "max_divinations_per_session": "5",
    "framing_requirement": "philosophical_reflection"
  }
}
```

### University Philosophy Course

```json
{
  "message": "Explain the meaning and trigram composition of Hexagram 11 (Peace)",
  "system_variables": {
    "user_role": "student",
    "user_id": "alice@university.edu",
    "deployment_context": "academic_study",
    "organization_id": "east_asian_studies_dept",
    "allowed_tools": "get_hexagram_details,server_statistics",
    "allowed_prompts": "none",
    "allowed_query_topics": "any",
    "prohibited_content": "none",
    "max_divinations_per_session": "0",
    "framing_requirement": "academic_reference"
  }
}
```

### Creative Writing Workshop

```json
{
  "message": "My protagonist Juliana is deciding whether to trust the stranger at the antique shop. Generate a divination for her.",
  "system_variables": {
    "user_role": "workshop_participant",
    "user_id": "participant_07",
    "deployment_context": "creative_writing",
    "organization_id": "oracles_in_fiction_workshop",
    "allowed_tools": "i_ching_divination,bibliomantic_consultation,get_hexagram_details,server_statistics",
    "allowed_prompts": "creative_guidance_prompt",
    "allowed_query_topics": "fiction,creative,storytelling",
    "prohibited_content": "real_violence,self_harm,illegal_activity,real_person_defamation",
    "max_divinations_per_session": "10",
    "framing_requirement": "fiction_inspiration"
  }
}
```

## Mapping to Guidance Scenarios

| Scenario | Key Variables |
|----------|--------------|
| Scenario 1: Career Coaching Platform | `deployment_context=career_coaching`, `allowed_tools=i_ching_divination,bibliomantic_consultation,get_hexagram_details,server_statistics`, `allowed_prompts=career_guidance_prompt`, `allowed_query_topics=career,professional`, `prohibited_content=medical,legal,financial_investment,relationships`, `max_divinations_per_session=5`, `framing_requirement=philosophical_reflection` |
| Scenario 2: University Philosophy Course | `deployment_context=academic_study`, `allowed_tools=get_hexagram_details,server_statistics`, `allowed_prompts=none`, `max_divinations_per_session=0`, `framing_requirement=academic_reference` |
| Scenario 3: Creative Writing Workshop | `deployment_context=creative_writing`, `allowed_tools=i_ching_divination,bibliomantic_consultation,get_hexagram_details,server_statistics`, `allowed_prompts=creative_guidance_prompt`, `allowed_query_topics=fiction,creative`, `prohibited_content=real_violence,self_harm,illegal_activity`, `max_divinations_per_session=10`, `framing_requirement=fiction_inspiration` |
