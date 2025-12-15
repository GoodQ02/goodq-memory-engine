# Model Scan Report (Updated) - vLLM Integration

**Date:** 2025-11-15  
**Scan Location:** `/mnt/l/_DATA/models/`  
**Status:** ⚠️ **GGUF Models Found - Conversion Needed**

---

## Scan Results

### ✅ Models Found: 17 GGUF Files (142 GB)

**Location:** `/mnt/l/_DATA/models/llm/chat/`

| Model | Format | Size | Quantization |
|-------|--------|------|--------------|
| microsoft_Phi-4-reasoning-plus | GGUF | 7.9 GB | Q4_K_S |
| DeepSeek-R1-0528-Qwen3-8B | GGUF | 8.2 GB | Q8_0 |
| II-Medical-8B-1706 | GGUF | 5.4 GB | Q5_K_S |
| Wizard-Vicuna-13B-Uncensored | GGUF | 8.6 GB | Q5_K_M |
| gemma-3-12b-it | GGUF | 12 GB | Q8_0 |
| ERNIE-4.5-21B-A3B-PT | GGUF | 13 GB | Q4_K_M |
| gpt-oss-120b | GGUF | 60 GB | MXFP4 (2 parts) |
| gpt-oss-20b | GGUF | 12 GB | MXFP4 |
| gemma-3-4b-it | GGUF | 3.9 GB | Q8_0 |
| gemma-3n-E4B-it | GGUF | 6.9 GB | Q8_0 |
| gemma-3-1B-it-QAT | GGUF | 688 MB | Q4_0 |
| Llama-3.2-1B-Instruct | GGUF | 1.3 GB | Q8_0 |
| LFM2-1.2B | GGUF | 2.2 GB + 1.2 GB | F16 + Q8_0 |

**Total:** 17 GGUF files, ~142 GB

### ❌ HuggingFace Format: NOT FOUND

```
HuggingFace configs (config.json): 0
Safetensors files: 0
PyTorch model files: 0
```

---

## Critical Issue: Format Incompatibility

### ⚠️ GGUF vs HuggingFace Format

**GGUF Format (What You Have):**
- Used by: LMStudio, llama.cpp, Ollama
- Optimized for: CPU/GPU inference with quantization
- File type: Single .gguf file per model
- Compatibility: ❌ **NOT directly supported by vLLM**

**HuggingFace Format (What vLLM Needs):**
- Used by: Transformers, vLLM, TGI
- Components: config.json, tokenizer files, model weights (safetensors/pytorch)
- File type: Multiple files in directory structure
- Compatibility: ✅ **Native vLLM support**

---

## Solutions & Recommendations

### Option 1: Download HuggingFace Models (RECOMMENDED ⭐)

**Best for:** Production deployment, maximum compatibility, best performance

**Action:** Download original HuggingFace format models

**Recommended Models:**

#### 🥇 Qwen/Qwen2.5-7B-Instruct
- **Why:** Best quality, excellent instruction following
- **Size:** ~14 GB (FP16)
- **Download:**
  ```bash
  source ~/vllm_server/activate.sh
  huggingface-cli download Qwen/Qwen2.5-7B-Instruct \
    --local-dir ~/vllm_server/models/llm/chat/Qwen2.5-7B-Instruct \
    --local-dir-use-symlinks False
  ```

#### 🥈 microsoft/Phi-3.5-mini-instruct  
- **Why:** Smaller, faster, MIT license
- **Size:** ~7 GB (FP16)
- **Download:**
  ```bash
  huggingface-cli download microsoft/Phi-3.5-mini-instruct \
    --local-dir ~/vllm_server/models/llm/chat/Phi-3.5-mini-instruct \
    --local-dir-use-symlinks False
  ```

#### 🥉 meta-llama/Llama-3.2-3B-Instruct
- **Why:** Fastest, smallest footprint
- **Size:** ~6 GB (FP16)
- **Note:** Requires HuggingFace token + accepting license

**Pros:**
- ✅ Native vLLM support
- ✅ Best performance
- ✅ No conversion needed
- ✅ Latest model versions
- ✅ Full feature support

**Cons:**
- ⏱️ Download time (7-14 GB)
- 💾 Additional disk space

---

### Option 2: Use Alternative Backend for GGUF

**Best for:** Using existing models immediately, no additional downloads

