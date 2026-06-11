---
name: fable-prompt-cache
description: Use to execute Claude Fable 5 prompts on Google Cloud Vertex AI using prompt caching breakpoints to minimize token usage costs by up to 90%.
---

# Claude Fable 5 Prompt Caching Workflow

Use this skill when running prompts against Anthropic's Claude Fable 5 model on Google Cloud Vertex AI. This workflow leverages Vertex AI's support for ephemeral prompt caching to optimize token usage.

## Prerequisites

1. **Vertex AI API Enablement:** Ensure the Generative AI / Vertex AI API is enabled in your active project.
2. **Quota Allocation:** Verify that your project has sufficient quota for:
   - Metric: `aiplatform.googleapis.com/online_prediction_input_tokens_per_minute_per_base_model`
   - Base Model: `anthropic-claude-fable-5`
   - Region: `us-east5`
   - Minimum Quota Target: **100,000 tokens** (default of 1,024 is too small since the stable cached system prompt exceeds 1,024 tokens).
3. **Authentication:** Obtain default credentials:
   ```powershell
   gcloud auth application-default login
   ```

## Prompt Caching Implementation

To trigger prompt caching, the cached portion of your prompt (e.g., system instructions or static context) must exceed the minimum size threshold (1,024 tokens).

### 1. Request Structure
Format the request as an array of content blocks and attach the `cache_control` parameter to the stable block you want to cache.

**Endpoint:**
`POST https://us-east5-aiplatform.googleapis.com/v1/projects/<PROJECT_ID>/locations/us-east5/publishers/anthropic/models/claude-fable-5:rawPredict`

**Payload Example:**
```json
{
  "anthropic_version": "vertex-2024-10-22",
  "messages": [
    {
      "role": "user",
      "content": "Perform the task based on the system instructions."
    }
  ],
  "system": [
    {
      "type": "text",
      "text": "... [Stable instructions (>1,024 tokens)] ...",
      "cache_control": {"type": "ephemeral"}
    }
  ],
  "max_tokens": 4096,
  "stream": false
}
```

### 2. Verify Cache Hits
In the API response, inspect the `usage` block:
* **Cache Write:** `cache_creation_input_tokens > 0` (first run / cache miss).
* **Cache Hit:** `cache_read_input_tokens > 0` and `cache_creation_input_tokens == 0` (subsequent runs within the 5-minute TTL).

## Executing the Diagnostic/Interactive Script

A pre-packaged script is located in the conversation's scratch directory (`scratch/fable_prompt_workflow.py`).

* **Run a single test query:**
  ```powershell
  conda run -n goodq_core python scratch/fable_prompt_workflow.py "Hello, verify model status."
  ```
* **Run the interactive chat loop:**
  ```powershell
  conda run -n goodq_core python scratch/fable_prompt_workflow.py
  ```
