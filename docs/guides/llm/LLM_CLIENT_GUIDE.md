<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_GUIDE -->
<!-- DOC_LAST_VERIFIED: 2026-05-21 -->

# GoodQ4All LLM Client Guide

## Purpose

`lib/llm_client.py` is the injected interface for local LLM access inside GoodQ4All.

It provides:
- endpoint health tracking
- model selection across the configured local endpoints
- retry and failover behavior
- an OpenAI-compatible `/v1/chat/completions` client surface

## Current Construction Contract

The current client is **not** a zero-config singleton.

It requires:
- an injected `models` list
- explicit runtime parameters
- an explicit `enable_health_checks` choice

The supported model list is built from config by:
- `steps/common/llm_model_factory.py`

## Working Initialization Pattern

```python
from steps.common.config_loader import load_configs
from steps.common.llm_model_factory import build_llm_models
from lib.llm_client import get_client

cfg = load_configs({})
models = build_llm_models(cfg)

client = get_client(
    models=models,
    health_check_interval=60,
    max_retries=3,
    timeout=30,
    cache_ttl=300,
    enable_health_checks=False,
)
```

Direct construction also works:

```python
from lib.llm_client import LLMClient

client = LLMClient(
    models=models,
    health_check_interval=60,
    max_retries=3,
    timeout=30,
    cache_ttl=300,
    enable_health_checks=False,
)
```

## Supported Models Today

The current config-driven factory builds two models:

| Name | Backend | Endpoint source | Default endpoint | Default model id |
|------|---------|-----------------|------------------|------------------|
| `Llama-1B-Speed` | `vllm` | `llm.vllm_url` / `llm.vllm_model` | `http://localhost:38005/v1` | `meta-llama/Llama-3.2-1B-Instruct` |
| `Phi4-Ollama` | `ollama` | `llm.ollama_url` / `llm.ollama_model` | `http://localhost:31434/v1` | `phi4:latest` |

The older multi-model entries for Llama-3B, Phi-3.5, and vision variants are **not** part of the current supported factory contract. The WSL vLLM service may serve the open Qwen bootstrap model when local config points the primary endpoint there; the client still treats it as the single configured primary vLLM slot.

## Basic Usage

```python
response = client.chat(
    messages=[
        {"role": "user", "content": "Summarize this scene in one sentence."}
    ],
    prefer_speed=True,
    max_tokens=120,
)

print(response["choices"][0]["message"]["content"])
```

## Status and Health

```python
status = client.get_status()

print(status["models_healthy"], status["models_total"])
for name, health in status["health_status"].items():
    print(name, health["healthy"], health["response_time_ms"])
```

If you want to force a refresh:

```python
client.check_all_health(force=True)
```

## Selection Behavior

### Prefer Speed

```python
response = client.chat(messages=messages, prefer_speed=True)
```

With the current factory, this normally prefers the primary vLLM endpoint when healthy.

### Prefer Quality

```python
response = client.chat(messages=messages, prefer_quality=True)
```

With only two configured models, this is still constrained to the current factory output. It does **not** imply a separate Qwen or 11B tier unless the injected model list explicitly includes one.

### Force a Specific Configured Model

```python
response = client.chat(
    messages=messages,
    model_name="Llama-1B-Speed",
)
```

## Convenience Helpers

The module-level helpers are still available, but they require injected state:

```python
from lib.llm_client import chat, get_status

response = chat(messages=messages, client=client, prefer_speed=True)
status = get_status(client=client)
```

Older examples such as:
- `get_client()` with no arguments
- `chat(...)` with no `client=...`
- `get_status()` with no `client=...`
- `LLMClient()` with no constructor arguments

are historical and do not match the current contract.

## Error Handling

`LLMClient.chat()` will:
1. choose the best healthy configured model
2. retry on failure
3. mark failed endpoints unhealthy
4. fail over to the next healthy configured model
5. raise an exception only after all configured attempts fail

Pattern:

```python
try:
    response = client.chat(messages=messages)
except Exception as exc:
    logger.error("LLM request failed: %s", exc)
    # degrade gracefully here
```

## Current Integration Surfaces

The injected client pattern is already used by:
- `api/main.py`
- `agents/control_agent.py`
- `agents/config_healer.py`

That is the pattern new integrations should follow.

## What To Avoid

Avoid documenting or relying on:
- zero-argument `LLMClient()` construction
- zero-argument `get_client()`
- historical model names that are not built by `build_llm_models(cfg)`
- direct-start `~/vllm_server/scripts/start_*.sh` flows as if they were the supported client contract

Use the config-driven factory and injected client instead.
