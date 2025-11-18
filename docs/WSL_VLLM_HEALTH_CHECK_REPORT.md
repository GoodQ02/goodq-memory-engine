# WSL/vLLM Health Check Report

**Date**: 2025-11-17 18:09 CST  
**Status**: ⚠️ Services Not Running (but infrastructure is healthy)

---

## 🎯 Executive Summary

**Good News**: All infrastructure is correctly configured and ready.  
**Issue**: Services need to be started - they're not running automatically.

---

## ✅ What's Working Perfectly

### 1. WSL Infrastructure
- **WSL Version**: 2.6.1.0 ✅
- **Distribution**: Ubuntu (Running) ✅
- **Network Mode**: Mirrored (correct for localhost access) ✅
- **Config File**: `~/.wslconfig` properly configured ✅

### 2. GPU & CUDA
- **GPU**: NVIDIA GeForce RTX 4070 Ti SUPER ✅
- **VRAM**: 16,376 MB total, 12,933 MB free ✅
- **Driver**: 581.80 ✅
- **CUDA**: 12.0 installed and working ✅
- **GPU accessible from WSL**: Yes ✅

### 3. vLLM Installation
- **Installed**: Yes (0.11.0) ✅
- **Location**: `~/vllm_server/venv/bin/vllm` ✅
- **Directory Structure**: Complete ✅
- **Model Symlink**: Correct → `/mnt/l/_DATA/models` ✅

### 4. Ollama Service
- **Running**: Yes (PID 184) ✅
- **Service**: Active since 06:31 (11+ hours uptime) ✅
- **Models Loaded**: phi4:latest ✅
- **Working from WSL**: Yes (responds to curl) ✅

---

## ❌ Issues Found

### ISSUE 1: vLLM Servers Not Running ⚠️

**Status**: All 5 vLLM model servers are stopped

| Model | Port | Status | Last Run |
|-------|------|--------|----------|
| Llama-1B-Speed | 8003 | ❌ Not running | Nov 16 01:15 |
| Llama-3B-Balanced | 8004 | ❌ Not running | Nov 15 20:57 |
| Phi-3.5-LongContext | 8001 | ❌ Not running | Nov 15 23:18 |
| Qwen-7B-Quality | 8000 | ❌ Not running | Never started |
| Llama-11B-Vision | 8005 | ❌ Not running | Never started |

**Evidence from Last Run** (llama1b.log from Nov 16):
```
(APIServer pid=20919) INFO: 127.0.0.1:52111 - "GET /v1/models HTTP/1.1" 200 OK
(APIServer pid=20919) INFO: 127.0.0.1:39572 - "POST /v1/chat/completions HTTP/1.1" 200 OK
```
- vLLM WAS working when it ran
- Server was responding successfully
- Chat completions were working
- **Simply needs to be restarted**

**Root Cause**: vLLM servers run in foreground (not as systemd services)
- They stop when terminal closes
- No auto-start on WSL boot
- Need manual launch via startup scripts

---

### ISSUE 2: Ollama Network Binding ⚠️

**Current Behavior**:
```bash
LISTEN 0  4096  127.0.0.1:11434  0.0.0.0:*
```

**Problem**: 
- Ollama binds to `127.0.0.1` (localhost only)
- Windows can't connect to `localhost:11434` from outside WSL
- WSL mirrored networking requires services to bind to `0.0.0.0` or `[::]`

**Why It Works Inside WSL But Not From Windows**:
- Inside WSL: `curl http://localhost:11434` → Works ✅
- From Windows: `curl http://localhost:11434` → Timeout ❌
- Mirrored mode forwards ports but Ollama isn't listening on the right interface

**Root Cause**: Missing `OLLAMA_HOST` environment variable in systemd service

---

### ISSUE 3: Port Connectivity from Windows ⚠️

**Test Results**:
| Port | Service | Windows Access | WSL Access |
|------|---------|----------------|------------|
| 3000 | GoodQ API | ❌ Not listening | N/A |
| 8000 | vLLM Qwen | ❌ Not listening | Server not running |
| 8001 | vLLM Phi-3.5 | ❌ Not listening | Server not running |
| 8003 | vLLM Llama-1B | ❌ Not listening | Server not running |
| 8004 | vLLM Llama-3B | ❌ Not listening | Server not running |
| 8005 | vLLM Llama-11B | ❌ Not listening | Server not running |
| 11434 | Ollama | ❌ Timeout | ✅ Works (127.0.0.1 binding issue) |

**Root Causes**:
1. vLLM servers aren't running (primary issue)
2. Ollama wrong binding (secondary issue)
3. GoodQ API not running (separate issue, not WSL-related)

---

## 🔍 Detailed Analysis

### Why vLLM Logs Show Activity

The most recent log (`llama1b.log`) shows successful activity from **Nov 16 00:45-00:50**:
- Health checks responding
- Chat completions working
- 178 tok/s performance
- Prefix cache working (49.6% hit rate)

**This proves**: vLLM worked perfectly when it was running. It just needs to be restarted.

### Why Ollama Responds Inside WSL But Not From Windows

**From Inside WSL** (works):
```bash
$ curl http://localhost:11434/v1/models
{"object":"list","data":[{"id":"phi4:latest",...}]}
```

**From Windows** (fails):
```powershell
Invoke-WebRequest http://localhost:11434/v1/models
# Error: The request was canceled due to timeout
```

