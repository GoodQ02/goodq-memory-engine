# GoodQ Quick Start Guide
## Updated: 2025-10-07 20:07:18

## 🚀 One-Click Launch
```batch
L:\zenml_project\LAUNCH_GOODQ.bat
```
This opens:
- Command Center Dashboard (PowerShell)
- FastAPI server (http://localhost:8000)
- API Documentation (http://localhost:8000/docs)

## �� Where Everything Lives

| What you need | Where it is |
|--------------|-------------|
| **Main code** | L:\zenml_project\ |
| **Database & outputs** | L:\GoodQ_Data\ (→ _DATA\GoodQ_Data\) |
| **AI models** | L:\models\ (→ _DATA\models\) |
| **Documentation** | L:\zenml_project\docs\ |
| **Scripts** | L:\zenml_project\scripts\ |
| **Environment configs** | L:\zenml_project\envs\ |
| **Old backups** | L:\_ARCHIVE\ |

## 🔧 Common Tasks

### Run a pipeline
```bash
cd L:\zenml_project
conda activate goodq_zenml
python cli/run_ingestion.py --video "path/to/video.mp4"
```

### Check system status
```bash
.\scripts\command_center.ps1
```

### Verify environments
```bash
.\scripts\verify_project_readiness.ps1
```

### Test smart memory
```bash
python .\scripts\test_smart_memory.py
```

## 🌐 API Endpoints

- Health: http://localhost:8000/health
- Retrieve: POST http://localhost:8000/retrieve
- Docs: http://localhost:8000/docs

## 📊 Project Organization Benefits

1. **Backward Compatible**: All scripts work unchanged (via symlinks)
2. **Easy to Navigate**: Clear separation of code, data, tools, archives
3. **Ready for Git**: Only zenml_project/ needs version control
4. **Clean Workspace**: Archives and caches organized separately

## 🔄 Environment Isolation

Each environment is strictly isolated:
- No shared user packages
- No cache sharing
- Vendored dependencies in endor/
- Explicit pip flags prevent cross-contamination

Active environments:
- goodq_zenml - Main pipeline environment
- goodq_image - Image processing
- goodq_text - NLP tasks
- goodq_audio - Audio processing
- Many more in nvs/ folder (44 total)

## 📖 Full Documentation

See L:\zenml_project\docs\ for:
- AGENTS.md - AI agent instructions
- TROUBLESHOOTING.md - Common issues & fixes
- GITHUB_SETUP_GUIDE.md - Git repository setup
- PROJECT_STATUS.md - Current project state
- System-Blueprint.txt - Comprehensive system design

## 🎯 Next Steps

1. Review L:\PROJECT_STRUCTURE.md for complete directory map
2. Check L:\zenml_project\docs\PROJECT_STATUS.md for current progress
3. Run verification: .\scripts\verify_project_readiness.ps1

---
*For more details, see PROJECT_STRUCTURE.md*
