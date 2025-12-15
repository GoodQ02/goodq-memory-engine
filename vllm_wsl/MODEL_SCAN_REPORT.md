# Model Scan Report - vLLM Integration

**Date:** 2025-11-15  
**Scan Location:** `/mnt/l/models/`

---

## Scan Results

### ❌ No vLLM-Compatible Chat Models Found

The models directory contains specialized models only:

| Model | Type | Purpose | vLLM Compatible |
|-------|------|---------|-----------------|
| bert-base-NER | BERT | Named Entity Recognition | ❌ No |
| roberta-emotion | RoBERTa | Emotion Classification | ❌ No |
| clip-vit-base | CLIP | Vision-Language | ❌ No |
| blip-image-captioning | BLIP | Image Captioning | ❌ No |
| wav2vec2-emotion | Wav2Vec2 | Speech Emotion | ❌ No |
| sentence-transformers | BERT | Embeddings | ❌ No |
| distilbert-sst | DistilBERT | Sentiment | ❌ No |

**Why Not Compatible:**
- These are encoder-only or specialized models
- vLLM requires decoder-only autoregressive LLMs
- Designed for classification/embedding, not text generation

---

## Recommended Models for Download

### 🥇 Option 1: Qwen/Qwen2.5-7B-Instruct (RECOMMENDED)

**Best for:** Production chat, instruction following, reasoning

**Specifications:**
- **Parameters:** 7.6 billion
- **Size:** ~14 GB (FP16) / ~7 GB (8-bit)
- **VRAM Required:** 14-16 GB (FP16), 8-10 GB (8-bit)
- **Context Length:** 32,768 tokens (configurable)
- **Performance:** 40-60 tokens/sec on RTX 4070 Ti SUPER
- **License:** Qwen License (permissive for commercial use)

**Strengths:**
- ✅ Excellent instruction following
- ✅ Strong reasoning capabilities
- ✅ Multi-turn conversation
- ✅ Function calling support
- ✅ Multilingual (English + 27 languages)
- ✅ High quality outputs

**Download Command:**
```bash
source ~/vllm_server/activate.sh
huggingface-cli download Qwen/Qwen2.5-7B-Instruct \
  --local-dir ~/vllm_server/models/Qwen2.5-7B-Instruct \
  --local-dir-use-symlinks False
```

---

### 🥈 Option 2: microsoft/Phi-3.5-mini-instruct (LIGHTER)

**Best for:** Fast responses, lower VRAM usage, good quality/size ratio

**Specifications:**
- **Parameters:** 3.8 billion
- **Size:** ~7 GB (FP16) / ~4 GB (8-bit)
- **VRAM Required:** 8-10 GB (FP16), 5-6 GB (8-bit)
- **Context Length:** 128,000 tokens (very long context!)
- **Performance:** 60-80 tokens/sec on RTX 4070 Ti SUPER
- **License:** MIT (fully open)

**Strengths:**
- ✅ Very long context window
- ✅ Small size, fast inference
- ✅ Good quality for parameters
- ✅ Lower VRAM requirements
- ✅ Fully open source

**Download Command:**
```bash
source ~/vllm_server/activate.sh
huggingface-cli download microsoft/Phi-3.5-mini-instruct \
  --local-dir ~/vllm_server/models/Phi-3.5-mini-instruct \
  --local-dir-use-symlinks False
```

---

### 🥉 Option 3: meta-llama/Llama-3.2-3B-Instruct (FASTEST)

**Best for:** Maximum speed, tight VRAM constraints, quick responses

**Specifications:**
- **Parameters:** 3 billion
- **Size:** ~6 GB (FP16) / ~3 GB (8-bit)
- **VRAM Required:** 6-8 GB (FP16), 4-5 GB (8-bit)
- **Context Length:** 8,192 tokens
- **Performance:** 70-90 tokens/sec on RTX 4070 Ti SUPER
- **License:** Llama 3.2 Community License

**Strengths:**
- ✅ Fastest inference
- ✅ Smallest VRAM footprint
- ✅ Good for chat tasks
- ✅ Can run alongside audio models
- ✅ Meta's latest architecture

**Download Command:**
```bash
source ~/vllm_server/activate.sh
huggingface-cli download meta-llama/Llama-3.2-3B-Instruct \
  --local-dir ~/vllm_server/models/Llama-3.2-3B-Instruct \
  --local-dir-use-symlinks False
```

**Note:** Requires HuggingFace account and accepting Meta's license

---

## Comparison Matrix

| Feature | Qwen 2.5 7B | Phi-3.5 Mini | Llama 3.2 3B |
|---------|-------------|--------------|--------------|
| **Quality** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Speed** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **VRAM Efficiency** | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Context Length** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Multi-language** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **License** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Audio Co-exist** | ⭐⭐ (8-bit) | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## Resource Allocation Scenarios

### Scenario 1: LLM-Only Serving
**Best Choice:** Qwen 2.5 7B (FP16)
- VRAM: 14 GB for model
- Remaining: 2 GB for KV cache
- Quality: Maximum

### Scenario 2: LLM + Audio Processing
**Best Choice:** Phi-3.5 Mini or Llama 3.2 3B
- LLM: 6-8 GB
- Audio (when active): 4-7 GB
- Total: 10-15 GB (fits comfortably)

### Scenario 3: Multi-Model Serving
**Best Choice:** Llama 3.2 3B (8-bit) × 2
- 2 models: 6-8 GB total
- Serve different tasks simultaneously
- Fast switching

---

## Download Recommendations

### For GoodQ4All Production:

**Primary Model:** Qwen/Qwen2.5-7B-Instruct
- Best overall quality
- Strong at following instructions
- Good for chat and QA

**Fallback Model:** microsoft/Phi-3.5-mini-instruct
- Use when audio processing is active
- Faster responses
- Lower VRAM usage

**Storage Location:** `~/vllm_server/models/` or `/mnt/l/models/llm/`

---

## Next Steps

1. ✅ Model scan complete
2. **Choose model** based on requirements
3. **Download model** using huggingface-cli
4. **Configure vLLM** for selected model
5. **Test serving** with sample requests
6. **Benchmark performance**
7. **Create production wrapper**

---

## HuggingFace Authentication

Some models require accepting licenses:

```bash
# Set HuggingFace token (if needed)
huggingface-cli login

# Or set environment variable
export HF_TOKEN="your_token_here"
```

**Required for:**
- Llama models (accept license on HF website)
- Gated models
- Private models

**Not required for:**
- Qwen models (public)
- Phi models (public)

---

*Scan completed: 2025-11-15*
