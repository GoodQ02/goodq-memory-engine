<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

> [!WARNING]
> ARCHIVE / NON-CANONICAL / DO NOT COPY PATHS
> This document is preserved as historical evidence and may contain obsolete fixed-drive paths, host-specific assumptions, stale commands, or superseded runtime guidance.
> Do not use it for current runtime, setup, migration, or copy-paste path decisions.
> Use active documentation, `config_loader`, and canonical path abstractions such as `<project_root>`, `<GOODQ_DATA_ROOT>`, and `<GOODQ_WSL_WORKSPACE>` instead.

# GoodQ4All Launch System - Quick Reference

## Single Source of Truth

All system launches now go through **ONE** master launcher:

```
L:\goodq4all\LAUNCH_GOODQ.bat
```

## What It Does

### ✅ Process Conflict Detection
- Checks if GoodQ is already running
- Prevents duplicate watchdog instances
- Warns before creating conflicts

### ✅ Menu-Driven Interface
1. **Launch Complete System** - Starts everything (API + Watchdog + UI)
2. **Launch API Server Only** - For manual testing
3. **Launch Watchdog Only** - Auto-ingestion only
4. **View System Status** - Check what's running
5. **Stop All Services** - Clean shutdown
6. **Exit**

### ✅ Proper Process Isolation
- Each service in its own window with clear title
- "GoodQ API Server" - Port 30000
- "GoodQ Watchdog" - Auto-ingestion monitor

## Quick Start

### First Time Setup
1. Run `FULL_SYSTEM_TEST.bat` to validate everything
2. Copy videos to `L:\_DATA\FAMILY_FEAST`
3. Run `LAUNCH_GOODQ.bat` and select option 1

### Normal Operation
1. Run `LAUNCH_GOODQ.bat`
2. Select option 1 (Complete System)
3. Drop videos in `L:\goodq4all\import_inbox`
4. Monitor at http://localhost:30000

### Stopping
- Option A: Run `LAUNCH_GOODQ.bat` → Option 5 (Stop All)
- Option B: Close the "GoodQ API Server" and "GoodQ Watchdog" windows
- Option C: Press Ctrl+C in each window

## Files Archived

The following old launchers have been archived to prevent confusion:
- ~~LAUNCH_GOODQ_PRODUCTION.bat~~ → Replaced
- ~~LAUNCH_GOODQ_SYSTEM.bat~~ → Replaced
- ~~ANALYTICS_LAUNCHER.bat~~ → Integrated
- ~~TEST_PROGRESS_TRACKING.bat~~ → Superseded

Archived to: `L:\_ARCHIVE\old_launchers_[timestamp]`

## Troubleshooting

### "Watchdog already running" Error
**Cause:** Multiple instances tried to start
**Fix:** Run `LAUNCH_GOODQ.bat` → Option 5 to stop all, then restart

### "Process cannot access file" Error
**Cause:** Two watchdogs tried to process same file
**Fix:** This is now prevented by the new launcher

### API Not Responding
**Check:** 
```
curl http://localhost:30000/api/status
```
**Fix:** Make sure API Server window is still open

### Videos Not Processing
**Check:** import_inbox for files
**Check:** Watchdog window for errors
**Fix:** Look at `L:\goodq4all\logs\watchdog.log`

## System Architecture

```
LAUNCH_GOODQ.bat (Master Control)
    │
    ├─► GoodQ API Server (api_server.py)
    │   └─► Port 30000
    │   └─► Serves UI + REST API
    │
    ├─► GoodQ Watchdog (scripts/watchdog_ingest.py)
    │   └─► Monitors import_inbox
    │   └─► Triggers pipeline on new files
    │   └─► Uses lock file to prevent duplicates
    │
    └─► Web Browser
        └─► http://localhost:30000
        └─► Real-time UI updates
```

## Ingestion Flow

1. **Drop video** → `import_inbox/`
2. **Watchdog detects** → Waits for file stability (3 sec)
3. **Starts ingestion** → Copies to processing area
4. **Pipeline runs** → Scene detection → Embeddings → Analysis
5. **Results stored** → SQLite + FAISS + Knowledge Graph
6. **UI updates** → Real-time progress via WebSocket
7. **File moved** → Cleanup from import_inbox

## Status Monitoring

### Via UI
- Open http://localhost:30000
- Check "Command Center" for live logs
- Check "Scenes" for processed content
- Check "Analytics" for statistics

### Via API
```bash
# System status
curl http://localhost:30000/api/status

# Progress
curl http://localhost:30000/api/progress

# Database stats
curl http://localhost:30000/api/analytics/database
```

### Via Log Files
```
L:\goodq4all\logs\watchdog.log          - Ingestion activity
L:\goodq4all\logs\command_center.log    - Pipeline output
L:\goodq4all\logs\progress.json         - Current progress
```

## Best Practices

### ✅ DO
- Use `LAUNCH_GOODQ.bat` for everything
- Check status before starting
- Monitor logs during processing
- Stop cleanly using option 5

### ❌ DON'T
- Don't run multiple launchers simultaneously
- Don't manually start api_server.py or watchdog_ingest.py
- Don't delete files from processing/ while running
- Don't edit videos in import_inbox while watchdog is running

## File Organization

```
L:\goodq4all\
├── LAUNCH_GOODQ.bat          ← MAIN LAUNCHER (use this!)
├── FULL_SYSTEM_TEST.bat      ← System validation
├── VALIDATE_PYTHON_PATHS.bat ← Path checking
├── import_inbox/             ← Drop videos here
├── data/
│   ├── memory.db            ← Scene & entity data
│   ├── knowledge_graph.db   ← Relationships
│   ├── unified_goodq.db     ← Consolidated
│   ├── faiss_indices/       ← Vector embeddings
│   └── processing/          ← Temp processing area
├── logs/
│   ├── watchdog.log         ← Ingestion logs
│   ├── command_center.log   ← Pipeline logs
│   └── progress.json        ← Current progress
└── output/                   ← Analysis results
```

## Emergency Recovery

### If System is Stuck
1. Stop all services: `LAUNCH_GOODQ.bat` → Option 5
2. Check for stale locks: Delete `data/.watchdog.lock` if exists
3. Check processing folder: `data/processing/` should be empty
4. Check logs: `logs/watchdog.log` for errors
5. Restart: `LAUNCH_GOODQ.bat` → Option 1

### If Database is Corrupted
1. Backup: Copy `data/*.db` to `L:\_ARCHIVE`
2. Clear: Delete `data/*.db`
3. Reprocess: Drop videos back in import_inbox
4. The pipeline will rebuild everything

## Version History

### v2.0 (Current) - November 2025
- Single master launcher
- Process conflict detection
- Eliminated duplicate batch files
- Integrated all functionality
- Added comprehensive testing

### v1.x (Archived)
- Multiple batch files
- No conflict detection
- Manual coordination needed
