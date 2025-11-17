# GoodQ Troubleshooting Guide

> Role: Canonical troubleshooting guide for GoodQ4All. Start here for common issues when launching or running services; use `docs/TROUBLESHOOTING_INDEX.md` to locate subsystem-specific fix reports when symptoms match.

**Last Updated:** October 6, 2025

Quick fixes for common issues when launching GoodQ services.

---

## 🚀 Quick Fixes

### Issue 1: Port 8000 Already in Use

**Error:**
```
ERROR: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000)
```

**Fix:**
```powershell
# Option A: Use the stop script
.\STOP_GOODQ.bat

# Option B: Manual cleanup
Get-NetTCPConnection -LocalPort 8000 | ForEach-Object { 
    Stop-Process -Id $_.OwningProcess -Force 
}
```

**Prevention:** The launcher now auto-clears port 8000 before starting.

---

### Issue 2: Heredoc Syntax Errors

**Error:**
```
ParserError: Missing file specification after redirection operator.
```

**Status:** ✅ **FIXED** (October 6, 2025)

All heredoc patterns replaced with temp file approach. If you still see this, ensure you have the latest `command_center.ps1`.

---

### Issue 3: Missing Property Errors

**Error:**
```
The property 'segments_sentiment' cannot be found on this object.
```

**Status:** ✅ **FIXED** (October 6, 2025)

Command Center now checks for property existence before accessing. This is normal if you haven't run a full ingestion yet.

---

### Issue 4: Conda Not Found

**Error:**
```
conda not found on PATH
```

**Fix:**
1. Open **Anaconda PowerShell Prompt** (not regular PowerShell/CMD)
2. Navigate to `L:\goodq4all`
3. Run the launcher from there

**Alternative:**
Add conda to your PATH:
```powershell
$env:PATH += ";C:\Users\<YourUser>\miniconda3\Scripts"
```

---

### Issue 5: Environment Not Found

**Error:**
```
EnvironmentLocationNotFound: Not a conda environment
```

**Fix:**
```powershell
# Recreate the missing environment
pwsh scripts/prepare_step_envs.ps1 -EnvPrefix goodq -Steps <missing_step> -LinkProject
```

---

### Issue 6: CUDA Out of Memory

**Error:**
```
RuntimeError: CUDA out of memory
```

**Fix:**
```powershell
# Clear GPU cache
python -c "import torch; torch.cuda.empty_cache()"

# Reduce processing limits
pwsh scripts/ingest_videos_lite.ps1 -MaxScenes 1
```

---

## 🔍 Diagnostic Commands

### Check System Health
```powershell
# Full diagnostic
pwsh scripts/mission_health_check.ps1 -EnvPrefix goodq

# Quick checks
python scripts/system_readiness_check.py
python scripts/cache_readiness_check.py
```

### Check Services
```powershell
# List all GoodQ jobs
Get-Job | Where-Object { $_.Name -like "*GoodQ*" }

# Check port 8000
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue

# Test API
Invoke-WebRequest http://localhost:8000/health
```

### Check Logs
```powershell
# Recent errors
Get-Content L:\GoodQ_Data\logs\step_runs.jsonl -Tail 100 | 
    Select-String '"status":"error"'

# Last 50 entries
Get-Content L:\GoodQ_Data\logs\step_runs.jsonl -Tail 50
```

---

## 🛠️ Advanced Fixes

### Reset Everything
```powershell
# Stop all services
.\STOP_GOODQ.bat

# Clear all GoodQ jobs
Get-Job | Where-Object { $_.Name -like "*GoodQ*" } | Stop-Job
Get-Job | Where-Object { $_.Name -like "*GoodQ*" } | Remove-Job

# Verify ports are clear
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
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
- ✅ Browser opens to http://localhost:8000/docs
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
