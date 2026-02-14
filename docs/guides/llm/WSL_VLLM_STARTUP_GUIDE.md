# WSL/vLLM Manual Startup Guide

**Date**: 2025-11-17  
**Status**: Interim solution while investigating auto-start issues

---

## 🎯 Quick Start (Manual Method)

The automated scripts are having issues, but vLLM worked perfectly when it ran yesterday. Here's the simple manual method:

### Start vLLM Llama-1B (Primary Model)

**Open a WSL terminal and run**:

```bash
# 1. Navigate to vLLM directory
cd ~/vllm_server

# 2. Activate Python environment
source venv/bin/activate

# 3. Start vLLM server (keep this terminal open)
python -m vllm.entrypoints.openai.api_server \
    --model /mnt/l/_DATA/models/llm/huggingface/Llama-3.2-1B-Instruct \
    --host 0.0.0.0 \
    --port 38005 \
    --gpu-memory-utilization 0.7 \
    --max-model-len 8192
```

**Expected output**:
- Model loading progress (30-60 seconds)
- "INFO: Application startup complete"
- "INFO: Uvicorn running on http://0.0.0.0:38005"

**Leave this terminal open** - vLLM runs in foreground.

---

### Fix Ollama Binding (One-time setup)

**In a separate WSL terminal**:

```bash
# Create systemd override directory
sudo mkdir -p /etc/systemd/system/ollama.service.d/

# Create override configuration
sudo tee /etc/systemd/system/ollama.service.d/override.conf << EOF
[Service]
Environment="OLLAMA_HOST=0.0.0.0:31434"
EOF

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart ollama

# Verify it's listening on 0.0.0.0
ss -tlnp | grep 31434
# Should show: 0.0.0.0:31434 (not 127.0.0.1:31434)
```

---

### Test from Windows

**PowerShell**:

```powershell
# Test vLLM
curl http://localhost:38005/v1/models

# Test Ollama
curl http://localhost:31434/v1/models

# Run full LLM client test
python <project_root>\scripts\test_llm_client.py
```

---

## 🔍 Troubleshooting

### vLLM shows CUDA error
```bash
# Check GPU
nvidia-smi

# Verify model path
ls -lh /mnt/l/_DATA/models/llm/huggingface/Llama-3.2-1B-Instruct/
```

### Ollama still won't bind to 0.0.0.0
```bash
# Check override was applied
systemctl cat ollama | grep OLLAMA_HOST

# Check Ollama logs
journalctl -u ollama -n 50 --no-pager
```

### Port already in use
```bash
# Find what's using the port
lsof -i:38005

# Kill old vLLM process
pkill -f "vllm.*38005"
```

---

## Next Steps

Once manual startup is working:
1. We'll investigate why the startup scripts aren't working
2. Create a proper systemd service for vLLM
3. Set up auto-start on WSL boot

For now, the manual method works and proves the infrastructure is healthy.

