# Call-for-Papers MCP Server: Tool Summary and Capability Analysis

## Overview

This MCP server provides a single tool for searching academic conference Call-for-Papers (CFP) listings by scraping WikiCFP (wikicfp.com). It is designed to help researchers and academics discover relevant conferences with upcoming submission deadlines.

## Exposed MCP Tools

### `get_events`

**Description:** Search for conferences matching specific keywords.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `keywords` | string | Yes | — | Search terms for finding conferences (e.g., "ai agent", "machine learning", "cybersecurity") |
| `limit` | integer | No | 10 | Maximum number of events to return |

**Returns:** A JSON object containing:
- `status`: "success" or "error"
- `count`: Number of events found
- `events`: Array of conference objects, each with:
  - `event_name`: Conference name/acronym
  - `event_description`: Full conference title or description
  - `event_time`: Conference dates
  - `event_location`: Venue/city/country
  - `deadline`: Paper submission deadline
  - `event_link`: URL to the WikiCFP event page

## Security-Sensitive Inputs

1. **`keywords` (string):** This is a free-text search parameter passed directly to WikiCFP's search endpoint as a query parameter. It controls what external HTTP requests are made to `http://www.wikicfp.com/cfp/servlet/tool.search`. While the server only queries WikiCFP (no arbitrary URL fetching), the keywords value is user-controlled input that influences external network requests.

2. **`limit` (integer):** Controls how many results are returned. Unbounded or very large values could lead to excessive scraping of WikiCFP pages.

## Parameters Defining Usage Boundaries

- **`keywords`**: Defines the topical scope of searches. Can be constrained to specific academic domains, fields, or conference types.
- **`limit`**: Defines the volume of data retrieved per request. Can be capped to prevent excessive resource usage or data collection.

## External Dependencies

- The server makes HTTP GET requests exclusively to `http://www.wikicfp.com/cfp/servlet/tool.search`
- Uses a browser-like User-Agent header for scraping
- Only performs read operations (no data modification on external systems)
- Year filter is hardcoded to `'t'` (this year) in the `getEvents` function

## Architecture Notes

- Single-tool MCP server using FastMCP (Python)
- Transport: stdio
- The scraper class (`WikiCFPScraper`) is instantiated fresh for each request
- No authentication, caching, or rate limiting is implemented
- No persistent state between requests
