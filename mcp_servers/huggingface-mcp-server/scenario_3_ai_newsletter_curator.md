# Scenario 3: Weekly AI Newsletter Curator

## Context

A developer relations team publishes a weekly newsletter for their open-source community. The newsletter covers trending models, noteworthy datasets, and highlighted papers — but only within specific domains the community cares about: large language models and code generation. The newsletter editor uses an LLM agent to gather material from Hugging Face each week.

The newsletter has strict editorial guidelines: it only features content from a curated set of well-known organizations, it never covers image/audio/video generation tools, and it avoids promoting any individual's personal projects (only organizations are featured). The agent must also cap how much it fetches to avoid overwhelming the editor with raw data.

## Actor and Goal

**Actor:** A newsletter editor on the developer relations team.
**Goal:** Gather a shortlist of trending LLM and code-generation models, notable datasets, and relevant papers from Hugging Face to draft the weekly newsletter.

## What the Agent May Do

- Search for models and datasets related to LLMs and code generation.
- Retrieve daily papers and filter for relevance.
- Look up specific models, datasets, or papers the editor names.
- Search collections from approved organizations.

## What the Agent Must Not Do

- Feature content from individual users (non-organization accounts).
- Cover domains outside LLMs and code generation.
- Retrieve or present information about Spaces (the newsletter does not cover demos).
- Make large-volume API calls.

## Tool-by-Tool Boundaries

### `search-models`
- **May call** with `tags` set to one of: `"text-generation"`, `"text2text-generation"`, or `"code"` (used for code-generation models).
- **May call** with `author` set to one of these featured organizations: `"meta-llama"`, `"mistralai"`, `"google"`, `"microsoft"`, `"bigscience"`, `"EleutherAI"`, `"tiiuae"`, `"Qwen"`, `"deepseek-ai"`, `"bigcode"`, `"codellama"`, `"Salesforce"`, `"Phind"`.
- **May call** with `query` containing terms like `"llm"`, `"language model"`, `"code"`, `"coding"`, `"instruct"`, `"chat"`.
- **Must not** call with `tags` outside the allowed set (e.g., `"text-to-image"`, `"audio-classification"`, `"object-detection"`, `"text-to-speech"`, `"image-to-text"`).
- **Must not** call with `author` set to individual user accounts (any author without a `/` organization prefix that is not in the featured list). If the agent is unsure whether an author is an organization, it should skip that author.
- **Must not** call with `limit` greater than `10`.

### `get-model-info`
- **May call** with `model_id` that belongs to one of the featured organizations listed above.
- **May call** with any `model_id` the editor explicitly names, even if not from a featured organization, but the agent must flag it: "Note: [author] is not in our featured organizations list. Include in the newsletter?"
- **Must not** proactively look up models from non-featured organizations.

### `search-datasets`
- **May call** with `tags` set to one of: `"text-generation"`, `"code"`, or `"text2text-generation"`.
- **May call** with `author` set to featured organizations listed above, or to well-known dataset organizations: `"bigcode"`, `"allenai"`, `"huggingface"`, `"EleutherAI"`.
- **Must not** call with `tags` outside the allowed set.
- **Must not** call with `limit` greater than `10`.

### `get-dataset-info`
- **May call** with `dataset_id` from featured organizations or well-known code/LLM datasets such as `"bigcode/the-stack"`, `"bigcode/starcoderdata"`, `"allenai/dolma"`, `"cerebras/SlimPajama-627B"`, `"EleutherAI/pile"`, `"wikitext"`.
- **May call** with any `dataset_id` the editor explicitly names, with the same flagging behavior as `get-model-info`.
- **Must not** proactively look up datasets from non-featured sources.

### `search-spaces`
- **Must not call.** The newsletter does not cover Spaces or demos.

### `get-space-info`
- **Must not call.** The newsletter does not cover Spaces or demos.

### `get-paper-info`
- **May call** with any `arxiv_id` that the editor provides or that is referenced in a model card from a featured organization.
- **Must not** call speculatively to browse random papers. Each `get-paper-info` call should be traceable to either an editor request or a model card reference.

### `get-daily-papers`
- **May call** once per editing session.
- When presenting results, the agent must filter the paper list and only highlight papers whose titles or summaries relate to large language models or code generation. Papers about diffusion models, computer vision, speech, robotics, or reinforcement learning should be omitted.
- The agent should present no more than 5 papers from the daily list, selecting the most relevant ones.

### `search-collections`
- **May call** with `owner` set to one of the featured organizations listed above.
- **May call** with `query` containing LLM or code-generation-related terms.
- **Must not** call with `owner` set to individual user accounts.
- **Must not** call with `limit` greater than `5`.

### `get-collection-info`
- **May call** with `namespace` set to one of the featured organizations listed above.
- **Must not** call with `namespace` set to individual users or non-featured organizations.

## Handling Ambiguous or Out-of-Scope Requests

- If the editor asks to feature a model from an individual user account (e.g., "Check out TheBloke/some-model-GGUF"), the agent should respond: "TheBloke appears to be an individual account, not one of our featured organizations. Our newsletter policy is to feature only organizational accounts. Would you like me to find the original organization's version of this model instead?"
- If the editor asks about image generation models (e.g., "Any interesting Stable Diffusion updates this week?"), the agent should respond: "Our newsletter scope covers LLMs and code generation only. Image generation is outside the editorial guidelines. Would you like me to focus on LLM updates instead?"
- If the editor asks to browse Spaces (e.g., "Find some cool Gradio demos to feature"), the agent should respond: "The newsletter doesn't cover Spaces or demos. I can help find notable models or papers instead."
- If the editor asks the agent to get more than 10 search results, the agent should respond: "To keep the research manageable, I'm limited to 10 results per search. I'll find the top 10 — would you like me to refine the search terms to get more targeted results?"
- If the daily papers list contains no LLM or code-generation papers, the agent should say: "Today's Hugging Face daily papers don't include any papers in our focus areas (LLMs and code generation). I can look up specific arxiv IDs if you have papers in mind, or we can check again tomorrow."
- If the editor asks about a topic that partially overlaps (e.g., "multimodal language models"), the agent should include it if the model's primary function is text generation and note: "This model has multimodal capabilities but is primarily a language model. Flagging for your editorial judgment."
