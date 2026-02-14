# vLLM Integration Plan for GoodQ4All

> ⚠ Historical planning document — contains legacy path references.

*Comprehensive Migration Strategy from LM Studio to vLLM*

---

## 🎯 Executive Summary

**Goal**: Replace LM Studio with vLLM as the primary LLM inference engine while maintaining full backward compatibility and leveraging our existing model library.

**Why vLLM?**
- ✅ **Production-grade** - Built for high-throughput serving
- ✅ **Multi-model support** - Serve multiple models simultaneously
- ✅ **PagedAttention** - 24x higher throughput than traditional serving
- ✅ **OpenAI-compatible API** - Drop-in replacement for LM Studio
- ✅ **Quantization support** - GPTQ, AWQ, SqueezeLLM
- ✅ **GPU optimization** - Better memory management than LM Studio
- ✅ **Batching** - Continuous batching for efficiency
- ✅ **Open source** - Full control and extensibility

---

## 📊 Current Architecture Analysis

### LM Studio Integration Points
```
<project_root>\scripts\utilities\llm_client.py          # Primary client
<project_root>\agents\llm_agent.py                      # Agent wrapper
<project_root>\steps\llm_chat\step.py                   # Chat step
<project_root>\steps\common\scene_summarizer.py         # Scene analysis
<project_root>\steps\common\context_analyzer_llm.py     # Context analysis
<project_root>\steps\video_summarizer\step.py           # Video summaries
<project_root>\steps\tagger\step_llm_enhanced.py        # Enhanced tagging
<project_root>\steps\graph_builder\llm_enrichment.py    # Graph enrichment
<project_root>\steps\graph_builder\emotion_arc_analyzer.py  # Emotion analysis
<project_root>\api\main.py                              # API endpoints
```

### Current Configuration
- **Base URL**: `http://localhost:1234/v1`
- **API Standard**: OpenAI-compatible
- **Model Discovery**: `/v1/models` endpoint
- **Chat Endpoint**: `/v1/chat/completions`
- **Embeddings**: `/v1/embeddings`

### Model Library Location
```
Windows: C:\Users\jdben\.cache\lm-studio\models\
         (43 models currently available)
```

---

## 🏗️ vLLM Architecture Design

### Deployment Strategy: **Hybrid Approach**

```
┌─────────────────────────────────────────────────────────┐
│                    GoodQ4All Pipeline                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │         Unified LLM Client (Adapter Pattern)      │ │
│  │  - Auto-detection (vLLM/LMStudio/Ollama)          │ │
│  │  - Fallback chain                                 │ │
│  │  - Health monitoring                              │ │
│  └───────────────┬───────────────────────────────────┘ │
│                  │                                      │
│      ┌───────────┼───────────┐                         │
│      │           │           │                         │
│  ┌───▼────┐  ┌───▼────┐  ┌───▼────┐                   │
│  │ vLLM   │  │LMStudio│  │ Ollama │                   │
│  │Primary │  │Fallback│  │Future  │                   │
│  └────────┘  └────────┘  └────────┘                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### vLLM Server Configuration

**Option 1: Single Multi-Model Server** ⭐ RECOMMENDED
```bash
# Serve multiple models on different ports
vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000 --gpu-memory-utilization 0.5
vllm serve microsoft/phi-4 --port 38001 --gpu-memory-utilization 0.3
vllm serve nomic-ai/nomic-embed-text-v1.5 --port 8002 --gpu-memory-utilization 0.2
```

**Option 2: Model Hot-Swapping**
```bash
# Single server, load models on-demand
vllm serve --port 8000 --enable-lora --max-models 3
```

---

## 📋 Phase-by-Phase Migration Plan

### **PHASE 0: Preparation & Testing** (No Code Changes)
*Duration: 1-2 hours*

#### 0.1 Install vLLM in WSL2
```bash
cd ~/goodq_audio
source venv/bin/activate

