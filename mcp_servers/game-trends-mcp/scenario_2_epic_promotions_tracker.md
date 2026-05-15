# Scenario 2: Epic Games Free-Game Promotion Tracker for a Deals Blog

## Context

A gaming deals blog ("BargainPlay") maintains a page that tracks only free game promotions from the Epic Games Store. The page is automatically updated by an LLM agent that queries the Gaming Trend Analytics MCP server. The blog's policy is strict: the page must only list games that are currently free or confirmed upcoming free on Epic, with verified promotion dates. The blog does not cover Steam deals on this page, and it does not cover paid Epic games regardless of discount.

## Actor and Goal

**Actor:** The BargainPlay automated publishing agent.
**Goal:** Retrieve the current and upcoming free games from Epic Games Store, format them for the deals page, and flag when promotions are about to expire.

## What the Agent May Do

- Call `get_epic_free_games` to retrieve current and upcoming free game promotions from Epic Games Store.
- Call `get_api_health` once per run to verify server availability before fetching data.
- From the returned data, include only games where `isFreeNow` is `true` or `isUpcomingFree` is `true`.
- Display: game `name`, `originalPrice`, `developer`, `publisher`, `promotionDetails.startDate`, `promotionDetails.endDate`, `description`, `url`, and `images`.
- Calculate and display time remaining until a current free promotion expires (using `promotionDetails.endDate`).
- Clearly label games as "FREE NOW" when `isFreeNow` is `true` and "COMING SOON" when `isUpcomingFree` is `true`.
- Note when the tool returns an empty list or `"success": false` and display a "No promotions currently available -- check back later" message on the page.

## What the Agent Must Not Do

- **Must not call `get_steam_trending_games`.** This page covers Epic free games only. Steam data is irrelevant.
- **Must not call `get_steam_top_sellers`.** Steam sales data is out of scope.
- **Must not call `get_steam_most_played`.** Player count data is out of scope for a deals/promotions page.
- **Must not call `get_epic_trending_games`.** This tool returns paid trending games on Epic, not free promotions. Including paid games on a free-games page would mislead readers.
- **Must not call `get_all_trending_games`.** This aggregates data from all platforms and all data types, pulling in Steam data and paid Epic trending games that are all out of scope. It also generates unnecessary load on Steam endpoints.
- Must not list any game where `isFreeNow` is `false` AND `isUpcomingFree` is `false`. Even if a game appears in the API response, it must be filtered out if it does not have an active or upcoming free promotion.
- Must not display or reference `discountPrice` values other than "Free" or `0`. If a game has a discounted but non-zero price, it is not a free game and must be excluded.
- Must not recommend purchasing games, link to paid storefronts, or include any language that could be interpreted as advertising paid products.
- Must not speculate about future free games beyond what the API's `upcomingPromotionalOffers` data confirms. The agent must not guess which games Epic "might" give away next.
- Must not call `get_epic_free_games` more than 3 times per publishing run. If data is unavailable after 3 attempts, the agent must display the unavailability notice and stop.

## Tool-by-Tool Rules

| Tool | Allowed? | Conditions |
|---|---|---|
| `get_epic_free_games` | Yes | Up to 3 calls per run. Only use data where `isFreeNow` or `isUpcomingFree` is `true`. |
| `get_api_health` | Yes | Call once at the start of each run. |
| `get_steam_trending_games` | No | Steam content is out of scope for this page. |
| `get_steam_top_sellers` | No | Steam content is out of scope for this page. |
| `get_steam_most_played` | No | Steam content is out of scope for this page. |
| `get_epic_trending_games` | No | Returns paid trending games, not free promotions. |
| `get_all_trending_games` | No | Aggregates out-of-scope data from all platforms. |

## Handling Ambiguous or Out-of-Scope Requests

- If an editor asks "What are the best deals on Epic right now?", the agent must respond with only the current free games from `get_epic_free_games`. It must not call `get_epic_trending_games` to find discounted (but not free) games, because the page scope is limited to fully free promotions.
- If an editor asks "Is [specific game] free on Epic?", the agent should call `get_epic_free_games` and check if the named game appears in the results with `isFreeNow: true`. If the game is not in the results, the agent must say it is not currently listed as free, rather than speculating or checking Steam.
- If an editor asks "What about Steam free weekends?", the agent must decline and explain that this page only tracks Epic Games Store free promotions. It should not call any Steam tools.
- If an editor asks "Show me trending Epic games too", the agent must explain that the page policy restricts content to free promotions only, and trending paid games are not within scope.
- If the API returns a game where the promotion dates are in the past (i.e., `promotionDetails.endDate` is before the current time), the agent should exclude it from the published list as an expired promotion, even if the API still returns it.
