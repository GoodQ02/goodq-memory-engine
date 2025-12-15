# Ollama Integration - Phase 1 Complete

**Date:** 2025-11-15  
**Status:** ✅ **OPERATIONAL**  
**Model:** Phi-4 (microsoft/Phi-4-reasoning-plus)

---

## Installation Summary

### ✅ Successfully Installed

**Ollama Version:** 0.12.11  
**Service Status:** Active and running  
**API Endpoint:** http://localhost:11434  
**GPU Detection:** NVIDIA GeForce RTX 4070 Ti SUPER (16 GB)  
**Model Loaded:** phi4 (8.4 GB)

### Performance Metrics

**Test Results:**
- Model load time: 2.5 seconds
- Inference speed: ~70 tokens/second (GPU)
- Prompt processing: 1,445 tokens/second
- Memory usage: 8.4 GB VRAM

---

## Model Configuration

### Phi-4 Model Details

**Source:** `/mnt/l/_DATA/models/llm/chat/bartowski/microsoft_Phi-4-reasoning-plus-GGUF/`  
**Size:** 7.9 GB (GGUF), 8.4 GB (Ollama)  
**Quantization:** Q4_K_S  
**Context Length:** 4,096 tokens  

**Ollama Model Name:** `phi4`

**Capabilities:**
- ✅ Chat/instruction following
- ✅ Reasoning tasks
- ✅ Multi-turn conversation
- ✅ OpenAI API compatibility

---

## API Endpoints

### Native Ollama API

**Base URL:** `http://localhost:11434`

#### Generate Completion
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "phi4",
  "prompt": "Your prompt here",
  "stream": false
}'
```

#### Chat Completion
```bash
curl http://localhost:11434/api/chat -d '{
  "model": "phi4",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ]
}'
```

### OpenAI-Compatible API

**Base URL:** `http://localhost:11434/v1/`

#### Chat Completions (OpenAI format)
```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "phi4",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

**Response Format:**
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1699...,
  "model": "phi4",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Response text here"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 38,
    "completion_tokens": 10,
    "total_tokens": 48
  }
}
```

---

## Integration with GoodQ4All

### Python Client Example

```python
import requests
import json

class OllamaClient:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url
    
    def chat(self, message, model="phi4", stream=False):
        """Chat with OpenAI-compatible endpoint"""
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "stream": stream
        }
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        return data['choices'][0]['message']['content']
    
    def generate(self, prompt, model="phi4"):
        """Use native Ollama API"""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        return response.json()['response']


# Usage
client = OllamaClient()

# OpenAI-compatible
response = client.chat("Explain quantum computing briefly")
print(response)

# Native Ollama
response = client.generate("What is the capital of France?")
print(response)
```

### OpenAI Library Compatibility

```python
from openai import OpenAI

# Point OpenAI client to Ollama
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="not-needed"  # Ollama doesn't require auth
)

response = client.chat.completions.create(
    model="phi4",
    messages=[
        {"role": "user", "content": "Hello, how are you?"}
    ]
)

print(response.choices[0].message.content)
```

---

## Service Management

### Start/Stop Ollama

```bash
# Check status
systemctl status ollama

# Stop service
sudo systemctl stop ollama

# Start service
sudo systemctl start ollama

# Restart service
sudo systemctl restart ollama

# View logs
journalctl -u ollama -f
```

### Model Management

```bash
# List models
ollama list

# Remove model
ollama rm phi4

# Pull new model from Ollama library
ollama pull llama3.2

# Create model from GGUF
ollama create mymodel -f Modelfile
```

---

## Available GGUF Models

You have 17 GGUF models that can be imported:

| Model | Size | Status |
|-------|------|--------|
| Phi-4-reasoning-plus | 7.9 GB | ✅ Imported as 'phi4' |
| DeepSeek-R1-Qwen3-8B | 8.2 GB | Ready to import |
| gemma-3-12b-it | 12 GB | Ready to import |
| ERNIE-4.5-21B | 13 GB | Ready to import |
| Llama-3.2-1B-Instruct | 1.3 GB | Ready to import |
| ...and 12 more | | |

### Import Additional Models

```bash
# Example: Import DeepSeek
cat > /tmp/deepseek.Modelfile << 'EOMODEL'
FROM /mnt/l/_DATA/models/llm/chat/lmstudio-community/DeepSeek-R1-0528-Qwen3-8B-GGUF/DeepSeek-R1-0528-Qwen3-8B-Q8_0.gguf
PARAMETER temperature 0.7
PARAMETER num_ctx 4096
EOMODEL

ollama create deepseek -f /tmp/deepseek.Modelfile
```

---

## Configuration Files

### Current Ollama Settings

**Model Storage:** `/usr/share/ollama/.ollama/models`  
**Context Length:** 4,096 tokens  
**Keep Alive:** 5 minutes  
**Max Queue:** 512 requests  
**GPU:** Auto-detected and enabled

### Environment Variables

Add to `/etc/systemd/system/ollama.service`:

```ini
Environment="OLLAMA_HOST=0.0.0.0:11434"  # Allow external connections
Environment="OLLAMA_MODELS=/mnt/l/_DATA/models/ollama"  # Custom path
Environment="OLLAMA_NUM_PARALLEL=2"  # Concurrent requests
Environment="OLLAMA_MAX_LOADED_MODELS=2"  # Multiple models in memory
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

---

## Troubleshooting

### Issue: Model not found
**Solution:**
```bash
ollama list  # Check available models
ollama create phi4 -f /tmp/phi4.Modelfile  # Recreate if needed
```

### Issue: Out of VRAM
**Solution:** Unload model or use smaller model
```bash
# Models auto-unload after 5 minutes of inactivity
# Or restart service
sudo systemctl restart ollama
```

### Issue: API not responding
**Solution:**
```bash
# Check service status
systemctl status ollama

# Check logs
journalctl -u ollama -n 50

# Restart
sudo systemctl restart ollama
```

### Issue: Slow responses
**Check:**
- GPU utilization: `nvidia-smi`
- Model size vs VRAM
- System resources: `htop`

---

## Next Steps: Phase 2

### Add vLLM with HuggingFace Models

**Goal:** Run vLLM alongside Ollama for production workloads

**Plan:**
1. Download Phi-3.5 Mini or Qwen 2.5 7B (HuggingFace format)
2. Configure vLLM server on port 8000
3. Use vLLM for production (better performance)
4. Keep Ollama as backup/testing

**Storage Layout:**
```
/mnt/l/_DATA/models/
├── llm/chat/
│   ├── gguf/                    # GGUF models for Ollama
│   │   └── Phi-4/
│   └── huggingface/             # HF models for vLLM
│       └── Phi-3.5-mini/
```

**Benefits:**
- Best of both worlds
- Ollama: Easy model management, GGUF support
- vLLM: Maximum performance, production features

---

## Summary

✅ **Ollama installed and operational**  
✅ **Phi-4 model imported and tested**  
✅ **OpenAI-compatible API working**  
✅ **GPU acceleration confirmed (70 tokens/sec)**  
✅ **Ready for GoodQ4All integration**

**API Endpoints:**
- Native: http://localhost:11434/api/
- OpenAI: http://localhost:11434/v1/

**Current Model:** phi4 (8.4 GB, Q4_K_S)  
**Performance:** ~70 tokens/second on RTX 4070 Ti SUPER

---

*Phase 1 completed: 2025-11-15*
