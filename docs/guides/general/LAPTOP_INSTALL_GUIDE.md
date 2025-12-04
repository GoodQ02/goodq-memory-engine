# 🚀 GoodQ4All - Laptop Installation Guide

## Fresh Installation on New Machine

### Prerequisites
- Windows 10/11 with WSL2 (optional but recommended for better performance)
- NVIDIA GPU with latest drivers (required for video processing)
- At least 32GB RAM recommended
- 100GB+ free disk space

---

## Step 1: Install Miniconda

```powershell
# Download Miniconda installer
Invoke-WebRequest -Uri "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe" -OutFile "$env:TEMP\miniconda.exe"

# Run installer (GUI)
Start-Process "$env:TEMP\miniconda.exe" -Wait

# Close and reopen terminal to refresh PATH
```

---

## Step 2: Clone Repository

```powershell
# Choose your installation directory
cd C:\Projects  # or wherever you prefer

# Clone the repository
git clone https://github.com/YOUR_USERNAME/goodq4all.git
cd goodq4all
```

---

## Step 3: Environment Setup

### Option A: Automated Setup (Recommended)

```powershell
# Run the automated environment configurator
python configure_envs_pythonpath.py
```

This will:
- ✅ Create all required conda environments
- ✅ Install dependencies for each environment
- ✅ Configure Python paths
- ✅ Validate GPU access

### Option B: Manual Setup

```powershell
# Create main environment
conda env create -f envs/goodq_zenml.yml

# Create specialized environments
conda env create -f envs/goodq_video_scene_detect.yml
conda env create -f envs/goodq_audio_transcribe.yml
conda env create -f envs/goodq_emotion_classify.yml
conda env create -f envs/goodq_face_embed.yml
conda env create -f envs/goodq_object_detect.yml
```

---

## Step 4: Verify Installation

```powershell
# Activate main environment
conda activate goodq_zenml

# Run validation tests
python test_python_paths.py
python diagnose_system.py
python test_gpu_management.py
```

Expected output:
```
✓ ALL TESTS PASSED
✓ GPU Access: CUDA Available
✓ All environments configured
```

---

## Step 5: Configure LM Studio Integration

1. **Install LM Studio** from https://lmstudio.ai/
2. **Download a model** (recommended: qwen2.5-7b-instruct or phi-4)
3. **Start LM Studio server**:
   - Open LM Studio
   - Go to "Local Server" tab
   - Click "Start Server"
   - Default: http://localhost:1234

4. **Update GoodQ configuration**:
```powershell
# Edit .env.local
notepad .env.local
```

Set:
```
LM_STUDIO_URL=http://localhost:1234
LM_STUDIO_MODEL=qwen2.5-7b-instruct
```

---

## Step 6: Initialize Databases

```powershell
# Initialize all databases
python -c "from common.db_utils import init_all_databases; init_all_databases()"

# Verify
python check_db_status.py
```

---

## Step 7: First Run

### Launch the System

```powershell
# Use the launcher (recommended)
.\LAUNCH_GOODQ.bat
```

Or manually:

```powershell
# Terminal 1: Start API server
conda activate goodq_zenml
python api_server.py

# Terminal 2: Start watchdog
conda activate goodq_zenml
python scripts\watchdog_ingest.py

# Terminal 3: Open UI
start http://localhost:30000
```

---

## Step 8: Test with Sample Video

```powershell
# Copy a test video to import inbox
copy "C:\path\to\your\video.mp4" ".\import_inbox\"

# Monitor progress
python monitor_progress.py
```

Or watch in the UI at http://localhost:30000

---

## Troubleshooting

### Issue: "Python not found"
**Solution:**
```powershell
# Run the Python alias fix
.\FIX_PYTHON_ALIAS.ps1

# Or disable Microsoft Store Python alias manually:
# Settings > Apps > Advanced app settings > App execution aliases
# Turn OFF "python.exe" and "python3.exe"
```

### Issue: "CUDA not available"
**Solution:**
```powershell
# Check NVIDIA driver
nvidia-smi

# Update CUDA toolkit if needed
# Visit: https://developer.nvidia.com/cuda-downloads
```

