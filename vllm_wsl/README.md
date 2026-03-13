# vLLM WSL2 Server - Reference Files

**Status:** ✅ Operational (systemd service)  
**Location:** WSL2 Ubuntu (`~/vllm_server/`)  
**Purpose:** GPU-accelerated LLM inference for GoodQ4All

---

## Architecture

### WSL2 Deployment

vLLM runs as a **systemd service** in WSL2 Ubuntu, providing:
- GPU-accelerated inference (CUDA 12.1)
- Multiple model servers (Llama, Phi, Qwen)
- Port proxy to Windows (ports 8000-8009)
- Zero Docker dependency

### Directory Structure

```
~/vllm_server/                    # WSL2 active directory
├── scripts/                      # Server management scripts
│   ├── start_all_servers.sh      # Launch all model servers
│   ├── start_llama*.sh           # Individual model launchers
│   ├── monitor.sh                # Health monitoring
│   ├── status_all.sh             # Check server status
│   └── test_*.sh                 # Testing scripts
├── configs/                      # Configuration files
│   ├── default.yaml              # Default vLLM settings
│   └── models.yaml               # Model definitions
├── logs/                         # Server logs
├── venv/                         # Python virtual environment
└── activate.sh                   # Environment activation

L:\goodq4all\vllm_wsl\            # Windows repo mirror
├── scripts/                      # Same scripts (reference)
├── configs/                      # Same configs (reference)
└── *.md, *.txt                   # Documentation
```

---

## Quick Start

### Starting vLLM Servers

**From Windows:**
```powershell
# Start all servers
.\scripts\start_vllm_servers.bat

# Check status
.\scripts\status_vllm_servers.bat

# Stop all servers
.\scripts\stop_vllm_servers.bat
```

**From WSL2:**
```bash
cd ~/vllm_server
source activate.sh
./scripts/start_all_servers.sh
./scripts/status_all.sh
```

### Accessing from Windows

Servers are accessible via port proxy:
- **Llama 3.2 1B:** http://localhost:8000
- **Llama 3.2 3B:** http://localhost:8001
- **Llama 3.3 11B:** http://localhost:8002
- **Phi 3.5 Mini:** http://localhost:8003
- **Qwen 2.5 0.5B:** http://localhost:8004

---

## Files in This Directory

### Scripts (scripts/)

**Server Management:**
- `start_all_servers.sh` - Launch all configured model servers
- `status_all.sh` - Check status of all servers
- `monitor.sh` - Continuous health monitoring

**Individual Launchers:**
- `start_llama1b.sh` - Llama 3.2 1B (fastest, lowest memory)
- `start_llama3b.sh` - Llama 3.2 3B (balanced)
- `start_llama11b.sh` - Llama 3.3 11B (best quality)
- `start_phi.sh` - Phi 3.5 Mini
- `start_qwen.sh` - Qwen 2.5 0.5B
- `start_llama.sh` - Generic launcher
- `start_server.sh` - Single server launcher

**Testing:**
- `test_debug.sh` - Debug server issues
- `test_models.sh` - Test model functionality
- `test_windows_connectivity.sh` - Test Windows port proxy

### Configs (configs/)

**default.yaml:**
- vLLM server configuration
- GPU memory settings
- Context window sizes
- Tensor parallelism

**models.yaml:**
- Model definitions
- HuggingFace model IDs
- Port assignments
- Resource requirements

### Documentation

**Setup & Installation:**
- `INSTALLATION_REPORT.md` - Complete installation guide
- `MODEL_DOWNLOAD_REPORT.md` - Model download instructions
- `QUICK_REFERENCE.txt` - Command quick reference

**Testing & Validation:**
- `LLAMA_TEST_RESULTS.md` - Test results for Llama models
- `TEST_DEBUG_GUIDE.md` - Debugging guide
- `WINDOWS_TEST_READY.txt` - Windows connectivity verification

**Integration:**
- `OLLAMA_INTEGRATION.md` - Ollama integration notes
- `MODEL_SCAN_REPORT.md` - Available models scan
- `MODEL_SCAN_UPDATED.md` - Updated model inventory

**Other:**
- `activate.sh` - Virtual environment activation script

---

## Systemd Service

vLLM runs as a systemd service in WSL2:

```bash
# Check service status
sudo systemctl status vllm

# Start service
sudo systemctl start vllm

# Stop service
sudo systemctl stop vllm

# View logs
sudo journalctl -u vllm -f
```

### Service Configuration

Located at: `/etc/systemd/system/vllm.service`

Installed via: `scripts/wsl/install_vllm_service.sh` (in repo root)

---

## Port Proxy (Windows ↔ WSL2)

> Historical note: older hosts used a manual Windows `netsh interface portproxy`
> helper to expose WSL vLLM services. That helper has been retired from the
> tracked surface. The supported path is to verify the WSL service directly from
> Windows using localhost.