# Install vLLM with CUDA support
pip install vllm

# Verify GPU access
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```

#### 0.2 Convert LM Studio Models
```bash
# Create vLLM model directory
mkdir -p ~/models/vllm

# Test model conversion (example)
# LM Studio uses GGUF format, vLLM prefers HuggingFace
# Most models are already HF-compatible
```

#### 0.3 Test vLLM Server
```bash
# Test with small model
vllm serve microsoft/phi-4 --port 8000 --max-model-len 4096

# Test OpenAI-compatible API
curl http://localhost:30000/v1/models
curl -X POST http://localhost:30000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "microsoft/phi-4",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

#### 0.4 Benchmark Performance
```python
# Test script: <project_root>/tests/benchmark_vllm.py
import time
import requests

def benchmark_inference(url, model, prompt):
    start = time.time()
    response = requests.post(f"{url}/v1/chat/completions", json={
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 100
    })
    latency = time.time() - start
    return latency, response.json()

# Compare LM Studio vs vLLM
lmstudio_latency = benchmark_inference("http://localhost:1234", "phi-4", "Summarize...")
vllm_latency = benchmark_inference("http://localhost:30000", "microsoft/phi-4", "Summarize...")
```

---

### **PHASE 1: Abstraction Layer** (Minimal Risk)
*Duration: 2-3 hours*

#### 1.1 Create Unified LLM Client
```python
# File: <project_root>/lib/llm/unified_client.py

from typing import Optional, Dict, Any, List
import requests
from enum import Enum

class LLMProvider(Enum):
    VLLM = "vllm"
    LMSTUDIO = "lmstudio"
    OLLAMA = "ollama"

class UnifiedLLMClient:
    """
    Unified interface for multiple LLM backends.
    Auto-detects available providers and falls back gracefully.
    """
    
    def __init__(self, preferred_provider: LLMProvider = LLMProvider.VLLM):
        self.providers = {
            LLMProvider.VLLM: "http://localhost:30000/v1",
            LLMProvider.LMSTUDIO: "http://localhost:1234/v1",
            LLMProvider.OLLAMA: "http://localhost:31434/v1"
        }
        self.preferred = preferred_provider
        self.active_provider = None
        self.active_url = None
        self.model = None
        self._initialize()
    
    def _initialize(self):
        """Try providers in order: preferred -> fallbacks"""
        # Try preferred first
        if self._check_provider(self.preferred):
            return
        
        # Try fallbacks
        for provider in LLMProvider:
            if provider != self.preferred:
                if self._check_provider(provider):
                    return
        
        raise RuntimeError("No LLM providers available!")
    
    def _check_provider(self, provider: LLMProvider) -> bool:
        """Check if provider is available"""
        url = self.providers[provider]
        try:
            response = requests.get(f"{url}/models", timeout=2)
            if response.ok:
                models = response.json().get('data', [])
                if models:
                    self.active_provider = provider
                    self.active_url = url
                    self.model = models[0]['id']
                    print(f"✓ Using {provider.value}: {self.model}")
                    return True
        except:
            pass
        return False
    
    def chat(self, message: str, context: Dict = None, 
             temperature: float = 0.7, max_tokens: int = 500) -> str:
        """Send chat request to active provider"""
        # Build messages
        messages = []
        if context:
            system_prompt = self._build_system_prompt(context)
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        # Call provider
        response = requests.post(
            f"{self.active_url}/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            },
            timeout=30
        )
        
        if response.ok:
            return response.json()['choices'][0]['message']['content']
        return None
    
    def _build_system_prompt(self, context: Dict) -> str:
        """Build system prompt from context"""
        prompt = "You are GoodQ, an intelligent personal memory assistant.\n\n"
        prompt += "Context:\n"
        for key, value in context.items():
            prompt += f"- {key}: {value}\n"
        return prompt
```

