# GoodQ Troubleshooting Guide

> **Role:** Canonical troubleshooting guide for GoodQ4All. Start here for common issues when launching or running services. See `docs/guides/` for specific subsystem guides (WSL2, Qdrant, GPU).

**Last Updated:** December 14, 2025  
**Status:** ✅ Reflects forensically verified operational system

Quick fixes for common issues when launching and running GoodQ services.

---

## 🚀 Quick Fixes

### Issue 1: System Won't Start

**Symptoms:**
```
No command window appears
LAUNCH_GOODQ.bat exits immediately
"System health check failed"
```

**Fix:**
```powershell
# Run health check first
python scripts/system_readiness_check.py

# Check for missing models
python scripts/cache_readiness_check.py

# Verify Qdrant is running
Invoke-WebRequest http://localhost:6333/health
```

**Common Causes:**
- Qdrant service not started (Port 6333)
- Missing conda environment (`goodq_core`)
- Missing HuggingFace token for WSL2 audio

---

### Issue 2: WSL2 Audio Service Not Running

**Error:**
```
[ERROR] WSL2 audio service not responding
[ERROR] Connection refused on WSL2 bridge
Audio processing failed
```

**Fix:**
```bash
# In WSL2, check if service is running
ps aux | grep audio_service

# Should show PID (e.g., 177) - if not, start it:
cd ~/goodq_audio
python audio_service.py &

# Verify it's working
ps aux | grep audio_service
# Expected: python audio_service.py (with PID)
```

**Verify GPU Access:**
```bash
# In WSL2
nvidia-smi

# Should show:
# CUDA Version: 12.8
# GPU: RTX 4070 Ti SUPER
```

**Check HuggingFace Token:**
```bash
# In WSL2
cat ~/.config/config.json | grep hf_token

# If empty, add token:
cd ~/goodq_audio
nano config.json
# Add: "hf_token": "hf_xxxxxxxxxxxxx"
```

---

### Issue 3: Qdrant Connection Failed

**Error:**
```
[ERROR] Failed to connect to Qdrant
Connection refused (port 6333)
```

**Fix:**
```powershell
# Check if Qdrant is running
Get-Process qdrant -ErrorAction SilentlyContinue

# If not running, start it:
cd L:\goodq4all\vendor\qdrant
.\qdrant.exe

# Or use the launcher:
.\START_QDRANT.bat
```

**Verify Collections:**
```powershell
# Test connection
Invoke-WebRequest http://localhost:6333/health

# Check collections exist
Invoke-WebRequest http://localhost:6333/collections
```

**Initialize if needed:**
```batch
INIT_QDRANT.bat
```

---

### Issue 4: CUDA Out of Memory

**Error:**
```
RuntimeError: CUDA out of memory
Tried to allocate X.XX GiB (GPU 0; 16.00 GiB total capacity)
```

**Current GPU Usage:**
```powershell
nvidia-smi

# Expected normal usage:
# Windows (goodq_core): 8-10GB
# WSL2 (audio service): 4-6GB
# Total: ~12-14GB / 16GB (85% utilization is normal)
```

**Fix:**
```powershell
# If over 95% utilization, clear GPU cache
python -c "import torch; torch.cuda.empty_cache()"

# Check what's using GPU
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
```

**Prevent:**
- Don't run other GPU-heavy tasks during processing
- WSL2 audio service + Windows vision pipeline share GPU (by design)
- 85% utilization is normal and stable

---

### Issue 5: Processing Stuck on Scene

**Symptoms:**
```
[INFO] Scene 15/30 - Processing...
(No updates for 5+ minutes)
```

**Check Progress:**
```powershell
# Check scene artifacts
Get-ChildItem "logs\scene_ingest\<video>\audio\" -Recurse | Select-Object Name, Length, LastWriteTime

# Check WSL2 output
wsl ls -lh ~/goodq_audio/output/result.json
```

