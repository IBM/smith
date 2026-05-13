# FruityVice MCP Server — Tool Summary and Capability Analysis

## Server Overview

The FruityVice MCP server is a lightweight Python server (using `FastMCP`) that provides a single tool for retrieving nutritional information about fruits. It acts as a proxy to the public [Fruityvice API](https://www.fruityvice.com/).

- **Server name:** `fruityvice-mcp`
- **Transport:** stdio
- **Runtime:** Python 3.11
- **External dependency:** `https://www.fruityvice.com/api/fruit/{fruit_name}`

---

## Exposed MCP Tools

### `get_fruit_nutrition`

| Attribute       | Detail |
|-----------------|--------|
| **Defined in**  | `server.py:8` (tool registration), `app.py:1` (implementation) |
| **Description** | Get nutritional information and details for a given fruit name. |
| **Returns**     | Dictionary with `name`, `family`, `genus`, `order`, `nutritions` (calories, fat, sugar, carbohydrates, protein), and `id`. On failure, returns `{"error": "..."}`. |

#### Parameters

| Parameter     | Type   | Required | Description |
|---------------|--------|----------|-------------|
| `fruit_name`  | `str`  | Yes      | The name of the fruit to look up (e.g., `"apple"`, `"banana"`, `"orange"`). |

#### Return Schema (success)

```json
{
  "name": "Apple",
  "family": "Rosaceae",
  "genus": "Malus",
  "order": "Rosales",
  "nutritions": {
    "calories": 52,
    "fat": 0.4,
    "sugar": 10.3,
    "carbohydrates": 11.4,
    "protein": 0.3
  },
  "id": 6
}
```

---

## Security-Sensitive Inputs

### 1. `fruit_name` — URL path injection

The `fruit_name` parameter is interpolated directly into a URL without sanitization:

```python
api_url = f"https://www.fruityvice.com/api/fruit/{fruit_name}"
```

This means a caller could supply values like:
- `"all"` — which hits the Fruityvice `/api/fruit/all` endpoint, returning data for every fruit rather than a single one.
- Path-traversal-style strings (e.g., `"../something"`) — these would alter the URL path sent to the upstream API.
- Excessively long strings — could be used for denial-of-service against the upstream API.
- URL-encoded special characters — could potentially alter the request semantics.

There is **no input validation, allowlist, or sanitization** applied to `fruit_name` before it is used in the HTTP request.

### 2. Unrestricted outbound HTTP requests

The server makes outbound HTTP `GET` requests to `www.fruityvice.com`. There is no:
- Rate limiting
- Timeout configuration on the `requests.get()` call
- Response size limit
- Caching layer

### 3. Error message information leakage

Error messages include the raw `fruit_name` input and network error details (`str(e)`), which could leak internal information if the server is part of a larger system.

---

## Parameters Defining Usage Boundaries

| Boundary Type        | Parameter      | Relevant Values |
|----------------------|----------------|-----------------|
| **Fruit category**   | `fruit_name`   | Specific fruit names (e.g., `apple`, `banana`, `mango`, `strawberry`) |
| **Data scope**       | `fruit_name`   | `"all"` returns the full fruit database vs. a single fruit |
| **API endpoint**     | (hardcoded)    | Always `https://www.fruityvice.com/api/fruit/` — not configurable |

### Known Fruits in the Fruityvice API

The Fruityvice API includes fruits such as: `apple`, `apricot`, `avocado`, `banana`, `blackberry`, `blueberry`, `cherry`, `cranberry`, `dragonfruit`, `durian`, `fig`, `gooseberry`, `grape`, `grapeberry`, `guava`, `kiwi`, `lemon`, `lime`, `lychee`, `mango`, `melon`, `nectarine`, `orange`, `papaya`, `passionfruit`, `peach`, `pear`, `persimmon`, `pineapple`, `plum`, `pomegranate`, `raspberry`, `strawberry`, `tangerine`, `tomato`, `watermelon`, among others.

---

## Summary

This is a single-tool, read-only MCP server. Its primary control surface is the `fruit_name` string parameter, which is the only user-controlled input. Guidance scenarios should focus on restricting which `fruit_name` values are permitted, how frequently the tool can be called, and whether bulk data retrieval (via `"all"`) is allowed.
