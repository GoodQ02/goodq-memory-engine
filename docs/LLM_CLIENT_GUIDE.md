# GoodQ4All LLM Client Guide

**Production-Grade Language Model Interface**  
Version: 1.0.0  
Last Updated: 2025-11-15

---

## 🎯 Overview

The `llm_client.py` provides a unified, production-ready interface for all LLM interactions in GoodQ4All with:

- **Intelligent Routing**: Automatic model selection based on task requirements
- **Automatic Failover**: Seamless fallback from vLLM → Ollama if primary fails
- **Health Monitoring**: Continuous health checks with exponential backoff
- **Connection Pooling**: Efficient HTTP session management
- **OpenAI-Compatible**: Drop-in replacement for OpenAI API calls

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│           GoodQ4All Application                 │
│                                                 │
│  ┌───────────────────────────────────────────┐ │
│  │        llm_client.LLMClient               │ │
│  │  (Intelligent Router + Health Monitor)    │ │
│  └──────────┬────────────────────────────────┘ │
│             │                                   │
└─────────────┼───────────────────────────────────┘
              │
       ┌──────┴──────┐
       │             │
    ┌──▼──┐      ┌──▼──┐
    │vLLM │      │Ollama│
    │(WSL)│      │(Win) │
    └─────┘      └──────┘
    Primary      Fallback
```

---

## 📦 Available Models

### Primary: vLLM (WSL)

| Model                  | Port | Speed       | VRAM  | Use Case           |
|------------------------|------|-------------|-------|--------------------|
| Llama-1B-Speed         | 8003 | 178 tok/s ⚡ | 2.3GB | Real-time chat     |
| Llama-3B-Balanced      | 8004 | 82 tok/s    | 6.1GB | Balanced quality   |
| Phi-3.5-LongContext    | 8001 | 73 tok/s    | 8.7GB | Long conversations |
| Llama-11B-Vision       | 8005 | 50 tok/s    | 13GB  | Image analysis     |
| Qwen-Quality           | 8000 | 55 tok/s    | 14GB  | Complex reasoning  |

### Fallback: Ollama (Windows)

| Model         | Port  | Speed     | VRAM  | Use Case    |
|---------------|-------|-----------|-------|-------------|
| Phi4-Ollama   | 11434 | 70 tok/s  | 8.4GB | Development |

---

## 🚀 Quick Start

### Basic Usage

```python
from lib.llm_client import get_client

# Get singleton client
client = get_client()

# Simple chat
response = client.chat(
    messages=[
        {"role": "user", "content": "Analyze this emotion: happy"}
    ]
)

print(response['choices'][0]['message']['content'])
```

### Convenience Functions

```python
from lib.llm_client import chat, get_status

# Direct chat call
response = chat(
    messages=[{"role": "user", "content": "Hello!"}],
    prefer_speed=True
)

# Check system status
status = get_status()
print(f"Healthy models: {status['models_healthy']}/{status['models_total']}")
```

---

## 🎛️ Advanced Usage

### Speed vs Quality

```python
# Prioritize speed (uses Llama-1B: 178 tok/s)
fast_response = client.chat(
    messages=[{"role": "user", "content": "Quick summary"}],
    prefer_speed=True
)

# Prioritize quality (uses Qwen-Quality or Llama-11B)
quality_response = client.chat(
    messages=[{"role": "user", "content": "Deep analysis required"}],
    prefer_quality=True
)
```

### Force Specific Model

```python
# Use specific model by name
response = client.chat(
    messages=[{"role": "user", "content": "Task"}],
    model_name="Llama-1B-Speed"
)
```

### Streaming Responses

```python
response = client.chat(
    messages=[{"role": "user", "content": "Tell a story"}],
    stream=True,
    max_tokens=500
)

# Process stream
for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```

### Vision/Multimodal

```python
# Requires Llama-11B-Vision
response = client.chat(
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
            ]
        }
    ],
    model_name="Llama-11B-Vision"
)
```

---

## 🔍 Health Monitoring

### Check Status

```python
status = client.get_status()

print(f"Timestamp: {status['timestamp']}")
print(f"Healthy: {status['models_healthy']}/{status['models_total']}")

# Per-model health
for name, health in status['health_status'].items():
    if health['healthy']:
        print(f"✓ {name}: {health['response_time_ms']:.0f}ms")
    else:
        print(f"✗ {name}: {health['last_error']}")
```

### Force Health Check

```python
# Health checks are cached (5min default)
# Force immediate check
client.check_all_health(force=True)
```

---

## 🛠️ Integration Examples

### Chat Interface

```python
# pipelines/interactive_chat.py
from lib.llm_client import get_client

client = get_client()
conversation = []

while True:
    user_input = input("You: ")
    if user_input.lower() in ['exit', 'quit']:
        break
    
    conversation.append({"role": "user", "content": user_input})
    
    response = client.chat(
        messages=conversation,
        prefer_speed=True  # Real-time chat needs speed
    )
    
    assistant_msg = response['choices'][0]['message']['content']
    conversation.append({"role": "assistant", "content": assistant_msg})
    
    print(f"Assistant: {assistant_msg}")
