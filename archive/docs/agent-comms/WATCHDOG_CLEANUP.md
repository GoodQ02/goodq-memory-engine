<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_CANONICAL_POINTER: docs/systems/WATCHDOG_SYSTEM.md -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

> [!WARNING]
> ARCHIVE / NON-CANONICAL / DO NOT COPY PATHS
> This document is preserved as historical evidence and may contain obsolete fixed-drive paths, host-specific assumptions, stale commands, or superseded runtime guidance.
> Do not use it for current runtime, setup, migration, or copy-paste path decisions.
> Use active documentation, `config_loader`, and canonical path abstractions such as `<project_root>`, `<GOODQ_DATA_ROOT>`, and `<GOODQ_WSL_WORKSPACE>` instead.

# Watchdog Scripts Cleanup - 2025-10-11

## Summary
Consolidated watchdog scripts to eliminate confusion and duplication.

## Changes Made

### Archived (Moved to _archive)
- **file_watchdog.py** - Older 246-line implementation, replaced by watchdog_ingest.py
- **watchdog_status.ps1** - PowerShell status script, replaced by check_watchdog_status.py

### Removed
- **CHECK_WATCHDOG.bat** - Duplicate of CHECK_WATCHDOG_STATUS.bat

### Active Watchdog Files

#### Scripts (Python)
1. **watchdog_ingest.py** - Main production watchdog (487 lines)
   - Monitors import_inbox folder
   - Queues and processes files
   - Handles video, image, audio, document ingestion
   - Location: `L:\goodq4all\scripts\watchdog_ingest.py`

2. **check_watchdog_status.py** - Status reporting (Python)
   - Shows file counts, processing state
   - Displays recent activity
   - Location: `L:\goodq4all\scripts\check_watchdog_status.py`

3. **test_watchdog.py** - Test suite (130 lines)
   - Tests file classification
   - Tests queue operations
   - Location: `L:\goodq4all\scripts\test_watchdog.py`

#### BAT Files (Launchers)
1. **START_WATCHDOG.bat** - Starts the watchdog service
   - Location: `L:\goodq4all\START_WATCHDOG.bat`
   - Command: Launches watchdog_ingest.py in goodq_zenml env

2. **CHECK_WATCHDOG_STATUS.bat** - One-time status check
   - Location: `L:\goodq4all\CHECK_WATCHDOG_STATUS.bat`
   - Command: Runs check_watchdog_status.py once and pauses

3. **MONITOR_WATCHDOG.bat** - Live monitoring dashboard
   - Location: `L:\goodq4all\MONITOR_WATCHDOG.bat`
   - Command: Continuously runs check_watchdog_status.py in loop (5s refresh)

#### Documentation
- `docs/WATCHDOG_GUIDE.md` - Comprehensive guide
- `docs/WATCHDOG_QUICKREF.md` - Quick reference
- `docs/WATCHDOG_SUMMARY.md` - Feature summary
- `docs/WATCHDOG_CHANGELOG.md` - Version history
- `docs/diagrams/watchdog_flow.md` - Architecture diagram

## Current Watchdog Architecture

```
User Actions:
  └─> START_WATCHDOG.bat
      └─> scripts/watchdog_ingest.py (main service)
          ├─> Monitors: import_inbox/
          ├─> Processing: import_inbox/.processing/
          ├─> Processed: import_inbox/.processed/
          └─> Failed: import_inbox/.failed/

Status Monitoring:
  ├─> CHECK_WATCHDOG_STATUS.bat (one-shot)
  └─> MONITOR_WATCHDOG.bat (live loop)
      └─> scripts/check_watchdog_status.py
          └─> Reads: logs/watchdog.log
```

## File Flow

1. User drops file → `import_inbox/`
2. Watchdog detects → waits for stability (3s)
3. File moved → `import_inbox/.processing/filename`
4. Ingestion runs → calls appropriate pipeline
5. Success → `import_inbox/.processed/filename_YYYYMMDD_HHMMSS.ext`
6. Failure → `import_inbox/.failed/filename_YYYYMMDD_HHMMSS.ext`

## Log Files
- Main log: `logs/watchdog.log`
- Run results: `logs/watchdog_YYYYMMDD_HHMMSS_results.json`
- Workspace: `logs/watchdog_YYYYMMDD_HHMMSS/`

## Next Steps
- All watchdog functionality now unified
- Single source of truth: watchdog_ingest.py
- Clear separation of concerns:
  - START = run the service
  - CHECK = view status once
  - MONITOR = live dashboard
