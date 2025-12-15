# 🚀 GoodQ4All Installation Guide

**Last Updated:** December 15, 2025  
**Status:** ✅ FULLY OPERATIONAL  
**Verified Configuration:** RTX 4070 Ti SUPER, 16GB VRAM, CUDA 12.8

---

## 📋 Prerequisites

### Hardware Requirements
- **Windows 10/11** (Primary OS)
- **NVIDIA GPU** with CUDA support (RTX series recommended)
  - **Verified Configuration:** RTX 4070 Ti SUPER, 16GB VRAM
  - Minimum: 8GB VRAM for full pipeline
- **Disk Space:** 100GB+ recommended (models + data)
- **RAM:** 32GB+ recommended (64GB optimal)

### Software Requirements
- **WSL2 (Ubuntu 22.04+)** - Required for audio processing
- **Miniconda or Anaconda** - For environment management
- **Git** - For cloning repository
- **CUDA 12.1+** - GPU acceleration (12.8 verified)
- **HuggingFace Account** - For gated model access (Pyannote)

### Optional But Recommended
- **Qdrant** - Vector database (Windows service mode)
- **vLLM** - Local LLM serving (WSL2 systemd service)
- **Ollama** - Alternative LLM backend

---

## ⚡ Quick Installation (Recommended)

### 1. Clone the Repository

```bash
git clone https://github.com/goodq4all/goodq4all.git
cd goodq4all
```

### 2. Run Automated Windows Installer

```powershell
# Run as Administrator
powershell -ExecutionPolicy Bypass -File scripts\install_pipeline_windows.ps1
```

**This will:**
- ✅ Create unified `goodq_core` conda environment
- ✅ Install all Windows-side dependencies
- ✅ Configure CUDA and GPU settings
- ✅ Set up Qdrant vector database
- ✅ Validate Python paths and model access
- ✅ Download required models (CLIP, DINO, YOLO, etc.)

### 3. Run WSL2 Audio Installer

```bash
# In WSL2 Ubuntu terminal
cd /mnt/l/goodq4all
python3 scripts/install_pipeline_wsl.py
```

**This will:**
- ✅ Create WSL2 Python venv at `~/goodq_audio/venv`
- ✅ Install Whisper large-v3, Pyannote 3.1, Wav2Vec2
- ✅ Configure CUDA for WSL2 (shared GPU with Windows)
- ✅ Set up audio service as systemd daemon
- ✅ Test HuggingFace authentication

### 4. Configure Settings

Edit `L:\goodq4all\configs\config.yaml`:

```yaml
# Project paths (default verified locations)
paths:
  base_data_dir: "L:/_DATA/GoodQ_Data"
  import_inbox: "L:/_DATA/GoodQ_Data/import_inbox"
  memory_db: "L:/_DATA/GoodQ_Data/memory.db"
  knowledge_graph_db: "L:/_DATA/GoodQ_Data/knowledge_graph.db"

# GPU Configuration
gpu:
  device: "cuda:0"
  memory_fraction: 0.85  # 85% utilization verified stable

# Qdrant Configuration
qdrant:
  url: "http://localhost:36335"
  collections:
    - goodq_text
    - goodq_image
    - goodq_audio
```

### 5. Launch System

```batch
# Double-click or run from PowerShell
LAUNCH_GOODQ.bat

# Select: 1 (Launch Complete System)
```

### 6. Verify Installation

```powershell
# Check GPU detection
nvidia-smi

# Expected: Python processes using 12-14GB VRAM
# GPU-Util: 85% during processing

# Check WSL2 audio service
wsl ps aux | grep audio_service

# Expected: PID (e.g., 177) running audio_service.py

# Run system validation
python -m cli.run_ingestion --help
```

---

## 🛠️ Manual Installation (Advanced)


### Step 1: Create Unified Environment

The project uses a **unified `goodq_core` environment** (consolidated from 6 previous environments in Dec 2025):

```powershell
# Activate base conda
conda activate base

# The goodq_core environment should already exist from automated install
# If not, it will be created on first launch by LAUNCH_GOODQ.bat

# Verify environment exists
conda env list | findstr goodq_core
```

