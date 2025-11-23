# GoodQ4All LLM Infrastructure

## Overview

Production-grade LLM infrastructure with intelligent failover, health monitoring, and automatic model selection.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Windows (GoodQ4All)                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              LLMClient (lib/llm_client.py)                 │ │
│  │  - Health monitoring                                       │ │
│  │  - Automatic failover                                      │ │
│  │  - Model selection by capability                          │ │
│  └───────────────┬──────────────────┬─────────────────────────┘ │
│                  │                  │                           │
└──────────────────┼──────────────────┼───────────────────────────┘
                   │                  │
        ┌──────────▼────────┐  ┌──────▼──────────┐
        │   WSL (vLLM)      │  │  Ollama         │
        │  ┌──────────────┐ │  │  (Fallback)     │
        │  │ Llama 1B     │ │  │  Port: 31434    │
        │  │ Port: 38005   │ │  │  Model: Phi-4   │
        │  │ 178 tok/s ⚡ │ │  │  70 tok/s       │
        │  └──────────────┘ │  └─────────────────┘
        │  ┌──────────────┐ │
        │  │ Llama 3B     │ │
        │  │ Port: 38004   │ │
        │  │ (Optional)   │ │
        │  └──────────────┘ │
        │  ┌──────────────┐ │
        │  │ Phi-3.5      │ │
        │  │ Port: 38001   │ │
        │  │ (Optional)   │ │
        │  └──────────────┘ │
        └───────────────────┘
```

## Quick Start

### 1. Start All LLM Servers

**Windows (Recommended):**
```cmd
L:\goodq4all\scripts\start_llm_servers.bat
```

**WSL Direct:**
```bash
wsl bash -c "/mnt/l/goodq4all/scripts/wsl/start_all_vllm.sh"
```

### 2. Test Connectivity

```cmd
python L:\goodq4all\scripts\test_llm_connectivity.py
```

### 3. Use in Code

```python
from lib.llm_client import LLMClient

# Initialize client
client = LLMClient()

# Chat completion
response = client.chat(
    messages=[
        {"role": "user", "content": "Hello!"}
    ],
    prefer_speed=True  # Use fastest model
)

print(response['choices'][0]['message']['content'])
```

## Available Models

| Model | Port | Speed | VRAM | Context | Best For |
|-------|------|-------|------|---------|----------|
| **Llama-1B-Speed** | 38005 | 178 tok/s ⚡ | 2.3 GB | 131K | Primary, fastest |
| **Llama-3B-Balanced** | 38004 | 82 tok/s | 6.1 GB | 131K | (optional) |
| **Phi-3.5-LongContext** | 38001 | 73 tok/s | 8.7 GB | 131K | Long conversations |
| **Phi4-Ollama** (fallback) | 31434 | 70 tok/s | 2.8 GB | 8K | Reliability |

## LLMClient Features

### Automatic Failover
- Primary: vLLM servers (fastest)
- Fallback: Ollama (reliability)
- Automatic recovery on failure

### Health Monitoring
- Continuous endpoint health checks
- Automatic model selection based on availability
- Failure tracking and circuit breaker pattern

### Intelligent Routing
```python
# Prefer speed
response = client.chat(messages, prefer_speed=True)

# Prefer long context
response = client.chat(messages, prefer_long_context=True)

# Auto-select best available
response = client.chat(messages)
```

### Retry Logic
- Exponential backoff
- Multiple retry attempts
- Graceful degradation

## Management

### Monitor Services

**GPU Status:**
```bash
wsl bash -c "nvidia-smi"
```

**Service Status:**
```bash
wsl bash -c "ps aux | grep -E '(vllm|ollama)'"
```

**Logs:**
```bash
wsl bash -c "tail -f ~/vllm_server/logs/*.log"
```

### Stop All vLLM Servers

```bash
wsl bash -c "pkill -f 'vllm.entrypoints'"
```

### Restart Individual Server

```bash
# Llama 1B (primary)
wsl bash -c "~/vllm_server/scripts/start_llama1b.sh"

# Llama 3B
wsl bash -c "~/vllm_server/scripts/start_llama3b.sh"

