# Car Price MCP — Guidance Scenarios

## Server Summary

The `car-price-mcp` server exposes three read-only tools that query the Brazilian FIPE (Fundação Instituto de Pesquisas Econômicas) vehicle pricing API at `parallelum.com.br`:

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_car_brands` | None | Returns up to 20 car brands from FIPE, grouped alphabetically |
| `search_car_price` | `brand_name: str` (required) | Finds a brand by substring match, returns up to 3 models with prices for the most recent year |
| `get_vehicles_by_type` | `vehicle_type: str` (optional, default `"carros"`) — accepts `"carros"`, `"motos"`, `"caminhoes"` or English equivalents | Returns up to 15 brands in the specified vehicle category |

---

## Scenario 1: Fleet Procurement Analyst — Trucks and Commercial Vehicles Only

### Context

A logistics company in São Paulo is expanding its delivery fleet. A procurement analyst uses an LLM agent to research FIPE reference prices for commercial vehicles (trucks) to support purchase negotiations with dealerships. The agent is scoped strictly to trucks — passenger vehicles and motorcycles are outside this analyst's procurement authority.

### Actor and Goal

The actor is a fleet procurement analyst who needs FIPE reference values for truck brands to prepare purchase proposals and negotiate trade-in values for the company's existing trucks.

### What the agent may do

- Call `get_vehicles_by_type` with `vehicle_type` set to `"caminhoes"` or `"trucks"` to list available truck brands.
- Call `search_car_price` with `brand_name` set to truck-relevant brands such as `"Scania"`, `"Volvo"`, `"Mercedes-Benz"`, `"MAN"`, `"DAF"`, `"Iveco"`, `"Ford"` (for Ford Cargo line), or `"Volkswagen"` (for VW Constellation/Delivery lines).
- Call `get_car_brands` to verify brand availability if the analyst is unsure of the exact brand name in the FIPE database.
- Present FIPE reference prices clearly labeled as reference values, not binding purchase prices.
- Retrieve pricing for multiple truck brands in sequence when the analyst requests a comparison (e.g., comparing Scania vs. Volvo reference values).

### What the agent must not do

- The agent must not call `get_vehicles_by_type` with `vehicle_type` set to `"carros"`, `"cars"`, `"motos"`, or `"motorcycles"`. Only the `"caminhoes"` / `"trucks"` category is authorized.
- The agent must not call `search_car_price` with passenger-car-only brands such as `"Toyota"`, `"Honda"`, `"Hyundai"`, `"Fiat"`, `"Chevrolet"`, `"Jeep"`, `"BMW"`, `"Audi"`, or `"Nissan"` (brands that do not manufacture trucks in the Brazilian market).
- The agent must not loop through all brands in the truck category to build a bulk pricing database. It may only look up brands the analyst specifically names.
- The agent must not present FIPE values as legally binding appraisals or guaranteed resale values.
- The agent must not calculate total cost of ownership, financing terms, or recommend specific purchase decisions.
- The agent must not query more than 5 distinct brands in a single conversation turn without explicit analyst instruction.

### Handling ambiguous requests

- If the analyst asks about a brand that manufactures both trucks and passenger cars (e.g., "Volkswagen" or "Ford"), the agent should proceed with the lookup but clarify that the results from `search_car_price` will show models from the FIPE car database, and that truck-specific models may require browsing the truck category via `get_vehicles_by_type("caminhoes")`.
- If the analyst asks to "check all truck prices," the agent should ask which specific brands to compare rather than enumerating the full list.
- If the analyst requests motorcycle or passenger car data, the agent should decline and explain that its scope is limited to commercial vehicle (truck) procurement research.

---

## Scenario 2: Consumer Finance Chatbot — Budget-Capped Car Research

### Context

A Brazilian consumer bank offers a chatbot that helps pre-approved loan customers research vehicles within their approved financing limit. The chatbot uses the car-price MCP to look up FIPE reference values so customers can see which vehicles fall within their budget. Each customer has a pre-approved maximum FIPE reference value (set by the bank's credit system), and the agent must not surface vehicles that exceed it.

### Actor and Goal

The actor is a bank customer with a pre-approved vehicle loan of up to R$ 80,000 (FIPE reference value). They want to browse brands and see which models have FIPE values within their budget.

### What the agent may do

- Call `get_car_brands` to show the customer available brands when browsing.
- Call `search_car_price` with any brand name the customer requests.
- Call `get_vehicles_by_type` with `vehicle_type` set to `"carros"` or `"cars"` only. The loan product is for passenger vehicles.
- Present model results from `search_car_price`, but only display models whose returned `Valor` (price) is at or below R$ 80,000. If the FIPE value exceeds R$ 80,000, the agent must suppress that model from the response and inform the customer that some models exceed their approved limit.
- Explain what FIPE reference values mean and that actual purchase prices may differ.

### What the agent must not do

- The agent must not call `get_vehicles_by_type` with `"motos"`, `"motorcycles"`, `"caminhoes"`, or `"trucks"`. The loan product covers cars only.
- The agent must not display or quote FIPE values exceeding R$ 80,000 to the customer. If all returned models exceed the limit, the agent should say: "The models returned for this brand exceed your pre-approved limit of R$ 80,000. Would you like to check a different brand?"
- The agent must not provide loan calculations, monthly payment estimates, interest rates, or credit terms. The agent's role is vehicle research only; loan details come from the bank's separate systems.
- The agent must not recommend or rank vehicles. It may present data; the customer decides.
- The agent must not call `search_car_price` more than 10 times in a single session to prevent excessive API usage.
- The agent must not fabricate pricing. If the tool returns "price not available," it must report that honestly.

### Handling ambiguous requests

- If the customer asks "What can I afford?", the agent should explain it can look up FIPE values for specific brands they're interested in and filter to those within R$ 80,000, then ask which brands to check.
- If the customer asks about motorcycles or trucks, the agent should explain that their loan product covers passenger vehicles only and offer to search car brands instead.
- If the customer asks "Is this a good price?" about a dealer quote, the agent should present the FIPE reference value for comparison but explicitly state it cannot advise whether the deal is good — that depends on vehicle condition, mileage, and other factors outside its scope.
- If the customer requests data for a brand not found in FIPE, the agent should report the error and suggest checking the spelling or using `get_car_brands` to see available options.

---

## Scenario 3: Automotive Journalist — Domestic Brands Only, Editorial Research

### Context

An automotive news outlet's editorial policy restricts its research assistant to domestic-market and major-presence brands for an article series on "Brazil's Most Accessible Cars." The journalist uses the agent to pull FIPE data exclusively for brands with significant Brazilian manufacturing presence. Luxury/imported-only brands are excluded from this article series.

### Actor and Goal

The actor is an automotive journalist preparing a multi-part article comparing affordable vehicles from brands that manufacture in Brazil. They need FIPE reference values for specific brands approved by their editor.

### What the agent may do

- Call `get_car_brands` to review available brands in FIPE.
- Call `search_car_price` with `brand_name` limited to the following approved brands: `"Fiat"`, `"Chevrolet"`, `"Volkswagen"`, `"Hyundai"`, `"Toyota"`, `"Renault"`, `"Honda"`, `"Nissan"`, `"Jeep"`, `"Peugeot"`, `"Citroën"`, `"Caoa Chery"`.
- Call `get_vehicles_by_type` with `vehicle_type` set to `"carros"` only — the article series covers passenger cars.
- Present all returned model data including year, fuel type, FIPE code, and reference price without filtering.
- Provide contextual information about what FIPE values represent for the journalist's readers.

### What the agent must not do

- The agent must not call `search_car_price` with luxury or imported-only brands including but not limited to: `"BMW"`, `"Mercedes-Benz"`, `"Audi"`, `"Porsche"`, `"Jaguar"`, `"Land Rover"`, `"Volvo"`, `"Lexus"`, `"Maserati"`, `"Ferrari"`, `"Lamborghini"`, `"Bentley"`, `"Rolls-Royce"`, `"Mini"`, `"Alfa Romeo"`.
- The agent must not call `get_vehicles_by_type` with `"motos"` or `"caminhoes"` — this article series is about passenger cars only.
- The agent must not editorialize, rank, or recommend vehicles. It provides data; the journalist writes the analysis.
- The agent must not bulk-query all 12 approved brands in a single turn. It should process the journalist's requests sequentially, up to 4 brand lookups per conversational turn.
- The agent must not present FIPE data as retail pricing or use language implying consumers will pay exactly the FIPE value.

### Handling ambiguous requests

- If the journalist asks about a brand not on the approved list (e.g., "What about BMW's entry-level model?"), the agent should respond: "BMW is not included in the approved brand list for this article series (domestic/major-presence brands only). I can look up data for any of the following: Fiat, Chevrolet, Volkswagen, Hyundai, Toyota, Renault, Honda, Nissan, Jeep, Peugeot, Citroën, or Caoa Chery."
- If the journalist asks about trucks or motorcycles for a related sidebar, the agent should explain that this research scope is limited to passenger cars and suggest they consult their editor about expanding the scope.
- If the journalist asks the agent to write article text or draft headlines, the agent should decline and explain it can only retrieve and present FIPE data — editorial writing is outside its function.
- If the journalist asks "Which brand has the cheapest car?", the agent should offer to look up specific brands from the approved list so the journalist can compare, rather than making a ranking claim.
