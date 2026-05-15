# Hugging Face MCP Server - Tool Summary and Capability Analysis

Source: `src/huggingface/server.py`

## Server Overview

A read-only MCP server that provides access to the Hugging Face Hub API. All tools perform GET requests against `https://huggingface.co/api`. No write, upload, or deletion operations are exposed. An optional `HF_TOKEN` environment variable can be set to authenticate requests, granting access to gated or private resources.

## Exposed MCP Tools

### 1. `search-models`
- **Description:** Search for models on Hugging Face Hub.
- **Parameters:**
  - `query` (string, optional) - Search term (e.g., `"bert"`, `"gpt"`).
  - `author` (string, optional) - Filter by author/organization (e.g., `"huggingface"`, `"google"`).
  - `tags` (string, optional) - Filter by tags (e.g., `"text-classification"`, `"translation"`).
  - `limit` (integer, optional, default 10) - Maximum number of results.
- **Returns:** List of model summaries (id, author, tags, downloads, likes, lastModified).

### 2. `get-model-info`
- **Description:** Get detailed information about a specific model.
- **Parameters:**
  - `model_id` (string, **required**) - Model identifier (e.g., `"google/bert-base-uncased"`).
- **Returns:** Model details including tags, pipeline_tag, downloads, likes, description, and model card.

### 3. `search-datasets`
- **Description:** Search for datasets on Hugging Face Hub.
- **Parameters:**
  - `query` (string, optional) - Search term.
  - `author` (string, optional) - Filter by author/organization.
  - `tags` (string, optional) - Filter by tags.
  - `limit` (integer, optional, default 10) - Maximum number of results.
- **Returns:** List of dataset summaries (id, author, tags, downloads, likes, lastModified).

### 4. `get-dataset-info`
- **Description:** Get detailed information about a specific dataset.
- **Parameters:**
  - `dataset_id` (string, **required**) - Dataset identifier (e.g., `"squad"`).
- **Returns:** Dataset details including tags, downloads, likes, description, and dataset card.

### 5. `search-spaces`
- **Description:** Search for Spaces on Hugging Face Hub.
- **Parameters:**
  - `query` (string, optional) - Search term.
  - `author` (string, optional) - Filter by author/organization.
  - `tags` (string, optional) - Filter by tags.
  - `sdk` (string, optional) - Filter by SDK (e.g., `"streamlit"`, `"gradio"`, `"docker"`).
  - `limit` (integer, optional, default 10) - Maximum number of results.
- **Returns:** List of Space summaries (id, author, sdk, tags, likes, lastModified).

### 6. `get-space-info`
- **Description:** Get detailed information about a specific Space.
- **Parameters:**
  - `space_id` (string, **required**) - Space identifier (e.g., `"huggingface/diffusers-demo"`).
- **Returns:** Space details including sdk, tags, likes, description, and URL.

### 7. `get-paper-info`
- **Description:** Get information about a specific paper on Hugging Face.
- **Parameters:**
  - `arxiv_id` (string, **required**) - arXiv ID (e.g., `"1810.04805"`).
- **Returns:** Paper details including title, authors, summary, URL, and linked implementations.

### 8. `get-daily-papers`
- **Description:** Get the list of daily papers curated by Hugging Face.
- **Parameters:** None.
- **Returns:** List of paper summaries (arxiv_id, title, authors, truncated summary).

### 9. `search-collections`
- **Description:** Search for collections on Hugging Face Hub.
- **Parameters:**
  - `owner` (string, optional) - Filter by owner.
  - `item` (string, optional) - Filter by item (e.g., `"models/teknium/OpenHermes-2.5-Mistral-7B"`).
  - `query` (string, optional) - Search term for titles and descriptions.
  - `limit` (integer, optional, default 10) - Maximum number of results.
- **Returns:** List of collection summaries (id, title, owner, description, items_count, upvotes, lastModified).

### 10. `get-collection-info`
- **Description:** Get detailed information about a specific collection.
- **Parameters:**
  - `namespace` (string, **required**) - Collection namespace (user or organization).
  - `collection_id` (string, **required**) - Collection ID.
- **Returns:** Collection details including title, owner, description, upvotes, and item list.

## Security-Sensitive Inputs

1. **`model_id`, `dataset_id`, `space_id`** - These resource identifiers are passed into URL construction via `quote_plus()`. While URL-encoded, they control which resources are fetched. An unrestricted agent could enumerate private/gated resources if `HF_TOKEN` is set.

2. **`arxiv_id`** - Inserted directly into the API path (`papers/{arxiv_id}` and `arxiv/{arxiv_id}/repos`). Uses no `quote_plus()` encoding, making it a path-traversal surface if the upstream API does not sanitize.

3. **`namespace` and `collection_id`** - Combined into a URL endpoint for collection lookup. The `collection_id` is split on `-` and reassembled, adding complexity to the URL construction path.

4. **`author` / `owner`** - Organization/user filters that can expose organizational structure or private namespaces.

5. **`limit`** - No upper bound enforced in code. A very large limit could cause excessive API traffic or memory consumption.

6. **`HF_TOKEN`** (environment variable) - If set, all API requests are authenticated, potentially granting access to private or gated resources beyond what the agent's use case requires.

## Parameters That Define Usage Boundaries

| Parameter | Boundary type | Examples |
|-----------|--------------|----------|
| `author` / `owner` | Organization/namespace scope | `"google"`, `"meta-llama"`, `"openai"` |
| `model_id` | Specific resource ID | `"google/bert-base-uncased"` |
| `dataset_id` | Specific resource ID | `"squad"`, `"glue"` |
| `space_id` | Specific resource ID | `"huggingface/diffusers-demo"` |
| `arxiv_id` | Paper identifier | `"1810.04805"` |
| `namespace` | Collection owner scope | `"huggingface"`, `"teknium"` |
| `tags` | Task/domain filter | `"text-classification"`, `"image-generation"` |
| `sdk` | Technology filter | `"gradio"`, `"streamlit"`, `"docker"` |
| `limit` | Result count threshold | `5`, `10`, `20` |
| `query` | Free-text search scope | Any search string |