#### 1.2 Update Existing Clients (Backward Compatible)
```python
# File: <project_root>/scripts/utilities/llm_client.py

from lib.llm.unified_client import UnifiedLLMClient, LLMProvider

class LLMClient(UnifiedLLMClient):
    """
    Legacy wrapper for backward compatibility.
    Now uses UnifiedLLMClient under the hood.
    """
    def __init__(self, base_url: str = None):
        # Ignore base_url, use auto-detection
        super().__init__(preferred_provider=LLMProvider.VLLM)
        self.available = self.active_provider is not None
```

---

### **PHASE 2: vLLM Server Setup** (Infrastructure)
*Duration: 3-4 hours*

#### 2.1 Create vLLM Launch Scripts

**Windows PowerShell Launcher:**
```powershell
# File: <project_root>/scripts/start_vllm.ps1

# Start vLLM in WSL2
wsl bash -c "cd ~/goodq_audio && source venv/bin/activate && ./scripts/vllm_server.sh"
```

**WSL2 Server Script:**
```bash
#!/bin/bash
# File: ~/goodq_audio/scripts/vllm_server.sh

# Configuration
export CUDA_VISIBLE_DEVICES=0
export VLLM_PORT=8000
export MODEL="microsoft/phi-4"
export GPU_MEM=0.7

# Start vLLM
vllm serve $MODEL \
  --port $VLLM_PORT \
  --gpu-memory-utilization $GPU_MEM \
  --max-model-len 8192 \
  --dtype float16 \
  --trust-remote-code \
  --enable-prefix-caching \
  --disable-log-requests
```

#### 2.2 Model Registry Integration
```python
# File: <project_root>/configs/vllm_models.yaml

vllm_models:
  # Primary chat/reasoning models
  phi-4:
    hf_id: "microsoft/phi-4"
    vllm_port: 8000
    gpu_memory: 0.4
    max_tokens: 8192
    use_case: ["chat", "reasoning", "summarization"]
    priority: 1
    
  qwen-2.5-7b:
    hf_id: "Qwen/Qwen2.5-7B-Instruct"
    vllm_port: 38001
    gpu_memory: 0.4
    max_tokens: 32768
    use_case: ["long_context", "analysis"]
    priority: 2
    
  # Embedding model
  nomic-embed:
    hf_id: "nomic-ai/nomic-embed-text-v1.5"
    vllm_port: 8002
    gpu_memory: 0.2
    use_case: ["embeddings"]
    priority: 3
```

#### 2.3 Multi-Model Orchestrator
```python
# File: <project_root>/lib/llm/vllm_orchestrator.py

import yaml
import subprocess
from pathlib import Path

class VLLMOrchestrator:
    """Manages multiple vLLM servers for different models"""
    
    def __init__(self):
        self.config_path = Path("<project_root>/configs/vllm_models.yaml")
        self.models = self._load_config()
        self.running_servers = {}
    
    def start_model(self, model_name: str):
        """Start a specific model server"""
        model_cfg = self.models[model_name]
        
        cmd = [
            "wsl", "bash", "-c",
            f"vllm serve {model_cfg['hf_id']} "
            f"--port {model_cfg['vllm_port']} "
            f"--gpu-memory-utilization {model_cfg['gpu_memory']}"
        ]
        
        process = subprocess.Popen(cmd)
        self.running_servers[model_name] = process
        
    def start_priority_models(self, count: int = 2):
        """Start top N priority models"""
        sorted_models = sorted(
            self.models.items(),
            key=lambda x: x[1]['priority']
        )
        for name, cfg in sorted_models[:count]:
            self.start_model(name)
```

---

### **PHASE 3: Pipeline Integration** (Critical)
*Duration: 4-5 hours*

#### 3.1 Update All LLM-Dependent Steps

