# Game Trends MCP Server -- Tool Summary and Capability Analysis

## Server Overview

**Server name:** Gaming Trend Analytics
**Framework:** FastMCP (Python, STDIO transport)
**Source:** `server.py` delegates to `GameAnalyticsApp` in `app.py`
**External data sources:** Steam Store, SteamCharts, Steam API, Epic Games Store, Epic Free Games Promotions API

The server exposes seven parameterless, read-only tools that scrape and aggregate real-time gaming market data from Steam and Epic Games. It has no authentication, no user-supplied parameters, and no write operations.

---

## Exposed MCP Tools

### 1. `get_steam_trending_games`
- **Description:** Returns trending games from Steam, aggregated from multiple sub-sources (featured homepage, New & Trending API, Popular New Releases API, SteamCharts top games, Steam global stats page).
- **Parameters:** None.
- **Return data per game:** `id`, `name`, `price`, `discount`, `headerImage`, `platform` ("Steam"), `releaseDate`, `reviewScore`, `tags`, `category`, `isTrending`, `source`.
- **External requests:** `store.steampowered.com` (homepage, search API), `steamcharts.com`, `store.steampowered.com/stats/`.

### 2. `get_steam_top_sellers`
- **Description:** Returns top-selling games from Steam's top sellers search API.
- **Parameters:** None.
- **Return data per game:** `id`, `name`, `price`, `discount`, `headerImage`, `platform`, `releaseDate`, `reviewScore`, `reviewCount`, `tags`, `rank`, `isTopSeller`.
- **External requests:** `store.steampowered.com/search/results/` with `filter=topsellers`.

### 3. `get_steam_most_played`
- **Description:** Returns most-played games with live player counts from SteamCharts and Steam stats.
- **Parameters:** None.
- **Return data per game:** `id`, `name`, `currentPlayers`, `peakPlayers`, `change24h`, `rank`, `platform`, `isPopular`, `lastUpdated`.
- **External requests:** `steamcharts.com`, `store.steampowered.com/stats/`.

### 4. `get_epic_free_games`
- **Description:** Returns current and upcoming free games from the Epic Games Store promotions API.
- **Parameters:** None.
- **Return data per game:** `id`, `namespace`, `name`, `description`, `originalPrice`, `discountPrice`, `platform` ("Epic Games"), `developer`, `publisher`, `releaseDate`, `tags`, `images`, `isFreeNow`, `isUpcomingFree`, `promotionDetails`, `productSlug`, `url`.
- **External requests:** `store-site-backend-static.ak.epicgames.com/freeGamesPromotions`.

### 5. `get_epic_trending_games`
- **Description:** Returns trending games from the Epic Games Store by scraping the browse page sorted by trending.
- **Parameters:** None.
- **Return data per game:** `name`, `price`, `url`, `image`, `platform` ("Epic Games"), `category`, `isTrending`.
- **External requests:** `store.epicgames.com/en-US/browse`, `store.epicgames.com/en-US/`.

### 6. `get_all_trending_games`
- **Description:** Aggregates data from all five data-fetching tools above (Steam trending, top sellers, most played; Epic free, trending) in a single call via `asyncio.gather`.
- **Parameters:** None.
- **Return structure:** `{ success, timestamp, data: { steam_trending, steam_top_sellers, steam_most_played, epic_free_games, epic_trending_games }, partial_failures_occurred }`.

### 7. `get_api_health`
- **Description:** Returns server health status, service initialization state, and version info.
- **Parameters:** None.
- **Return data:** `status`, `timestamp`, `app_initialization_time`, `version`, `description`, `services_status`, `notes`.

---

## Security and Boundary Analysis

### No User-Supplied Parameters
All seven tools are parameterless. The server does not accept any user input that flows into HTTP requests, file paths, commands, or queries. This eliminates direct injection vectors (SSRF, command injection, SQL injection) at the MCP tool boundary.

### Fixed External Request Targets
HTTP requests are made only to hardcoded domains:
- `store.steampowered.com`
- `api.steampowered.com`
- `steamcharts.com`
- `store-site-backend-static.ak.epicgames.com`
- `store.epicgames.com`

### Rate Limiting
`SteamService` enforces a 1.5-second minimum delay between requests. `EpicGamesService` does not have explicit rate limiting.

### Data Exposure
All returned data is publicly available market data (game names, prices, player counts, promotion dates). No credentials, personal data, or private content is exposed through any tool.

### Potential Concern: Output Volume
`get_all_trending_games` fetches data from five endpoints concurrently and can return large payloads. An agent calling this tool repeatedly could generate excessive outbound traffic to Steam/Epic or consume significant context window space.

---

## Parameters That Could Define Usage Boundaries

Since all tools are parameterless, boundaries must be expressed at the **tool level** rather than the parameter level. Meaningful boundary dimensions include:

| Boundary Dimension | Applicable Values |
|---|---|
| **Platform scope** | Steam-only tools vs. Epic-only tools vs. combined |
| **Data type** | Trending, top sellers, most played, free games, health |
| **Call frequency** | How often each tool may be invoked per session/time window |
| **Output usage** | Whether results may be used for recommendations, price comparisons, competitive analysis, content creation, etc. |
| **Audience/context** | Who the agent is serving (e.g., a specific brand, a content creator, a storefront) |