**If truly stuck:**
```powershell
# Check GPU is active
nvidia-smi

# Check WSL2 service
wsl ps aux | grep python

# Review logs
Get-Content "logs\scene_ingest\<video>\*.log" -Tail 50
```

**Restart if needed:**
1. Stop: Ctrl+C in command window
2. Check GPU: `nvidia-smi` (verify nothing hung)
3. Restart WSL2 service if needed: `wsl pkill python; wsl cd ~/goodq_audio && python audio_service.py &`
4. Resume processing

---

### Issue 6: Entity Extraction Errors

**Error:**
```
[ERROR] KeyError: 'transcript'
[ERROR] Entity extraction failed
[ERROR] Field 'objects' not found
```

**Status:** ✅ **FIXED** (December 13-14, 2025)

Recent fixes applied to `steps/video/entity_extractor.py`. If you still see this:

```powershell
# Verify you have latest code
git pull origin main

# Check entity extractor version
Get-Content "steps\video\entity_extractor.py" | Select-String "Updated:"
# Should show: December 13-14, 2025
```

**Verify fields are populated:**
- `transcript` from WSL2 audio processing
- `caption` from BLIP2 image captioning
- `ocr_text` from Tesseract
- `objects` from YOLOv8 detection

---

### Issue 7: Knowledge Graph Not Updating

**Symptoms:**
```
Entity extraction runs
No errors shown
knowledge_graph.db file size not growing
```

**Check:**
```powershell
# Verify KG database exists
Test-Path "L:\_DATA\GoodQ_Data\knowledge_graph.db"

# Check file size
Get-Item "L:\_DATA\GoodQ_Data\knowledge_graph.db" | Select-Object Name, Length, LastWriteTime

# Verify entities are being extracted
Get-Content "logs\*.log" | Select-String "entity"
```

**Status:** ✅ **OPERATIONAL** (Dec 14, 2025)
- Knowledge graph updates confirmed working
- Real-time insertion active via `lib/kg_realtime_integration.py:109`
- File should grow with each scene processed

---

## 🔍 Diagnostic Commands

### System Health Checks
```powershell
# Quick health check
python scripts/system_readiness_check.py

# Check model cache
python scripts/cache_readiness_check.py

# Verify all services
# 1. Qdrant
Invoke-WebRequest http://localhost:6333/health

# 2. WSL2 Audio Service
wsl ps aux | grep audio_service
# Should show: PID 177 (or similar) running

# 3. GPU Status
nvidia-smi
# Expected: 12-14GB used, 85% utilization when processing
```

### Check Services Status

```powershell
# Check Qdrant
Get-Process qdrant -ErrorAction SilentlyContinue
Invoke-WebRequest http://localhost:6333/collections

# Check WSL2 Audio
wsl pgrep -f audio_service
# Returns PID if running

# Check Python processes
Get-Process python | Select-Object Id, ProcessName, WorkingSet, CPU
```

### Check Logs

```powershell
# Scene processing logs
Get-ChildItem "logs\scene_ingest\" -Recurse -Filter "*.log" | Select-Object FullName, Length, LastWriteTime

# WSL2 audio logs
wsl tail -f ~/goodq_audio/logs/audio_service.log

# Recent entity extraction
Get-Content "logs\*.log" -Tail 100 | Select-String "entity"

# Knowledge graph updates
Get-Item "L:\_DATA\GoodQ_Data\knowledge_graph.db" | Select-Object Name, Length, LastWriteTime
```

### Check Databases

```powershell
# Memory DB
Get-Item "L:\_DATA\GoodQ_Data\memory.db" | Select-Object Name, Length, LastWriteTime

# Knowledge Graph DB
Get-Item "L:\_DATA\GoodQ_Data\knowledge_graph.db" | Select-Object Name, Length, LastWriteTime

# Qdrant collections
Invoke-WebRequest http://localhost:6333/collections | ConvertFrom-Json
```