**Technical Explanation**:
- Ollama binds to `127.0.0.1:11434` (IPv4 loopback)
- In WSL, `localhost` resolves to `127.0.0.1` → works
- WSL mirrored networking forwards ports BUT...
- Services must bind to `0.0.0.0` (all interfaces) for Windows to access
- Ollama needs `OLLAMA_HOST=0.0.0.0:11434` environment variable

---

## 🛠️ Fix Plan

### Fix 1: Start vLLM Llama-1B Server (Primary Model)

**Command**:
```bash
wsl bash -c "cd ~/vllm_server && source activate.sh && ./scripts/start_llama1b.sh"
```

**Expected Output**:
- Server starts on port 8003
- Loads model (takes ~30 seconds)
- Begins accepting requests
- Log file created at `~/vllm_server/logs/llama1b.log`

**Verification**:
```powershell
# From Windows
curl http://localhost:8003/v1/models
```

---

### Fix 2: Configure Ollama for Windows Access

**Step 1: Edit systemd service**
```bash
wsl bash -c "sudo systemctl edit ollama --full"
```

**Step 2: Add OLLAMA_HOST to [Service] section**
```ini
[Service]
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin"
Environment="OLLAMA_HOST=0.0.0.0:11434"  # <-- ADD THIS LINE
ExecStart=/usr/local/bin/ollama serve
```

**Step 3: Reload and restart**
```bash
wsl bash -c "sudo systemctl daemon-reload && sudo systemctl restart ollama"
```

**Verification**:
```bash
# Check new binding
wsl bash -c "ss -tlnp | grep 11434"
# Should show: 0.0.0.0:11434 instead of 127.0.0.1:11434

# Test from Windows
curl http://localhost:11434/v1/models
```

---

### Fix 3: Optional - Auto-Start vLLM on WSL Boot

**Create startup script** (`~/.wsl_startup.sh`):
```bash
#!/bin/bash
# Auto-start Llama-1B on WSL boot
sleep 5  # Wait for system to stabilize
cd ~/vllm_server
source activate.sh
nohup ./scripts/start_llama1b.sh > /dev/null 2>&1 &
```

**Add to .bashrc**:
```bash
# Auto-start vLLM if not already running
if [ -z "$(pgrep -f 'vllm.*8003')" ]; then
    bash ~/.wsl_startup.sh
fi
```

---

## 📊 Expected State After Fixes

### Listening Ports
```
LISTEN  0.0.0.0:8003   vLLM Llama-1B
LISTEN  0.0.0.0:11434  Ollama
```

### Windows Connectivity
```powershell
# All should return 200 OK
curl http://localhost:8003/v1/models  # vLLM
curl http://localhost:11434/v1/models # Ollama
```

### LLM Client Behavior
1. Primary: vLLM Llama-1B (8003) - 178 tok/s ⚡
2. Fallback: Ollama Phi-4 (11434) - 70 tok/s
3. Last resort: LM Studio (1234) - if running

---

## 🎯 Priority Order

**IMMEDIATE** (5 minutes):
1. Start vLLM Llama-1B server
2. Test from Windows
3. Verify chat completion works

**HIGH** (10 minutes):
1. Fix Ollama binding
2. Test Windows→Ollama connectivity
3. Verify LLM client failover

**MEDIUM** (optional):
1. Set up auto-start script
2. Start additional vLLM models (3B, Phi-3.5)
3. Update documentation

---

## 📝 Commands to Run Now

```powershell
# 1. Start vLLM Llama-1B
wsl bash -c "cd ~/vllm_server && source activate.sh && ./scripts/start_llama1b.sh &"

# 2. Wait 30 seconds for model to load

# 3. Test from Windows
curl http://localhost:8003/v1/models

# 4. Fix Ollama (requires sudo password)
wsl bash -c "echo 'Environment=\"OLLAMA_HOST=0.0.0.0:11434\"' | sudo tee -a /etc/systemd/system/ollama.service.d/override.conf"
wsl bash -c "sudo systemctl daemon-reload && sudo systemctl restart ollama"

# 5. Test Ollama
curl http://localhost:11434/v1/models

# 6. Run full LLM client test
python L:\goodq4all\scripts\test_llm_client.py
```

---

## ✅ Success Criteria

After fixes, you should see:
- ✅ vLLM responding on port 8003 from Windows
- ✅ Ollama responding on port 11434 from Windows
- ✅ LLM client health checks passing
- ✅ Chat completions working with 178 tok/s
- ✅ Failover chain operational

---

## 🔧 If Something Goes Wrong

### vLLM Won't Start
```bash
# Check logs
wsl bash -c "tail -100 ~/vllm_server/logs/llama1b.log"

# Check GPU memory
wsl bash -c "nvidia-smi"

# Verify model files exist
wsl bash -c "ls -lh /mnt/l/_DATA/models/llm/huggingface/Llama-3.2-1B-Instruct/"
```

### Ollama Won't Restart
```bash
# Check service status
wsl bash -c "systemctl status ollama"

# View logs
wsl bash -c "journalctl -u ollama -n 50"

# Manual restart
wsl bash -c "sudo systemctl restart ollama"
```

### Port Still Not Accessible
```bash
# Check firewall (Windows)
Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*WSL*"}

# Check port forwarding
wsl bash -c "ss -tlnp | grep -E '8003|11434'"

# Restart WSL networking
wsl --shutdown
wsl
```

---

**Status**: Ready to implement fixes. All infrastructure is healthy, services just need to be started correctly.
