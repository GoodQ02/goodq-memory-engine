# GoodQ4All Scripts Guide

## 🎯 Single Source of Truth

**ALL scripts are in:** `<project_root>\`

- **Batch files (.bat):** In `<project_root>\` root
- **Python scripts (.py):** In `<project_root>\scripts\`
- **PowerShell scripts (.ps1):** In `<project_root>\scripts\`

## 🚀 Quick Start Scripts (Use These!)

### Main Launch Script
```batch
<project_root>\LAUNCH_GOODQ.bat
```
**What it does:**
- Health checks (conda, python, ffmpeg, tesseract, nvidia-smi)
- CUDA verification for all GPU environments
- Dry run ingestion
- Starts command center dashboard
- Opens API documentation

### Simple Launch (No Dashboard)
```batch
<project_root>\LAUNCH_GOODQ_SIMPLE.bat
```
**What it does:**
- Basic health checks
- Runs ingestion without command center

### Start File Watchdog
```batch
<project_root>\START_WATCHDOG.bat
```
**What it does:**
- Monitors `<project_root>\import_inbox` for new files
- Automatically queues files for ingestion
- Renames processed files with `_INGESTED` suffix

### Stop All Services
```batch
<project_root>\STOP_GOODQ.bat
```
**What it does:**
- Stops API server
- Stops watchdog
- Cleans up processes

## 📊 Monitoring & Status Scripts

### Check Watchdog Status
```batch
<project_root>\CHECK_WATCHDOG.bat
```
Shows current watchdog status and queue

### Monitor Watchdog (Live)
```batch
<project_root>\MONITOR_WATCHDOG.bat
```
Live tail of watchdog logs

### Run Health Check
```batch
<project_root>\RUN_HEALTH_CHECK.bat
```
Quick system health verification

## 🔧 Python Utility Scripts

All in `<project_root>\scripts\`:

### Production Status
```batch
conda run -n goodq_zenml python <project_root>\scripts\check_production_status.py
```
Shows ingestion progress, database stats, knowledge graph status

### System Readiness
```batch
conda run -n goodq_zenml python <project_root>\scripts\system_readiness_check.py
```
Comprehensive system validation (models, datasets, environments)

### Check Memory Database
```batch
conda run -n goodq_zenml python <project_root>\scripts\check_memory_db.py
```
Query memory database contents

### Knowledge Graph Test
```batch
conda run -n goodq_zenml python <project_root>\scripts\test_knowledge_graph.py
```
Test and verify knowledge graph functionality

### Clear Databases
```batch
conda run -n goodq_zenml python <project_root>\scripts\clear_databases.py
```
Clean slate for fresh ingestion

## 📁 Project Structure

```
<project_root>\                      # Main project directory
├── *.bat                          # All batch launcher scripts (USE THESE!)
├── scripts\                       # All Python and PowerShell scripts
│   ├── *.py                      # Python utilities
│   └── *.ps1                     # PowerShell utilities
├── import_inbox\                  # Drop files here for ingestion
├── logs\                          # All log outputs
│   └── ingest_full\              # Current ingestion workspace
├── api\                           # FastAPI server
├── configs\                       # Configuration files
├── envs\                          # Environment definitions
├── pipelines\                     # ZenML pipeline definitions
└── steps\                         # ZenML step implementations
```

## 🎬 Typical Workflow

1. **First Time Setup:**
   ```batch
   <project_root>\LAUNCH_GOODQ.bat
   ```
   
2. **Start Watchdog (in separate window):**
   ```batch
   <project_root>\START_WATCHDOG.bat
   ```

3. **Drop files into:**
   ```
   <project_root>\import_inbox\
   ```

4. **Monitor progress:**
   - Check command center dashboard
   - Or run: `<project_root>\CHECK_WATCHDOG.bat`
   - Or check: `<project_root>\logs\watchdog\watchdog.log`

5. **Check results:**
   ```batch
   conda run -n goodq_zenml python <project_root>\scripts\check_production_status.py
   ```

## 🛑 Common Issues

### "Port 8000 already in use"
```batch
<project_root>\STOP_GOODQ.bat
```

### "Watchdog not processing files"
Check logs:
```batch
<project_root>\MONITOR_WATCHDOG.bat
```

### "Environment errors"
Run health check:
```batch
<project_root>\RUN_HEALTH_CHECK.bat
```

## 📝 Notes

- **Never run scripts from <project_root> root** - they don't exist there anymore
- **All paths reference <project_root>** - this is the single source of truth
- **Logs go to:** `<project_root>\logs\`
- **Data goes to:** `<GOODQ_DATA_ROOT>\` (large files, databases, models)
- **Imports go to:** `<project_root>\import_inbox\`