```

### Emotion Analysis

```python
# steps/analyze_emotion.py
from lib.llm_client import chat

def analyze_emotion(text: str) -> dict:
    """Analyze emotional content of text"""
    
    response = chat(
        messages=[
            {
                "role": "system",
                "content": "You are an emotion analysis expert. Respond with JSON only."
            },
            {
                "role": "user",
                "content": f"Analyze emotions in this text and return JSON with 'primary_emotion', 'intensity' (0-1), and 'secondary_emotions' list: {text}"
            }
        ],
        prefer_quality=True,  # Emotion analysis needs accuracy
        temperature=0.3,      # Lower temp for consistent output
        max_tokens=200
    )
    
    # Parse JSON response
    import json
    return json.loads(response['choices'][0]['message']['content'])
```

### Scene Description

```python
# steps/describe_scene.py
from lib.llm_client import get_client

def describe_scene(visual_features: dict, audio_transcript: str) -> str:
    """Generate rich scene description from multimodal inputs"""
    
    client = get_client()
    
    # Select best model for task
    models = client.get_healthy_models(
        capabilities=["chat"],
        prefer_quality=True
    )
    
    if not models:
        raise Exception("No models available")
    
    prompt = f"""
    Create a vivid scene description combining:
    
    Visual: {visual_features}
    Audio: {audio_transcript}
    
    Focus on emotional atmosphere and context.
    """
    
    response = client.chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,  # Higher temp for creative descriptions
        max_tokens=500
    )
    
    return response['choices'][0]['message']['content']
```

---

## 🔧 Configuration

### Model Configuration

Models are defined in `llm_client.py` in the `MODELS` list. To add a new model:

```python
ModelConfig(
    name="MyNewModel",
    base_url="http://localhost",
    port=8010,
    model_id="organization/model-name",
    backend="vllm",  # or "ollama"
    vram_gb=10.0,
    tokens_per_sec=100,
    context_length=8192,
    capabilities=["chat", "custom-capability"],
    priority=85  # Higher = preferred (0-100)
)
```

### Client Parameters

```python
client = LLMClient(
    health_check_interval=60,  # Health check cache TTL (seconds)
    max_retries=3,             # Retry attempts before failing
    timeout=30,                # Request timeout (seconds)
    cache_ttl=300              # Health cache duration (seconds)
)
```

---

## 🚨 Error Handling

### Automatic Failover

The client automatically handles failures:

1. **Primary Attempt**: Try selected model
2. **Retry Logic**: 3 attempts with exponential backoff (2^n seconds)
3. **Failover**: Switch to next healthy model
4. **Final Fallback**: Use Ollama if all vLLM models fail

```python
try:
    response = client.chat(messages=[...])
except Exception as e:
    # All models failed
    logger.error(f"Chat failed: {e}")
    # Handle gracefully (e.g., queue for later, use cached response, etc.)
```

### Manual Health Management

```python
# Check if any models are healthy
status = client.get_status()
if status['models_healthy'] == 0:
    logger.critical("No LLM models available!")
    # Send alert, use fallback logic, etc.

# Get healthy models for a task
candidates = client.get_healthy_models(capabilities=["chat"])
if not candidates:
    # No suitable models available
    pass
```

---

## 📊 Performance Tuning

### Speed Optimization

```python
# For real-time applications (chat, live transcription)
response = client.chat(
    messages=messages,
    prefer_speed=True,      # Selects Llama-1B (178 tok/s)
    temperature=0.7,
    max_tokens=100          # Limit response length
)
```

### Quality Optimization

```python
# For analysis, reasoning, complex tasks
response = client.chat(
    messages=messages,
    prefer_quality=True,    # Selects Qwen or Llama-11B
    temperature=0.3,        # Lower temp for consistency
    max_tokens=1000
)
```

### Batch Processing

```python
# Process multiple items efficiently
items = ["text1", "text2", "text3"]
results = []

client = get_client()
# Select model once
model = client.select_model(prefer_speed=True)

for item in items:
    response = client.chat(
        messages=[{"role": "user", "content": item}],
        model_name=model.name  # Force same model for consistency
    )
    results.append(response)
