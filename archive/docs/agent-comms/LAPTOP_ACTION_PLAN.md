<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

> [!WARNING]
> ARCHIVE / NON-CANONICAL / DO NOT COPY PATHS
> This document is preserved as historical evidence and may contain obsolete fixed-drive paths, host-specific assumptions, stale commands, or superseded runtime guidance.
> Do not use it for current runtime, setup, migration, or copy-paste path decisions.
> Use active documentation, `config_loader`, and canonical path abstractions such as `<project_root>`, `<GOODQ_DATA_ROOT>`, and `<GOODQ_WSL_WORKSPACE>` instead.

# 🚀 LAPTOP DEPLOYMENT - ACTION PLAN

## On Your Laptop (Fresh Machine)

### Step 1: Clone Repository (5 minutes)
```powershell
# Open PowerShell as Administrator
cd C:\Projects  # or your preferred location
git clone https://github.com/JoesDomingo/Goodq4all.git
cd Goodq4all
```

### Step 2: Install Miniconda (10 minutes)
```powershell
# Download installer
Invoke-WebRequest -Uri "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe" -OutFile "$env:TEMP\miniconda.exe"

# Run installer (follow GUI prompts)
Start-Process "$env:TEMP\miniconda.exe" -Wait

# IMPORTANT: Close and reopen PowerShell after installation
```

### Step 3: Quick Validation Test (2 minutes)
```powershell
# After reopening PowerShell
cd C:\Projects\Goodq4all  # or wherever you cloned
.\quick_laptop_test.ps1
```

**Expected Result**: 8-10 tests should pass  
**If <8 pass**: Check LAPTOP_INSTALL_GUIDE.md troubleshooting section

### Step 4: Setup Environments (20-30 minutes)
```powershell
# Automated setup (recommended)
python configure_envs_pythonpath.py

# This will create all 6 conda environments and install dependencies
# Grab coffee - this takes a while!
```

### Step 5: Install LM Studio (10 minutes)
1. Download from https://lmstudio.ai/
2. Install and launch
3. Download a model:
   - Recommended: **qwen2.5-7b-instruct** (good balance)
   - Alternative: **phi-4** (lighter, faster)
   - Alternative: **llama-3.1-8b** (most capable)
4. Start Local Server in LM Studio
5. Verify: http://localhost:1234/v1/models should show your model

### Step 6: Configure Environment (2 minutes)
```powershell
# Copy template
copy .env.local.template .env.local

# Edit configuration
notepad .env.local
```

**Set these values**:
```env
LM_STUDIO_URL=http://localhost:1234
LM_STUDIO_MODEL=qwen2.5-7b-instruct  # or whatever you downloaded
```

### Step 7: Initialize Databases (1 minute)
```powershell
conda activate goodq_zenml
python -c "from common.db_utils import init_all_databases; init_all_databases()"
```

### Step 8: First Launch! (30 seconds)
```powershell
.\LAUNCH_GOODQ.bat
# Select option 1 (Complete System)
```

**What should happen**:
- Terminal 1: API server starts on port 30000
- Terminal 2: Watchdog starts monitoring import_inbox
- Browser: Opens http://localhost:30000 automatically

### Step 9: Test with Sample Video (2-5 minutes)
```powershell
# Copy a short test video
copy "C:\path\to\test.mp4" "import_inbox\"

# Watch in UI:
# - Navigate to "Command Center" to see live logs
# - Check "Scene Explorer" after processing
# - Try chatting: "Show system status"
```

---

## ✅ SUCCESS CRITERIA

Your installation is successful if:

1. ✅ UI loads at http://localhost:30000
2. ✅ Command Center shows live logs
3. ✅ Sample video processes without errors
4. ✅ Scene Explorer shows detected scenes
5. ✅ Chat responds (if LM Studio is running)
6. ✅ No critical errors in logs

---

## 🎯 FIRST PRODUCTION RUN

After successful test:

