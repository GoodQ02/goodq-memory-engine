# WSL Agent Briefing - GoodQ4All vLLM Integration
**Created:** 2025-11-15  
**Status:** Phase 2 - LLM Client Integration Active

---

## 🎯 Mission Overview
We are integrating a production-grade vLLM/Ollama infrastructure into the GoodQ4All emotional analytics pipeline. You (WSL Agent) are responsible for managing all GPU-accelerated services running in WSL2 Ubuntu.

---

## 📁 Critical Directory Structure

### Windows Side (Accessible via /mnt/)
```
<project_root>\                          # Main repository
├── lib/
│   └── llm_client.py                 # NEW: Production LLM client (CREATED)
├── configs/
│   └── llm_config.yaml               # NEW: LLM configuration (CREATED)
├── scripts/
│   └── test_llm_client.py            # NEW: Client test script (CREATED)
└── docs/
    └── WSL_AGENT_BRIEFING.md         # This file

<GOODQ_DATA_ROOT>/models/llm/
├── huggingface/                      # vLLM-compatible models
│   ├── Qwen2.5-7B-Instruct/         # 15 GB - Quality leader
│   ├── Phi-3.5-mini-instruct/        # 7.2 GB - 128K context
│   ├── Llama-3.2-1B-Instruct/        # 2.5 GB - Speed king (178 tok/s)
│   ├── Llama-3.2-3B-Instruct/        # 6.2 GB - Balanced
│   └── Llama-3.2-11B-Vision-Instruct/ # 22 GB - Multimodal
└── gguf/                             # Ollama-compatible models
    └── [17 GGUF models, 142 GB]

<windows_user_home>\.wslconfig             # WSL network config (CREATED)
```

### WSL Side (Your Home Territory)
```
~/goodq_audio/                        # Audio processing stack
├── venv/                             # Python 3.12 environment
├── scripts/
│   ├── process.sh                    # Audio transcription + diarization
│   └── process.py                    # Main processing script
└── [Documentation files]

~/vllm_server/                        # vLLM infrastructure
├── venv/                             # Separate Python 3.12 environment
├── models/ -> /mnt/l/_DATA/models/llm/huggingface/  # Symlink
├── configs/
│   ├── default.yaml                  # vLLM server config
│   └── models.yaml                   # Model registry
├── scripts/
│   ├── start_qwen.sh                 # Port 8000
│   ├── start_phi.sh                  # Port 38001
│   ├── start_llama3b.sh              # Port 38004
│   ├── start_llama11b.sh             # Port 38005 (Vision)
│   └── test_models.sh                # Test all models
└── logs/                             # Service logs

/etc/wsl.conf                         # WSL configuration
```

---

## 🚀 Services Currently Deployed

### 1. Ollama (Port 31434)
- **Status:** Running as systemd service
- **Model Loaded:** phi4 (8.4 GB, 70 tok/s)
- **API:** http://localhost:31434/v1/ (OpenAI-compatible)
- **Control:**
  ```bash
  sudo systemctl status ollama
  sudo systemctl start/stop/restart ollama
  ```

### 2. vLLM Servers (Ports 38000-38006)
- **Status:** Ready to start on-demand
- **Available Models:**
  - Port 38000: Qwen 2.5 7B (quality)
  - Port 38001: Phi-3.5 Mini (long context)
  - Port 38005: Llama 1B (speed - 178 tok/s) ⭐ RECOMMENDED
  - Port 38004: Llama 3B (balanced)
  - Port 38006: Llama 11B Vision (multimodal) [if used]
- **Start:** `~/vllm_server/scripts/start_llama1b.sh` (ensure it uses --port 38005)

### 3. Audio Processing (Port: N/A - CLI tool)
- **Status:** Operational
- **Script:** `~/goodq_audio/process.sh`
- **Features:** GPU-accelerated Whisper + PyAnnote diarization

---

## 🔧 Current Integration Status

### ✅ COMPLETED
1. **Phase 1: Audio Processing**
   - Faster-Whisper with GPU acceleration
   - PyAnnote speaker diarization
   - cuDNN libraries fixed and working
   - Wrapper script with proper environment

2. **Phase 2: Ollama Installation**
   - Ollama 0.12.11 installed
   - Phi-4 model loaded and tested
   - OpenAI-compatible API verified
   - Systemd service running

3. **Phase 2: vLLM Infrastructure**
   - Downloaded 5 HuggingFace models (79 GB)
   - Tested 4 models successfully
   - Startup scripts created
   - Model registry configured