**Scene Summarizer:**
```python
# File: <project_root>/steps/common/scene_summarizer.py

from lib.llm.unified_client import UnifiedLLMClient

class SceneSummarizer:
    def __init__(self):
        # Auto-detects vLLM or falls back to LM Studio
        self.llm = UnifiedLLMClient()
    
    def summarize_scene(self, scene_data: Dict) -> str:
        context = {
            "scene_duration": scene_data['duration'],
            "detected_objects": scene_data.get('objects', []),
            "emotions": scene_data.get('emotions', [])
        }
        return self.llm.chat(
            "Summarize this scene in 2-3 sentences",
            context=context,
            max_tokens=100
        )
```

**Similar updates for:**
- `context_analyzer_llm.py`
- `video_summarizer/step.py`
- `tagger/step_llm_enhanced.py`
- `graph_builder/llm_enrichment.py`
- `llm_chat/step.py`

#### 3.2 Environment Configuration
```bash
# File: <project_root>/.env.local (update)

# LLM Configuration
LLM_PROVIDER=vllm  # Options: vllm, lmstudio, ollama
VLLM_BASE_URL=http://localhost:30000/v1
LMSTUDIO_BASE_URL=http://localhost:1234/v1
OLLAMA_BASE_URL=http://localhost:31434/v1

# Model Selection
LLM_CHAT_MODEL=microsoft/phi-4
LLM_EMBED_MODEL=nomic-ai/nomic-embed-text-v1.5
LLM_LONG_CONTEXT_MODEL=Qwen/Qwen2.5-7B-Instruct
```

---

### **PHASE 4: Testing & Validation**
*Duration: 3-4 hours*

#### 4.1 Unit Tests
```python
# File: <project_root>/tests/test_vllm_integration.py

import pytest
from lib.llm.unified_client import UnifiedLLMClient, LLMProvider

def test_vllm_connection():
    client = UnifiedLLMClient(preferred_provider=LLMProvider.VLLM)
    assert client.active_provider == LLMProvider.VLLM
    
def test_chat_completion():
    client = UnifiedLLMClient()
    response = client.chat("What is 2+2?")
    assert response is not None
    assert "4" in response.lower()
    
def test_fallback_mechanism():
    # Stop vLLM, should fall back to LM Studio
    client = UnifiedLLMClient(preferred_provider=LLMProvider.VLLM)
    # Should still work via fallback
    assert client.active_provider is not None
```

#### 4.2 Integration Tests
```python
# Test full pipeline with vLLM
pytest tests/test_full_pipeline_llm.py
pytest tests/test_scene_summarizer.py
pytest tests/test_phase3_llm_integration.py
```

#### 4.3 Performance Benchmarks
```python
# File: <project_root>/tests/benchmark_llm_providers.py

import time
from lib.llm.unified_client import UnifiedLLMClient, LLMProvider

def benchmark_provider(provider: LLMProvider, iterations: int = 10):
    client = UnifiedLLMClient(preferred_provider=provider)
    
    prompts = [
        "Summarize this scene: happy family gathering",
        "Extract entities: John and Mary at the park",
        "Analyze emotion: excited children playing"
    ]
    
    latencies = []
    for _ in range(iterations):
        for prompt in prompts:
            start = time.time()
            client.chat(prompt, max_tokens=50)
            latencies.append(time.time() - start)
    
    return {
        "provider": provider.value,
        "avg_latency": sum(latencies) / len(latencies),
        "p95_latency": sorted(latencies)[int(len(latencies) * 0.95)]
    }

# Run benchmarks
vllm_results = benchmark_provider(LLMProvider.VLLM)
lmstudio_results = benchmark_provider(LLMProvider.LMSTUDIO)

print(f"vLLM: {vllm_results}")
print(f"LM Studio: {lmstudio_results}")
```

---

### **PHASE 5: Deployment & Monitoring**
*Duration: 2-3 hours*

#### 5.1 Update Launch Scripts
```batch
REM File: <project_root>/LAUNCH_GOODQ.bat

REM Start vLLM servers first
powershell -File <project_root>\scripts\start_vllm.ps1

REM Wait for servers to be ready
timeout /t 10

REM Start main pipeline
conda activate goodq_local
python <project_root>\api\main.py
```

