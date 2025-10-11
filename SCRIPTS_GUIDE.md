# GoodQ4All Scripts Guide

## 🎯 Single Source of Truth

**ALL scripts are in:** `L:\goodq4all\`

- **Batch files (.bat):** In `L:\goodq4all\` root
- **Python scripts (.py):** In `L:\goodq4all\scripts\`
- **PowerShell scripts (.ps1):** In `L:\goodq4all\scripts\`

## 🚀 Quick Start Scripts (Use These!)

### Main Launch Script
```batch
L:\goodq4all\LAUNCH_GOODQ.bat
```
**What it does:**
- Health checks (conda, python, ffmpeg, tesseract, nvidia-smi)
- CUDA verification for all GPU environments
- Dry run ingestion
- Starts command center dashboard
- Opens API documentation

### Simple Launch (No Dashboard)
```batch
L:\goodq4all\LAUNCH_GOODQ_SIMPLE.bat
```
**What it does:**
- Basic health checks
- Runs ingestion without command center

### Start File Watchdog
```batch
L:\goodq4all\START_WATCHDOG.bat
```
**What it does:**
- Monitors `L:\goodq4all\import_inbox` for new files
- Automatically queues files for ingestion
- Renames processed files with `_INGESTED` suffix

### Stop All Services
```batch
L:\goodq4all\STOP_GOODQ.bat
```
**What it does:**
- Stops API server
- Stops watchdog
- Cleans up processes

## 📊 Monitoring & Status Scripts

### Check Watchdog Status
```batch
L:\goodq4all\CHECK_WATCHDOG.bat
```
Shows current watchdog status and queue

### Monitor Watchdog (Live)
```batch
L:\goodq4all\MONITOR_WATCHDOG.bat
```
Live tail of watchdog logs

### Run Health Check
```batch
L:\goodq4all\RUN_HEALTH_CHECK.bat
```
Quick system health verification

## 🔧 Python Utility Scripts

All in `L:\goodq4all\scripts\`:

### Production Status
```batch
conda run -n goodq_zenml python L:\goodq4all\scripts\check_production_status.py
```
Shows ingestion progress, database stats, knowledge graph status

### System Readiness
```batch
conda run -n goodq_zenml python L:\goodq4all\scripts\system_readiness_check.py
```
Comprehensive system validation (models, datasets, environments)

### Check Memory Database
```batch
conda run -n goodq_zenml python L:\goodq4all\scripts\check_memory_db.py
```
Query memory database contents

### Knowledge Graph Test
```batch
conda run -n goodq_zenml python L:\goodq4all\scripts\test_knowledge_graph.py
```
Test and verify knowledge graph functionality

### Clear Databases
```batch
conda run -n goodq_zenml python L:\goodq4all\scripts\clear_databases.py
```
Clean slate for fresh ingestion

## 📁 Project Structure

```
L:\goodq4all\                      # Main project directory
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
   L:\goodq4all\LAUNCH_GOODQ.bat
   ```
   
2. **Start Watchdog (in separate window):**
   ```batch
   L:\goodq4all\START_WATCHDOG.bat
   ```

3. **Drop files into:**
   ```
   L:\goodq4all\import_inbox\
   ```

4. **Monitor progress:**
   - Check command center dashboard
   - Or run: `L:\goodq4all\CHECK_WATCHDOG.bat`
   - Or check: `L:\goodq4all\logs\watchdog\watchdog.log`

5. **Check results:**
   ```batch
   conda run -n goodq_zenml python L:\goodq4all\scripts\check_production_status.py
   ```

## 🛑 Common Issues

### "Port 8000 already in use"
```batch
L:\goodq4all\STOP_GOODQ.bat
```

### "Watchdog not processing files"
Check logs:
```batch
L:\goodq4all\MONITOR_WATCHDOG.bat
```

### "Environment errors"
Run health check:
```batch
L:\goodq4all\RUN_HEALTH_CHECK.bat
```

## 📝 Notes

- **Never run scripts from L:\ root** - they don't exist there anymore
- **All paths reference L:\goodq4all** - this is the single source of truth
- **Logs go to:** `L:\goodq4all\logs\`
- **Data goes to:** `L:\_DATA\` (large files, databases, models)
- **Imports go to:** `L:\goodq4all\import_inbox\`
