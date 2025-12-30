# GoodQ4All LLM Infrastructure - Test & Debug Guide
**Last Updated:** 2025-11-16 00:09 UTC
**Status:** ✅ OPERATIONAL

---

## 🟢 Currently Running Services

### 1. vLLM - Llama-3.2-1B-Instruct (Port 8003)
- **Status:** ✅ READY & TESTED
- **PID:** 19201
- **Performance:** 178 tok/s (fastest)
- **VRAM:** ~15.5 GB (high utilization for stability)
- **Endpoint:** `http://localhost:8003/v1/chat/completions`
- **Test Result:** ✅ Chat completions working

### 2. Ollama - Phi4 (Port 31434)
- **Status:** ✅ READY (Fallback)
- **PID:** 178
- **Performance:** ~70 tok/s
- **Endpoint:** `http://localhost:31434/v1/chat/completions`
- **Model ID:** `phi4:latest`

---

## 🔧 Testing From Windows

### Quick Tests

```powershell
# Test vLLM (Primary)
curl http://localhost:8003/v1/models

# Test Ollama (Fallback)
curl http://localhost:31434/v1/models

# Test chat completion (vLLM)
curl http://localhost:8003/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d '{\"model\": \"/mnt/l/_DATA/models/llm/huggingface/Llama-3.2-1B-Instruct\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello!\"}], \"max_tokens\": 50}'
```

### Run Control Agent

```powershell
cd L:\goodq4all
python scripts\run_control_agent.py
```

**Expected Behavior:**
1. Control Agent connects to vLLM at port 8003 (primary)
2. If vLLM fails, falls back to Ollama at port 31434
3. Generates AI-powered diagnostics for logs

---

## 📊 System Status

**GPU:** NVIDIA GeForce RTX 4070 Ti SUPER
- **Total VRAM:** 16,376 MiB
- **Used:** 15,766 MiB (96%)
- **Free:** 298 MiB
- **Utilization:** 6%

**Note:** High VRAM usage is normal with vLLM's GPU memory utilization at 0.70

---

## 🐛 Troubleshooting

### Issue: vLLM not responding
```bash
# From WSL
pkill -f vllm.entrypoints
~/vllm_server/scripts/start_llama1b.sh
```

### Issue: Port already in use
```bash
# Find process on port
lsof -i :8003

# Kill specific PID
kill -9 <PID>
```

### Issue: GPU out of memory
```bash
# Stop all vLLM servers
pkill -f vllm.entrypoints

# Wait for memory to clear
sleep 5

# Restart with lower utilization (already set to 0.70)
~/vllm_server/scripts/start_llama1b.sh
```

### Issue: Ollama not working from Windows
```bash
# Ollama binds to 127.0.0.1, need to check configuration
# This is expected - it may only be accessible from WSL
```

---

## 🚀 WSL Diagnostic Commands

### Monitor Services
```bash
# Comprehensive test
~/vllm_server/scripts/test_debug.sh

# Quick status
~/vllm_server/scripts/status_all.sh

# Watch GPU
watch -n 1 nvidia-smi

# Monitor logs
tail -f ~/vllm_server/logs/llama1b.log
```

### Start/Stop Services
```bash
# Stop all vLLM
pkill -f vllm.entrypoints

# Start Llama 1B (fastest, recommended)
~/vllm_server/scripts/start_llama1b.sh

# Start Llama 3B (balanced)
~/vllm_server/scripts/start_llama3b.sh

# Start Qwen 2.5 7B (best quality, requires stopping others first)
pkill -f vllm.entrypoints && sleep 3
~/vllm_server/scripts/start_qwen.sh
```

---

## 📝 Integration Points

### Frontend (Windows)
- Should connect to: `http://localhost:8003/v1/chat/completions`
- Or use: `L:\goodq4all\lib\llm_client.py` (auto-failover)

### Ingestion Pipeline
- Can use same endpoints for text analysis
- Llama 1B is optimized for speed (178 tok/s)

### Control Agent
- Located at: `L:\goodq4all\scripts\run_control_agent.py`
- Uses: `L:\goodq4all\lib\llm_client.py`
- Auto-failover: vLLM → Ollama → LMStudio

---

## 🔍 Debugging Your Application

### Check if frontend can reach vLLM
```powershell
# From Windows PowerShell
Test-NetConnection -ComputerName localhost -Port 8003
```

### Test LLM Client
```powershell
# From Windows
cd L:\goodq4all
python -c "from lib.llm_client import LLMClient; c = LLMClient(); print(c.chat([{'role': 'user', 'content': 'test'}]))"
```

### Check ingestion pipeline logs
```bash
# If ingestion is running in WSL
ps aux | grep python | grep ingestion

# Check for errors
journalctl -xe | grep -i error
```

---

## 📈 Performance Characteristics

| Metric | Value |
|--------|-------|
| Average latency | ~140ms |
| Tokens/second | 178 |
| Max context | 8,192 tokens |
| Concurrent requests | Limited by VRAM |

---

## ✅ Quick Validation

Run this to verify everything is working:

```bash
# From WSL
curl -s http://localhost:8003/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "/mnt/l/_DATA/models/llm/huggingface/Llama-3.2-1B-Instruct",
    "messages": [{"role": "user", "content": "Say: System operational"}],
    "max_tokens": 10
  }' | python3 -m json.tool | grep content
```

**Expected output:**
```json
"content": "System operational",
```

---

## 🆘 Emergency Reset

If everything is broken:

```bash
# From WSL
# 1. Kill all LLM services
pkill -f vllm.entrypoints
sudo systemctl stop ollama

# 2. Wait for cleanup
sleep 5

# 3. Start fresh
sudo systemctl start ollama
~/vllm_server/scripts/start_llama1b.sh

# 4. Verify
~/vllm_server/scripts/test_debug.sh
```

---

## 📞 Status Check Command

Quick one-liner to check if ready for testing:

```bash
curl -s http://localhost:8003/v1/models >/dev/null && echo "✅ vLLM READY" || echo "❌ vLLM DOWN"
```

---

**Ready to test your frontend and ingestion! Let me know what issues you encounter.** 🚀