```

---

## 🐛 Troubleshooting

### No Healthy Models

**Problem**: `Exception: No healthy chat models available`

**Solutions**:
1. Check if vLLM servers are running (WSL):
   ```bash
   # In WSL
   ~/vllm_server/scripts/start_llama1b.sh
   ```

2. Check if Ollama is running (Windows):
   ```powershell
   # Check service
   Get-Service ollama
   
   # Restart if needed
   Restart-Service ollama
   ```

3. Force health check:
   ```python
   client.check_all_health(force=True)
   ```

### Slow Response Times

**Problem**: Responses taking too long

**Solutions**:
1. Use speed-optimized model:
   ```python
   response = client.chat(messages=messages, prefer_speed=True)
   ```

2. Reduce max_tokens:
   ```python
   response = client.chat(messages=messages, max_tokens=100)
   ```

3. Check if multiple heavy models are running simultaneously
4. Monitor VRAM usage - may need to stop other models

### Connection Refused Errors

**Problem**: `Failed to establish a new connection: [WinError 10061]`

**Cause**: vLLM server not running on that port

**Solution**: Start the appropriate server or rely on fallback:
```bash
# In WSL
cd ~/vllm_server
./scripts/start_llama1b.sh  # Port 8003
./scripts/start_phi.sh      # Port 8001
```

---

## 📚 API Reference

### LLMClient Class

#### `__init__(health_check_interval, max_retries, timeout, cache_ttl)`
Initialize client with configuration parameters.

#### `chat(messages, model_name=None, prefer_speed=False, prefer_quality=False, temperature=0.7, max_tokens=2048, stream=False, **kwargs)`
Send chat completion request with automatic model selection and failover.

**Parameters**:
- `messages` (List[Dict]): Chat messages in OpenAI format
- `model_name` (str, optional): Force specific model
- `prefer_speed` (bool): Prefer fastest model
- `prefer_quality` (bool): Prefer highest quality model
- `temperature` (float): Sampling temperature (0-2)
- `max_tokens` (int): Maximum tokens to generate
- `stream` (bool): Enable streaming
- `**kwargs`: Additional API parameters

**Returns**: OpenAI-compatible response dict

#### `get_status()`
Get comprehensive client status including health info and metrics.

**Returns**: Status dictionary

#### `check_all_health(force=False)`
Check health of all model endpoints.

**Parameters**:
- `force` (bool): Force check even if cache is valid

**Returns**: Dict of model name → HealthStatus

#### `get_healthy_models(capabilities=None, prefer_speed=False, prefer_quality=False)`
Get list of healthy models matching criteria.

**Parameters**:
- `capabilities` (List[str], optional): Required capabilities
- `prefer_speed` (bool): Prioritize fastest models
- `prefer_quality` (bool): Prioritize highest quality models

**Returns**: List of ModelConfig

#### `select_model(capabilities=None, prefer_speed=False, prefer_quality=False, model_name=None)`
Select best available model based on criteria.

**Returns**: ModelConfig or None

---

## 🔐 Best Practices

### 1. Use Singleton Pattern

```python
# ✅ Good - Reuses connection pool
from lib.llm_client import get_client
client = get_client()

# ❌ Bad - Creates multiple clients
from lib.llm_client import LLMClient
client1 = LLMClient()  # New connection pool
client2 = LLMClient()  # Another new pool
```

### 2. Choose Right Model for Task

```python
# ✅ Good - Task-appropriate selection
real_time_chat = client.chat(messages, prefer_speed=True)
deep_analysis = client.chat(messages, prefer_quality=True)

# ❌ Bad - Using slow model for real-time
real_time = client.chat(messages, model_name="Qwen-Quality")  # Too slow!
```

### 3. Handle Failures Gracefully

```python
# ✅ Good - Graceful degradation
try:
    response = client.chat(messages)
except Exception as e:
    logger.error(f"LLM failed: {e}")
    # Use cached response, simplified logic, or notify user
    response = get_cached_response() or generate_fallback_response()

# ❌ Bad - Let it crash
response = client.chat(messages)  # Uncaught exception
```

### 4. Monitor Health

```python
# ✅ Good - Proactive monitoring
status = client.get_status()
if status['models_healthy'] < 2:
    alert_admin("Low LLM availability")

# ❌ Bad - Discover failures during requests
# (Client handles this, but monitoring is better)
```

---

## 📈 Metrics & Monitoring

### Key Metrics to Track

```python
status = client.get_status()

# Overall health
healthy_ratio = status['models_healthy'] / status['models_total']

# Per-model metrics
for name, health in status['health_status'].items():
    metrics = {
        'model': name,
        'healthy': health['healthy'],
        'response_time_ms': health['response_time_ms'],
        'consecutive_failures': health['consecutive_failures']
    }
    # Log to monitoring system
    send_to_grafana(metrics)
```

### Logging

```python
import logging

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)

# Client logs include:
# - Health check results
# - Model selection decisions
# - Request attempts and failures
# - Failover events
```

---

## 🎯 Next Steps

1. **Start vLLM Servers** (in WSL):
   ```bash
   ~/vllm_server/scripts/start_llama1b.sh
   ```

2. **Test Integration**:
   ```python
   python lib/llm_client.py
   ```

3. **Update Existing Code**:
   Replace LMStudio calls with `llm_client`

4. **Monitor Performance**:
   Track response times and failover events

5. **Tune Configuration**:
   Adjust model priorities and health check intervals

---

## 📞 Support

- **Documentation**: `L:/goodq4all/docs/`
- **Issues**: Check logs in `data/logs/`
- **Testing**: Run `python lib/llm_client.py`

---

**Last Updated**: 2025-11-15  
**Version**: 1.0.0  
**Status**: ✅ Production Ready