4. **Phase 2: Windows LLM Client** (JUST COMPLETED)
   - `<project_root>\lib\llm_client.py` - Production client with fallback
   - `<project_root>\configs\llm_config.yaml` - Configuration
   - `<project_root>\scripts\test_llm_client.py` - Test script
   - Features: Automatic failover, health monitoring, metrics

5. **Phase 2: WSL Network Configuration**
   - Created `<windows_user_home>\.wslconfig`
   - Enabled localhost forwarding
   - Mirrored networking mode
   - Auto memory/swap management

### 🔄 IN PROGRESS
- **Testing Windows → WSL connectivity**
- **Starting vLLM service (Llama 1B recommended)**
- **Verifying LLM client failover chain**

### ⏳ PENDING
- Integration with GoodQ4All pipeline steps
- Chat interface updates
- Production deployment testing
- Performance benchmarking

---

## 🎯 Immediate Next Steps

1. **Start Llama 1B vLLM Server**
   ```bash
   source ~/vllm_server/venv/bin/activate
   ~/vllm_server/scripts/start_llama1b.sh
   ```

2. **Verify Server Running**
   ```bash
   curl http://localhost:38005/v1/models
   ```

3. **Test from Windows**
   - Windows agent will run: `python <project_root>\scripts\test_llm_client.py`
   - Should connect to: vLLM (38005) → Ollama (31434) → LMStudio (1234)

4. **Monitor Logs**
   ```bash
   tail -f ~/vllm_server/logs/llama1b.log
   ```

---

## 📊 Performance Benchmarks (Tested)

| Model | Speed | VRAM | Context | Best For |
|-------|-------|------|---------|----------|
| Llama 1B | 178 tok/s ⚡ | 2.3 GB | 128K | Speed, efficiency |
| Llama 3B | 82.5 tok/s | 4.8 GB | 128K | Balance |
| Phi-3.5 Mini | 73.6 tok/s | 7.1 GB | 128K | Long context |
| Qwen 2.5 7B | ~50 tok/s | 14.2 GB | 32K | Quality |

**Recommendation:** Llama 1B for production (fastest + smallest footprint)

---

## 🔥 Quick Reference Commands

### Check All Services
```bash
# Ollama
sudo systemctl status ollama
curl http://localhost:31434/v1/models

# vLLM (if running)
curl http://localhost:38005/v1/models

# Audio processing test
~/goodq_audio/process.sh /mnt/<drive>/<repo_root>/samples/audio/test_audio.mp3
```

### Start vLLM Server
```bash
source ~/vllm_server/venv/bin/activate
~/vllm_server/scripts/start_llama1b.sh  # Fastest, recommended
# Or: start_phi.sh, start_qwen.sh, start_llama3b.sh, start_llama11b.sh
```

### Stop Services
```bash
# Ollama
sudo systemctl stop ollama

# vLLM (find and kill)
pkill -f "vllm.entrypoints"
```

### Check GPU
```bash
nvidia-smi
# Should show: RTX 4070 Ti SUPER, 16 GB VRAM
```

---

## 📚 Documentation Files

All reports are in `~/vllm_server/`:
- `INSTALLATION_REPORT.md` - vLLM setup
- `MODEL_DOWNLOAD_REPORT.md` - HuggingFace models
- `TEST_RESULTS_REPORT.md` - Performance testing
- `LLAMA_TEST_RESULTS.md` - Llama-specific tests
- `OLLAMA_INTEGRATION.md` - Ollama setup

Audio processing docs in `~/goodq_audio/`:
- `INSTALLATION_COMPLETE.md`
- `QUICKSTART.md`
- `CUDNN_FIX.md`
- `DIARIZATION_SETUP.md`

---

## 🎯 Your Mission Now

**Primary Goal:** Start and verify Llama-3.2-1B vLLM server so Windows can connect

**Steps:**
1. Activate vLLM environment
2. Start Llama 1B server on port 38005
3. Verify it's responding to API calls
4. Report back status so Windows agent can test connectivity

**Expected Result:**
- vLLM server running on port 38005
- Windows LLM client successfully connects
- Fallback chain verified (vLLM → Ollama → LMStudio)

---

## 💬 Communication Protocol

When reporting status, please include:
- ✅/❌ Status indicators
- Port numbers
- Any error messages
- Performance metrics (if applicable)

Example:
```
✅ Llama 1B vLLM server started
   Port: 38005
   Model loaded: 12.3 seconds
   API responding: Yes
   Ready for Windows connection test
```

---

**You are the WSL agent. The Windows agent (GoodQ) is coordinating. Let's make this integration flawless!** 🚀