```powershell
# Test connectivity from Windows
.\scripts\test_vllm_from_windows.ps1

# View current proxies on a legacy host (cleanup/inspection only)
netsh interface portproxy show all
```

**Ports proxied:** 8000-8009 (10 ports for multiple models)

---

## GPU Requirements

**Minimum:**
- NVIDIA GPU with CUDA support
- 8GB VRAM (for 1B models)
- CUDA 12.1+ in WSL2

**Recommended:**
- 16GB+ VRAM (for 11B models)
- RTX 3090, 4090, or A100

**Current Setup (Verified):**
- RTX 4070 Ti SUPER 16GB
- CUDA 12.8 (WSL2)
- Shared with audio processing (85% total GPU util)

---

## Integration with GoodQ4All

### Current Status

**⊘ Phase 7 - Not Yet Integrated**

vLLM servers are **operational** but not yet called by the main ingestion pipeline.

**Planned Use Cases:**
1. Entity resolution (LLM-based disambiguation)
2. Scene summarization (generate descriptions)
3. Query expansion (semantic search enhancement)
4. Metadata enrichment (infer tags/categories)

### When Integrated

The pipeline will call vLLM via HTTP API:
```python
# Example future integration
from lib.vllm_client import VLLMClient

client = VLLMClient(base_url="http://localhost:8000")
summary = client.generate(prompt=f"Summarize: {scene_data}")
```

---

## Model Information

### Available Models

| Model | Size | VRAM | Port | Use Case |
|-------|------|------|------|----------|
| Llama 3.2 1B | 1B | 4GB | 8000 | Fast inference, high throughput |
| Llama 3.2 3B | 3B | 8GB | 8001 | Balanced quality/speed |
| Llama 3.3 11B | 11B | 16GB | 8002 | Best quality, slower |
| Phi 3.5 Mini | 3.8B | 8GB | 8003 | Instruction following |
| Qwen 2.5 0.5B | 0.5B | 2GB | 8004 | Ultra-fast, minimal quality |

### Model Downloads

Models are downloaded from HuggingFace:
- Stored in: `~/.cache/huggingface/hub/`
- Requires: HuggingFace token (gated models)
- Size: ~2-20GB per model

---

## Troubleshooting

### Service Not Starting

```bash
# Check service logs
sudo journalctl -u vllm -n 50

# Check GPU availability
nvidia-smi

# Verify CUDA
python3 -c "import torch; print(torch.cuda.is_available())"
```

### Port Proxy Issues

```powershell
# Check existing legacy portproxy rules
netsh interface portproxy show all

# Test connectivity
.\scripts\test_vllm_from_windows.ps1
```

### Model Loading Errors

```bash
# Check HuggingFace token
huggingface-cli whoami

# Check model cache
ls ~/.cache/huggingface/hub/

# Re-download model
huggingface-cli download meta-llama/Llama-3.2-1B-Instruct
```

---

## Notes

### Relationship to wsl2_audio/

Similar architecture:
- **wsl2_audio/** - WSL2 audio processing (Whisper, Pyannote)
- **vllm_wsl/** - WSL2 LLM inference (vLLM servers)
- Both run in WSL2 with GPU acceleration
- Both accessible from Windows via network

### Ollama vs vLLM

**Ollama:**
- Installed on Windows AND WSL2
- Simple API (similar to OpenAI)
- Good for interactive use
- Version: 0.13.1 (Windows), 0.12.11 (WSL2)

**vLLM:**
- WSL2 only (systemd service)
- High-performance batch inference
- Better for pipeline integration
- OpenAI-compatible API

---

## Files Synced

**Last Sync:** December 15, 2025 01:38 UTC  
**Source:** `\\wsl.localhost\Ubuntu\home\joesdomingo\vllm_server`  
**Destination:** `L:\goodq4all\vllm_wsl`  
**Files:** 25 files (scripts, configs, documentation)  
**Status:** ✅ In sync with WSL2 active environment

---

## Related Documentation

**In Repository:**
- `docs/guides/llm/VLLM_SYSTEMD_SETUP.md` - Systemd setup guide
- `docs/guides/llm/WSL_VLLM_STARTUP_GUIDE.md` - Startup procedures
- `docs/guides/llm/VLLM_INTEGRATION_PLAN.md` - Integration roadmap
- `scripts/wsl/install_vllm_service.sh` - Service installation

**In This Directory:**
- `INSTALLATION_REPORT.md` - Complete setup walkthrough
- `QUICK_REFERENCE.txt` - Command cheat sheet
- `TEST_DEBUG_GUIDE.md` - Troubleshooting guide

---

**Architecture:** WSL2 systemd service + Windows port proxy  
**Status:** ✅ Operational, Phase 7 integration pending  
**GPU:** Shared with audio (vLLM + Whisper + Pyannote)  
**Purpose:** Zero-Docker local LLM inference

---

*"Local LLMs. GPU-accelerated. Docker-free. Production-ready."*