# Phi-3.5
wsl bash -c "~/vllm_server/scripts/start_phi.sh"
```

## Performance

### Llama 1B (Primary - Port 38005)
- **Speed**: 178 tokens/second (fastest!)
- **VRAM**: 2.3 GB (very efficient)
- **Latency**: ~140ms first token
- **Concurrent**: Can run with audio processing
- **Use Case**: Real-time chat, fast responses

### Phi4 Ollama (Fallback - Port 31434)
- **Speed**: 70 tokens/second
- **VRAM**: 2.8 GB
- **Latency**: ~300ms
- **Reliability**: Extremely stable
- **Use Case**: Backup, development

## Troubleshooting

### vLLM Server Won't Start

**Check if port is in use:**
```bash
wsl bash -c "lsof -i:38005"
```

**Kill and restart:**
```bash
wsl bash -c "pkill -f 'vllm.entrypoints' && ~/vllm_server/scripts/start_llama1b.sh"
```

### Connection Refused from Windows

**Check WSL networking:**
```bash
wsl bash -c "curl http://localhost:38005/v1/models"
```

**Verify .wslconfig:**
```ini
# C:\Users\<username>\.wslconfig
[wsl2]
networkingMode=mirrored
```

**Restart WSL:**
```cmd
wsl --shutdown
wsl
```

### Out of VRAM

**Check current usage:**
```bash
wsl bash -c "nvidia-smi"
```

**Stop optional models:**
```bash
# Keep only Llama 1B (primary)
wsl bash -c "pkill -f 'port 38004'"  # Stop Llama 3B
wsl bash -c "pkill -f 'port 38001'"  # Stop Phi-3.5
```

## Configuration

### Model Priority

Edit `lib/llm_client.py`:
```python
MODELS = [
    ModelConfig(
        name="Llama-1B-Speed",
        priority=100,  # Higher = preferred
        ...
    ),
]
```

### Startup Models

Edit `scripts/wsl/start_all_vllm.sh` to comment/uncomment models.

### Health Check Interval

```python
client = LLMClient()
client.cache_ttl = 60  # Health check cache in seconds
```

## Integration Examples

### Control Agent (Phase 1)
```python
from agents.control_agent import ControlAgent

agent = ControlAgent()
agent.analyze_logs()  # Uses LLMClient automatically
```

### Pipeline Diagnostics
```python
from lib.llm_client import LLMClient

client = LLMClient()
diagnosis = client.chat(
    messages=[{
        "role": "user", 
        "content": f"Analyze this error: {error_log}"
    }]
)
```

### Chat Interface
```python
# Streaming chat
for chunk in client.stream_chat(messages):
    print(chunk, end='', flush=True)
```

## Files

```
goodq4all/
├── lib/
│   └── llm_client.py          # Main LLM client (19KB)
├── agents/
│   └── control_agent.py       # Control agent using LLM (16KB)
├── scripts/
│   ├── start_llm_servers.bat  # Windows launcher
│   ├── test_llm_connectivity.py # Test script
│   ├── run_control_agent.py   # Control agent runner
│   └── wsl/
│       └── start_all_vllm.sh  # WSL vLLM startup
└── docs/
    └── LLM_INFRASTRUCTURE.md  # This file
```

## Version History

### v1.0.0 (2025-11-15)
- ✅ Production LLMClient with failover
- ✅ vLLM integration (Llama 1B, 3B, Phi-3.5)
- ✅ Ollama fallback (Phi-4)
- ✅ Automatic health monitoring
- ✅ Control Agent Phase 1
- ✅ Comprehensive testing suite
- ✅ WSL/Windows hybrid architecture

## Next Steps

### Phase 2: Advanced Orchestration
- [ ] Auto-healing pipeline integration
- [ ] Real-time log analysis
- [ ] Dynamic config modification
- [ ] Performance optimization suggestions

### Phase 3: Learning Loop
- [ ] SQLite knowledge base
- [ ] Fine-tuning corpus generation
- [ ] Success/failure tracking
- [ ] Self-optimization

## Support

For issues or questions:
1. Check logs: `wsl bash -c "tail -100 ~/vllm_server/logs/*.log"`
2. Test connectivity: `python scripts\test_llm_connectivity.py`
3. Restart services: `scripts\start_llm_servers.bat`

---

**Status**: ✅ Production Ready  
**Last Updated**: 2025-11-15  
**Maintainer**: GoodQ4All Team