### Check Scene Artifacts

```powershell
# List recent videos processed
Get-ChildItem "logs\scene_ingest\" -Directory | Select-Object Name, LastWriteTime | Sort-Object LastWriteTime -Descending

# Check specific video artifacts
$video = "your_video_name"
Get-ChildItem "logs\scene_ingest\$video" -Recurse | Select-Object FullName, Length, LastWriteTime

# Count scenes processed
(Get-ChildItem "logs\scene_ingest\$video\audio\*.wav").Count
(Get-ChildItem "logs\scene_ingest\$video\video\*.jpg").Count
```

---

## 🛠️ Advanced Fixes

### Reset Services (Nuclear Option)

```powershell
# Stop all Python processes
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# Stop Qdrant
Get-Process qdrant -ErrorAction SilentlyContinue | Stop-Process -Force

# Stop WSL2 audio service
wsl pkill -f audio_service

# Restart everything
.\LAUNCH_GOODQ.bat
```

### Rebuild Conda Environment

```powershell
# If goodq_core is corrupted
conda env remove -n goodq_core
conda create -n goodq_core python=3.10 -y
conda activate goodq_core

# Reinstall requirements
pip install -r requirements.txt
```

### Reinitialize Qdrant

```powershell
# Stop Qdrant
Get-Process qdrant | Stop-Process -Force

# Backup data (optional)
Copy-Item "L:\_DATA\qdrant_storage" "L:\_DATA\qdrant_storage_backup" -Recurse

# Delete collections
Remove-Item "L:\_DATA\qdrant_storage\collections\*" -Recurse -Force

# Start Qdrant
cd L:\goodq4all\vendor\qdrant
.\qdrant.exe

# Reinitialize
.\INIT_QDRANT.bat
```

### Reset WSL2 Audio Environment

```bash
# In WSL2
cd ~/goodq_audio

# Stop service
pkill -f audio_service

# Clear output
rm -rf output/*

# Restart service
python audio_service.py &

# Verify
ps aux | grep audio_service
```

### Clear GPU Memory

```powershell
# Force clear CUDA cache
python -c "import torch; torch.cuda.empty_cache(); torch.cuda.synchronize()"

# Check freed memory
nvidia-smi

# If still stuck, restart driver (requires admin)
# Note: This will disconnect any GPU applications
Restart-Service -Name "NVIDIA Display Container LS"
```
```

### Rebuild Environment
```powershell
# Full rebuild
pwsh scripts/prepare_step_envs.ps1 -EnvPrefix goodq -ForceReinstall -LinkProject

# Specific environment
conda env remove -n goodq_<step> -y
pwsh scripts/prepare_step_envs.ps1 -EnvPrefix goodq -Steps <step> -LinkProject
```

### Clear and Restart
```powershell
# Full cleanup
.\STOP_GOODQ.bat
Remove-Item L:\goodq4all\logs\*.tmp -Force -ErrorAction SilentlyContinue
timeout /t 3

# Fresh start
.\LAUNCH_GOODQ.bat
```

---

## 📊 Expected Behavior

### Successful Launch
You should see:
- ✅ API Server window opens
- ✅ Command Center window opens
- ✅ Browser opens to http://localhost:30000/docs
- ✅ No red error messages in either window

### Command Center Display
```
== GoodQ Command Center ==
== GPU ==
NVIDIA GeForce RTX 4070 Ti SUPER, 16376, 1980, 0

== DB / FAISS ==
DB: {"embeddings": 2, "links": 11}
FAISS → text:missing dino:missing clip:missing audio:2

== DB↔FAISS Drift ==
audio (id_map): faiss=2 db=2 drift=0.0%