**What's in `goodq_core`:**
- All vision models (CLIP, DINO, YOLO, BLIP)
- All text models (sentiment, entity extraction)
- Face recognition (InsightFace)
- OCR (Tesseract)
- Qdrant client
- Scene detection
- Knowledge graph tools

**Disk Savings:** 30GB reduction from previous multi-environment setup  
**Startup:** Instant (no environment switching)

### Step 2: Create WSL2 Audio Environment

```bash
# In WSL2 terminal
cd ~
mkdir -p goodq_audio
cd goodq_audio

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install audio processing stack
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install openai-whisper
pip install pyannote.audio
pip install transformers
pip install librosa soundfile
pip install pydub
```

### Step 3: Install System Dependencies

**Windows Side:**
```powershell
# Qdrant vector database (Windows service mode)
# Download from: https://qdrant.tech/
# Extract to: L:\goodq4all\vendor\qdrant\
# Start service: vendor\qdrant\qdrant.exe --config-path configs\qdrant_config.yaml

# Tesseract OCR (if not installed)
choco install tesseract
```

**WSL2 Side:**
```bash
# FFmpeg for audio processing
sudo apt update
sudo apt install ffmpeg

# Audio codec support
sudo apt install libsndfile1

# System monitoring tools
sudo apt install htop nvtop
```

### Step 4: Configure HuggingFace Authentication

Pyannote 3.1 requires HuggingFace authentication for gated model access:

```bash
# In WSL2
pip install huggingface_hub
huggingface-cli login

# Enter your HF token when prompted
# Get token from: https://huggingface.co/settings/tokens
```

⚠️ **Security Note:** Token is stored in plaintext in `~/.cache/huggingface/token`. For production, use environment variables.

### Step 5: Validate Installation

```powershell
# Windows validation
conda activate goodq_core
python -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}')"
python -c "import qdrant_client; print('Qdrant client OK')"

# Expected output:
# CUDA Available: True
# Qdrant client OK
```

```bash
# WSL2 validation
source ~/goodq_audio/venv/bin/activate
python -c "import whisper; print('Whisper OK')"
python -c "from pyannote.audio import Pipeline; print('Pyannote OK')"
python -c "import torch; print(f'CUDA in WSL2: {torch.cuda.is_available()}')"

# Expected output:
# Whisper OK
# Pyannote OK
# CUDA in WSL2: True
```

---

## 📁 Project Structure (Current)


```
goodq4all/
├── LAUNCH_GOODQ.bat         # 🚀 Main system launcher
├── config.yaml              # ⚙️ Legacy config (use configs/config.yaml)
├── configs/
│   └── config.yaml          # ✅ Active configuration file
│
├── cli/                     # Command-line interfaces
│   ├── run_ingestion.py     # Main ingestion pipeline (1541 lines)
│   └── watchdog.py          # Auto-ingest daemon
│
├── steps/                   # Processing modules
│   ├── audio/               # Audio processing bridges
│   ├── video/               # Vision + entity extraction
│   └── common/              # Shared utilities
│
├── lib/                     # Core libraries
│   ├── kg_realtime_integration.py  # Knowledge graph engine
│   ├── qdrant_client.py     # Vector database client
│   └── entity_extractor.py  # Legacy (superseded by steps/video/)
│
├── envs/                    # 🎯 Unified goodq_core environments
│   ├── image_caption/       # BLIP captioning
│   ├── object_detect/       # YOLOv8 detection
│   ├── face_embed/          # Face recognition
│   ├── ocr/                 # Tesseract OCR
│   ├── video_scene_detect/  # Scene detection
│   └── [18 more micro-environments]
│
├── wsl2_audio/              # 🎙️ WSL2 audio stack (reference copies)
│   ├── audio_service.py     # Long-running queue-based service
│   ├── process_audio.py     # Direct invocation processor
│   └── queue_in/            # Input queue for service mode
│
├── vllm_wsl/                # 🤖 vLLM systemd service (reference)
│
├── docs/                    # 📚 Documentation
│   ├── guides/              # Setup and usage guides
│   ├── architecture/        # System design docs
│   ├── components/          # Component specifications
│   └── fix-reports/         # Historical bug fixes
│
├── logs/
│   └── scene_ingest/        # ✅ Active artifact location
│       └── <video>/
│           ├── audio/       # scene_XXXX.wav chunks
│           └── video/       # scene_XXXX.jpg keyframes
│
└── L:\_DATA\GoodQ_Data/     # 💾 Primary data storage
    ├── import_inbox/        # Drop videos here
    ├── memory.db            # Scene bundles & metadata
    ├── knowledge_graph.db   # Entity relationships
    └── qdrant/              # Vector embeddings (if file-based)
```

