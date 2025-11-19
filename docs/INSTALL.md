# GoodQ4All Installation Guide

## Prerequisites

- **Windows 10/11** with WSL2 (optional but recommended for performance)
- **Miniconda or Anaconda** installed
- **NVIDIA GPU** with CUDA support (recommended)
- **LM Studio** installed and running (for local LLM)
- **Git** for cloning the repository

## Quick Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/goodq4all.git
cd goodq4all
```

### 2. Run Automated Setup

```bash
# Windows (PowerShell as Administrator)
.\INSTALL.bat

# Or manually with Python
python scripts\setup\install_goodq.py
```

### 3. Configure Environment

Edit `.env.local` with your settings:

```ini
# LM Studio Configuration
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=qwen/qwen3-vl-4b

# Project Paths
BASE_DIR=L:\goodq4all
IMPORT_INBOX=L:\goodq4all\import_inbox
OUTPUT_DIR=L:\goodq4all\output

# GPU Configuration
CUDA_VISIBLE_DEVICES=0
GPU_MEMORY_FRACTION=0.8
```

### 4. Launch GoodQ

```bash
# Use the launcher
.\LAUNCH_GOODQ.bat

# The launcher will:
# - Activate the conda environment
# - Start the API server
# - Start the watchdog
# - Open the web interface
```

## Manual Installation

### Step 1: Create Conda Environment

```bash
conda env create -f envs/goodq_zenml.yaml
conda activate goodq_zenml
```

### Step 2: Install Dependencies

```bash
# Core dependencies
pip install -r requirements.txt

# ZenML integration
pip install zenml[server]

# Optional: GPU optimizations
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Step 3: Configure Paths

```bash
python scripts/setup/configure_envs_pythonpath.py
```

### Step 4: Verify Installation

```bash
python scripts/diagnostics/verify_installation.py
```

## Project Structure

```
goodq4all/
├── INSTALL.bat              # Automated installer
├── LAUNCH_GOODQ.bat         # Main launcher
├── config.yaml              # Main configuration
├── api_server.py            # FastAPI backend
├── index.html               # Web UI
├── analytics_dashboard.py   # Analytics engine
│
├── agents/                  # AI agent definitions
├── config/                  # Configuration files
├── data/                    # Data storage
│   ├── processing/          # Temporary processing
│   └── videos.db            # Main database
├── docs/                    # Documentation
├── envs/                    # Conda environment specs
├── import_inbox/            # Drop videos here
├── logs/                    # Application logs
├── output/                  # Processed outputs
├── pipelines/               # ZenML pipelines
├── scripts/                 # Utility scripts
│   ├── backup/              # Backup files
│   ├── diagnostics/         # Diagnostic tools
│   ├── setup/               # Setup scripts
│   └── utilities/           # Utility functions
├── steps/                   # ZenML pipeline steps
├── tests/                   # Test files
└── web/                     # Web interface components
```

## Troubleshooting

### Python Not Found

If you see "Python was not found", disable the Microsoft Store Python alias:

```powershell
# Run as Administrator
.\scripts\setup\FIX_PYTHON_ALIAS.ps1
```

### CUDA/GPU Issues

```bash
# Check GPU availability
python -c "import torch; print(torch.cuda.is_available())"

# Verify GPU configuration
python scripts/diagnostics/audit_gpu_steps.py
```

### Port Already in Use

If port 3000 is in use, edit `config.yaml`:

```yaml
api:
  host: "0.0.0.0"
  port: 3000  # Change to another port
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
3. Monitor progress at http://localhost:3000

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