== Hot Cache (HF/Torch) ==
HF_HOME: 367551895777 bytes
TORCH_HOME: 367551895777 bytes
```

**Note:** "missing" indices are normal if you haven't run full ingestion yet.

---

## 🔄 Clean Slate Procedure

If nothing works, start fresh:

```powershell
# 1. Stop everything
.\STOP_GOODQ.bat
Get-Process | Where-Object { $_.ProcessName -like "*python*" } | Stop-Process -Force

# 2. Clear temp files
Remove-Item $env:TEMP\__conda_tmp_* -Force -ErrorAction SilentlyContinue
Remove-Item L:\goodq4all\logs\*.tmp -Force -ErrorAction SilentlyContinue

# 3. Verify conda
conda --version

# 4. Health check
pwsh scripts/mission_health_check.ps1 -EnvPrefix goodq

# 5. Fresh launch
.\LAUNCH_GOODQ.bat
```

---

## 📞 Still Having Issues?

### Collect Diagnostics
```powershell
# Generate diagnostic bundle
pwsh scripts/run_full_dry_run.ps1

# Check syntax
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
    "L:\goodq4all\scripts\command_center.ps1",
    [ref]$null, [ref]$errors
)
$errors
```

### What to Report
Include:
1. Error message (exact text)
2. Steps to reproduce
3. Output of health check
4. Last 10 lines of step_runs.jsonl

---

## ✅ Known Working Configuration

- **OS:** Windows 11
- **Python:** 3.10 (via Conda)
- **PowerShell:** 7+
- **GPU:** NVIDIA RTX 4070 Ti SUPER
- **Conda:** Miniconda3

---

## 🎯 Quick Reference

| Problem | Solution |
|---------|----------|
| Port in use | `.\STOP_GOODQ.bat` |
| Conda missing | Use Anaconda PowerShell Prompt |
| Env missing | `pwsh scripts/prepare_step_envs.ps1` |
| CUDA OOM | Reduce MaxScenes to 1 |
| Syntax error | Update scripts (heredoc fix applied) |
| Property missing | Normal if no ingestion run yet |

---

*For detailed documentation, see:*
- **LAUNCHER_GUIDE.md** - Complete launcher guide
- **QUICK_REFERENCE.md** - Essential commands
- **docs/guides/USER_GUIDE.md** - Full user manual

---

*Last reviewed: October 6, 2025*

---

### Issue 5: ImportError - AppleFrameworkLoader

**Error:**
```
Could not import runpy module
ImportError: cannot import name 'AppleFrameworkLoader' from 'importlib._bootstrap_external'
```

**Status:** ✅ **FIXED** (October 8, 2025)

**Cause:** Base conda Python's runpy module corruption affecting `python -m pip` calls.

**Solution Applied:**
- All GoodQ scripts now use `pip` directly instead of `python -m pip`
- Scripts updated: enable_cuda.ps1, fix_audio_emotion.ps1, index_to_chroma.ps1, lock_envs.ps1, prepare_step_envs.ps1, start_api.ps1

**If Issue Persists:**
```powershell
# Option A: Update base conda
conda update -n base conda python -y

