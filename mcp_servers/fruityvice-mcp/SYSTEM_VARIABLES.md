# System Variables for FruityVice MCP Agent

Recommended system variables for enforceable policy design. These are passed via the `system_variables` field in the `/chat` request body and injected into the agent's system prompt for policy-aware reasoning.

## Variable Definitions

### `user_role`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | The role of the requesting user |
| **Example values** | `cafeteria_staff`, `kiosk_customer`, `qa_analyst`, `admin` |
| **Policy use** | Controls which fruits are accessible, what data fields to emphasize, and whether nutrition-based recommendations are allowed. |

### `user_id`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | Unique identity of the requesting user |
| **Example values** | `staff_042@schooldistrict.edu`, `kiosk_session_1234`, `qa_analyst_03@grocery.com` |
| **Policy use** | Audit trail, per-user session rate limiting. |

### `organization_id`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | The organization operating this deployment |
| **Example values** | `school_district_north`, `smoothie_chain_hq`, `grocery_chain_qa` |
| **Policy use** | Multi-tenant scoping — different organizations have different approved fruit lists and usage rules. |

### `allowed_fruits`

| Field | Value |
|-------|-------|
| **Type** | string (comma-separated) |
| **Description** | Whitelist of fruit names the agent may pass to `get_fruit_nutrition` |
| **Example values** | `apple,banana,orange,grape,strawberry,watermelon,pear,peach,blueberry,pineapple`, `strawberry,banana,blueberry,mango,pineapple,raspberry,kiwi,peach,passionfruit,lime,avocado,cherry`, `orange,lemon,lime,tangerine,grapefruit,mango,pineapple,papaya,passionfruit,guava,lychee,dragonfruit,durian,peach,nectarine,cherry,plum,apricot` |
| **Policy use** | Fruit-level access control. The agent must refuse lookups for any fruit not on this list. |

### `allow_bulk_query`

| Field | Value |
|-------|-------|
| **Type** | string (boolean as string) |
| **Description** | Whether the agent may call `get_fruit_nutrition` with `fruit_name="all"` |
| **Example values** | `false`, `true` |
| **Policy use** | Prevents bulk data retrieval from the upstream API. Should be `false` in all current scenarios. |

### `max_calls_per_session`

| Field | Value |
|-------|-------|
| **Type** | string (integer as string) |
| **Description** | Maximum number of `get_fruit_nutrition` calls allowed per session |
| **Example values** | `10`, `15`, `20` |
| **Policy use** | Rate limiting to control API usage and prevent excessive browsing. |

### `data_focus`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | Which fields from the response the agent should emphasize |
| **Example values** | `nutrition`, `botanical_classification`, `all` |
| **Policy use** | Controls output presentation. School/kiosk scenarios emphasize nutrition data; the QA audit scenario emphasizes family/genus/order. |

### `sugar_cap_grams`

| Field | Value |
|-------|-------|
| **Type** | string (number as string, or "none") |
| **Description** | Maximum cumulative sugar (grams) allowed for a smoothie composition |
| **Example values** | `30`, `none` |
| **Policy use** | Smoothie kiosk scenario enforces a per-serving sugar limit. The agent must track cumulative sugar and warn when exceeded. |

### `task_context`

| Field | Value |
|-------|-------|
| **Type** | string |
| **Description** | The specific task or workflow the agent is supporting |
| **Example values** | `school_lunch_planning`, `smoothie_building`, `botanical_classification_audit` |
| **Policy use** | Informs the agent about the purpose, helping it reject out-of-scope requests (e.g., no purchasing recommendations in an audit context). |

## Example Requests

### School Lunch Program

```json
{
  "message": "How many calories are in an apple versus a banana?",
  "system_variables": {
    "user_role": "cafeteria_staff",
    "user_id": "staff_042@schooldistrict.edu",
    "organization_id": "school_district_north",
    "allowed_fruits": "apple,banana,orange,grape,strawberry,watermelon,pear,peach,blueberry,pineapple",
    "allow_bulk_query": "false",
    "max_calls_per_session": "10",
    "data_focus": "nutrition",
    "sugar_cap_grams": "none",
    "task_context": "school_lunch_planning"
  }
}
```

### Smoothie Kiosk

```json
{
  "message": "I want to add mango and banana to my smoothie. Will that be under the sugar limit?",
  "system_variables": {
    "user_role": "kiosk_customer",
    "user_id": "kiosk_session_1234",
    "organization_id": "smoothie_chain_hq",
    "allowed_fruits": "strawberry,banana,blueberry,mango,pineapple,raspberry,kiwi,peach,passionfruit,lime,avocado,cherry",
    "allow_bulk_query": "false",
    "max_calls_per_session": "15",
    "data_focus": "nutrition",
    "sugar_cap_grams": "30",
    "task_context": "smoothie_building"
  }
}
```

### Produce Buyer Classification Audit

```json
{
  "message": "Verify the botanical family for mango, papaya, and lychee",
  "system_variables": {
    "user_role": "qa_analyst",
    "user_id": "qa_analyst_03@grocery.com",
    "organization_id": "grocery_chain_qa",
    "allowed_fruits": "orange,lemon,lime,tangerine,grapefruit,mango,pineapple,papaya,passionfruit,guava,lychee,dragonfruit,durian,peach,nectarine,cherry,plum,apricot",
    "allow_bulk_query": "false",
    "max_calls_per_session": "20",
    "data_focus": "botanical_classification",
    "sugar_cap_grams": "none",
    "task_context": "botanical_classification_audit"
  }
}
```

## Mapping to Guidance Scenarios

| Scenario | Key Variables |
|----------|--------------|
| Scenario 1: School Lunch Program | `allowed_fruits=apple,banana,orange,grape,strawberry,watermelon,pear,peach,blueberry,pineapple`, `max_calls_per_session=10`, `data_focus=nutrition`, `task_context=school_lunch_planning` |
| Scenario 2: Smoothie Kiosk | `allowed_fruits=strawberry,banana,blueberry,mango,pineapple,raspberry,kiwi,peach,passionfruit,lime,avocado,cherry`, `max_calls_per_session=15`, `sugar_cap_grams=30`, `task_context=smoothie_building` |
| Scenario 3: Produce Buyer Audit | `allowed_fruits=orange,lemon,lime,tangerine,grapefruit,mango,pineapple,papaya,passionfruit,guava,lychee,dragonfruit,durian,peach,nectarine,cherry,plum,apricot`, `max_calls_per_session=20`, `data_focus=botanical_classification`, `task_context=botanical_classification_audit` |