### Issue: "Module not found"
**Solution:**
```powershell
# Ensure you're in the correct environment
conda activate goodq_zenml

# Reinstall dependencies
conda env update -f envs\goodq_zenml.yml --prune
```

### Issue: "API server not responding"
**Solution:**
```powershell
# Check if port 30000 is already in use
netstat -ano | findstr :30000

# Kill process if needed
taskkill /PID <PID> /F

# Restart server
python api_server.py
```

### Issue: "GPU out of memory"
**Solution:**
Edit `gpu_config.py`:
```python
GPU_MEMORY_FRACTION = 0.4  # Reduce from 0.6
MAX_CONCURRENT_GPU_TASKS = 1  # Reduce from 2
```

---

## Quick Reference

### Daily Usage

```powershell
# Start everything
.\LAUNCH_GOODQ.bat

# Add videos
copy videos\*.mp4 import_inbox\

# Monitor
# Open browser: http://localhost:30000

# Stop
# Ctrl+C in all terminals
```

### Health Checks

```powershell
# Quick system status
python diagnose_system.py

# Database stats
python check_db_stats.py

# GPU usage
nvidia-smi
```

### Log Locations

- **Watchdog**: `logs/watchdog.log`
- **API Server**: `logs/api_server.log`
- **Command Center**: `logs/command_center.log`
- **Step Logs**: `logs/steps/*`

---

## Performance Optimization

### For Laptops with Limited GPU Memory

1. **Reduce batch sizes** in `config.yaml`:
```yaml
face_embed:
  batch_size: 8  # Reduce from 16

object_detect:
  batch_size: 4  # Reduce from 8
```

2. **Enable sequential GPU processing**:
```python
# gpu_config.py
MAX_CONCURRENT_GPU_TASKS = 1
```

3. **Lower VRAM allocation**:
```python
# gpu_config.py
GPU_MEMORY_FRACTION = 0.3  # For 8GB GPUs
```

### For Desktop with High-End GPU

1. **Increase concurrency**:
```python
# gpu_config.py
MAX_CONCURRENT_GPU_TASKS = 3
GPU_MEMORY_FRACTION = 0.7
```

2. **Larger batch sizes**:
```yaml
face_embed:
  batch_size: 32

object_detect:
  batch_size: 16
```

---

## Features Checklist

After installation, verify these features work:

- [ ] Video ingestion from import_inbox
- [ ] Scene detection and splitting
- [ ] Audio transcription and diarization
- [ ] Face detection and recognition
- [ ] Object detection
- [ ] Emotion classification
- [ ] Knowledge graph building
- [ ] Web UI accessible
- [ ] Chat with LLM about memories
- [ ] Search and filtering
- [ ] Analytics dashboard
- [ ] Process monitoring

---

## Next Steps

1. **Add your home movies** to `import_inbox/`
2. **Monitor first ingestion** in the UI
3. **Explore memories** via chat interface
4. **Check analytics** for insights
5. **Fine-tune settings** based on performance

---

## Support

- **Documentation**: See `/docs` folder
- **Logs**: Check `/logs` for detailed errors
- **GitHub Issues**: Report bugs at repository
- **Configuration**: All settings in `config.yaml` and `.env.local`

---

## System Requirements Summary

### Minimum
- CPU: Intel i5 / AMD Ryzen 5
- RAM: 16GB
- GPU: NVIDIA GTX 1660 (6GB VRAM)
- Storage: 50GB SSD

### Recommended
- CPU: Intel i7 / AMD Ryzen 7
- RAM: 32GB
- GPU: NVIDIA RTX 3060 (12GB VRAM)
- Storage: 100GB+ SSD

### Optimal
- CPU: Intel i9 / AMD Ryzen 9
- RAM: 64GB
- GPU: NVIDIA RTX 4090 (24GB VRAM)
- Storage: 500GB+ NVMe SSD

---

**Last Updated**: November 11, 2025
**Version**: 2.0.0
**Status**: Production Ready ✅