# Option B: Reinstall Miniconda
# Download from: https://docs.conda.io/en/latest/miniconda.html
```

---

### Issue 6: goodq_face_embed Environment Failures

**Error:**
```
ERROR: Cannot install torch==2.3.1 and facenet-pytorch==2.6.0
ERROR: Failed building wheel for dlib
```

**Status:** ⚠️ **KNOWN ISSUE** - Non-critical (face embedding optional)

**Causes:**
1. **Dependency Conflict:** facenet-pytorch 2.6.0 requires torch<2.3.0, but GoodQ needs 2.3.1 for CUDA 12.1
2. **Build Requirement:** dlib requires CMake for Windows compilation

**Workaround:** Environment temporarily excluded from CUDA enablement. Other envs work normally.

**Permanent Fix Options:**

**Option A: Install CMake** (Recommended)
```powershell
# 1. Download from https://cmake.org/download/
# 2. Add CMake to system PATH
# 3. Run repair script
L:\goodq4all\scripts\emergency_conda_repair.ps1
```

**Option B: Use Alternative**
Replace face-recognition with `insightface`, `deepface`, or `mediapipe` (no CMake needed)

**More Info:** See `L:\goodq4all\envs\face_embed\KNOWN_ISSUES.md`

---

---

## 📚 Detailed Subsystem Guides

For comprehensive troubleshooting of specific components:

### WSL2 Audio System
- **[START_HERE_WSL2.md](guides/wsl2/START_HERE_WSL2.md)** - Complete WSL2 audio setup and troubleshooting
- **[WSL2_AUDIO_SUMMARY.md](guides/wsl2/WSL2_AUDIO_SUMMARY.md)** - Architecture and performance details
- **[WSL2_BENCHMARKS.md](guides/wsl2/WSL2_BENCHMARKS.md)** - Performance comparisons

**Common WSL2 Issues:**
- Service won't start → Check HuggingFace token in config.json
- GPU not accessible → Verify CUDA 12.8 with `nvidia-smi` in WSL2
- Diarization failing → Accept Pyannote model terms on HuggingFace
- Slow processing → Enable Silero VAD in service mode

### Qdrant Vector Database
- **[QDRANT_SETUP.md](guides/QDRANT_SETUP.md)** - Installation, initialization, and usage
- **[QDRANT_QUICKREF.md](QDRANT_QUICKREF.md)** - Quick reference for queries

**Common Qdrant Issues:**
- Connection refused → Start service with `START_QDRANT.bat`
- Collections missing → Run `INIT_QDRANT.bat`
- Slow queries → Check collection size with `http://localhost:6333/collections`
- Port conflict → Qdrant uses standard port 6333

### GPU Configuration
- **[GPU_SETUP.md](guides/gpu/GPU_SETUP.md)** - GPU configuration for Windows
- **[GPU_MANAGEMENT_GUIDE.md](guides/gpu/GPU_MANAGEMENT_GUIDE.md)** - GPU memory management
- **[GPU_LLM_WSL_INDEX.md](guides/gpu/GPU_LLM_WSL_INDEX.md)** - Comprehensive GPU, LLM, WSL2 guide

**Common GPU Issues:**
- Out of memory → 85% utilization is normal (12-14GB / 16GB)
- No GPU detected → Check CUDA 12.1 (Windows) or 12.8 (WSL2)
- Slow processing → Verify GPU is not being used by other apps
- Driver issues → Update to latest NVIDIA drivers

### Environment & Installation
- **[CONSOLIDATION_EXPLAINED.md](guides/CONSOLIDATION_EXPLAINED.md)** - Unified goodq_core environment
- **[INSTALL.md](guides/general/INSTALL.md)** - Complete installation guide
- **[LAPTOP_INSTALL_GUIDE.md](guides/general/LAPTOP_INSTALL_GUIDE.md)** - Installation for laptops

**Common Environment Issues:**
- Missing goodq_core → Unified environment replaces 6 separate envs
- Import errors → Ensure `conda activate goodq_core` before running
- Package conflicts → Unified env eliminates most conflicts
- Old envs still present → Safe to remove (goodq_image_caption, goodq_object_detect, etc.)

---

## 🆘 Getting Help

### Check Documentation First
1. This troubleshooting guide (you are here)
2. **[README.md](../README.md)** - System overview and status
3. **[QUICK_START.md](QUICK_START.md)** - Quick start guide
4. **[START_HERE.md](START_HERE.md)** - Complete navigation guide

### Check System Status
`powershell
# Run health checks
python scripts/system_readiness_check.py
python scripts/cache_readiness_check.py

# Check services
Invoke-WebRequest http://localhost:6333/health  # Qdrant
wsl ps aux | grep audio_service                   # WSL2 Audio
nvidia-smi                                         # GPU Status
`

