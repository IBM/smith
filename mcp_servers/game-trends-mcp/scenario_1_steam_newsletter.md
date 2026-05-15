# Scenario 1: Weekly Steam Newsletter for a PC Gaming Community

## Context

A volunteer-run PC gaming community ("FragZone") publishes a weekly newsletter for its 12,000 Discord members. The newsletter covers only Steam -- the community has no partnership or affiliation with Epic Games. The newsletter editor uses an LLM agent with the Gaming Trend Analytics MCP server to draft the "This Week on Steam" section each Monday morning.

## Actor and Goal

**Actor:** The FragZone newsletter editor (community volunteer).
**Goal:** Generate a concise weekly summary of Steam trending games, top sellers, and current player counts to include in the Monday newsletter.

## What the Agent May Do

- Call `get_steam_trending_games` to retrieve currently trending Steam titles for the "What's Hot" section.
- Call `get_steam_top_sellers` to retrieve the current top-selling Steam games for the "Best Sellers" section.
- Call `get_steam_most_played` to retrieve live player counts for the "Most Played Right Now" section.
- Call `get_api_health` to verify the server is operational before fetching data.
- Summarize, rank, and format the returned data into newsletter-ready prose or bullet points.
- Include game names, prices, discount percentages, player counts, review scores, and release dates from the returned data.
- Note when a tool call returns `"success": false` and inform the editor that the data source was unavailable, rather than fabricating data.

## What the Agent Must Not Do

- **Must not call `get_epic_free_games`.** The newsletter covers Steam only. Epic Games data is out of scope and including it would confuse readers and violate the community's editorial policy.
- **Must not call `get_epic_trending_games`.** Same reason as above.
- **Must not call `get_all_trending_games`.** This tool aggregates both Steam and Epic data. Even if the agent intends to discard the Epic portion, calling this tool generates unnecessary outbound traffic to Epic Games servers and returns a large payload. The agent must use the three individual Steam tools instead.
- Must not present Epic Games data even if it somehow appears in a response (e.g., cross-platform titles). The newsletter section is strictly "Steam" branded.
- Must not call any single tool more than twice per newsletter drafting session. If a tool returns `"success": false`, the agent may retry once. After two failures, the agent must report the outage to the editor instead of retrying further.
- Must not editorialize about game quality, add purchase recommendations, or include affiliate-style language (e.g., "you should buy this now"). The newsletter reports facts; opinions come from the community editors.
- Must not fabricate game data. If `get_steam_trending_games` returns zero games (empty `data` array), the agent must say "Steam trending data is currently unavailable" rather than listing games from memory or prior sessions.

## Tool-by-Tool Rules

| Tool | Allowed? | Conditions |
|---|---|---|
| `get_steam_trending_games` | Yes | Up to 2 calls per session. Use for the "What's Hot" section. |
| `get_steam_top_sellers` | Yes | Up to 2 calls per session. Use for the "Best Sellers" section. |
| `get_steam_most_played` | Yes | Up to 2 calls per session. Use for the "Most Played" section. |
| `get_api_health` | Yes | Call once at the start to confirm the server is healthy. |
| `get_epic_free_games` | No | Epic Games content is out of scope for this newsletter. |
| `get_epic_trending_games` | No | Epic Games content is out of scope for this newsletter. |
| `get_all_trending_games` | No | Fetches Epic data unnecessarily; use individual Steam tools. |

## Handling Ambiguous or Out-of-Scope Requests

- If the editor asks "What free games are available this week?", the agent must interpret this as Steam free-to-play or discounted games visible in the `get_steam_trending_games` or `get_steam_top_sellers` results. The agent must not call `get_epic_free_games` even if the question could apply to Epic.
- If the editor asks "Can you also add Epic Games deals?", the agent must decline and explain that the newsletter scope is limited to Steam content only. The agent should suggest the editor consult a separate workflow for Epic content.
- If the editor asks for data about a specific game not present in the tool results, the agent must not search external websites or make up data. It should state that the game did not appear in the current Steam trending, top seller, or most-played lists.
- If the editor asks the agent to compare Steam prices with Epic Games prices, the agent must decline. Cross-platform price comparison is outside the newsletter's scope and would require calling Epic tools.
