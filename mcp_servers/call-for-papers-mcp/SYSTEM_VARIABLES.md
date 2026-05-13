# System Variables for Call-for-Papers MCP Agent

Recommended system variables for enforceable policy design. These are passed via the `system_variables` field in the `/chat` request body and injected into the agent's system prompt for policy-aware reasoning.

## Variable Definitions

### `user_role`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | The role of the requesting user within the organization |
| **Example values** | `faculty`, `phd_student`, `admin_coordinator`, `advisor`, `guest` |
| **Policy use** | Controls topic scope, result caps, rate limits, and what actions the agent may take. For example, a `phd_student` may be restricted to their dissertation topic, while `faculty` has broader access. |

### `user_id`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | Unique identity of the requesting user |
| **Example values** | `jdoe@university.edu`, `student_2024_0042` |
| **Policy use** | Audit trail for tool invocations, per-user rate limiting, and session tracking. |

### `department`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | The academic department or unit the user belongs to |
| **Example values** | `computer_science`, `electrical_engineering`, `multidisciplinary` |
| **Policy use** | Topic restrictions — e.g., a CS department policy may restrict searches to AI/ML, cybersecurity, and software engineering topics only. |

### `research_area`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | The user's specific research focus or dissertation topic |
| **Example values** | `federated_learning_healthcare`, `natural_language_processing`, `network_security` |
| **Policy use** | Narrow keyword restrictions for focused users (e.g., PhD students must search within their dissertation scope). |

### `organization_id`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | The organization or consortium the user belongs to |
| **Example values** | `eu_research_consortium_42`, `university_of_example` |
| **Policy use** | Multi-tenant scoping — different organizations may have different policies for the same tool. |

### `max_results_per_query`

| Field | Value |
|-------|-------|
| **Type** | string (integer as string) |
| **Description** | Maximum number of results the agent should return per tool call |
| **Example values** | `5`, `10`, `15`, `20` |
| **Policy use** | Per-role volume control. Advisors may cap students at 5 results to prevent information overload; coordinators may allow up to 20. |

### `max_queries_per_session`

| Field | Value |
|-------|-------|
| **Type** | string (integer as string) |
| **Description** | Maximum number of `get_events` calls allowed in a single conversation session |
| **Example values** | `3`, `5`, `10` |
| **Policy use** | Rate limiting to prevent excessive scraping and keep users focused on deliberate searches. |

### `allowed_topics`

| Field | Value |
|-------|-------|
| **Type** | string (comma-separated) |
| **Description** | List of permitted topic areas for searches |
| **Example values** | `AI,cybersecurity,software_engineering`, `any`, `federated_learning,healthcare` |
| **Policy use** | Topic-based access control. The agent should refuse to search for keywords outside these areas. |

### `region_filter`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | Geographic region constraint for post-processing results |
| **Example values** | `europe`, `asia`, `any` |
| **Policy use** | Location-based filtering — e.g., a European consortium only wants conferences held in Europe flagged as actionable. |

## Example Request

```json
{
  "message": "Find NLP conferences with upcoming deadlines",
  "system_variables": {
    "user_role": "phd_student",
    "user_id": "alice@cs.example.edu",
    "department": "computer_science",
    "research_area": "natural_language_processing",
    "organization_id": "university_of_example",
    "max_results_per_query": "10",
    "max_queries_per_session": "5",
    "allowed_topics": "AI,cybersecurity,software_engineering",
    "region_filter": "any"
  }
}
```

## Mapping to Guidance Scenarios

| Scenario | Key Variables |
|----------|--------------|
| Scenario 1: Department Research Assistant | `user_role=faculty`, `department=computer_science`, `allowed_topics=AI,cybersecurity,software_engineering`, `max_results_per_query=15`, `max_queries_per_session=5` |
| Scenario 2: European Travel Coordinator | `user_role=admin_coordinator`, `allowed_topics=any`, `region_filter=europe`, `max_results_per_query=20`, `max_queries_per_session=10` |
| Scenario 3: PhD Student (Narrow Focus) | `user_role=phd_student`, `research_area=federated_learning_healthcare`, `max_results_per_query=5`, `max_queries_per_session=3` |
