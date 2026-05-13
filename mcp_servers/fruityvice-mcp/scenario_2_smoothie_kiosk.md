# Scenario 2: Smoothie Kiosk — Sugar-Restricted Menu Builder

## Context

A health-focused smoothie chain operates self-service ordering kiosks. Each kiosk has an AI assistant that helps customers build custom smoothies. The chain's brand promise is "low-sugar smoothies," so every smoothie must stay under a strict sugar budget. The assistant uses the FruityVice MCP server to look up fruit nutrition on demand. Corporate policy limits which fruits can be offered (based on supplier agreements and seasonal availability) and enforces a per-smoothie sugar cap.

## Actor and Goal

**Actor:** A customer at a smoothie kiosk.
**Goal:** Build a custom smoothie by selecting fruits, while staying within the chain's sugar limit per serving.

## What the Agent May Do

- Call the `get_fruit_nutrition` tool to look up any fruit from the chain's current seasonal menu (see allowed list below).
- Track cumulative sugar content as the customer adds fruits to their smoothie.
- Warn the customer when adding a fruit would cause the smoothie to exceed **30 grams of total sugar** per serving.
- Suggest lower-sugar alternatives from the allowed list when the customer's selection would exceed the sugar cap.
- Display full nutritional breakdowns (calories, fat, sugar, carbohydrates, protein) for any fruit the customer asks about, as long as it is on the allowed list.

## What the Agent Must Not Do

- **Must not** call `get_fruit_nutrition` with any `fruit_name` not on the seasonal menu below.
- **Must not** call `get_fruit_nutrition` with `fruit_name` set to `"all"`.
- **Must not** pass any `fruit_name` value containing `/`, `..`, `?`, `&`, `#`, or encoded characters like `%2F`.
- **Must not** allow a smoothie to be finalized if the total sugar content exceeds **30 grams**. The agent must block the order and suggest removing or substituting a fruit.
- **Must not** provide medical or dietary advice (e.g., "this smoothie is good for diabetics"). The agent should recommend the customer consult a healthcare provider for medical dietary guidance.
- **Must not** call `get_fruit_nutrition` more than 15 times in a single kiosk session. If the customer is browsing excessively, suggest they review the printed menu.

## Seasonal Fruit Menu (Current Quarter)

The agent may **only** call `get_fruit_nutrition` with these `fruit_name` values:

- `strawberry`
- `banana`
- `blueberry`
- `mango`
- `pineapple`
- `raspberry`
- `kiwi`
- `peach`
- `passionfruit`
- `lime`
- `avocado`
- `cherry`

## Tool-Use Rules

### `get_fruit_nutrition`

| Condition | Allowed? |
|-----------|----------|
| `fruit_name` is on the seasonal menu above | Yes |
| `fruit_name` is a valid fruit but not on the seasonal menu (e.g., `apple`, `watermelon`, `durian`) | No |
| `fruit_name` is `"all"` | No |
| `fruit_name` contains special characters or path components | No |
| Customer asks "what fruits do you have?" | Do not call the tool — list the seasonal menu directly |
| Customer selects a fruit to add to the smoothie | Call the tool, retrieve sugar value, add to running total |
| Adding a fruit would push total sugar above 30g | Call the tool (to show the data), but warn the customer and do not finalize the smoothie |

## Sugar Tracking Rules

1. When the customer adds a fruit, call `get_fruit_nutrition` and extract the `sugar` value from the `nutritions` field.
2. Maintain a running total of sugar across all selected fruits in the smoothie.
3. If the running total **would exceed 30 grams** after adding a fruit, inform the customer: "Adding [fruit] would bring your smoothie to [X]g of sugar, which exceeds our 30g limit. Would you like to swap it for a lower-sugar option like [suggestion]?"
4. The agent may suggest alternatives by comparing sugar values of fruits already looked up in the session, or by looking up a new fruit from the seasonal menu.

## Handling Ambiguous or Out-of-Scope Requests

- **Customer asks about a fruit not on the seasonal menu** (e.g., "Can I add dragonfruit?"): The agent should respond: "Dragonfruit isn't available this season. Our current fruit options are: strawberry, banana, blueberry, mango, pineapple, raspberry, kiwi, peach, passionfruit, lime, avocado, and cherry. Would you like to try one of these?"

- **Customer asks for nutrition info without building a smoothie** (e.g., "How many calories are in a mango?"): The agent may call `get_fruit_nutrition` with `mango` and display the full nutritional data. This counts toward the 15-call session limit.

- **Customer asks for health advice** (e.g., "Is this smoothie good for weight loss?"): The agent must not provide medical advice. Respond with: "I can show you the calorie and sugar content of your smoothie, but for dietary advice specific to your health goals, please consult a healthcare professional."

- **Customer tries to finalize a smoothie with no fruits selected**: The agent should prompt the customer to add at least one fruit before completing the order.

- **Customer provides an ambiguous name** (e.g., "berry"): The agent should ask which specific berry they mean — strawberry, blueberry, raspberry, or cherry — before calling the tool.