### 1. Clear Test Data
```powershell
# Stop all services first (Ctrl+C in both terminals)
Remove-Item import_inbox\* -Exclude ".gitkeep"
Remove-Item output\videos\* -Recurse -Force
```

### 2. Copy Your First Home Movie
```powershell
# From your backup location
copy "L:\_DATA\FAMILY_FEAST\*.mp4" "C:\Projects\Goodq4all\import_inbox\"
```

### 3. Start and Monitor
```powershell
.\LAUNCH_GOODQ.bat
# Select option 1

# Open UI: http://localhost:30000
# Watch progress in Command Center
```

### 4. Expected Timeline
- **2-hour video** on RTX 3060: ~3-4 hours
- **2-hour video** on RTX 4070: ~1.5-2 hours

### 5. Monitor GPU
```powershell
# In new terminal
nvidia-smi -l 1
```

Watch for:
- ✅ GPU usage: 50-90% (good)
- ✅ Memory: <80% of total (good)
- ⚠️ If OOM errors: Reduce GPU_MEMORY_FRACTION in gpu_config.py

---

## 🔥 OPTIMIZATION FOR LAPTOPS

### If You Have 8GB GPU:
Edit `gpu_config.py`:
```python
GPU_MEMORY_FRACTION = 0.4  # Reduce from 0.6
MAX_CONCURRENT_GPU_TASKS = 1  # Reduce from 2
```

### If You Have 16GB+ GPU:
```python
GPU_MEMORY_FRACTION = 0.7  # Increase
MAX_CONCURRENT_GPU_TASKS = 3  # Can handle more
```

### For Faster Scene Detection:
Edit `config.yaml`:
```yaml
scene_detect:
  min_scene_len: 180  # 3 minutes (reduce from 5 for more scenes)
```

---

## 📊 WHAT TO EXPECT

### Processing Your 24 Hours of Home Movies

**Sequential (One at a time)**:
- 12 videos × 2 hours each = 24 hours content
- ~3 hours processing per video = 36 hours total
- **About 1.5 days of continuous processing**

**Optimized (With tweaks)**:
- Reduce scene detection quality slightly
- Process during nights/weekends
- **Complete in 1-2 weeks of casual processing**

### Disk Space Usage
- **Input**: 24 hours @ 720p = ~50-100GB
- **Output**: Scenes + embeddings + DB = ~30-50GB
- **Total needed**: 100-150GB free

---

## 🆘 QUICK TROUBLESHOOTING

### "Conda command not found"
```powershell
# Add to PATH manually
$env:Path += ";C:\Users\$env:USERNAME\miniconda3\Scripts"
# Or reinstall Miniconda
```

### "CUDA out of memory"
```powershell
# Reduce batch sizes in config.yaml
# Reduce GPU_MEMORY_FRACTION in gpu_config.py
# Process one video at a time
```

### "Port 30000 already in use"
```powershell
netstat -ano | findstr :30000
taskkill /PID <PID_NUMBER> /F
```

### "LM Studio not responding"
1. Restart LM Studio
2. Check server is running (green indicator)
3. Test: http://localhost:1234/v1/models
4. Verify .env.local has correct URL

### "Pipeline hangs at scene detection"
- This was a known issue, now fixed!
- Scenes are now minimum 5 minutes (300 sec)
- If still happens: Check logs/scene_detect.log

---

## 📞 SUPPORT

- **Documentation**: See `/docs` folder in repository
- **Troubleshooting**: LAPTOP_INSTALL_GUIDE.md
- **GitHub Issues**: Report bugs at repository
- **Logs**: Always check `/logs` for detailed errors

---

## 🎉 YOU'RE READY!

Everything is committed, tested, and documented.  
The system is production-ready.  
Your 24 hours of home movies await analysis.

**Time to build your personal memory time machine! 🚀**

---

**Total Setup Time**: 1-2 hours  
**First Video**: 2-4 hours  
**Full Library**: 1-2 weeks casual processing

**Let's do this!** 💪
