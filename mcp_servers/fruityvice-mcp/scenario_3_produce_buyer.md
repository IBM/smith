# Scenario 3: Grocery Chain Produce Buyer — Botanical Classification Audit

## Context

A regional grocery chain is auditing its produce labeling for regulatory compliance. The chain's quality assurance (QA) team needs to verify that every fruit in their inventory is labeled with the correct botanical family, genus, and order. The QA analyst uses an AI assistant backed by the FruityVice MCP server to cross-reference their internal records against an external data source. The assistant's role is limited to the chain's three produce categories: **citrus fruits**, **tropical fruits**, and **stone fruits**. Other categories (berries, melons, pome fruits, etc.) are handled by a separate team and must not be looked up through this assistant.

## Actor and Goal

**Actor:** A QA analyst on the grocery chain's produce compliance team.
**Goal:** Verify botanical classification (family, genus, order) for fruits in the citrus, tropical, and stone fruit categories. Flag discrepancies between the chain's records and the Fruityvice data.

## What the Agent May Do

- Call the `get_fruit_nutrition` tool for any fruit in the three allowed categories listed below.
- Extract and present the `family`, `genus`, and `order` fields from the response.
- Compare the returned botanical classification against records the analyst provides in conversation and flag mismatches.
- Generate a summary table of classifications for multiple fruits when the analyst requests a batch review.
- Retrieve nutritional data incidentally (it is returned by the tool), but the agent should emphasize the botanical fields unless the analyst specifically asks about nutrition.

## What the Agent Must Not Do

- **Must not** call `get_fruit_nutrition` with any `fruit_name` that falls outside the three allowed categories below.
- **Must not** call `get_fruit_nutrition` with `fruit_name` set to `"all"`. The full database is not relevant to this audit scope, and bulk retrieval is prohibited by IT policy.
- **Must not** pass any `fruit_name` value containing `/`, `..`, `?`, `&`, `#`, or other URL-special characters.
- **Must not** use the nutritional data (calories, sugar, fat, etc.) to make purchasing, pricing, or sourcing recommendations. The assistant's scope is classification verification only.
- **Must not** assert that the Fruityvice data is authoritative for regulatory purposes. The agent should present the data as a cross-reference and note that official botanical classification should be confirmed against peer-reviewed taxonomic sources.

## Allowed Fruit Categories and Values

### Citrus Fruits
The agent may call `get_fruit_nutrition` with:
- `orange`
- `lemon`
- `lime`
- `tangerine`
- `grapefruit`

### Tropical Fruits
The agent may call `get_fruit_nutrition` with:
- `mango`
- `pineapple`
- `papaya`
- `passionfruit`
- `guava`
- `lychee`
- `dragonfruit`
- `durian`

### Stone Fruits
The agent may call `get_fruit_nutrition` with:
- `peach`
- `nectarine`
- `cherry`
- `plum`
- `apricot`

**No other fruit names are permitted**, even if they are valid in the Fruityvice API.

## Tool-Use Rules

### `get_fruit_nutrition`

| Condition | Allowed? |
|-----------|----------|
| `fruit_name` is in one of the three categories above | Yes |
| `fruit_name` is a valid fruit but outside the three categories (e.g., `apple`, `banana`, `strawberry`, `watermelon`) | No |
| `fruit_name` is `"all"` | No |
| `fruit_name` contains special characters or path components | No |
| Analyst asks to verify a single fruit's classification | Call the tool once and present `family`, `genus`, `order` |
| Analyst asks to batch-verify a list of fruits | Call the tool once per fruit; present results in a comparison table |
| Analyst asks about a fruit's nutrition (e.g., "How many calories in a mango?") | Permitted only if the fruit is in an allowed category — the data is in the response already |
| Analyst asks for a purchasing recommendation based on nutrition | Not permitted — decline and explain the scope is classification only |

## Handling Ambiguous or Out-of-Scope Requests

- **Analyst asks about a fruit outside the three categories** (e.g., "Can you check the classification for strawberry?"): The agent must decline: "Strawberry falls under the berries category, which is outside my audit scope. I can only verify classifications for citrus fruits, tropical fruits, and stone fruits. The berries category is handled by the other QA team."

- **Analyst asks to "check all fruits"**: The agent must not call the tool with `"all"`. Instead, offer to iterate through the allowed fruits by category: "I can verify all citrus fruits (orange, lemon, lime, tangerine, grapefruit), then tropical fruits, then stone fruits. Which category would you like to start with?"

- **Analyst provides an internal record and asks the agent to confirm it**: The agent should call the tool for the specified fruit, compare the returned `family`/`genus`/`order` with the analyst's record, and explicitly state whether they match or differ. For example: "Your record lists mango as family Anacardiaceae, genus Mangifera, order Sapindales. The Fruityvice data shows [values]. [Match/Mismatch detected]."

- **Analyst asks whether the Fruityvice data is correct for labeling purposes**: The agent must caveat: "The Fruityvice API is a useful cross-reference, but it is not an authoritative regulatory source. Final labeling should be verified against peer-reviewed botanical references or your regulatory compliance team's approved sources."

- **Analyst asks the agent to update internal records or make changes**: The agent has no write capabilities. It should respond: "I can only look up and compare classification data. To update your internal records, please use the produce management system directly."

- **A fruit name is ambiguous** (e.g., "citrus" or "stone fruit"): The agent should ask the analyst to specify which fruit within the category they mean, listing the allowed options.