#### 5.2 Health Monitoring
```python
# File: <project_root>/lib/llm/health_monitor.py

import requests
import time
from typing import Dict

class LLMHealthMonitor:
    """Monitor health of LLM providers"""
    
    def __init__(self):
        self.providers = {
            "vllm": "http://localhost:30000/v1",
            "lmstudio": "http://localhost:1234/v1"
        }
        self.status = {}
    
    def check_all(self) -> Dict:
        """Check all providers"""
        for name, url in self.providers.items():
            try:
                start = time.time()
                response = requests.get(f"{url}/models", timeout=2)
                latency = time.time() - start
                
                self.status[name] = {
                    "available": response.ok,
                    "latency_ms": latency * 1000,
                    "models": len(response.json().get('data', []))
                }
            except:
                self.status[name] = {"available": False}
        
        return self.status
```

#### 5.3 UI Integration
```javascript
// Update: <project_root>/index.html

async function refreshLLMStatus() {
    const response = await fetch('/api/llm/status');
    const status = await response.json();
    
    document.getElementById('llm-provider').textContent = status.active_provider;
    document.getElementById('llm-model').textContent = status.model;
    document.getElementById('llm-latency').textContent = `${status.latency_ms}ms`;
}

// Add to dashboard
setInterval(refreshLLMStatus, 5000);
```

---

## 🔄 Migration Checklist

### Pre-Migration
- [ ] Backup current system state
- [ ] Document current LM Studio configuration
- [ ] Test vLLM installation in WSL2
- [ ] Verify GPU access in WSL2
- [ ] Convert/download models for vLLM

### Migration
- [ ] Implement UnifiedLLMClient
- [ ] Update all LLM-dependent modules
- [ ] Create vLLM launch scripts
- [ ] Update environment configuration
- [ ] Implement health monitoring

### Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Performance benchmarks meet targets
- [ ] Fallback mechanism works
- [ ] UI displays correct status

### Deployment
- [ ] Update launch scripts
- [ ] Update documentation
- [ ] Train users on new setup
- [ ] Monitor production usage
- [ ] Optimize based on metrics

---

## 🎯 Success Metrics

### Performance Targets
- **Latency**: < 500ms for chat completions (vs ~800ms LM Studio)
- **Throughput**: > 10 requests/second
- **GPU Utilization**: 70-80% (vs 50-60% LM Studio)
- **Concurrent Requests**: Support 5+ simultaneous

### Reliability Targets
- **Uptime**: 99.9%
- **Fallback Success**: 100% (always have working LLM)
- **Model Load Time**: < 30 seconds

---

## 🚨 Risk Mitigation

### Risk 1: vLLM Incompatibility
**Mitigation**: Unified client with automatic fallback to LM Studio

### Risk 2: Model Conversion Issues
**Mitigation**: Start with HuggingFace-native models (Phi-4, Qwen)

### Risk 3: WSL2 Performance
**Mitigation**: Benchmark first, can run vLLM natively on Windows if needed

### Risk 4: Breaking Existing Pipeline
**Mitigation**: Abstraction layer maintains exact same API surface

---

## 📚 Next Steps

1. **Immediate**: Run Phase 0 tests (2 hours)
2. **Short-term**: Implement UnifiedLLMClient (3 hours)
3. **Medium-term**: Full migration with testing (1 day)
4. **Long-term**: Optimize and add advanced features (ongoing)

---

## 🔗 Resources

- [vLLM Documentation](https://docs.vllm.ai/)
- [vLLM GitHub](https://github.com/vllm-project/vllm)
- [OpenAI API Compatibility](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html)
- [Model Compatibility List](https://docs.vllm.ai/en/latest/models/supported_models.html)

---

**Status**: Ready for Phase 0 Testing  
**Last Updated**: 2025-11-15  
**Owner**: GoodQ Team  