**Key Changes from Legacy:**
- ❌ **Removed:** `pipelines/` - ZenML integration not active
- ❌ **Removed:** `agents/` - Microsoft Agents framework artifact (archived)
- ✅ **Active:** `cli/run_ingestion.py` - Main pipeline orchestrator
- ✅ **Active:** `envs/` - Unified goodq_core micro-environments
- ✅ **Active:** `configs/config.yaml` - Current configuration (not root config.yaml)

---

## 🔧 Troubleshooting



### ❌ Python Not Found

If you see "Python was not found", disable the Microsoft Store Python alias:

```powershell
# Run as Administrator
powershell -ExecutionPolicy Bypass -File scripts\setup\FIX_PYTHON_ALIAS.ps1
```

Or manually:
```
Settings → Apps → Apps & features → App execution aliases → Disable "python.exe"
```

### ❌ CUDA/GPU Issues

**Check GPU Availability:**
```powershell
# Windows
conda activate goodq_core
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}')"

# Expected output:
# CUDA: True, Device: NVIDIA GeForce RTX 4070 Ti SUPER
```

**Check WSL2 GPU:**
```bash
# WSL2
source ~/goodq_audio/venv/bin/activate
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
nvidia-smi

# Expected: Same GPU visible from both Windows and WSL2
```

**Common Fix:**
```powershell
# Reinstall PyTorch with correct CUDA version
conda activate goodq_core
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --force-reinstall
```

### ❌ WSL2 Audio Service Not Running

```bash
# Check if service is running
ps aux | grep audio_service

# If not running, start manually
cd ~/goodq_audio
source venv/bin/activate
python audio_service.py &

# Or set up as systemd service (recommended)
# See: docs/guides/wsl2/START_HERE_WSL2.md
```

### ❌ Qdrant Connection Failed

```powershell
# Check if Qdrant is running
Get-Process | Where-Object {$_.ProcessName -like "*qdrant*"}

# Start Qdrant manually
cd L:\goodq4all\vendor\qdrant
.\qdrant.exe --config-path ..\..\configs\qdrant_config.yaml

# Verify connection
curl http://localhost:36335/collections
```

### ❌ HuggingFace Authentication Failed

```bash
# Re-authenticate
huggingface-cli login

# Or set token as environment variable (WSL2)
export HF_TOKEN="your_token_here"

# Verify access to gated models
python -c "from pyannote.audio import Pipeline; Pipeline.from_pretrained('pyannote/speaker-diarization-3.1')"
```

### ❌ Import Inbox Not Monitored

**Check Watchdog:**
```powershell
# Verify watchdog is running
Get-Process python | Where-Object {$_.CommandLine -like "*watchdog*"}

# Check logs
type logs\watchdog.log

# Restart watchdog
python -m cli.watchdog --input-dir "L:\_DATA\GoodQ_Data\import_inbox"
```

### ❌ Scene Detection Stuck

**Check Scene Detection Output:**
```powershell
# Monitor live processing
type logs\scene_ingest\<video_name>\processing.log

# Check for partial output
dir logs\scene_ingest\<video_name>\video\

# Expected: scene_0000.jpg, scene_0001.jpg, etc.
```

**Force Cleanup:**
```powershell
# Stop all Python processes
Stop-Process -Name python -Force

# Clear processing locks
Remove-Item logs\scene_ingest\<video_name>\*.lock

# Restart pipeline
python -m cli.run_ingestion --input-dir "L:\_DATA\GoodQ_Data\import_inbox"
```

