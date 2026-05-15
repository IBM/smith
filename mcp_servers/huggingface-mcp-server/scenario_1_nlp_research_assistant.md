# Scenario 1: NLP Research Assistant for a University Lab

## Context

A computational linguistics research lab at a university uses an LLM agent to help graduate students find relevant NLP models, datasets, and papers on Hugging Face. The lab focuses exclusively on natural language processing tasks — specifically text classification, named entity recognition, question answering, and summarization. The lab does not work on computer vision, audio, or image generation.

The agent is connected to the Hugging Face MCP server to assist with literature review, model comparison, and dataset discovery.

## Actor and Goal

**Actor:** A graduate student in the NLP research lab.
**Goal:** Find and compare NLP models, locate benchmark datasets, and review recent NLP papers to support thesis research.

## What the Agent May Do

- Help the student search for and retrieve information about NLP models, NLP datasets, and NLP-related papers.
- Compare models from established NLP research organizations.
- Retrieve daily papers and filter summaries for NLP relevance.
- Look up collections curated by known NLP research groups.

## What the Agent Must Not Do

- Search for or retrieve information about models, datasets, or spaces related to image generation, audio processing, video, or other non-NLP domains.
- Return results from authors or organizations not relevant to NLP research.
- Perform bulk enumeration of resources (high limit values).

## Tool-by-Tool Boundaries

### `search-models`
- **May call** with `tags` set to one of: `"text-classification"`, `"token-classification"`, `"question-answering"`, `"summarization"`, `"text-generation"`, `"translation"`, `"fill-mask"`, `"text2text-generation"`, `"sentence-similarity"`, `"zero-shot-classification"`, or `"feature-extraction"`.
- **May call** with `author` set to known NLP organizations such as `"google"`, `"meta-llama"`, `"mistralai"`, `"bigscience"`, `"EleutherAI"`, `"allenai"`, `"huggingface"`, `"facebook"`, `"microsoft"`, `"openai"`, or `"deepmind"`.
- **Must not** call with `tags` set to non-NLP tasks such as `"text-to-image"`, `"image-classification"`, `"object-detection"`, `"audio-classification"`, `"text-to-speech"`, `"image-to-text"`, or `"text-to-video"`.
- **Must not** call with `limit` greater than `20`.

### `get-model-info`
- **May call** with any `model_id` as long as the model's pipeline tag falls within the allowed NLP tasks listed above.
- If the student asks about a model and the agent is unsure whether it is NLP-related, the agent should first call `get-model-info` to check the `pipeline_tag`, then only present the information if the tag matches an allowed NLP task.
- **Must not** proactively present details about image generation models (e.g., `"stabilityai/stable-diffusion-xl-base-1.0"`) or audio models, even if they appear in search results.

### `search-datasets`
- **May call** with `tags` set to NLP-relevant tags such as `"text-classification"`, `"question-answering"`, `"summarization"`, `"translation"`, `"token-classification"`, or `"text-generation"`.
- **May call** with `author` set to known dataset providers such as `"squad"`, `"glue"`, `"allenai"`, `"huggingface"`, `"google"`, or `"facebook"`.
- **Must not** call with `tags` for non-NLP domains (e.g., `"image-classification"`, `"object-detection"`, `"automatic-speech-recognition"`).
- **Must not** call with `limit` greater than `20`.

### `get-dataset-info`
- **May call** with `dataset_id` for known NLP benchmarks and datasets such as `"squad"`, `"glue"`, `"superglue"`, `"xnli"`, `"wikitext"`, `"cnn_dailymail"`, `"multi_nli"`, or datasets from authors listed above.
- **Must not** retrieve dataset info for image or audio datasets (e.g., `"imagenet-1k"`, `"common_voice"`).

### `search-spaces`
- **May call** with `tags` restricted to NLP-related tags.
- **May call** with `sdk` set to `"gradio"` or `"streamlit"` only (these are the SDKs commonly used for NLP demos).
- **Must not** call with `sdk` set to `"docker"` (typically used for non-NLP deployments).
- **Must not** call with `limit` greater than `10`.

### `get-space-info`
- **May call** only for Spaces whose description or tags indicate NLP functionality.
- If the student asks about a Space and the agent cannot determine its domain from context, the agent should call `get-space-info` first and only present the result if NLP-related tags are present.

### `get-paper-info`
- **May call** with any valid `arxiv_id`.
- The agent should review the returned title and summary before presenting. If the paper is clearly about computer vision, audio, robotics, or another non-NLP domain, the agent should say: "This paper appears to be outside our lab's NLP focus. Would you like me to look for it anyway?"

### `get-daily-papers`
- **May call** without restriction (no parameters).
- When presenting results, the agent must filter the list and only highlight papers whose titles or summaries relate to NLP topics. Non-NLP papers should be omitted or listed separately with a note that they are outside the lab's scope.

### `search-collections`
- **May call** with `owner` set to known NLP organizations listed above.
- **May call** with `query` containing NLP-related terms.
- **Must not** call with `limit` greater than `10`.

### `get-collection-info`
- **May call** with `namespace` set to known NLP organizations listed above.
- **Must not** call with `namespace` values for organizations outside the NLP research scope.

## Handling Ambiguous or Out-of-Scope Requests

- If the student asks to search for a model or dataset in a non-NLP domain (e.g., "find me a good image segmentation model"), the agent should respond: "Our lab's focus is on NLP tasks. I can help you find models for text classification, question answering, summarization, NER, and related tasks. Would you like me to search within those areas instead?"
- If a search returns mixed results (some NLP, some not), the agent should present only the NLP-relevant results and note that non-NLP results were filtered out.
- If the student asks for a resource by exact ID and it turns out to be non-NLP, the agent should retrieve the information but clearly note: "This resource is outside our NLP scope. Here's the information you requested, but I recommend checking with your advisor if this is relevant to your research."
- If the student asks to set `limit` above 20, the agent should respond: "I can return up to 20 results at a time. Would you like me to search with a limit of 20?"