### Review Recent Changes
`powershell
# Check recent documentation updates
Get-ChildItem docs\*.md | Sort-Object LastWriteTime -Descending | Select-Object Name, LastWriteTime -First 10

# Check recent code changes
git log --oneline -n 10
`

### Collect Diagnostic Information
If reporting an issue, collect this information:

`powershell
# System info
nvidia-smi > diagnostic_gpu.txt
conda info >> diagnostic_gpu.txt
python --version >> diagnostic_gpu.txt

# Service status
Get-Process python,qdrant | Select-Object Id, ProcessName, WorkingSet > diagnostic_services.txt
wsl ps aux | grep python >> diagnostic_services.txt

# Recent logs
Get-Content "logs\*.log" -Tail 100 > diagnostic_logs.txt
wsl tail -100 ~/goodq_audio/logs/audio_service.log >> diagnostic_logs.txt

# Database status
Get-Item "L:\_DATA\GoodQ_Data\*.db" | Select-Object Name, Length, LastWriteTime > diagnostic_db.txt
`

---

## 📋 Verification Checklist

Before reporting issues, verify:

- [ ] **System Requirements Met**
  - [ ] NVIDIA GPU with CUDA support (RTX 40-series or equivalent)
  - [ ] 16GB+ RAM (32GB recommended)
  - [ ] Windows 11 + WSL2 (Ubuntu)
  - [ ] 100GB+ free disk space

- [ ] **Services Running**
  - [ ] Qdrant on port 6333 (`Invoke-WebRequest http://localhost:6333/health`)
  - [ ] WSL2 audio service (`wsl ps aux | grep audio_service`)
  - [ ] GPU accessible (`nvidia-smi` shows CUDA 12.1/12.8)

- [ ] **Environment Configured**
  - [ ] goodq_core conda environment exists (`conda env list | grep goodq_core`)
  - [ ] HuggingFace token configured in WSL2 (`wsl cat ~/.config/config.json`)
  - [ ] Qdrant collections initialized (`Invoke-WebRequest http://localhost:6333/collections`)

- [ ] **Data Paths Exist**
  - [ ] `L:\_DATA\GoodQ_Data\` directory exists
  - [ ] `L:\_DATA\GoodQ_Data\import_inbox\` for input files
  - [ ] `logs\scene_ingest\` for scene artifacts
  - [ ] WSL2: `~/goodq_audio/` for audio processing

- [ ] **Recent Updates Applied**
  - [ ] Latest code from main branch (`git pull origin main`)
  - [ ] Entity extraction fixes (Dec 13-14, 2025)
  - [ ] Documentation sync (Dec 14, 2025)

---

## 🔄 System Status (December 14, 2025)

### ✅ Verified Operational
- Scene detection (30 scenes processed)
- WSL2 audio service (PID 177, CUDA 12.8)
- Speaker diarization (52 segments, 2 speakers)
- Entity extraction (cross-modal resolution)
- Knowledge graph updates (real-time insertion)
- Qdrant vector storage (3 collections active)
- GPU utilization (85% stable, RTX 4070 Ti SUPER)

### ⊘ Built But Not Wired (Phase 7 Planned)
- FastAPI server (scaffolded in `api/`)
- Web UI (frontend in `ui/`)
- Multimodal search (`retrieval/multimodal_search.py`)
- Cross-modal harmonizer (`steps/video/cross_modal_harmonizer.py`)

### ⚠️ Known Issues
- Config drift: Artifacts in `logs/scene_ingest/` not `processing/` (documented, not a bug)
- Legacy audio steps still run alongside unified WSL2 call (cleanup planned)
- API/UI mentioned in old docs but not yet deployed

---

**Last Updated:** December 14, 2025  
**Status:** Forensically verified operational system  
**Next Update:** After Phase 7 (API/UI deployment)

---

*"If you can't fix it with a shell command, try turning it off and on again."*  
*"When in doubt, check the logs. Always check the logs."*