---

## 📊 Post-Installation Verification

### Full System Test

```powershell
# 1. Launch system
LAUNCH_GOODQ.bat

# 2. Drop test video
copy test_input\sample.mp4 L:\_DATA\GoodQ_Data\import_inbox\

# 3. Monitor processing (expect 30 scenes for 1hr video)
# Check command window for:
# - Scene detection progress
# - Audio transcription (WSL2)
# - Entity extraction
# - Knowledge graph updates

# 4. Verify outputs after completion
```

**Expected Results:**
```
✅ Scene audio chunks: logs\scene_ingest\sample\audio\scene_0000.wav to scene_0029.wav
✅ Scene keyframes: logs\scene_ingest\sample\video\scene_0000.jpg to scene_0029.jpg
✅ Memory DB updated: L:\_DATA\GoodQ_Data\memory.db (30 scenes registered)
✅ Knowledge graph populated: L:\_DATA\GoodQ_Data\knowledge_graph.db (entities + relationships)
✅ Qdrant collections populated: http://localhost:36335/collections
✅ WSL2 transcription: \\wsl.localhost\Ubuntu\home\<user>\goodq_audio\output\result.json
```

### Performance Benchmarks (RTX 4070 Ti SUPER, 16GB)

| Task | Time (1hr video) | GPU Util | Notes |
|------|------------------|----------|-------|
| Scene Detection | 2-20 min | Low | CPU-bound |
| Vision Processing | 20-40 min | High (85%) | Per-scene parallel |
| Audio Transcription | 15-30 min | High (WSL2) | Whisper large-v3 |
| Entity Extraction | 5-10 min | Moderate | Cross-modal resolution |
| Knowledge Graph | 2-5 min | Low | Database operations |
| **Total Pipeline** | **1-2 hours** | **85% avg** | Concurrent Windows + WSL2 |

---

## 🎓 Next Steps

✅ **Installation Complete!** Now see:

1. **[Quick Start Guide](QUICK_START_CLEAN.md)** - Launch and process your first video
2. **[CLI Reference](../../CLI-REFERENCE.md)** - All command-line options
3. **[Watchdog Guide](../../guides/watchdog/WATCHDOG_QUICKSTART.txt)** - Auto-ingestion setup
4. **[Troubleshooting](../../TROUBLESHOOTING.md)** - Common issues and fixes

---

**Last Updated:** December 15, 2025  
**Verified Configuration:** RTX 4070 Ti SUPER, 16GB VRAM, CUDA 12.8  
**Status:** ✅ PRODUCTION READY

If port 30000 is in use, edit `config.yaml`:

```yaml
api:
  host: "0.0.0.0"
  port: 30000  # Change to another port
```

### Database Issues

```bash
# Check database status
python scripts/diagnostics/check_db_status.py

# Reset database (WARNING: deletes all data)
python scripts/utilities/reset_database.py
```

## Post-Installation

### 1. Test the System

```bash
# Run smoke test
python tests/test_sample.py

# Full system test
.\FULL_SYSTEM_TEST.bat
```

### 2. Import Your First Video

1. Place a video file in `import_inbox/`
2. The watchdog will automatically detect and process it
3. Monitor progress at http://localhost:30000

### 3. Explore the Interface

- **Chat**: Interact with your memories
- **Scenes**: Browse extracted scenes
- **Knowledge Graph**: Explore relationships
- **Analytics**: View processing statistics
- **Command Center**: Monitor system logs

## Advanced Configuration

### GPU Optimization

See `docs/GPU_QUICK_START.md` for detailed GPU configuration.

### Custom Agents

Edit agent configurations in `agents/` directory.

### Pipeline Customization

Modify pipeline steps in `steps/` and register in `pipelines/`.

## Getting Help

- 📖 **Documentation**: Check the `docs/` folder
- 🐛 **Issues**: Report on GitHub
- 💬 **Discussions**: Use GitHub Discussions

## Next Steps

- Read `QUICK_START_GUIDE.md` for usage instructions
- See `docs/ARCHITECTURE.md` for system architecture
- Check `docs/DEVELOPMENT.md` for development guidelines