#### A. Ollama (Easiest)
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Create model from existing GGUF
ollama create phi-4 -f /mnt/l/_DATA/models/llm/chat/microsoft_Phi-4-reasoning-plus-GGUF/microsoft_Phi-4-reasoning-plus-Q4_K_S.gguf

# Serve with OpenAI-compatible API
ollama serve
```

**Pros:**
- ✅ Uses existing GGUF models
- ✅ OpenAI-compatible API
- ✅ Easy setup
- ✅ No additional downloads

**Cons:**
- ❌ Less optimized than vLLM
- ❌ Different tool/ecosystem
- ❌ Fewer features than vLLM

#### B. llama.cpp Server
```bash
# Install llama.cpp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make LLAMA_CUDA=1

# Run server
./llama-server -m /mnt/l/_DATA/models/llm/chat/microsoft_Phi-4-reasoning-plus-GGUF/microsoft_Phi-4-reasoning-plus-Q4_K_S.gguf --port 8000
```

**Pros:**
- ✅ Native GGUF support
- ✅ GPU acceleration
- ✅ OpenAI-compatible API

**Cons:**
- ⚙️ Manual build required
- 📚 More complex setup

---

### Option 3: Convert GGUF to HuggingFace (NOT RECOMMENDED)

**Why not recommended:**
- ⚠️ Lossy conversion process
- ⚠️ May lose quantization benefits
- ⚠️ Complex and error-prone
- ⚠️ Better to download original HF models

---

## Final Recommendation for GoodQ4All

### 🎯 Recommended Path Forward

**Phase 1: Quick Testing (Use Ollama)**
1. Install Ollama for immediate access to existing GGUF models
2. Test integration with GoodQ4All using Phi-4 or DeepSeek
3. Validate API compatibility and response quality
4. Timeline: 1-2 hours

**Phase 2: Production Deployment (Download HF Models)**
1. Download Qwen 2.5 7B (primary) or Phi-3.5 Mini (lighter)
2. Configure vLLM for optimal performance
3. Benchmark and tune settings
4. Full integration with GoodQ4All pipeline
5. Timeline: 2-4 hours (including download)

### Storage Strategy

```
/mnt/l/_DATA/models/
├── llm/
│   ├── chat/
│   │   ├── gguf/                    # Keep existing GGUF models
│   │   │   ├── Phi-4/
│   │   │   ├── DeepSeek/
│   │   │   └── ...
│   │   └── huggingface/             # New HF format models
│   │       ├── Qwen2.5-7B-Instruct/
│   │       ├── Phi-3.5-mini/
│   │       └── ...
```

**Total Additional Space Needed:** ~7-14 GB (1-2 models)

---

## Next Steps

### Immediate (Testing):
```bash
# Option A: Use Ollama with existing GGUF
curl -fsSL https://ollama.com/install.sh | sh
ollama create phi-4 -f /path/to/phi4.gguf
ollama run phi-4 "Hello, test!"

# Option B: Download small HF model for vLLM
source ~/vllm_server/activate.sh
huggingface-cli download microsoft/Phi-3.5-mini-instruct \
  --local-dir ~/vllm_server/models/llm/chat/Phi-3.5-mini-instruct
```

### Production (Best Performance):
```bash
# Download Qwen 2.5 7B
source ~/vllm_server/activate.sh
huggingface-cli download Qwen/Qwen2.5-7B-Instruct \
  --local-dir ~/vllm_server/models/llm/chat/Qwen2.5-7B-Instruct \
  --local-dir-use-symlinks False

# Start vLLM server
vllm serve ~/vllm_server/models/llm/chat/Qwen2.5-7B-Instruct \
  --port 8000 --gpu-memory-utilization 0.90
```

---

## Model Recommendations Based on Use Case

| Use Case | Model | Format | Size | Priority |
|----------|-------|--------|------|----------|
| **Quick Testing** | Existing Phi-4 | GGUF + Ollama | 7.9 GB | ⭐⭐⭐ |
| **Production Chat** | Qwen 2.5 7B | HF + vLLM | 14 GB | ⭐⭐⭐⭐⭐ |
| **Fast Responses** | Phi-3.5 Mini | HF + vLLM | 7 GB | ⭐⭐⭐⭐ |
| **Audio Co-exist** | Llama 3.2 3B | HF + vLLM | 6 GB | ⭐⭐⭐⭐ |
| **Large Scale** | Existing DeepSeek | GGUF + Ollama | 8.2 GB | ⭐⭐⭐ |

---

*Scan completed: 2025-11-15*  
*Updated with GGUF findings and recommendations*
